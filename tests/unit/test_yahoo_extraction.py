"""Extractor de Yahoo: parseo, límite de tasa, backoff, caché, manifiesto y parada. Sin red."""

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest
import requests

from stockpredictor.extraction import manifest as mf
from stockpredictor.extraction import yahoo as y
from stockpredictor.extraction.yahoo_parse import ChartParseError, parse_chart

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
OK = (FIX / "SAN.MC.json").read_bytes()
NOT_FOUND = (FIX / "BKIA.MC.json").read_bytes()


class FakeTransport:
    """Responde en orden con una lista de HttpResult o excepciones y guarda las URL pedidas."""

    def __init__(self, script):
        self.script = list(script)
        self.urls: list[str] = []

    def __call__(self, url):
        self.urls.append(url)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def res(status, body=b"", headers=None):
    return y.HttpResult(status, body, headers or {})


def make_client(script, **settings):
    sleeps: list[float] = []
    clock = {"t": 0.0}

    def sleep(s):
        sleeps.append(s)
        clock["t"] += s

    transport = FakeTransport(script)
    client = y.YahooClient(
        transport,
        y.YahooSettings(jitter=0.0, **settings),
        sleep=sleep,
        monotonic=lambda: clock["t"],
    )
    return client, transport, sleeps


def test_parse_chart_fixture_real():
    p = parse_chart(OK)
    assert p.prices.schema["date"] == pl.Date
    assert p.prices.height == 12
    assert p.meta["currency"] == "EUR"
    assert p.meta["longName"] == "Banco Santander, S.A."
    # La fecha es la local de Madrid (la marca de tiempo es 09:00 CET), no la UTC anterior.
    assert p.prices["date"][0] == dt.date(2020, 11, 10)
    assert p.prices["adj_close"].null_count() == 0
    split = p.events.filter(pl.col("event_type") == "split")
    assert split.height == 1
    assert split["split_ratio"][0] == "24:23"
    assert split["date"][0] == dt.date(2020, 11, 16)


def test_parse_chart_not_found_y_anomalias():
    p = parse_chart(NOT_FOUND)
    assert p.error_code == "Not Found"
    assert p.prices.height == 0
    with pytest.raises(ChartParseError):
        parse_chart(b"<html>Too Many Requests</html>")
    with pytest.raises(ChartParseError):
        parse_chart(json.dumps({"chart": {"result": [], "error": None}}).encode())


def test_parse_chart_longitudes_inconsistentes():
    d = json.loads(OK)
    d["chart"]["result"][0]["indicators"]["quote"][0]["close"].pop()
    with pytest.raises(ChartParseError):
        parse_chart(json.dumps(d).encode())


def test_parse_chart_sin_adjclose_ni_eventos():
    d = json.loads(OK)
    del d["chart"]["result"][0]["indicators"]["adjclose"]
    del d["chart"]["result"][0]["events"]
    p = parse_chart(json.dumps(d).encode())
    assert p.prices["adj_close"].null_count() == p.prices.height
    assert p.events.height == 0


def test_chart_url_usa_split_en_singular_y_codifica_el_ticker():
    url = y.chart_url("^IBEX", 1_700_000_000)
    assert "%5EIBEX" in url
    assert "events=div%2Csplit" in url
    assert "includeAdjustedClose=true" in url


def test_limite_de_tasa_espacia_peticiones():
    client, _, sleeps = make_client([res(200, OK)] * 3, min_interval=2.0)
    for _ in range(3):
        client.fetch("u")
    assert len(sleeps) == 2
    assert all(abs(s - 2.0) < 1e-9 for s in sleeps)


def test_backoff_ante_429_y_recuperacion():
    client, transport, sleeps = make_client(
        [res(429), res(429, headers={"Retry-After": "100"}), res(200, OK)],
        min_interval=2.0,
        backoff_base=30.0,
    )
    out = client.fetch("u")
    assert out.status == "ok" and out.attempts == 3
    backoffs = [s for s in sleeps if s >= 30]
    assert backoffs == [30.0, 100.0]  # exponencial, y Retry-After manda si es mayor
    assert len(transport.urls) == 3


def test_429_agotado_es_rate_limited_sin_bucle_infinito():
    client, transport, _ = make_client([res(429)] * 3, max_retries=2)
    out = client.fetch("u")
    assert out.status == "rate_limited" and out.attempts == 3
    assert len(transport.urls) == 3


