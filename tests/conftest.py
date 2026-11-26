"""Datos sintéticos compartidos por los tests de evaluación (sin red ni datos reales)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
import pytest


def make_prices(
    n_companies: int = 12,
    start: dt.date = dt.date(2000, 1, 3),
    n_sessions: int = 1500,
    seed: int = 7,
    drift_sd: float = 0.0,
    vol: float = 0.015,
) -> pl.DataFrame:
    """Paseos aleatorios log-normales con un factor común. ``drift_sd`` > 0 da a cada empresa un
    drift diario persistente (el momentum pasa a predecir el target transversal)."""
    rng = np.random.default_rng(seed)
    dates = pl.date_range(start, start + dt.timedelta(days=int(n_sessions * 1.5)), "1d", eager=True)
    dates = dates.filter(dates.dt.weekday() <= 5)[:n_sessions]
    market = rng.normal(0.0002, 0.01, n_sessions)
    mu = rng.normal(0.0, drift_sd, n_companies)
    rows = []
    for i in range(n_companies):
        ret = market + mu[i] + rng.normal(0.0, vol, n_sessions)
        adj = 10.0 * np.exp(np.cumsum(ret))
        rows.append(
            pl.DataFrame(
                {"company_id": f"c{i:02d}", "date": dates, "adj_close": adj},
            )
        )
    return pl.concat(rows)


def make_intervals(prices: pl.DataFrame) -> pl.DataFrame:
    """Todas las empresas son miembros durante todo el periodo."""
    ids = prices["company_id"].unique().sort()
    return pl.DataFrame(
        {"company_id": ids, "valid_from": [dt.date(1990, 1, 1)] * len(ids)},
        schema_overrides={"valid_to": pl.Date},
    ).with_columns(pl.lit(None, dtype=pl.Date).alias("valid_to"))


@pytest.fixture(scope="session")
def prices_factory():
    return make_prices


@pytest.fixture(scope="session")
def intervals_factory():
    return make_intervals
