import datetime as dt

import numpy as np
import polars as pl
import pytest
from scipy import stats

from stockpredictor.evaluation import panel as pn
from stockpredictor.evaluation import power, windows
from stockpredictor.evaluation.permutation import permutation_test

D = dt.date


def _panel(prices, intervals_factory, h=30, freq="weekly"):
    p = pn.clean_prices(prices)
    s = pn.sessions_table(p)
    return pn.build_panel(pn.signal_table(p, s), s, intervals_factory(p), h, freq), s


def test_rankic_matches_scipy_spearman(prices_factory, intervals_factory):
    prices = prices_factory(n_companies=15, n_sessions=700, drift_sd=0.001)
    panel, _ = _panel(prices, intervals_factory)
    ic = power.rankic_by_date(panel, "momentum_12_1", 10)
    assert ic.height > 20
    for d in ic["date"].to_list()[::10]:
        sub = panel.filter(
            (pl.col("date") == d)
            & pl.col("y_cs").is_not_null()
            & pl.col("momentum_12_1").is_not_null()
        )
        expected = stats.spearmanr(sub["momentum_12_1"].to_numpy(), sub["y_cs"].to_numpy())[0]
        got = ic.filter(pl.col("date") == d)["ic"][0]
        assert got == pytest.approx(expected, abs=1e-12)