def test_404_no_se_reintenta_y_4xx_es_error():
    client, transport, _ = make_client([res(404, NOT_FOUND), res(403, b"no")])
    assert client.fetch("u").status == "not_found"
    assert client.fetch("u").status == "error"
    assert len(transport.urls) == 2


def test_error_de_red_se_reintenta():
    client, _, _ = make_client([requests.ConnectionError("x"), res(200, OK)])
    assert client.fetch("u").status == "ok"


def targets():
    return [y.Target("SAN.MC", "es_santander"), y.Target("BKIA.MC", "es_bankia")]


def test_descarga_escribe_raw_manifiesto_y_cachea(tmp_path):
    client, transport, _ = make_client([res(200, OK), res(404, NOT_FOUND)])
    s = y.download_snapshot(targets(), tmp_path, "t1", client, now=lambda: 1_700_000_000)
    assert (s.ok, s.not_found, s.failed, s.cached) == (1, 1, 0, 0)
    sdir = y.snapshot_dir(tmp_path, "t1")
    rows = mf.read_rows(sdir / mf.MANIFEST_NAME)
    assert [r["status"] for r in rows] == ["ok", "not_found"]
    ok = rows[0]
    assert ok["provider"] == "yahoo_chart_v8"
    assert ok["sha256"] == mf.sha256_bytes(OK) == mf.sha256_file(sdir / ok["file"])
    assert ok["n_rows"] == "12" and ok["first_date"] == "2020-11-10"
    assert ok["currency"] == "EUR" and ok["long_name"] == "Banco Santander, S.A."
    assert "period2=1700000000" in ok["url"]
    assert (sdir / ok["file"]).read_bytes() == OK  # byte a byte
    # Segunda ejecución: todo en caché, ninguna petición.
    client2, transport2, _ = make_client([])
    s2 = y.download_snapshot(targets(), tmp_path, "t1", client2)
    assert (s2.cached, s2.requested) == (2, 0)
    assert transport2.urls == []
    assert len(mf.read_rows(sdir / mf.MANIFEST_NAME)) == 2


def test_raw_es_inmutable(tmp_path):
    p = tmp_path / "a" / "x.json"
    mf.write_immutable(p, b"1")
    with pytest.raises(FileExistsError):
        mf.write_immutable(p, b"2")
    assert p.read_bytes() == b"1"
    assert not list(p.parent.glob("*.part"))


def test_429_aborta_y_la_instantanea_es_reanudable(tmp_path):
    ts = targets()
    client, _, _ = make_client([res(200, OK)] + [res(429)] * 3, max_retries=2)
    with pytest.raises(y.RunAborted) as exc:
        y.download_snapshot(ts + [y.Target("X.MC", "es_x")], tmp_path, "t2", client)
    assert exc.value.summary.ok == 1
    rows = mf.read_rows(y.snapshot_dir(tmp_path, "t2") / mf.MANIFEST_NAME)
    assert [r["status"] for r in rows] == ["ok", "rate_limited"]
    # Reanudar: SAN.MC en caché; el fallido se reintenta, el resto sigue.
    client2, transport2, _ = make_client([res(404, NOT_FOUND), res(404, NOT_FOUND)])
    s = y.download_snapshot(ts + [y.Target("X.MC", "es_x")], tmp_path, "t2", client2)
    assert (s.cached, s.not_found) == (1, 2)
    assert len(transport2.urls) == 2
    latest = mf.latest_by_ticker(y.snapshot_dir(tmp_path, "t2") / mf.MANIFEST_NAME)
    assert latest["BKIA.MC"]["status"] == "not_found"


def test_respuesta_anomala_con_200_es_error_y_tres_seguidas_paran(tmp_path):
    bad = res(200, b"<html>captcha</html>")
    client, _, _ = make_client([bad, bad, bad], max_consecutive_errors=3)
    ts = [y.Target(f"T{i}.MC", f"es_t{i}") for i in range(5)]
    with pytest.raises(y.RunAborted):
        y.download_snapshot(ts, tmp_path, "t3", client)
    rows = mf.read_rows(y.snapshot_dir(tmp_path, "t3") / mf.MANIFEST_NAME)
    assert len(rows) == 3 and {r["status"] for r in rows} == {"error"}
    assert "anómala" in rows[0]["error"]
