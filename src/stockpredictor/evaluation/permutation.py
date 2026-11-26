"""Contraste de permutación real: se baraja ``y_cs`` entre nombres dentro de cada fecha.

Con la señal fija, ``rank(y_cs)`` permutado dentro de la fecha da el RankIC nulo. Como el
denominador de Spearman es invariante a la permutación, cada repetición cuesta una ordenación y
un producto de matrices.

Límite: barajar por fecha, de forma independiente entre fechas, rompe la dependencia temporal de
los rangos de ``y_cs`` (etiquetas solapadas, señales persistentes). Es exacto bajo H0 en cada fecha,
pero la varianza nula de la media sobre fechas solapadas queda subestimada; por eso el contraste
principal sigue siendo el de submuestras no solapadas (ADR 0022) y aquí se reporta también la media
de cada submuestra disjunta.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from stockpredictor.evaluation.windows import date_days, subsample_indices


def permutation_test(
    panel: pl.DataFrame,
    signal: str,
    horizon_days: int,
    min_names: int,
    n_perm: int = 1000,
    seed: int = 20261126,
) -> dict[str, float | int]:
    df = (
        panel.filter(pl.col("y_cs").is_not_null() & pl.col(signal).is_not_null())
        .with_columns(
            rs=pl.col(signal).rank("average").over("date"),
            ry=pl.col("y_cs").rank("average").over("date"),
        )
        .sort("date")
    )
    counts = df.group_by("date", maintain_order=True).agg(
        n=pl.len(),
        entry_date=pl.col("entry_date").first(),
        label_end_date=pl.col("label_end_date").first(),
    )
    counts = counts.filter(pl.col("n") >= min_names)
    df = df.join(counts.select("date"), on="date", how="semi")
    n_d = counts["n"].to_numpy().astype(np.int64)
    n_dates = len(n_d)
    if n_dates == 0:
        return {"n_dates": 0}
    k = int(np.max(n_d))
    starts = np.concatenate([[0], np.cumsum(n_d)[:-1]])
    row = np.repeat(np.arange(n_dates), n_d)
    col = np.arange(int(n_d.sum())) - np.repeat(starts, n_d)
    mask = np.zeros((n_dates, k), dtype=bool)
    mask[row, col] = True
    rs = np.zeros((n_dates, k))
    ry = np.zeros((n_dates, k))
    rs[row, col] = df["rs"].to_numpy()
    ry[row, col] = df["ry"].to_numpy()
    rs = (rs - (rs.sum(1) / n_d)[:, None]) * mask
    ry = (ry - (ry.sum(1) / n_d)[:, None]) * mask
    denom = np.sqrt((rs**2).sum(1) * (ry**2).sum(1))
    ok = denom > 0
    if not ok.all():  # fecha con señal o target constante: sin RankIC
        rs, ry, denom, mask, n_d = rs[ok], ry[ok], denom[ok], mask[ok], n_d[ok]
        counts = counts.filter(pl.Series(ok))
        n_dates = int(ok.sum())
    obs = (rs * ry).sum(1) / denom

    subs = subsample_indices(
        date_days(counts["entry_date"]), date_days(counts["label_end_date"]), horizon_days
    )
    sub_w = np.zeros((len(subs), n_dates))
    for j, idx in enumerate(subs):
        sub_w[j, idx] = 1.0 / len(idx)
    obs_sub = sub_w @ obs

    rng = np.random.default_rng(seed)
    null_all = np.empty(n_perm)
    null_sub = np.empty((n_perm, len(subs)))
    for b in range(n_perm):
        keys = rng.random((n_dates, k))
        keys[~mask] = 2.0  # las posiciones vacías quedan al final
        perm = np.argsort(keys, axis=1)
        ic = (rs * np.take_along_axis(ry, perm, axis=1)).sum(1) / denom
        null_all[b] = ic.mean()
        null_sub[b] = sub_w @ ic

    def pval(null: np.ndarray, value: float) -> float:
        return float((1 + np.sum(np.abs(null) >= abs(value) - 1e-12)) / (len(null) + 1))

    p_sub = [pval(null_sub[:, j], float(obs_sub[j])) for j in range(len(subs))]
    return {
        "n_dates": n_dates,
        "n_perm": n_perm,
        "mean_ic_obs": float(obs.mean()),
        "null_sd_all": float(null_all.std(ddof=1)),
        "p_all": pval(null_all, float(obs.mean())),
        "null_sd_sub": float(np.mean(null_sub.std(axis=0, ddof=1))),
        "p_sub_median": float(np.median(p_sub)),
        "p_sub_min": float(np.min(p_sub)),
    }
