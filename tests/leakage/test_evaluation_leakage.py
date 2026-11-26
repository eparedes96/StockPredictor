"""Anti-fuga de P1-0: señales, target, universo y límites fuera de muestra."""

import datetime as dt

import polars as pl
import pytest

from stockpredictor.evaluation import panel as pn
from stockpredictor.evaluation import windows

pytestmark = pytest.mark.leakage
D = dt.date


def _build(prices, intervals, h=60, freq="weekly"):
    p = pn.clean_prices(prices)
    s = pn.sessions_table(p)
    return pn.build_panel(pn.signal_table(p, s), s, intervals, h, freq), s


@pytest.fixture(scope="module")
def base(prices_factory, intervals_factory):
    prices = prices_factory(n_companies=10, n_sessions=900, seed=4)
    return prices, intervals_factory(prices)


def _same_rows(a: pl.DataFrame, b: pl.DataFrame, mask_a: pl.Expr) -> None:
    cols = ["date", "company_id", "y", "y_med", "y_cs", *pn.SIGNALS]
    x = a.filter(mask_a).select(cols).sort("date", "company_id")
    y = (
        b.filter(pl.col("date").is_in(x["date"].unique().implode()))
        .select(cols)
        .sort("date", "company_id")
    )
    assert x.height > 20
    assert x.equals(y)


def test_future_prices_do_not_change_past_rows(base):
    prices, iv = base
    full, sessions = _build(prices, iv)
    cutoff = sessions["date"][600]
    corrupted = prices.with_columns(
        pl.when(pl.col("date") > cutoff)
        .then(pl.col("adj_close") * 7.0 + 3.0)
        .otherwise(pl.col("adj_close"))
        .alias("adj_close")
    )
    alt, _ = _build(corrupted, iv)
    # las filas cuya etiqueta termina antes del corte no cambian (señales, y, y_med, y_cs)
    _same_rows(full, alt, pl.col("label_end_date") <= cutoff)


def test_signals_at_t_ignore_everything_after_t(base):
    prices, iv = base
    full, sessions = _build(prices, iv)
    cutoff = sessions["date"][500]
    truncated = prices.filter(pl.col("date") <= cutoff)
    alt, _ = _build(truncated, iv)
    # al truncar, las fechas con etiqueta inmadura desaparecen; se compara el resto
    keep = alt["date"].unique()
    a = full.filter(pl.col("date").is_in(keep.implode()) & (pl.col("date") <= cutoff)).select(
        "date", "company_id", *pn.SIGNALS
    )
    b = alt.filter(pl.col("date") <= cutoff).select("date", "company_id", *pn.SIGNALS)
    assert a.height > 100
    assert a.sort("date", "company_id").equals(b.sort("date", "company_id"))


def test_target_does_not_depend_on_price_at_t(base):
    """La entrada es el cierre de t+1: cambiar el precio de t no mueve y (solo anula la señal)."""
    prices, iv = base
    full, sessions = _build(prices, iv)
    t = full["date"].unique().sort()[40]
    corrupted = prices.with_columns(
        pl.when(pl.col("date") == t)
        .then(pl.col("adj_close") * 3.0)
        .otherwise(pl.col("adj_close"))
        .alias("adj_close")
    )
    alt, _ = _build(corrupted, iv)
    a = full.filter(pl.col("date") == t).sort("company_id")
    b = alt.filter(pl.col("date") == t).sort("company_id")
    assert a["y"].to_list() == b["y"].to_list()
    assert a["y_cs"].to_list() == b["y_cs"].to_list()


def test_membership_changes_after_t_do_not_alter_rows_at_t(base):
    prices, iv = base
    full, sessions = _build(prices, iv)
    t = sessions["date"][300]
    late = iv.with_columns(
        pl.when(pl.col("company_id").is_in(["c00", "c01"]))
        .then(pl.lit(t + dt.timedelta(days=30)))
        .otherwise(pl.lit(D(1990, 1, 1)))
        .alias("valid_from")
    )
    alt, _ = _build(prices, late)
    a = full.filter(pl.col("date") <= t)
    b = alt.filter(pl.col("date") <= t)
    assert set(a["company_id"]) >= set(
        b["company_id"]
    )  # c00 y c01 solo se pierden antes de su alta
    early = alt.filter(pl.col("date") > t + dt.timedelta(days=60))
    assert {"c00", "c01"} <= set(early["company_id"])


def test_cross_sectional_median_uses_only_same_date(base):
    prices, iv = base
    full, _ = _build(prices, iv)
    d0 = full["date"].unique().sort()[40]
    # cambiar el target de otra fecha (vía precios de su ventana) no altera y_med en d0
    other = full["date"].unique().sort()[100]
    alt_prices = prices.with_columns(
        pl.when((pl.col("date") > other) & (pl.col("date") < other + dt.timedelta(days=5)))
        .then(pl.col("adj_close") * 2.0)
        .otherwise(pl.col("adj_close"))
        .alias("adj_close")
    )
    alt, _ = _build(alt_prices, iv)
    a = full.filter(pl.col("date") == d0)["y_med"].unique().to_list()
    b = alt.filter(pl.col("date") == d0)["y_med"].unique().to_list()
    assert a == b


@pytest.mark.parametrize("h,freq", [(90, "weekly"), (365, "monthly")])
def test_oos_purge_and_reserve_invariants(prices_factory, intervals_factory, h, freq):
    """ADR 0008 y 0021: max(label_end train) < test_start - embargo; OOS acaba antes del bloque."""
    prices = prices_factory(n_companies=10, n_sessions=3500, seed=8)
    iv = intervals_factory(prices)
    panel, sessions = _build(prices, iv, h, freq)
    dec = panel.group_by("date").agg(pl.col("si").first(), pl.col("exit_si").first()).sort("date")
    embargo = 5
    b = windows.oos_bounds(
        sessions, dec, prices_from=D(2000, 1, 3), train_years=3,
        embargo_sessions=embargo, final_test_years=2,
    )  # fmt: skip
    train = dec.filter(pl.col("date") <= windows.add_years(D(2000, 1, 3), 3))
    assert train["exit_si"].max() < b.test_start_si - embargo
    oos = windows.in_oos(dec, b)
    assert oos.height > 0
    assert oos["si"].min() >= b.test_start_si
    reserve_start = windows.add_years(sessions["date"].max(), -2)
    reserve_si = sessions.filter(pl.col("date") >= reserve_start)["si"].min()
    assert oos["exit_si"].max() < reserve_si - embargo
    # el bloque reservado no tiene ninguna etiqueta que arranque dentro de la zona OOS
    last_label_date = sessions.filter(pl.col("si") == oos["exit_si"].max())["date"][0]
    assert last_label_date < reserve_start
