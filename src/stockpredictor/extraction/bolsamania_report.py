"""Informe de cobertura de una instantánea de Bolsamanía y diagnóstico del cociente real/Yahoo.

Cobertura: por empresa, tramo de fechas frente a la ventana de pertenencia (con el suelo de la
fuente), huecos y estado de cada slug. Cuota de miembros con precio por año antes (solo Yahoo) y
después (Yahoo ∪ Bolsamanía). Diagnóstico P2 10a: en las empresas con las dos series, el cociente
``close_raw / adj_close`` es constante a tramos; cada escalón es un evento corporativo candidato
(split, ampliación, dividendo). **Solo diagnóstico**: no se confirma ningún evento ni se ajusta.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from stockpredictor.extraction.bolsamania import SOURCE_FLOOR
from stockpredictor.extraction.bolsamania_tables import PRICES_FILE
from stockpredictor.extraction.manifest import MANIFEST_NAME, read_rows
from stockpredictor.extraction.yahoo_report import GAP_DAYS, member_coverage_by_year
from stockpredictor.extraction.yahoo_tickers import check_identity

SOURCE_START = dt.date(2006, 11, 30)  # primera fecha con datos observada (Santander, Bankinter)
STEP_TOL = 0.005  # |ln(cociente_t / cociente_t-1)| a partir del cual hay un escalón


def coverage(
    bolsa: pl.DataFrame,
    windows: pl.DataFrame,
    manifest_dir: Path,
    jobs: pl.DataFrame,
    *,
    as_of: dt.date,
) -> pl.DataFrame:
    """Una fila por empresa y slug de ``jobs`` (columnas company_id, slug, purpose)."""
    status_by_job: dict[tuple[str, str], list[str]] = {}
    for r in read_rows(manifest_dir / MANIFEST_NAME):
        status_by_job.setdefault((r["company_id"], r["ticker"].split("@", 1)[0]), []).append(
            r["status"]
        )
    st = (
        bolsa.sort(["company_id", "slug", "date"])
        .with_columns(
            (pl.col("date") - pl.col("date").shift(1).over(["company_id", "slug"]))
            .dt.total_days()
            .alias("gap")
        )
        .group_by(["company_id", "slug"])
        .agg(
            pl.len().alias("n_rows"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            (pl.col("gap") > GAP_DAYS).sum().alias("n_gaps"),
            pl.col("gap").max().alias("max_gap_days"),
            (pl.col("date").len() - pl.col("date").n_unique()).alias("n_duplicate_dates"),
            (pl.col("close_raw") <= 0).sum().alias("n_nonpositive_close"),
        )
    )
    win = {r["company_id"]: r for r in windows.iter_rows(named=True)}
    s_by = {(r["company_id"], r["slug"]): r for r in st.iter_rows(named=True)}
    rows: list[dict[str, object]] = []
    for j in jobs.iter_rows(named=True):
        w = win.get(j["company_id"])
        s = s_by.get((j["company_id"], j["slug"]), {})
        statuses = status_by_job.get((j["company_id"], j["slug"]), [])
        w_start = max(w["window_start"], SOURCE_START) if w else None
        w_end = (as_of if w["current_member"] else w["window_end"]) if w else None
        if w_end is not None and w_end < SOURCE_START:
            verdict, detail = "outside_source_range", f"la ventana acaba el {w_end}"
        elif not j["slug"]:
            verdict, detail = "no_slug", "sin slug conocido en la tabla"
        elif not statuses:
            verdict, detail = "not_requested", ""
        elif "slug_not_found" in statuses:
            verdict, detail = "slug_not_found", "la web responde 'Página no encontrada'"
        elif "no_history" in statuses:
            verdict, detail = "no_history", "ficha sin sección de históricos"
        elif not s:
            verdict, detail = "no_data", "slug válido sin filas en la ventana pedida"
        else:
            assert w_start is not None and w_end is not None
            v = check_identity(s["first_date"], s["last_date"], w_start, w_end)
            verdict, detail = v.verdict, v.detail
        rows.append(
            {
                "company_id": j["company_id"],
                "slug": j["slug"],
                "purpose": j["purpose"],
                "window_start": w["window_start"] if w else None,
                "window_end": w_end,
                "first_date": s.get("first_date"),
                "last_date": s.get("last_date"),
                "n_rows": s.get("n_rows"),
                "n_gaps": s.get("n_gaps"),
                "max_gap_days": s.get("max_gap_days"),
                "n_duplicate_dates": s.get("n_duplicate_dates"),
                "n_nonpositive_close": s.get("n_nonpositive_close"),
                "verdict": verdict,
                "detail": detail,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None)


def coverage_by_year_before_after(
    yahoo: pl.DataFrame, bolsa_gap_fill: pl.DataFrame, *, last_year: int
) -> pl.DataFrame:
    """Cuota de miembros con precio a 30 de junio: solo Yahoo (``before``) y con Bolsamanía."""
    before = member_coverage_by_year(yahoo, last_year=last_year)
    union = pl.concat(
        [yahoo.select("company_id", "date"), bolsa_gap_fill.select("company_id", "date")]
    )
    after = member_coverage_by_year(union, last_year=last_year)
    return before.join(
        after.select(
            "year",
            pl.col("n_priced").alias("n_priced_after"),
            pl.col("share_priced").alias("share_after"),
        ),
        on="year",
    ).rename({"n_priced": "n_priced_before", "share_priced": "share_before"})


def ratio_diagnostic(
    bolsa: pl.DataFrame, yahoo: pl.DataFrame, *, tol: float = STEP_TOL
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Cociente ``close_raw / adj_close`` por fecha común y sus escalones, por empresa.

    Devuelve (resumen por empresa, lista de escalones). Un escalón es una fecha donde el log del
    cociente cambia más de ``tol`` respecto de la sesión anterior común.
    """
    y = yahoo.select("company_id", "date", "adj_close", "close_split_adjusted").filter(
        pl.col("adj_close") > 0
    )
    b = bolsa.select("company_id", "slug", "date", "close_raw").filter(pl.col("close_raw") > 0)
    j = (
        b.join(y, on=["company_id", "date"], how="inner")
        .sort(["company_id", "date"])
        .with_columns(
            (pl.col("close_raw") / pl.col("adj_close")).alias("ratio_adj"),
            (pl.col("close_raw") / pl.col("close_split_adjusted")).alias("ratio_close"),
        )
        .with_columns(
            pl.col("ratio_adj").log().diff().over("company_id").alias("log_step_adj"),
            pl.col("ratio_close").log().diff().over("company_id").alias("log_step_close"),
        )
    )
    steps = (
        j.filter(pl.col("log_step_adj").abs() > tol)
        .select(
            "company_id", "date", "close_raw", "adj_close", "close_split_adjusted",
            "ratio_adj", "log_step_adj", "log_step_close",
            pl.col("ratio_adj").shift(1).over("company_id").alias("ratio_adj_prev"),
        )
        .sort(["company_id", "date"])
    )  # fmt: skip
    steps = j.join(
        steps.select("company_id", "date", "ratio_adj_prev"), on=["company_id", "date"], how="inner"
    ).select(
        "company_id", "date", "close_raw", "adj_close", "close_split_adjusted", "ratio_adj",
        "ratio_adj_prev", "log_step_adj", "log_step_close",
    )  # fmt: skip
    summary = (
        j.group_by("company_id")
        .agg(
            pl.len().alias("n_common_dates"),
            pl.col("date").min().alias("first_common"),
            pl.col("date").max().alias("last_common"),
            pl.col("ratio_adj").first().alias("ratio_first"),
            pl.col("ratio_adj").last().alias("ratio_last"),
            (pl.col("log_step_adj").abs() > tol).sum().alias("n_steps"),
            pl.col("log_step_adj").abs().max().alias("max_abs_log_step"),
            (pl.col("log_step_adj").abs() <= tol).mean().alias("share_days_constant"),
        )
        .sort("company_id")
    )
    return summary, steps