def test_rankic_ties_use_average_rank():
    df = pl.DataFrame(
        {
            "date": [D(2024, 1, 5)] * 12,
            "si": [1] * 12,
            "exit_si": [9] * 12,
            "entry_date": [D(2024, 1, 8)] * 12,
            "label_end_date": [D(2024, 3, 8)] * 12,
            "y_cs": [1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
            "s": [3.0, 1.0, 1.0, 2.0, 5.0, 4.0, 4.0, 7.0, 6.0, 9.0, 8.0, 10.0],
        }
    )
    got = power.rankic_by_date(df, "s", 10)["ic"][0]
    assert got == pytest.approx(stats.spearmanr(df["s"], df["y_cs"])[0])


def test_rankic_requires_min_names():
    df = pl.DataFrame(
        {
            "date": [D(2024, 1, 5)] * 5, "si": [1] * 5, "exit_si": [9] * 5,
            "entry_date": [D(2024, 1, 8)] * 5, "label_end_date": [D(2024, 3, 8)] * 5,
            "y_cs": [1.0, 2.0, 3.0, 4.0, 5.0], "s": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )  # fmt: skip
    assert power.rankic_by_date(df, "s", 10).is_empty()
    assert power.rankic_by_date(df, "s", 5)["ic"][0] == pytest.approx(1.0)


def test_mde_t_converges_to_normal_and_is_larger_for_small_n():
    assert power.mde_t(0.3, 100000) == pytest.approx(power.mde_normal(0.3, 100000), rel=2e-3)
    assert power.mde_normal(1.0, 100) == pytest.approx(2.8016 / 10, rel=1e-3)
    assert power.mde_t(0.3, 13) > power.mde_normal(0.3, 13)


def test_mde_t_has_80_percent_power_in_simulation():
    n, sigma = 13, 1.0
    mde = power.mde_t(sigma, n)
    rng = np.random.default_rng(0)
    x = rng.normal(mde, sigma, size=(40000, n))
    t = x.mean(1) / (x.std(1, ddof=1) / np.sqrt(n))
    reject = np.abs(t) > stats.t.ppf(0.975, n - 1)
    assert reject.mean() == pytest.approx(0.80, abs=0.01)


def test_mde_t_degenerate_inputs():
    assert np.isnan(power.mde_t(0.3, 2))
    assert np.isnan(power.mde_t(0.0, 20))
    assert power.required_n(0.3, 0.05) == pytest.approx((2.8016 * 0.3 / 0.05) ** 2, rel=1e-3)


def test_subsample_indices_disjoint_and_cover_all_offsets():
    entry = np.arange(0, 1000, 7)  # una fecha por semana
    end = entry + 90
    subs = windows.subsample_indices(entry, end, 90)
    assert len(subs) == int(np.sum(entry < entry[0] + 90))
    for idx in subs:
        assert np.all(entry[idx][1:] >= end[idx][:-1])  # entrada >= fin de la etiqueta anterior
        assert len(idx) >= 9
    assert windows.subsample_indices(np.array([]), np.array([]), 90) == []


def test_viability_thresholds():
    assert windows.viability(10, 10, 4) == "viable"
    assert windows.viability(9, 10, 4) == "exploratorio"
    assert windows.viability(4, 10, 4) == "exploratorio"
    assert windows.viability(3, 10, 4) == "no evaluable con rigor"


def test_n_eff_counts_disjoint_windows():
    entry = [D(2010, 1, 1) + dt.timedelta(days=7 * i) for i in range(200)]
    df = pl.DataFrame({"entry_date": entry}).with_columns(
        (pl.col("entry_date") + pl.duration(days=90)).alias("label_end_date")
    )
    r = windows.n_eff(df, 90)
    assert r["n_dates"] == 200
    assert r["n_eff"] == pytest.approx(200 * 7 / 91, abs=2)  # ~15 ventanas
    assert r["windows_span"] == (199 * 7 + 90) // 90
    assert windows.n_eff(df.head(0), 90)["n_eff"] == 0


def test_summarize_signal_on_noise_has_small_mean_and_sane_mde(prices_factory, intervals_factory):
    prices = prices_factory(n_companies=20, n_sessions=2500, seed=11)
    panel, _ = _panel(prices, intervals_factory, h=60)
    ic = power.rankic_by_date(panel, "reversal_1m", 10)
    summ = power.summarize_signal(ic, 60, 0.05)
    assert abs(summ["mean_ic_sub"]) < 3 * summ["se"]
    assert 0.1 < summ["sd_ic"] < 0.4  # ~1/sqrt(19) bajo la nula
    assert summ["mde_t"] > summ["mde_normal"] * 0.99


def test_permutation_matches_rankic_and_detects_planted_signal(prices_factory, intervals_factory):
    prices = prices_factory(n_companies=20, n_sessions=2500, seed=5, drift_sd=0.0015)
    panel, _ = _panel(prices, intervals_factory, h=60)
    ic = power.rankic_by_date(panel, "momentum_12_1", 10)
    res = permutation_test(panel, "momentum_12_1", 60, 10, n_perm=200, seed=1)
    assert res["mean_ic_obs"] == pytest.approx(ic["ic"].mean(), abs=1e-12)
    assert res["mean_ic_obs"] > 0.3  # drift persistente: el momentum acierta
    assert res["p_all"] == pytest.approx(1 / 201)  # ninguna permutación lo iguala
    assert res["null_sd_all"] < 0.05


def test_permutation_on_noise_is_not_significant_and_reproducible(
    prices_factory, intervals_factory
):
    prices = prices_factory(n_companies=20, n_sessions=2500, seed=21)
    panel, _ = _panel(prices, intervals_factory, h=60)
    a = permutation_test(panel, "low_vol_60", 60, 10, n_perm=300, seed=3)
    b = permutation_test(panel, "low_vol_60", 60, 10, n_perm=300, seed=3)
    assert a == b
    assert a["p_sub_median"] > 0.05
    # la σ nula de la media de una submuestra coincide con ~σ_IC_nula/sqrt(n)
    assert a["null_sd_sub"] > a["null_sd_all"]


def test_target_correlation_absolute_vs_cross_sectional(prices_factory, intervals_factory):
    prices = prices_factory(n_companies=16, n_sessions=2500, seed=2)
    panel, _ = _panel(prices, intervals_factory, h=60)
    y = power.target_correlation(panel, "y", 60)
    ycs = power.target_correlation(panel, "y_cs", 60)
    assert y["rho_mean"] > 0.1  # el factor común domina el retorno absoluto
    assert abs(ycs["rho_mean"]) < y["rho_mean"]
    assert ycs["rho_mean"] < 0.05
