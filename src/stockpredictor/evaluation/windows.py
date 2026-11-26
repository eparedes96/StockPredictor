"""Ventanas fuera de muestra evaluables y N_eff (ADR 0007, 0008, 0021).

Walk-forward sin entrenar nada (P1-0 solo mide potencia): el train mínimo fija dónde empieza la
evaluación; la purga exige ``max(label_end train) < inicio del test - embargo`` y el bloque
reservado (ADR 0021) queda fuera, con la misma purga hacia él.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import polars as pl


def add_years(d: dt.date, years: int) -> dt.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year + years, day=28)


@dataclass(frozen=True)
class Bounds:
    """Límites (índices de sesión) de la evaluación fuera de muestra."""

    test_start_si: int  # primera sesión de decisión admisible (tras train mínimo, purga, embargo)
    exit_limit_si: int  # exclusivo: ``exit_si`` de toda fecha evaluada debe ser menor
    reserve_start: dt.date | None


def oos_bounds(
    sessions: pl.DataFrame,
    decisions: pl.DataFrame,
    *,
    prices_from: dt.date,
    train_years: int,
    embargo_sessions: int,
    final_test_years: int | None,
) -> Bounds:
    """``decisions`` trae ``date, si, exit_si`` de las fechas de decisión con etiqueta madura.

    Con ``final_test_years=None`` no se aparta el bloque reservado (solo para cifras informativas
    de diseño, que no usan retornos).
    """
    train = decisions.filter(pl.col("date") <= add_years(prices_from, train_years))
    if train.is_empty():
        raise ValueError("train mínimo sin fechas de decisión")
    test_start = int(train["exit_si"].max()) + embargo_sessions + 1  # type: ignore[arg-type]
    last_si = int(sessions["si"].max())  # type: ignore[arg-type]
    if final_test_years is None:
        return Bounds(test_start, last_si + 1, None)
    data_end = sessions["date"].max()
    reserve_start = add_years(data_end, -final_test_years)  # type: ignore[arg-type]
    reserve_si = int(sessions.filter(pl.col("date") >= reserve_start)["si"].min())  # type: ignore[arg-type]
    return Bounds(test_start, reserve_si - embargo_sessions, reserve_start)


def in_oos(df: pl.DataFrame, bounds: Bounds) -> pl.DataFrame:
    """Filas con ``si >= test_start`` y etiqueta que termina antes del límite (purga al bloque)."""
    return df.filter(
        (pl.col("si") >= bounds.test_start_si) & (pl.col("exit_si") < bounds.exit_limit_si)
    )


def subsample_indices(
    entry_days: np.ndarray, end_days: np.ndarray, horizon_days: int
) -> list[np.ndarray]:
    """Submuestras de etiquetas disjuntas, una por desfase inicial.

    Los arrays van ordenados por fecha de decisión. Una submuestra empieza en cada fecha cuya
    entrada cae en los primeros N días y encadena la primera fecha cuya entrada es >= fin de la
    etiqueta anterior: las etiquetas no se solapan (ADR 0022).
    """
    n = len(entry_days)
    if n == 0:
        return []
    out: list[np.ndarray] = []
    for start in np.nonzero(entry_days < entry_days[0] + horizon_days)[0]:
        idx = [int(start)]
        while True:
            nxt = int(np.searchsorted(entry_days, end_days[idx[-1]], side="left"))
            if nxt >= n:
                break
            idx.append(nxt)
        out.append(np.array(idx))
    return out


def date_days(series: pl.Series) -> np.ndarray:
    return series.cast(pl.Int32).to_numpy().astype(np.int64)


def n_eff(dates: pl.DataFrame, horizon_days: int) -> dict[str, float | int]:
    """N_eff: tamaño de la submuestra disjunta (mediana, mín y máx entre desfases).

    ``dates`` trae ``entry_date`` y ``label_end_date`` de las fechas evaluables, ordenadas.
    ``windows_span`` es la cota ideal ``floor(tramo / N)`` sin la rejilla de fechas.
    """
    if dates.is_empty():
        return {"n_dates": 0, "n_eff": 0, "n_eff_min": 0, "n_eff_max": 0, "windows_span": 0}
    d = dates.sort("entry_date")
    e, x = date_days(d["entry_date"]), date_days(d["label_end_date"])
    sizes = [len(i) for i in subsample_indices(e, x, horizon_days)]
    span = int(x.max() - e.min())
    return {
        "n_dates": d.height,
        "n_eff": float(np.median(sizes)),
        "n_eff_min": min(sizes),
        "n_eff_max": max(sizes),
        "windows_span": span // horizon_days,
    }


def viability(n_windows: float, viable_min: int, exploratory_min: int) -> str:
    """Regla del ADR 0007 sobre ventanas disjuntas fuera de muestra."""
    if n_windows >= viable_min:
        return "viable"
    if n_windows >= exploratory_min:
        return "exploratorio"
    return "no evaluable con rigor"
