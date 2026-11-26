"""Panel de decisión de P1-0: señales transversales simples y target ``y_cs`` solo con precios.

Reglas que aplica (ver ADR 0005, 0026, 0029 y ``CLAUDE.md``):

* Las señales en ``t`` usan solo ``adj_close`` hasta el cierre de ``t`` (ventanas en sesiones).
* Entrada al cierre de la sesión siguiente a ``t``; salida en la última sesión
  ``<= entrada + N`` días naturales (N en días naturales). Si ``entrada + N`` supera la última
  sesión conocida, la etiqueta no ha madurado y la fecha se descarta.
* Universo point-in-time: miembros del índice en ``t`` (``valid_from <= t < valid_to``) con
  precio en ``t``, en la entrada y en la salida. Sin deslistadas: lo que Yahoo no tiene no entra.
* ``y = ln(P_salida / P_entrada)``; ``y_med`` = mediana de la fecha; ``y_cs = y - y_med``.

Solo polars y numpy; sin pandas.
"""

from __future__ import annotations

import numpy as np
import polars as pl

SIGNALS = ("momentum_12_1", "low_vol_60", "reversal_1m")
MOM_SKIP = 21  # sesiones que se saltan (el "1" de 12-1)
MOM_LOOKBACK = 252  # sesiones (el "12")
REV_WINDOW = 21
VOL_WINDOW = 60
VOL_MIN_OBS = 48  # 0,80 * 60 (window_min_coverage de preregistered.yaml)
FREQUENCIES = {"weekly", "monthly"}


def clean_prices(prices: pl.DataFrame) -> pl.DataFrame:
    """``company_id, date, adj_close`` sin nulos ni valores <= 0; falla si hay duplicados."""
    out = prices.select("company_id", "date", "adj_close").filter(
        pl.col("adj_close").is_not_null() & (pl.col("adj_close") > 0)
    )
    if out.select(pl.struct("company_id", "date").is_duplicated().any()).item():
        raise ValueError("precios duplicados por (company_id, date)")
    return out


def sessions_table(prices: pl.DataFrame) -> pl.DataFrame:
    """Calendario de sesiones: fechas con precio de al menos una empresa. ``si`` es su índice."""
    return (
        prices.select("date")
        .unique()
        .sort("date")
        .with_row_index("si")
        .with_columns(pl.col("si").cast(pl.Int64))
    )


def signal_table(prices: pl.DataFrame, sessions: pl.DataFrame) -> pl.DataFrame:
    """Señales y log-precio por (empresa, sesión) sobre la rejilla completa empresa x sesión.

    Un hueco de precio de una empresa deja nulas las señales que lo usan (no se rellena).
    """
    companies = prices.select("company_id").unique().sort("company_id")
    grid = companies.join(sessions, how="cross")
    over = "company_id"
    g = (
        grid.join(prices, on=["company_id", "date"], how="left")
        .sort("company_id", "si")
        .with_columns(lp=pl.col("adj_close").log())
        .with_columns(r1=pl.col("lp") - pl.col("lp").shift(1).over(over))
    )
    g = g.with_columns(
        momentum_12_1=pl.col("lp").shift(MOM_SKIP).over(over)
        - pl.col("lp").shift(MOM_LOOKBACK).over(over),
        reversal_1m=-(pl.col("lp") - pl.col("lp").shift(REV_WINDOW).over(over)),
        low_vol_60=-pl.col("r1").rolling_std(VOL_WINDOW, min_samples=VOL_MIN_OBS).over(over),
    )
    return g.select("company_id", "si", "date", "lp", *SIGNALS)


def horizon_calendar(sessions: pl.DataFrame, horizon_days: int) -> pl.DataFrame:
    """Por sesión ``t``: sesión de entrada (t+1) y de salida (última <= entrada + N días)."""
    days = sessions["date"].cast(pl.Int32).to_numpy()
    dates = sessions["date"].to_numpy()
    n = len(days)
    if n < 2:
        raise ValueError("hacen falta al menos dos sesiones")
    si = np.arange(n - 1)
    target = days[1:] + horizon_days
    mature = target <= days[-1]
    exit_si = np.searchsorted(days, target, side="right") - 1
    si, exit_si = si[mature], exit_si[mature]
    return pl.DataFrame(
        {
            "si": si,
            "entry_si": si + 1,
            "exit_si": exit_si,
            "entry_date": dates[si + 1],
            "label_end_date": dates[exit_si],
        },
        schema_overrides={"si": pl.Int64, "entry_si": pl.Int64, "exit_si": pl.Int64},
    )


