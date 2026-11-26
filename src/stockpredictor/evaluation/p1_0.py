"""P1-0: potencia del IBEX solo con precios (ADR 0019, 0022, 0026, 0027, 0029).

Mide, sin entrenar ningún modelo, si el IBEX puede detectar un RankIC medio de 0,05: ventanas
fuera de muestra (N_eff), error típico real de tres baselines transversales, MDE y permutación.
Todo resultado lleva la etiqueta "con sesgo de supervivencia (sin deslistadas)".
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import polars as pl
import scipy
import yaml

from stockpredictor.evaluation import panel as pn
from stockpredictor.evaluation import power, windows
from stockpredictor.evaluation.permutation import permutation_test
from stockpredictor.extraction.manifest import sha256_file

LABEL_SURVIVORSHIP = "con sesgo de supervivencia (sin deslistadas)"
LABEL_DETECTABLE = "detectable"
LABEL_INCONCLUSIVE = "no concluyente por diseño"
CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs"


@dataclass(frozen=True)
class Params:
    horizons: tuple[int, ...] = (90, 365)
    descriptive_horizons: tuple[int, ...] = (1500,)
    frequency: dict[int, str] = field(default_factory=lambda: {90: "weekly", 365: "monthly"})
    descriptive_frequency: str = "monthly"
    train_years_grid: tuple[int, ...] = (5, 8, 10)
    primary_train_years: int = 8
    embargo_sessions: int = 5
    final_test_years: int = 3
    min_names: int = 10
    effect: float = 0.05
    alpha: float = 0.05
    power: float = 0.80
    viable_min: int = 10
    exploratory_min: int = 4
    n_perm: int = 1000
    seed: int = 20261126

    @classmethod
    def from_configs(cls, config_dir: Path = CONFIG_DIR, **overrides: object) -> Params:
        pre = yaml.safe_load((config_dir / "preregistered.yaml").read_text(encoding="utf8"))
        hor = yaml.safe_load((config_dir / "horizons.yaml").read_text(encoding="utf8"))
        sampling = {int(k): str(v) for k, v in hor["decision_date_sampling"].items()}
        base = cls(
            horizons=tuple(int(h) for h in hor["horizons_days"]),
            descriptive_horizons=tuple(int(h) for h in hor.get("descriptive_horizons_days", [])),
            frequency=sampling,
            embargo_sessions=int(pre["embargo_sessions"]),
            final_test_years=int(pre["final_test_years"]),
            min_names=int(pre["min_names_per_date_rankic"]),
            effect=float(pre["effect_of_interest_rankic"]),
            viable_min=int(pre["viable_min_windows"]),
            exploratory_min=int(pre["exploratory_min_windows"]),
        )
        return cls(**{**asdict(base), **overrides})  # type: ignore[arg-type]


@dataclass
class Results:
    meta: dict[str, object]
    n_eff: pl.DataFrame
    signals: pl.DataFrame
    permutation: pl.DataFrame
    target_corr: pl.DataFrame
    coverage: pl.DataFrame
    summary: pl.DataFrame


def load_prices_verified(raw_dir: Path, snapshot_id: str) -> tuple[pl.DataFrame, str]:
    """Lee ``prices.parquet`` tras comprobar su sha256 contra ``tables_manifest.json``."""
    sdir = raw_dir / "prices" / "yahoo" / snapshot_id
    manifest = json.loads((sdir / "tables_manifest.json").read_text(encoding="utf8"))
    expected = manifest["prices"]["sha256"]
    actual = sha256_file(sdir / manifest["prices"]["file"])
    if actual != expected:
        raise RuntimeError(f"{sdir}: sha256 de precios distinto del manifiesto")
    return pl.read_parquet(sdir / manifest["prices"]["file"]), expected


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def _decisions(panel: pl.DataFrame) -> pl.DataFrame:
    return (
        panel.group_by("date")
        .agg(
            pl.col("si").first(),
            pl.col("exit_si").first(),
            pl.col("entry_date").first(),
            pl.col("label_end_date").first(),
            n_valid=pl.col("y_cs").is_not_null().sum(),
        )
        .sort("date")
    )


def run(
    prices: pl.DataFrame,
    intervals: pl.DataFrame,
    prices_from: dt.date,
    params: Params,
    meta: dict[str, object] | None = None,
) -> Results:
    clean = pn.clean_prices(prices.filter(pl.col("date") >= prices_from))
    sessions = pn.sessions_table(clean)
    signals = pn.signal_table(clean, sessions)
    data_end = sessions["date"].max()
    n_eff_rows: list[dict[str, object]] = []
    sig_rows: list[dict[str, object]] = []
    perm_rows: list[dict[str, object]] = []
    corr_rows: list[dict[str, object]] = []
    cov_rows: list[pl.DataFrame] = []

    all_h = [(h, params.frequency[h], False) for h in params.horizons] + [
        (h, params.descriptive_frequency, True) for h in params.descriptive_horizons
    ]
    for h, freq, descriptive in all_h:
        panel = pn.build_panel(signals, sessions, intervals, h, freq)
        dec = _decisions(panel)
        elig = dec.filter(pl.col("n_valid") >= params.min_names)
        cov_rows.append(_coverage_by_year(panel).with_columns(pl.lit(h).alias("horizon")))
        for ty in params.train_years_grid:
            for reserved in (True, False):
                b = windows.oos_bounds(
                    sessions, dec, prices_from=prices_from, train_years=ty,
                    embargo_sessions=params.embargo_sessions,
                    final_test_years=params.final_test_years if reserved else None,
                )  # fmt: skip
                sel = windows.in_oos(elig, b)
                row = windows.n_eff(sel, h)
                eff = float(row["n_eff"])  # type: ignore[arg-type]
                n_eff_rows.append(
                    {
                        "horizon": h, "descriptive": descriptive, "train_years": ty,
                        "reserved_block": reserved,
                        "first_oos": sel["date"].min() if sel.height else None,
                        "last_oos_label_end": sel["label_end_date"].max() if sel.height else None,
                        **row,
                        "viability": windows.viability(
                            eff, params.viable_min, params.exploratory_min
                        ),
                    }
                )  # fmt: skip
        if descriptive:
            continue
        for ty in params.train_years_grid:
            b = windows.oos_bounds(
                sessions, dec, prices_from=prices_from, train_years=ty,
                embargo_sessions=params.embargo_sessions,
                final_test_years=params.final_test_years,
            )  # fmt: skip
            oos = windows.in_oos(panel, b)
            for s in pn.SIGNALS:
                ic = power.rankic_by_date(oos, s, params.min_names)
                stats = power.summarize_signal(ic, h, params.effect)
                sig_rows.append({"horizon": h, "train_years": ty, "signal": s, **stats})
                if ty == params.primary_train_years:
                    perm = permutation_test(oos, s, h, params.min_names, params.n_perm, params.seed)
                    n_sub = int(round(float(stats["n_sub"])))  # type: ignore[arg-type]
                    sigma_null = float(perm["null_sd_sub"]) * n_sub**0.5  # type: ignore[arg-type]
                    perm_rows.append(
                        {
                            "horizon": h, "signal": s, **perm,
                            "sigma_null": sigma_null, "sigma_emp": stats["sd_ic"],
                            "mde_null_sigma": power.mde_t(sigma_null, n_sub),
                        }
                    )  # fmt: skip
            if ty == params.primary_train_years:
                for col in ("y", "y_cs"):
                    corr_rows.append(
                        {"horizon": h, "target": col, **power.target_correlation(oos, col, h)}
                    )

    n_eff_df = _frame(n_eff_rows)
    sig_df = _frame(sig_rows)
    summary = _summary(n_eff_df, sig_df, params)
    full_meta: dict[str, object] = {
        "label": LABEL_SURVIVORSHIP,
        "prices_from": prices_from.isoformat(),
        "data_end": str(data_end),
        "params": asdict(params),
        "commit": _git_commit(),
        "versions": {"polars": pl.__version__, "numpy": np.__version__, "scipy": scipy.__version__},
        **(meta or {}),
    }
    return Results(
        meta=full_meta,
        n_eff=n_eff_df,
        signals=sig_df,
        permutation=_frame(perm_rows),
        target_corr=_frame(corr_rows),
        coverage=pl.concat(cov_rows),
        summary=summary,
    )


def _frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


def _coverage_by_year(panel: pl.DataFrame) -> pl.DataFrame:
    return (
        pn.coverage_by_date(panel)
        .with_columns(pl.col("date").dt.year().alias("year"))
        .group_by("year")
        .agg(
            dates=pl.len(),
            mean_members=pl.col("n_members").mean(),
            mean_valid=pl.col("n_valid").mean(),
            share_valid=pl.col("share_valid").mean(),
        )
        .sort("year")
    )


def _summary(n_eff: pl.DataFrame, sig: pl.DataFrame, params: Params) -> pl.DataFrame:
    rows = []
    for h in params.horizons:
        ne = n_eff.filter(
            (pl.col("horizon") == h)
            & (pl.col("train_years") == params.primary_train_years)
            & pl.col("reserved_block")
        ).row(0, named=True)
        s = sig.filter(
            (pl.col("horizon") == h) & (pl.col("train_years") == params.primary_train_years)
        )
        mde = float(s["mde_t"].median())  # type: ignore[arg-type]
        sd = float(s["sd_ic"].median())  # type: ignore[arg-type]
        rows.append(
            {
                "horizon": h,
                "n_eff": ne["n_eff"],
                "viability": ne["viability"],
                "mde_headline": mde,
                "mde_min_signal": float(s["mde_t"].min()),  # type: ignore[arg-type]
                "mde_max_signal": float(s["mde_t"].max()),  # type: ignore[arg-type]
                "effect": params.effect,
                "n_required": power.required_n(sd, params.effect),
                "label": LABEL_DETECTABLE if mde <= params.effect else LABEL_INCONCLUSIVE,
            }
        )
    return pl.DataFrame(rows)


# ---------------------------------------------------------------- salida


def write_outputs(res: Results, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    res.n_eff.write_csv(out_dir / "n_eff.csv")
    res.signals.write_csv(out_dir / "rankic_mde.csv")
    res.permutation.write_csv(out_dir / "permutacion.csv")
    res.target_corr.write_csv(out_dir / "correlacion_targets.csv")
    res.coverage.write_csv(out_dir / "cobertura_por_anio.csv")
    res.summary.write_csv(out_dir / "resumen.csv")
    (out_dir / "run.json").write_text(
        json.dumps(res.meta, indent=2, default=str, ensure_ascii=False), encoding="utf8"
    )
    (out_dir / "informe.md").write_text(render_report(res), encoding="utf8")


def _f(x: object, nd: int = 3) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return "-" if x != x else f"{x:.{nd}f}".replace(".", ",")
    return str(x)


def _num(x: object) -> float:
    return float(x)  # type: ignore[arg-type]


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def render_report(res: Results) -> str:
    p = res.meta["params"]
    assert isinstance(p, dict)
    ty = p["primary_train_years"]
    eff = p["effect"]
    out = [
        "# Informe P1-0: potencia del IBEX solo con precios",
        f"**Resultados {LABEL_SURVIVORSHIP}.** Precios: Yahoo `adj_close`, instantánea "
        f"`{res.meta.get('snapshot_id')}` (sha256 `{str(res.meta.get('prices_sha256'))[:12]}…`). "
        f"Datos desde {res.meta['prices_from']} hasta {res.meta['data_end']}. "
        f"Commit: `{res.meta.get('commit')}`. Generado con `stockpredictor report-p1-0` "
        "(parámetros, versiones y semilla en `run.json`).",
        "",
        "## 1. Resultado por horizonte",
        f"Efecto de interés: RankIC medio de {_f(eff, 2)} (ADR 0019). Train mínimo principal: "
        f"{ty} años. MDE con α = {_f(p['alpha'], 2)} bilateral y potencia {_f(p['power'], 2)}, "
        "t de Student no central; cifra titular = mediana de los tres baselines. "
        'La etiqueta es "detectable" si MDE ≤ efecto y "no concluyente por diseño" si no.',
        "",
    ]
    rows = []
    for r in res.summary.iter_rows(named=True):
        rows.append(
            [
                f"h{r['horizon']}", _f(float(r["n_eff"]), 0), r["viability"],
                _f(r["mde_headline"]), f"{_f(r['mde_min_signal'])} a {_f(r['mde_max_signal'])}",
                _f(r["n_required"], 0), f"**{r['label']}**",
            ]
        )  # fmt: skip
    out.append(
        _table(
            [
                "Horizonte",
                "N_eff",
                "Viabilidad (ADR 0007)",
                "MDE titular",
                "MDE por baseline",
                "N necesarias p/ 0,05",
                "Etiqueta (ADR 0019)",
            ],
            rows,
        )  # fmt: skip
    )
    out += [
        "",
        "N_eff = ventanas disjuntas de etiqueta fuera de muestra (mediana entre desfases), tras el "
        f"train mínimo, la purga, el embargo de {p['embargo_sessions']} sesiones y el bloque "
        f'reservado de {p["final_test_years"]} años (ADR 0008, 0021). "N necesarias" = '
        "observaciones independientes que harían falta para detectar 0,05 con la σ medida "
        "(aproximación normal).",
        "",
        "## 2. N_eff y ventanas evaluables",
        "Sensibilidad al train mínimo. Con bloque reservado = cifra de decisión; sin él = solo "
        "informativa (no se calcula ningún retorno con ese bloque). `Ventanas (tramo/N)` es la "
        "cota ideal sin rejilla de fechas. h1500 es descriptivo (ADR 0030).",
        "",
    ]
    rows = []
    for r in res.n_eff.sort(
        "horizon", "reserved_block", "train_years", descending=[False, True, False]
    ).iter_rows(named=True):
        rows.append(
            [
                f"h{r['horizon']}" + (" (desc.)" if r["descriptive"] else ""),
                str(r["train_years"]), "sí" if r["reserved_block"] else "no",
                str(r["first_oos"]), str(r["last_oos_label_end"]), str(r["n_dates"]),
                f"{_f(float(r['n_eff']), 0)} ({r['n_eff_min']}-{r['n_eff_max']})",
                str(r["windows_span"]), r["viability"],
            ]
        )  # fmt: skip
    out.append(
        _table(
            [
                "Horizonte",
                "Train (años)",
                "Reserva",
                "Primera fecha OOS",
                "Última etiqueta",
                "Fechas",
                "N_eff (mín-máx)",
                "Ventanas (tramo/N)",
                "Viabilidad",
            ],
            rows,
        )  # fmt: skip
    )
    out += [
        "",
        f"## 3. RankIC, error típico y MDE por baseline (train {ty} años)",
        "Spearman por fecha entre la señal y `y_cs`. Error típico = media entre desfases del error "
        "típico de la media en submuestras de etiquetas disjuntas (ADR 0022). σ = desviación "
        "típica del RankIC entre fechas de la submuestra. `t medio` y `% |t|>1,96` son sobre las "
        "submuestras (una por desfase). Señales: momentum 12-1 (ln P[t-21] − ln P[t-252]), baja "
        "volatilidad 60 (−σ de retornos diarios de 60 sesiones, mínimo 48) y reversión a 1 mes "
        "(−ln P[t]/P[t-21]). Son diagnósticos de potencia: no hay ajuste ni se presentan como "
        "evidencia de señal (tres señales y dos horizontes sin corrección por comparaciones "
        "múltiples).",
        "",
    ]
    prim = res.signals.filter(pl.col("train_years") == ty).sort("horizon", "signal")
    rows = []
    for r in prim.iter_rows(named=True):
        rows.append(
            [
                f"h{r['horizon']}", r["signal"], str(r["n_dates"]), _f(r["n_sub"], 0),
                _f(r["mean_ic_all"], 4), _f(r["mean_ic_sub"], 4),
                f"{_f(r['ic_min_offset'], 3)} a {_f(r['ic_max_offset'], 3)}",
                _f(r["sd_ic"]), _f(r["se"], 4), _f(r["t_mean"], 2),
                _f(100 * r["share_abs_t_gt_1_96"], 0), _f(r["mde_t"]), _f(r["mde_normal"]),
            ]
        )  # fmt: skip
    out.append(
        _table(
            [
                "H",
                "Señal",
                "Fechas",
                "n sub.",
                "RankIC medio (todas)",
                "RankIC medio (sub.)",
                "Rango entre desfases",
                "σ",
                "Error típico",
                "t medio",
                "% |t|>1,96",
                "MDE (t)",
                "MDE (normal)",
            ],
            rows,
        )  # fmt: skip
    )
    out += ["", "## 4. Sensibilidad del MDE al train mínimo", ""]
    rows = []
    for h in sorted(res.signals["horizon"].unique().to_list()):
        for y in sorted(res.signals["train_years"].unique().to_list()):
            s = res.signals.filter((pl.col("horizon") == h) & (pl.col("train_years") == y))
            med = {c: _num(s[c].median()) for c in ("n_sub", "sd_ic", "mde_t")}
            rows.append(
                [
                    f"h{h}", str(y), _f(med["n_sub"], 0), _f(med["sd_ic"]), _f(med["mde_t"]),
                    _f(_num(s["mde_t"].min())), _f(_num(s["mde_t"].max())),
                ]
            )  # fmt: skip
    out.append(
        _table(
            [
                "H",
                "Train (años)",
                "n sub. (mediana)",
                "σ (mediana)",
                "MDE titular",
                "MDE mín",
                "MDE máx",
            ],
            rows,
        )  # fmt: skip
    )
    out += [
        "",
        f"## 5. Permutación ({p['n_perm']} repeticiones, semilla {p['seed']}, train {ty} años)",
        "Se baraja `y_cs` entre nombres dentro de cada fecha: contrasta la nula fuerte (ninguna "
        "relación señal-retorno en ninguna fecha). `p (todas)`: media sobre todas las fechas de la "
        "rejilla; barajar por fecha rompe la dependencia entre etiquetas solapadas, así que "
        "subestima la varianza real y su p-valor es liberal. `p (sub., mediana)`: p-valor de la "
        "media de cada submuestra disjunta, mediana entre desfases. Aun así la permutación es "
        "liberal si el RankIC varía en el tiempo con media cero: `σ nula` es la desviación del "
        "RankIC por fecha que daría el azar y `σ empírica` la medida (sección 3). La σ empírica "
        "es mayor porque el RankIC de estas señales cambia de signo con el régimen; el contraste "
        "principal y el MDE titular usan la empírica (ADR 0022). `MDE (σ nula)` es el MDE "
        "optimista que saldría de suponer solo ruido de muestreo; no sirve para etiquetar.",
        "",
    ]
    rows = []
    for r in res.permutation.sort("horizon", "signal").iter_rows(named=True):
        rows.append(
            [
                f"h{r['horizon']}", r["signal"], _f(r["mean_ic_obs"], 4), _f(r["null_sd_all"], 4),
                _f(r["p_all"], 3), _f(r["null_sd_sub"], 4), _f(r["p_sub_median"], 3),
                _f(r["p_sub_min"], 3), _f(r["sigma_null"]), _f(r["sigma_emp"]),
                _f(r["mde_null_sigma"]),
            ]
        )  # fmt: skip
    out.append(
        _table(
            [
                "H",
                "Señal",
                "RankIC obs. (todas)",
                "σ nula (todas)",
                "p (todas)",
                "σ nula media (sub.)",
                "p (sub., mediana)",
                "p (sub., mín)",
                "σ nula",
                "σ empírica",
                "MDE (σ nula)",
            ],
            rows,
        )  # fmt: skip
    )
    out += [
        "",
        f"## 6. Correlación transversal de los targets (train {ty} años)",
        "Correlación media por pares entre nombres sobre fechas no solapadas (≥ 10 fechas en "
        "común), media entre desfases. Con `y_cs` la media está sesgada a −1/(N−1) por "
        "construcción (se resta la mediana), así que solo `y` tiene Deff interpretable: con "
        "ρ ≈ 0,4 el retorno absoluto de ~29 nombres equivale a pocos nombres independientes, "
        "el motivo del target transversal (ADR 0029). `Deff = 1 + (N−1)ρ`; "
        "nombres equivalentes = N/Deff.",
        "",
    ]
    rows = []
    for r in res.target_corr.sort("horizon", "target").iter_rows(named=True):
        deff = r["deff"]
        rows.append(
            [
                f"h{r['horizon']}", r["target"], _f(r["rho_mean"]), _f(r["mean_names"], 1),
                _f(deff, 2),
                _f(r["mean_names"] / deff, 1) if r["target"] == "y" and deff and deff > 0 else "-",
            ]
        )  # fmt: skip
    out.append(
        _table(["H", "Target", "ρ medio", "Nombres por fecha", "Deff", "Nombres equiv."], rows)
    )
    out += ["", "## 7. Cobertura de miembros con target válido (fechas de decisión por año)", ""]
    h0 = p["horizons"][0]
    cov = res.coverage.filter(pl.col("horizon") == h0).sort("year")
    rows = [
        [str(r["year"]), str(r["dates"]), _f(r["mean_members"], 1), _f(r["mean_valid"], 1),
         _f(100 * r["share_valid"], 0)]
        for r in cov.iter_rows(named=True)
    ]  # fmt: skip
    out.append(
        _table(["Año", "Fechas", "Miembros (media)", "Con target válido", "% con target"], rows)
    )
    out += [
        "",
        f"(Cobertura de h{h0}; las demás en `cobertura_por_anio.csv`.) Miembros sin target: sin "
        "ticker en Yahoo (34 de 83 tickers dan 404, en su mayoría empresas ya desaparecidas) o "
        "sin precio en t, entrada o salida.",
        "",
        "## 8. Lectura y limitaciones",
        f"- Todo es {LABEL_SURVIVORSHIP}: las empresas que salieron del IBEX y Yahoo no cotiza "
        "no entran. Eso reduce los nombres por fecha, puede sesgar el nivel del RankIC (más en "
        "momentum y reversión) y no se corrige con este informe; Bolsamanía se integrará después.",
        "- El MDE usa la σ del RankIC medida en las fechas fuera de muestra con estos tres "
        "baselines. Un modelo con otra σ tendría otro MDE; es una cifra de diseño, no una "
        "garantía.",
        "- El bloque final reservado (ADR 0021) no entra en ninguna cifra de retornos.",
        "- `adj_close` de Yahoo incorpora dividendos y splits tal como están hoy; el ruido de "
        "redondeo entre descargas llega a 1,9e-6 (ADR 0033). Sesión faltante global: Yahoo no "
        "trae 2018-09-20 (`docs/limitaciones.md`).",
        "- Calendario de sesiones = unión de fechas con precio de alguna empresa; N en días "
        "naturales, entrada al cierre de t+1, salida en la última sesión ≤ entrada + N (ADR 0005).",
        "- Fechas de decisión: última sesión de cada semana ISO (h90) o mes (h365) (ADR 0026).",
        "- Una persona con experiencia en factores debería revisar el análisis de potencia "
        "(ADR 0019).",
        "",
    ]
    return "\n".join(out)
