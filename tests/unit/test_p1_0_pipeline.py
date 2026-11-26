import json

import polars as pl
import pytest

from stockpredictor.cli import build_parser, main
from stockpredictor.evaluation import p1_0


def _small_params(**kw):
    base = dict(
        horizons=(60,), frequency={60: "weekly"}, descriptive_horizons=(300,),
        train_years_grid=(2, 3), primary_train_years=3, final_test_years=1, n_perm=50,
    )  # fmt: skip
    return p1_0.Params(**{**base, **kw})


@pytest.fixture(scope="module")
def result(prices_factory, intervals_factory):
    prices = prices_factory(n_companies=14, n_sessions=3000, seed=9, drift_sd=0.0008)
    from datetime import date

    return p1_0.run(
        prices, intervals_factory(prices), date(2000, 1, 3), _small_params(),
        {"snapshot_id": "test", "prices_sha256": "0" * 64},
    )  # fmt: skip


def test_run_produces_consistent_tables(result):
    s = result.summary.row(0, named=True)
    assert s["horizon"] == 60
    assert s["label"] in (p1_0.LABEL_DETECTABLE, p1_0.LABEL_INCONCLUSIVE)
    assert s["label"] == (
        p1_0.LABEL_DETECTABLE if s["mde_headline"] <= 0.05 else p1_0.LABEL_INCONCLUSIVE
    )
    sig = result.signals
    assert set(sig["signal"]) == {"momentum_12_1", "low_vol_60", "reversal_1m"}
    assert set(sig["train_years"]) == {2, 3}
    # más train mínimo -> menos ventanas OOS
    n = result.n_eff.filter((pl.col("horizon") == 60) & pl.col("reserved_block")).sort(
        "train_years"
    )
    assert n["n_eff"][0] >= n["n_eff"][1]
    # sin bloque reservado hay al menos tantas ventanas
    a = result.n_eff.filter((pl.col("horizon") == 60) & (pl.col("train_years") == 3))
    assert (
        a.filter(~pl.col("reserved_block"))["n_eff"][0]
        >= a.filter(pl.col("reserved_block"))["n_eff"][0]
    )
    assert result.n_eff.filter(pl.col("descriptive"))["horizon"].unique().to_list() == [300]
    assert result.meta["label"] == p1_0.LABEL_SURVIVORSHIP


def test_planted_momentum_is_visible_in_momentum_only(result):
    sig = result.signals.filter(pl.col("train_years") == 3)
    mom = sig.filter(pl.col("signal") == "momentum_12_1")["mean_ic_all"][0]
    rev = sig.filter(pl.col("signal") == "low_vol_60")["mean_ic_all"][0]
    assert mom > 0.2 and abs(rev) < mom


def test_report_and_outputs(result, tmp_path):
    text = p1_0.render_report(result)
    assert "con sesgo de supervivencia (sin deslistadas)" in text
    assert "no concluyente por diseño" in text or "detectable" in text
    assert "## 5. Permutación" in text
    p1_0.write_outputs(result, tmp_path)
    for name in ("informe.md", "n_eff.csv", "rankic_mde.csv", "permutacion.csv", "resumen.csv",
                 "correlacion_targets.csv", "cobertura_por_anio.csv", "run.json"):  # fmt: skip
        assert (tmp_path / name).exists()
    meta = json.loads((tmp_path / "run.json").read_text(encoding="utf8"))
    assert meta["params"]["seed"] == 20261126


def test_same_seed_same_result(prices_factory, intervals_factory):
    from datetime import date

    prices = prices_factory(n_companies=12, n_sessions=2200, seed=13)
    kw = dict(descriptive_horizons=(), train_years_grid=(2,), primary_train_years=2)
    a = p1_0.run(prices, intervals_factory(prices), date(2000, 1, 3), _small_params(**kw))
    b = p1_0.run(prices, intervals_factory(prices), date(2000, 1, 3), _small_params(**kw))
    assert a.permutation.equals(b.permutation)
    assert a.signals.equals(b.signals)


def test_params_from_configs():
    p = p1_0.Params.from_configs()
    assert p.horizons == (90, 365)
    assert p.frequency == {90: "weekly", 365: "monthly"}
    assert p.effect == 0.05 and p.embargo_sessions == 5 and p.final_test_years == 3
    assert p.n_perm == 1000


def test_cli_parser_has_report_p1_0():
    args = build_parser().parse_args(["report-p1-0", "--snapshot", "x", "--permutations", "5"])
    assert args.command == "report-p1-0" and args.permutations == 5


def test_load_prices_verified_rejects_edited_file(tmp_path, prices_factory):
    sdir = tmp_path / "prices" / "yahoo" / "s1"
    sdir.mkdir(parents=True)
    prices_factory(n_companies=2, n_sessions=50).write_parquet(sdir / "prices.parquet")
    from stockpredictor.extraction.manifest import sha256_file

    good = sha256_file(sdir / "prices.parquet")
    (sdir / "tables_manifest.json").write_text(
        json.dumps({"prices": {"file": "prices.parquet", "sha256": good}}), encoding="utf8"
    )
    df, sha = p1_0.load_prices_verified(tmp_path, "s1")
    assert sha == good and df.height == 100
    (sdir / "tables_manifest.json").write_text(
        json.dumps({"prices": {"file": "prices.parquet", "sha256": "bad"}}), encoding="utf8"
    )
    with pytest.raises(RuntimeError):
        p1_0.load_prices_verified(tmp_path, "s1")


def test_main_without_args_still_zero():
    assert main([]) == 0
