"""RankIC por fecha, error típico en submuestras no solapadas y MDE (ADR 0019, 0022)."""

from __future__ import annotations

import math

import numpy as np
import polars as pl
from scipy import optimize, stats

from stockpredictor.evaluation.windows import date_days, subsample_indices


def rankic_by_date(panel: pl.DataFrame, signal: str, min_names: int) -> pl.DataFrame:
    """Spearman entre ``signal`` y ``y_cs`` por fecha, sobre los nombres con ambos datos."""
    df = panel.filter(pl.col("y_cs").is_not_null() & pl.col(signal).is_not_null())
    return (
        df.with_columns(
            rs=pl.col(signal).rank("average").over("date"),
            ry=pl.col("y_cs").rank("average").over("date"),
        )
        .group_by("date")
        .agg(
            pl.col("si").first(),
            pl.col("exit_si").first(),
            pl.col("entry_date").first(),
            pl.col("label_end_date").first(),
            n=pl.len(),
            ic=pl.corr("rs", "ry"),
        )
        .filter((pl.col("n") >= min_names) & pl.col("ic").is_finite())
        .sort("date")
    )


def mde_normal(sigma: float, n: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """Efecto mínimo detectable con aproximación normal, bilateral."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * sigma / math.sqrt(n))


def mde_t(sigma: float, n: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """MDE con t de Student no central (``n - 1`` g.l.), bilateral: potencia exacta del test t."""
    if n < 3 or not sigma > 0:
        return float("nan")
    df = n - 1
    tcrit = stats.t.ppf(1 - alpha / 2, df)

    def gap(ncp: float) -> float:
        p = stats.nct.sf(tcrit, df, ncp) + stats.nct.cdf(-tcrit, df, ncp)
        return float(p - power)

    hi = tcrit + 1.0  # la potencia crece con ncp; se amplía el intervalo hasta cruzar `power`
    while gap(hi) < 0:
        hi *= 1.5
        if hi > 1e3:
            return float("nan")
    ncp = optimize.brentq(gap, 0.0, hi)
    return float(ncp * sigma / math.sqrt(n))


def required_n(sigma: float, effect: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """Observaciones independientes para detectar ``effect`` (aproximación normal)."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float((z * sigma / effect) ** 2)


def subsample_stats(ic: pl.DataFrame, horizon_days: int) -> pl.DataFrame:
    """Media, desviación, error típico y t por submuestra disjunta (todos los desfases)."""
    ic = ic.sort("date")
    values = ic["ic"].to_numpy()
    subs = subsample_indices(
        date_days(ic["entry_date"]), date_days(ic["label_end_date"]), horizon_days
    )
    rows = []
    for k, idx in enumerate(subs):
        x = values[idx]
        n = len(x)
        sd = float(np.std(x, ddof=1)) if n > 1 else float("nan")
        se = sd / math.sqrt(n) if n > 1 else float("nan")
        mean = float(np.mean(x))
        rows.append(
            {
                "offset": k,
                "n": n,
                "mean": mean,
                "sd": sd,
                "se": se,
                "t": mean / se if se and se > 0 else float("nan"),
                "mde_t": mde_t(sd, n) if n > 2 else float("nan"),
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "offset": pl.Int64, "n": pl.Int64, "mean": pl.Float64, "sd": pl.Float64,
            "se": pl.Float64, "t": pl.Float64, "mde_t": pl.Float64,
        },
    )  # fmt: skip


def summarize_signal(ic: pl.DataFrame, horizon_days: int, effect: float) -> dict[str, float | int]:
    """Resumen de un baseline: media de RankIC, error típico y MDE entre desfases."""
    sub = subsample_stats(ic, horizon_days)
    if sub.is_empty():
        return {"n_dates": 0}
    t = sub["t"].drop_nulls()
    sd_mean = float(sub["sd"].mean())  # type: ignore[arg-type]
    n_med = float(sub["n"].median())  # type: ignore[arg-type]
    return {
        "n_dates": ic.height,
        "mean_ic_all": float(ic["ic"].mean()),  # type: ignore[arg-type]
        "n_sub": n_med,
        "mean_ic_sub": float(sub["mean"].mean()),  # type: ignore[arg-type]
        "ic_min_offset": float(sub["mean"].min()),  # type: ignore[arg-type]
        "ic_max_offset": float(sub["mean"].max()),  # type: ignore[arg-type]
        "sd_ic": sd_mean,
        "se": float(sub["se"].mean()),  # type: ignore[arg-type]
        "t_mean": float(t.mean()) if len(t) else float("nan"),  # type: ignore[arg-type]
        "share_abs_t_gt_1_96": float((t.abs() > 1.96).mean()) if len(t) else float("nan"),  # type: ignore[arg-type]
        "mde_t": float(sub["mde_t"].mean()),  # type: ignore[arg-type]
        "mde_normal": mde_normal(sd_mean, int(round(n_med))) if n_med >= 2 else float("nan"),
        "n_required_for_effect": required_n(sd_mean, effect),
    }


def target_correlation(
    panel: pl.DataFrame, column: str, horizon_days: int, min_overlap: int = 10
) -> dict[str, float]:
    """Correlación media por pares entre nombres del target (fechas no solapadas).

    Pares con menos de ``min_overlap`` fechas en común se omiten. ``deff`` es el efecto de
    diseño ``1 + (N - 1) * rho`` con el número medio de nombres por fecha.
    """
    df = panel.filter(pl.col(column).is_not_null())
    dates = (
        df.group_by("date")
        .agg(
            pl.col("entry_date").first(),
            pl.col("label_end_date").first(),
            n=pl.len(),
        )
        .sort("date")
    )
    subs = subsample_indices(
        date_days(dates["entry_date"]), date_days(dates["label_end_date"]), horizon_days
    )
    rhos: list[float] = []
    for idx in subs:
        keep = dates["date"].gather(idx.tolist())
        wide = (
            df.filter(pl.col("date").is_in(keep.implode()))
            .pivot(on="company_id", index="date", values=column)
            .drop("date")
        )
        x = wide.to_numpy().astype(float)
        mask = ~np.isnan(x)
        vals = []
        for i in range(x.shape[1]):
            for j in range(i + 1, x.shape[1]):
                both = mask[:, i] & mask[:, j]
                if both.sum() >= min_overlap:
                    a, b = x[both, i], x[both, j]
                    if a.std() > 0 and b.std() > 0:
                        vals.append(float(np.corrcoef(a, b)[0, 1]))
        if vals:
            rhos.append(float(np.mean(vals)))
    names = float(dates["n"].mean())  # type: ignore[arg-type]
    rho = float(np.mean(rhos)) if rhos else float("nan")
    return {"rho_mean": rho, "mean_names": names, "deff": 1 + (names - 1) * rho}
