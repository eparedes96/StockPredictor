import datetime as dt

import numpy as np
import polars as pl
import pytest

from stockpredictor.evaluation import panel as pn

D = dt.date


def _sessions(dates):
    return pn.sessions_table(pl.DataFrame({"date": dates, "company_id": "a", "adj_close": 1.0}))


def test_horizon_calendar_exit_is_last_session_within_n_days():
    # lunes a viernes de dos semanas; N = 7: entrada mar 2, límite 9 (mar) -> salida mar 9
    dates = [D(2024, 1, d) for d in (1, 2, 3, 4, 5, 8, 9, 10, 11, 12)]
    cal = pn.horizon_calendar(_sessions(dates), 7)
    first = cal.row(0, named=True)
    assert first["entry_date"] == D(2024, 1, 2)
    assert first["label_end_date"] == D(2024, 1, 9)
    # N = 6 desde la entrada del 2 -> límite 8 (lunes): salida lunes 8
    cal6 = pn.horizon_calendar(_sessions(dates), 6)
    assert cal6.row(0, named=True)["label_end_date"] == D(2024, 1, 8)


def test_horizon_calendar_drops_immature_labels():
    dates = [D(2024, 1, d) for d in (1, 2, 3, 4, 5, 8, 9, 10, 11, 12)]
    cal = pn.horizon_calendar(_sessions(dates), 7)
    # entrada + 7 días debe caer en o antes de la última sesión (12): entradas hasta el 5
    assert cal["entry_date"].max() == D(2024, 1, 5)
    assert cal["label_end_date"].max() <= D(2024, 1, 12)


def test_exit_skips_non_sessions():
    dates = [D(2024, 1, 1), D(2024, 1, 2), D(2024, 1, 3), D(2024, 1, 10)]
    cal = pn.horizon_calendar(_sessions(dates), 5)
    row = cal.row(0, named=True)  # entrada el 2 -> límite el 7 -> última sesión <= 7 es el 3
    assert row["label_end_date"] == D(2024, 1, 3)


def test_decision_dates_weekly_and_monthly():
    dates = pl.date_range(D(2024, 1, 1), D(2024, 3, 31), "1d", eager=True)
    dates = dates.filter(dates.dt.weekday() <= 5)
    s = _sessions(dates.to_list())
    weekly = pn.decision_dates(s, "weekly")["date"].to_list()
    assert all(d.weekday() == 4 for d in weekly[:-1])  # viernes
    monthly = pn.decision_dates(s, "monthly")["date"].to_list()
    assert monthly == [D(2024, 1, 31), D(2024, 2, 29), D(2024, 3, 29)]
    with pytest.raises(ValueError):
        pn.decision_dates(s, "daily")


def _flat_prices(path: dict[str, list[float]], start: dt.date | None = None):
    start = start or D(2024, 1, 1)
    n = len(next(iter(path.values())))
    dates = [start + dt.timedelta(days=i) for i in range(n)]
    return pl.concat(
        [pl.DataFrame({"company_id": c, "date": dates, "adj_close": v}) for c, v in path.items()]
    )


def test_signals_match_hand_computation():
    n = 300
    rng = np.random.default_rng(3)
    p = 20 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    prices = _flat_prices({"a": list(p)})
    s = pn.sessions_table(prices)
    sig = pn.signal_table(prices, s).sort("si")
    t = 290
    lp = np.log(p)
    r = np.diff(lp)  # r[k] = lp[k+1] - lp[k]
    row = sig.row(t, named=True)
    assert row["momentum_12_1"] == pytest.approx(lp[t - 21] - lp[t - 252])
    assert row["reversal_1m"] == pytest.approx(-(lp[t] - lp[t - 21]))
    assert row["low_vol_60"] == pytest.approx(-np.std(r[t - 60 : t], ddof=1))
    assert sig.row(100, named=True)["momentum_12_1"] is None  # sin 252 sesiones de historia


def test_low_vol_needs_min_observations():
    n = 200
    p = list(20 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, n))))
    for k in range(100, 130):  # 30 huecos seguidos -> menos de 48 retornos válidos en la ventana
        p[k] = None
    prices = _flat_prices({"a": p}).filter(pl.col("adj_close").is_not_null())
    s = pn.sessions_table(_flat_prices({"a": [1.0] * n}))
    sig = pn.signal_table(prices, s).sort("si")
    assert sig.row(140, named=True)["low_vol_60"] is None


def test_panel_target_is_cross_sectional_and_uses_entry_t_plus_1():
    n = 60
    growth = {"a": 0.002, "b": 0.001, "c": 0.0}
    prices = _flat_prices({c: list(10 * np.exp(g * np.arange(n))) for c, g in growth.items()})
    s = pn.sessions_table(prices)
    sig = pn.signal_table(prices, s)
    iv = pl.DataFrame(
        {"company_id": list(growth), "valid_from": [D(2000, 1, 1)] * 3, "valid_to": [None] * 3},
        schema_overrides={"valid_to": pl.Date},
    )
    panel = pn.build_panel(sig, s, iv, 10, "weekly")
    r = panel.filter(pl.col("date") == panel["date"].min()).sort("company_id")
    assert r["label_end_date"][0] - r["entry_date"][0] == dt.timedelta(days=10)
    # el retorno es g * 10 días exactos entre entrada y salida (calendario diario sin huecos)
    assert r["y"].to_list() == pytest.approx([0.02, 0.01, 0.0])
    assert r["y_med"].to_list() == pytest.approx([0.01] * 3)
    assert r["y_cs"].to_list() == pytest.approx([0.01, 0.0, -0.01])
    assert (r["entry_date"] - r["date"]).dt.total_days().to_list() == [1, 1, 1]


def test_panel_respects_membership_and_missing_prices():
    n = 60
    prices = _flat_prices({c: list(10 + np.arange(n) * 0.1) for c in "abc"})
    prices = prices.filter(~((pl.col("company_id") == "c") & (pl.col("date") >= D(2024, 1, 25))))
    s = pn.sessions_table(prices)
    sig = pn.signal_table(prices, s)
    iv = pl.DataFrame(
        {
            "company_id": ["a", "b", "c"],
            "valid_from": [D(2000, 1, 1), D(2024, 1, 20), D(2000, 1, 1)],
            "valid_to": [None, None, None],
        },
        schema_overrides={"valid_to": pl.Date},
    )
    panel = pn.build_panel(sig, s, iv, 10, "weekly")
    early = panel.filter(pl.col("date") < D(2024, 1, 20))
    assert set(early["company_id"]) == {"a", "c"}  # b aún no es miembro
    late = panel.filter(pl.col("date") >= D(2024, 1, 22))
    c_late = late.filter(pl.col("company_id") == "c")
    assert c_late["y"].null_count() == c_late.height  # sin precio de salida: target nulo
    # y_med solo usa filas con target válido
    valid = late.filter(pl.col("y").is_not_null())
    assert valid["y_med"].null_count() == 0
    assert valid["y_cs"].null_count() == 0


def test_clean_prices_rejects_duplicates_and_nonpositive():
    df = pl.DataFrame(
        {
            "company_id": ["a", "a", "b", "b"],
            "date": [D(2024, 1, 1), D(2024, 1, 2), D(2024, 1, 1), D(2024, 1, 2)],
            "adj_close": [1.0, None, -1.0, 2.0],
        }
    )
    assert pn.clean_prices(df).height == 2
    dup = pl.concat([df, df.head(1)])
    with pytest.raises(ValueError):
        pn.clean_prices(dup)
