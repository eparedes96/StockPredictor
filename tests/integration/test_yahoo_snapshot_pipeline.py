"""Instantánea completa con respuestas grabadas: descarga, tablas, cobertura, regresión."""

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest

from stockpredictor import cli
from stockpredictor.extraction import manifest as mf
from stockpredictor.extraction import yahoo as y
from stockpredictor.extraction import yahoo_report as rep
from stockpredictor.extraction import yahoo_tables as tb

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
RAW_OK = (FIX / "SAN.MC.json").read_bytes()
NOT_FOUND = (FIX / "BKIA.MC.json").read_bytes()
D = dt.date


def shifted(body: bytes, days: int) -> bytes:
    """Mueve todas las fechas ``days`` días (la grabación es de 2020; el SAN de prueba, de 2000)."""
    d = json.loads(body)
    r = d["chart"]["result"][0]
    r["timestamp"] = [t + days * 86400 for t in r["timestamp"]]
    return json.dumps(d).encode()


OK = shifted(RAW_OK, -7305)  # SAN.MC de prueba: 2000-11-10..2000-11-27
MVC = RAW_OK  # el MVC.MC "actual" de 2020


def run(raw, snap, bodies):
    script = [y.HttpResult(200 if b is not OK_404 else 404, b) for b in bodies]
    it = iter(script)
    client = y.YahooClient(lambda url: next(it), y.YahooSettings(jitter=0), sleep=lambda s: None)
    targets = [
        y.Target("SAN.MC", "es_santander"),
        y.Target("BKIA.MC", "es_bankia"),
        y.Target("MVC.MC", "es_metrovacesa"),
    ]
    return y.download_snapshot(targets, raw, snap, client, now=lambda: 1_700_000_000)


OK_404 = NOT_FOUND


def revised(body: bytes, factor: float = 1.0, drop_last: bool = False) -> bytes:
    d = json.loads(body)
    r = d["chart"]["result"][0]
    adj = r["indicators"]["adjclose"][0]["adjclose"]
    r["indicators"]["adjclose"][0]["adjclose"] = [v * factor for v in adj]
    if drop_last:
        r["timestamp"].pop()
        for k in r["indicators"]["quote"][0]:
            r["indicators"]["quote"][0][k].pop()
        r["indicators"]["adjclose"][0]["adjclose"].pop()
    return json.dumps(d).encode()


def bad_return(body: bytes) -> bytes:
    d = json.loads(body)
    adj = d["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"]
    adj[5] *= 1.01  # un retorno revisado en una sola sesión
    return json.dumps(d).encode()


@pytest.fixture
def raw(tmp_path):
    # MVC.MC devuelve datos de 2020 (ticker reutilizado): fuera de la ventana de Metrovacesa.
    run(tmp_path, "a", [OK, NOT_FOUND, MVC])
    # b: dividendo posterior que reescala todo el nivel pasado (los retornos no cambian) y una
    # sesión menos; c: un retorno cambia de verdad.
    run(tmp_path, "b", [revised(OK, 0.97, drop_last=True), NOT_FOUND, MVC])
    run(tmp_path, "c", [bad_return(OK), NOT_FOUND, MVC])
    return tmp_path


def test_tablas_parquet_y_sha256(raw):
    info = tb.build_tables(raw, "a")
    sdir = y.snapshot_dir(raw, "a")
    prices = pl.read_parquet(sdir / tb.PRICES_FILE)
    events = pl.read_parquet(sdir / tb.EVENTS_FILE)
    assert prices.height == 24 and prices["ticker"].n_unique() == 2
    assert prices["date"].min() == D(2000, 11, 10)
    assert set(prices.columns) >= {"company_id", "date", "adj_close", "close_split_adjusted"}
    assert events.filter(pl.col("event_type") == "split").height == 2
    assert info["prices"]["rows"] == 24
    assert (sdir / tb.TABLES_MANIFEST).exists()
    # Un raw tocado a mano se rechaza.
    row = mf.latest_by_ticker(sdir / mf.MANIFEST_NAME)["SAN.MC"]
    p = sdir / row["file"]
    p.chmod(0o644)
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(tb.IntegrityError):
        tb.build_tables(raw, "a")


def table_and_windows():
    table = pl.DataFrame(
        {
            "company_id": ["es_santander", "es_bankia", "es_metrovacesa", "es_cub"],
            "yahoo_ticker": ["SAN.MC", "BKIA.MC", "MVC.MC", ""],
            "ticker_status": ["candidate", "candidate", "candidate", "unresolved"],
        }
    )
    windows = pl.DataFrame(
        {
            "company_id": ["es_santander", "es_bankia", "es_metrovacesa", "es_cub"],
            "window_start": [D(2000, 11, 10)] * 2 + [D(1993, 1, 4), D(1993, 1, 4)],
            "window_end": [D(2000, 11, 25), D(2021, 3, 29), D(2007, 7, 2), D(1997, 6, 2)],
            "current_member": [False] * 4,
        }
    )
    return table, windows


def test_cobertura_detecta_404_ticker_reutilizado_y_sin_ticker(raw):
    tb.build_tables(raw, "a")
    table, windows = table_and_windows()
    cov, no_ticker, s = rep.coverage(raw, "a", table, windows, as_of=D(2026, 11, 26))
    by = {r["ticker"]: r for r in cov.iter_rows(named=True)}
    assert by["SAN.MC"]["identity"] == "ok"
    assert by["BKIA.MC"]["identity"] == "not_found"
    assert by["MVC.MC"]["identity"] == "no_overlap"
    assert no_ticker["company_id"].to_list() == ["es_cub"]
    assert s["companies_in_scope"] == 4
    assert s["companies_with_prices"] == 1
    assert s["companies_404"] == 1
    assert s["tickers_no_overlap"] == 1
    md = rep.render_markdown("a", cov, no_ticker, s)
    assert "sesgo de supervivencia" in md and "MVC.MC" in md


def test_regresion_de_retornos_ignora_reescalado_y_detecta_cambios(raw):
    for s in "abc":
        tb.build_tables(raw, s)
    per, s = rep.compare_snapshots(raw, "a", "b")
    assert s["tickers_in_both"] == 2
    assert s["returns_changed"] == 0  # reescalar el nivel no cambia retornos
    assert s["tickers_with_removed_dates"] == 1  # b perdió una sesión
    per, s = rep.compare_snapshots(raw, "a", "c")
    san = per.filter(pl.col("ticker") == "SAN.MC").row(0, named=True)
    assert s["tickers_with_changed_returns"] >= 1
    assert san["n_changed"] == 2  # el retorno de la sesión modificada y el siguiente
    assert san["max_abs_diff"] == pytest.approx(0.00995, abs=1e-4)


def test_cli_extract_dry_run_y_report(raw, capsys):
    assert cli.main(["extract-prices-yahoo", "--dry-run", "--tickers", "SAN.MC"]) == 0
    assert "SAN.MC\tes_santander" in capsys.readouterr().out
    # El informe de la CLI usa la tabla y la composición reales: ningún ticker real descargado
    # aquí cuenta como ok, pero el comando debe completarse y escribir sus archivos.
    assert cli.main(["report-prices-yahoo", "--snapshot", "a", "--raw-dir", str(raw)]) == 0
    sdir = y.snapshot_dir(raw, "a")
    assert (sdir / "coverage.csv").exists() and (sdir / "coverage_report.md").exists()
