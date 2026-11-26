"""Anti-fuga: la composición en t no depende de eventos posteriores a t."""

import datetime as dt

import polars as pl
import pytest

from stockpredictor.universe import membership as m

pytestmark = pytest.mark.leakage

SAMPLE_DATES = [
    dt.date(1990, 6, 1), dt.date(1999, 4, 19), dt.date(2001, 4, 15), dt.date(2008, 2, 4),
    dt.date(2013, 12, 23), dt.date(2017, 6, 7), dt.date(2022, 6, 13), dt.date(2025, 1, 1),
]  # fmt: skip


@pytest.fixture(scope="module")
def events() -> pl.DataFrame:
    return m.load_events("ibex35")


@pytest.fixture(scope="module")
def code_map() -> pl.DataFrame:
    return m.load_code_map()


@pytest.mark.parametrize("t", SAMPLE_DATES)
def test_truncating_future_events_does_not_change_membership(t, events, code_map):
    full = m.members_at(t, events=events, code_map=code_map)
    truncated = events.filter(pl.col("effective_date") <= t)
    assert m.members_at(t, events=truncated, code_map=code_map) == full


@pytest.mark.parametrize("t", SAMPLE_DATES)
def test_corrupting_future_events_does_not_change_membership(t, events, code_map):
    full = m.members_at(t, events=events, code_map=code_map)
    future = pl.col("effective_date") > t
    corrupted = events.with_columns(
        # bajas de códigos inexistentes, altas duplicadas y fechas alteradas, solo en el futuro
        pl.when(future).then(pl.lit("ZZZZ")).otherwise(pl.col("bme_code")).alias("bme_code"),
        pl.when(future)
        .then(pl.lit("deletion"))
        .otherwise(pl.col("event_type"))
        .alias("event_type"),
    )
    assert m.members_at(t, events=corrupted, code_map=code_map) == full


def test_adding_a_future_event_does_not_change_the_past(events, code_map):
    t = dt.date(2010, 1, 1)
    extra = events.head(1).with_columns(
        pl.lit(dt.date(2030, 1, 1)).alias("effective_date"),
        pl.lit("addition").alias("event_type"),
        pl.lit("TEF").alias("bme_code"),
    )
    bigger = pl.concat([events, extra])
    assert m.members_at(t, events=bigger, code_map=code_map) == m.members_at(
        t, events=events, code_map=code_map
    )


def test_membership_is_monotone_in_information(events, code_map):
    # Reproducir el índice día a día con eventos ≤ t equivale a hacerlo de golpe.
    dates = sorted(set(events["effective_date"].to_list()))
    for t in dates[::12]:
        assert m.members_at(
            t, events=events.filter(pl.col("effective_date") <= t), code_map=code_map
        ) == m.members_at(t, events=events, code_map=code_map)