def decision_dates(sessions: pl.DataFrame, frequency: str) -> pl.DataFrame:
    """Última sesión de cada semana ISO (``weekly``) o de cada mes (``monthly``)."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"frecuencia desconocida: {frequency}")
    if frequency == "weekly":
        keys = [pl.col("date").dt.iso_year().alias("k1"), pl.col("date").dt.week().alias("k2")]
    else:
        keys = [pl.col("date").dt.year().alias("k1"), pl.col("date").dt.month().alias("k2")]
    return (
        sessions.with_columns(keys)
        .group_by("k1", "k2")
        .agg(pl.col("si").max(), pl.col("date").max())
        .sort("si")
        .select("si", "date")
    )


def build_panel(
    signals: pl.DataFrame,
    sessions: pl.DataFrame,
    intervals: pl.DataFrame,
    horizon_days: int,
    frequency: str,
) -> pl.DataFrame:
    """Filas (fecha de decisión, miembro del índice en esa fecha) con señales y target.

    ``intervals`` trae ``company_id, valid_from, valid_to`` (``valid_to`` nulo = vigente).
    Las filas sin precio en ``t``, entrada o salida tienen ``y`` nulo y no entran en ``y_med``.
    """
    cal = horizon_calendar(sessions, horizon_days)
    dec = decision_dates(sessions, frequency).join(cal, on="si", how="inner")
    members = (
        dec.select("si", "date")
        .join(intervals.select("company_id", "valid_from", "valid_to"), how="cross")
        .filter(
            (pl.col("valid_from") <= pl.col("date"))
            & (pl.col("valid_to").is_null() | (pl.col("date") < pl.col("valid_to")))
        )
        .select("si", "date", "company_id")
        .unique(["si", "company_id"])
    )
    lp = signals.select("company_id", "si", "lp")
    out = (
        members.join(
            signals.select("company_id", "si", *SIGNALS), on=["company_id", "si"], how="left"
        )
        .join(lp.rename({"lp": "lp_t"}), on=["company_id", "si"], how="left")
        .join(dec.select("si", "entry_si", "exit_si", "entry_date", "label_end_date"), on="si")
        .join(
            lp.rename({"si": "entry_si", "lp": "lp_entry"}),
            on=["company_id", "entry_si"],
            how="left",
        )
        .join(
            lp.rename({"si": "exit_si", "lp": "lp_exit"}),
            on=["company_id", "exit_si"],
            how="left",
        )
    )
    y = pl.when(pl.col("lp_t").is_not_null()).then(pl.col("lp_exit") - pl.col("lp_entry"))
    out = out.with_columns(y.alias("y")).with_columns(
        pl.col("y").median().over("date").alias("y_med")
    )
    # Sin precio en t no hay señal utilizable: las señales se anulan para no puntuar esas filas.
    out = out.with_columns(
        [pl.when(pl.col("lp_t").is_not_null()).then(pl.col(s)).alias(s) for s in SIGNALS]
    )
    return (
        out.with_columns((pl.col("y") - pl.col("y_med")).alias("y_cs"))
        .select(
            "date",
            "si",
            "entry_si",
            "exit_si",
            "entry_date",
            "label_end_date",
            "company_id",
            "y",
            "y_med",
            "y_cs",
            *SIGNALS,
        )  # fmt: skip
        .sort("date", "company_id")
    )


def coverage_by_date(panel: pl.DataFrame) -> pl.DataFrame:
    """Miembros del índice y miembros con target válido por fecha de decisión."""
    return (
        panel.group_by("date")
        .agg(
            n_members=pl.len(),
            n_valid=pl.col("y_cs").is_not_null().sum(),
        )
        .with_columns(share_valid=pl.col("n_valid") / pl.col("n_members"))
        .sort("date")
    )