def render_markdown(
    snapshot_id: str,
    cov: pl.DataFrame,
    by_year: pl.DataFrame,
    ratio: tuple[pl.DataFrame, pl.DataFrame, str] | None = None,
) -> str:
    gap_fill = cov.filter(pl.col("purpose") == "gap_fill")
    recovered = gap_fill.filter(pl.col("n_rows") > 0)
    no_slug_verdicts = ["slug_not_found", "no_slug", "no_history", "no_data"]
    n_no_slug = gap_fill.filter(pl.col("verdict").is_in(no_slug_verdicts))["company_id"].n_unique()
    n_outside = gap_fill.filter(pl.col("verdict") == "outside_source_range")[
        "company_id"
    ].n_unique()
    lines = [f"# Informe de cobertura: precios de Bolsamanía, instantánea `{snapshot_id}`", ""]
    lines += [
        "Todo resultado con estos datos lleva la etiqueta **con sesgo de supervivencia**. "
        "`price_quality = close_only`: cierre real sin ajustar, sin volumen, sin `adj_close`.",
        "",
        "## Resumen (empresas que Yahoo no tiene)",
        "",
        "| Medida | Valor |",
        "|---|---|",
        f"| empresas en el hueco (404 en Yahoo) | {gap_fill['company_id'].n_unique()} |",
        f"| con precios de Bolsamanía | {recovered['company_id'].n_unique()} |",
        f"| sin slug conocido, página inexistente o sin datos | {n_no_slug} |",
        f"| con ventana anterior al inicio de la fuente ({SOURCE_START}) | {n_outside} |",
        "",
        "## Miembros con precio a 30 de junio: antes (Yahoo) y después (Yahoo + Bolsamanía)",
        "",
        "| Año | Miembros | Antes | Cuota antes | Después | Cuota después |",
        "|---|---|---|---|---|---|",
    ]
    for r in by_year.iter_rows(named=True):
        lines.append(
            f"| {r['year']} | {r['n_members']} | {r['n_priced_before']} | "
            f"{r['share_before']:.0%} | {r['n_priced_after']} | {r['share_after']:.0%} |"
        )
    lines += ["", "## Cobertura por empresa y slug", ""]
    lines += [
        "| Empresa | Slug | Uso | Ventana | Datos | Filas | Huecos | Estado |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in cov.sort(["purpose", "company_id", "slug"]).iter_rows(named=True):
        win = f"{r['window_start']}..{r['window_end']}"
        dat = f"{r['first_date']}..{r['last_date']}" if r["n_rows"] else ""
        lines.append(
            f"| {r['company_id']} | {r['slug']} | {r['purpose']} | {win} | {dat} | "
            f"{r['n_rows'] or ''} | {r['n_gaps'] if r['n_gaps'] is not None else ''} | "
            f"{r['verdict']} {r['detail']} |"
        )
    if ratio:
        summary, steps, yahoo_id = ratio
        lines += [
            "",
            f"## Diagnóstico del cociente `close_raw / adj_close` (Yahoo `{yahoo_id}`)",
            "",
        ]
        lines += [
            f"Escalón = cambio del log del cociente > {STEP_TOL:.1%} entre sesiones comunes. "
            "Solo diagnóstico (P2 10a): cada escalón es un evento candidato (split, ampliación o "
            "dividendo), sin confirmar.",
            "",
            "| Empresa | Fechas comunes | Cociente inicial | Cociente final | Escalones | "
            "Máx. escalón (ln) | % días constantes |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in summary.iter_rows(named=True):
            lines.append(
                f"| {r['company_id']} | {r['n_common_dates']} | {r['ratio_first']:.3f} | "
                f"{r['ratio_last']:.3f} | {r['n_steps']} | {r['max_abs_log_step']:.3f} | "
                f"{r['share_days_constant']:.1%} |"
            )
    return "\n".join(lines) + "\n"


def load_prices(raw_snapshot_dir: Path) -> pl.DataFrame:
    return pl.read_parquet(raw_snapshot_dir / PRICES_FILE)


__all__ = ["SOURCE_FLOOR", "coverage", "coverage_by_year_before_after", "ratio_diagnostic"]
