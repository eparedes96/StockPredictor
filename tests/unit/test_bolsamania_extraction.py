"""Extractor de Bolsamanía: parser con fixtures reales, tramos, caché, parada y tablas. Sin red."""

import datetime as dt
import gzip
from pathlib import Path

import polars as pl
import pytest
import requests

from stockpredictor.extraction import bolsamania as bm
from stockpredictor.extraction import bolsamania_report as br
from stockpredictor.extraction import bolsamania_slugs as bs
from stockpredictor.extraction import manifest as mf
from stockpredictor.extraction.bolsamania_parse import (
    BolsamaniaParseError,
    parse_date,
    parse_history,
    parse_price,
)
from stockpredictor.extraction.bolsamania_tables import build_tables
from stockpredictor.extraction.yahoo import HttpResult, RunAborted
from stockpredictor.extraction.yahoo_tables import IntegrityError

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "bolsamania"
OK = (FIX / "BANKINTER.2007-07-16.2007-07-31.html").read_bytes()
EMPTY = (FIX / "empty.html").read_bytes()
NOT_FOUND = (FIX / "slug_not_found.html").read_bytes()
NO_HISTORY = (FIX / "no_history.html").read_bytes()
D = dt.date


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, form):
        self.calls.append((url, dict(form)))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def res(status, body=b"", headers=None):
    return HttpResult(status, body, headers or {})


def make_client(script, **settings):
    sleeps: list[float] = []
    clock = {"t": 0.0}

    def sleep(s):
        sleeps.append(s)
        clock["t"] += s

    transport = FakeTransport(script)
    client = bm.BolsamaniaClient(
        transport,
        bm.BolsamaniaSettings(jitter=0.0, **settings),
        sleep=sleep,
        monotonic=lambda: clock["t"],
    )
    return client, transport, sleeps


def test_parse_fixture_real_conserva_el_close_sin_ajustar():
    p = parse_history(OK.decode("utf8"))
    assert p.page_status == "ok" and p.n_rows == 12
    assert p.prices.columns == ["date", "close_raw", "high", "low", "open"]
    rows = {r["date"]: r for r in p.prices.iter_rows(named=True)}
    assert rows[D(2007, 7, 20)]["close_raw"] == 64.05
    assert rows[D(2007, 7, 23)]["close_raw"] == 13.04  # el split 5:1 se ve en el precio
    assert rows[D(2007, 7, 23)]["high"] == 13.06 and rows[D(2007, 7, 23)]["open"] == 12.89


def test_variacion_porcentual_no_se_extrae():
    # P2.1: la columna está ajustada (+1,80 % el día del split) y no debe llegar a la tabla.
    p = parse_history(OK.decode("utf8"))
    assert not any("var" in c.lower() or "pct" in c.lower() for c in p.prices.columns)


def test_parse_estados_de_pagina():
    assert parse_history(EMPTY.decode()).page_status == "empty"
    assert parse_history(NOT_FOUND.decode()).page_status == "slug_not_found"
    assert parse_history(NO_HISTORY.decode()).page_status == "no_history"


def test_parse_pagina_anomala_lanza():
    with pytest.raises(BolsamaniaParseError):
        parse_history("<html><body><h1>Acceso denegado</h1></body></html>")
    with pytest.raises(BolsamaniaParseError):
        parse_history(OK.decode().replace("<th>Precio<span></span></th>", "<th>Cierre</th>"))


def test_parse_fecha_e_importes():
    assert parse_date("16-jul-07") == D(2007, 7, 16)
    assert parse_date("04-ene-26") == D(2026, 1, 4)
    with pytest.raises(BolsamaniaParseError):
        parse_date("16-xxx-07")
    assert parse_price("66,250€") == 66.25
    assert parse_price("1.234,50€") == 1234.5
    assert parse_price("-") is None
    with pytest.raises(BolsamaniaParseError):
        parse_price("abc")


def test_plan_chunks_disjuntos_y_completos():
    chunks = bm.plan_chunks(D(2006, 11, 1), D(2007, 12, 31))
    assert chunks[0][0] == D(2006, 11, 1) and chunks[-1][1] == D(2007, 12, 31)
    for (_, a_end), (b_start, _) in zip(chunks, chunks[1:], strict=False):
        assert b_start == a_end + dt.timedelta(days=1)
    assert all((e - s).days < bm.CHUNK_DAYS for s, e in chunks)


def test_fetch_post_con_fechas_y_sin_prefijo_de_ticker():
    client, tr, _ = make_client([res(200, OK)])
    out = client.fetch("BANCO-SANTANDER", D(2007, 7, 16), D(2007, 7, 31))
    assert out.status == "ok"
    url, form = tr.calls[0]
    assert url == "https://www.bolsamania.com/accion/BANCO-SANTANDER/historico-precios"
    assert form == {"startDate": "2007-07-16", "endDate": "2007-07-31", "output": ""}


def test_limite_de_tasa_entre_peticiones():
    client, _, sleeps = make_client([res(200, OK), res(200, OK)], min_interval=2.0)
    client.fetch("A", D(2007, 1, 1), D(2007, 3, 1))
    client.fetch("A", D(2007, 3, 2), D(2007, 5, 1))
    assert sleeps == [2.0]


def test_backoff_ante_429_y_luego_ok():
    client, _, sleeps = make_client(
        [res(429, headers={"Retry-After": "100"}), res(200, OK)], min_interval=0.0
    )
    out = client.fetch("A", D(2007, 1, 1), D(2007, 3, 1))
    assert out.status == "ok" and out.attempts == 2
    assert sleeps[0] == 100.0


def test_403_no_se_reintenta():
    client, tr, _ = make_client([res(403, b"denegado")], min_interval=0.0)
    out = client.fetch("A", D(2007, 1, 1), D(2007, 3, 1))
    assert out.status == "error" and out.http_status == 403 and len(tr.calls) == 1


def test_error_de_red_se_reintenta():
    client, _, _ = make_client(
        [requests.ConnectionError("x"), res(200, OK)], min_interval=0.0, backoff_base=1.0
    )
    assert client.fetch("A", D(2007, 1, 1), D(2007, 3, 1)).status == "ok"


def job(slug="BANKINTER", start=None, end=None, purpose="gap_fill"):
    return bm.Job("es_bankinter", slug, start or D(2007, 7, 16), end or D(2007, 7, 31), purpose)


def test_descarga_guarda_raw_inmutable_manifiesto_y_cache(tmp_path):
    client, tr, _ = make_client([res(200, OK)], min_interval=0.0)
    s1 = bm.download_snapshot([job()], tmp_path, "t1", client)
    assert (s1.requested, s1.ok, s1.cached) == (1, 1, 0)
    sdir = bm.snapshot_dir(tmp_path, "t1")
    rows = mf.read_rows(sdir / mf.MANIFEST_NAME)
    assert len(rows) == 1 and rows[0]["status"] == "ok" and rows[0]["n_rows"] == "12"
    assert rows[0]["ticker"] == "BANKINTER@2007-07-16..2007-07-31"
    assert rows[0]["first_date"] == "2007-07-16" and rows[0]["last_date"] == "2007-07-31"
    f = sdir / rows[0]["file"]
    assert mf.sha256_file(f) == rows[0]["sha256"]
    assert gzip.decompress(f.read_bytes()) == OK  # byte a byte
    # Segunda ejecución: todo en caché, sin red.
    client2, tr2, _ = make_client([], min_interval=0.0)
    s2 = bm.download_snapshot([job()], tmp_path, "t1", client2)
    assert (s2.requested, s2.cached) == (0, 1) and tr2.calls == []


def test_tramo_con_posible_truncado_se_parte(tmp_path):
    # Simula 80 filas repitiendo la tabla real con fechas distintas.
    months = ["ene", "feb", "mar", "abr", "may", "jun"]
    days = [D(2007, 1, 1) + dt.timedelta(days=i) for i in range(85)]
    cells = (
        "<td>1,000€</td><td><span>0,00%</span></td><td>1,100€</td><td>0,900€</td><td>1,000€</td>"
    )
    body_rows = "".join(
        f"<tr><td>{d.day:02d}-{months[d.month - 1]}-07</td>{cells}</tr>" for d in days
    )
    head_end = OK.decode().split("<tbody>")[0]
    big = (head_end + "<tbody>" + body_rows + "</tbody></table></body></html>").encode()
    client, tr, _ = make_client([res(200, big), res(200, EMPTY), res(200, EMPTY)], min_interval=0.0)
    summary = bm.download_snapshot(
        [job(start=D(2007, 1, 1), end=D(2007, 3, 31))], tmp_path, "t2", client, row_cap=80
    )
    assert summary.split == 1 and summary.requested == 3
    forms = [c[1] for c in tr.calls]
    assert forms[0]["startDate"] == "2007-01-01" and forms[0]["endDate"] == "2007-03-31"
    assert forms[1]["endDate"] < forms[2]["startDate"]  # mitades disjuntas
    assert forms[1]["startDate"] == "2007-01-01" and forms[2]["endDate"] == "2007-03-31"
    rows = mf.read_rows(bm.snapshot_dir(tmp_path, "t2") / mf.MANIFEST_NAME)
    assert all(r["status"] == "empty" for r in rows)  # el tramo truncado no se guardó como ok


def test_slug_inexistente_corta_el_trabajo_y_se_cachea(tmp_path):
    client, tr, _ = make_client([res(200, NOT_FOUND)], min_interval=0.0)
    s = bm.download_snapshot(
        [job(start=D(2007, 1, 1), end=D(2008, 12, 31))], tmp_path, "t3", client
    )
    assert s.slug_not_found == 1 and len(tr.calls) == 1 and s.skipped_jobs
    client2, tr2, _ = make_client([], min_interval=0.0)
    s2 = bm.download_snapshot(
        [job(start=D(2007, 1, 1), end=D(2008, 12, 31))], tmp_path, "t3", client2
    )
    assert tr2.calls == [] and s2.skipped_jobs


def test_parada_ante_429_sin_saltarse_el_bloqueo(tmp_path):
    client, tr, _ = make_client([res(429)] * 2, min_interval=0.0, max_retries=1, backoff_base=1.0)
    with pytest.raises(RunAborted):
        bm.download_snapshot([job()], tmp_path, "t4", client)
    rows = mf.read_rows(bm.snapshot_dir(tmp_path, "t4") / mf.MANIFEST_NAME)
    assert rows[-1]["status"] == "rate_limited"


def test_pagina_anomala_cuenta_como_error_y_para(tmp_path):
    bad = b"<html><body><h1>Verificacion</h1></body></html>"
    client, _, _ = make_client([res(200, bad)] * 3, min_interval=0.0, max_consecutive_errors=3)
    jobs = [job(start=D(2007, 1, 1), end=D(2007, 12, 31))]
    with pytest.raises(RunAborted):
        bm.download_snapshot(jobs, tmp_path, "t5", client)
    rows = mf.read_rows(bm.snapshot_dir(tmp_path, "t5") / mf.MANIFEST_NAME)
    assert [r["status"] for r in rows] == ["error"] * 3 and "anómala" in rows[0]["error"]


def test_tablas_regeneradas_con_calidad_y_sin_volumen(tmp_path):
    client, _, _ = make_client([res(200, OK)], min_interval=0.0)
    bm.download_snapshot([job()], tmp_path, "t6", client)
    info = build_tables(tmp_path, "t6")
    assert info["prices"]["rows"] == 12
    df = pl.read_parquet(bm.snapshot_dir(tmp_path, "t6") / "prices.parquet")
    assert set(df["price_quality"]) == {"close_only"} and set(df["source"]) == {"bolsamania"}
    assert "volume" not in df.columns and df["date"].is_unique().all()
    assert df["company_id"].unique().to_list() == ["es_bankinter"]


def test_tablas_rechazan_raw_modificado(tmp_path):
    client, _, _ = make_client([res(200, OK)], min_interval=0.0)
    bm.download_snapshot([job()], tmp_path, "t7", client)
    sdir = bm.snapshot_dir(tmp_path, "t7")
    f = next((sdir / "html").iterdir())
    f.chmod(0o644)
    f.write_bytes(gzip.compress(b"otra cosa", mtime=0))
    with pytest.raises(IntegrityError):
        build_tables(tmp_path, "t7")


# ---- tabla de slugs y trabajos ----


def test_tabla_de_slugs_valida_y_sin_duplicados_de_gap_fill():
    t = bs.load_slug_table()
    assert t.height > 0
    gap = t.filter(pl.col("purpose") == "gap_fill")
    assert gap["company_id"].is_unique().all()
    named = t.filter(pl.col("bolsamania_slug") != "")
    assert named["bolsamania_slug"].str.contains(r"^[A-Z0-9-]+$").all()
    assert "POPULAR" not in named["bolsamania_slug"].to_list()  # es una acción de EE. UU.


def test_gap_fill_cubre_las_33_empresas_sin_yahoo():
    from stockpredictor.extraction import yahoo_tickers as yt

    yahoo = yt.load_ticker_table()
    missing = set(yahoo.filter(pl.col("ticker_status") == "not_found")["company_id"]) - set(
        yahoo.filter(pl.col("ticker_status") != "not_found")["company_id"]
    )
    gap = set(bs.load_slug_table().filter(pl.col("purpose") == "gap_fill")["company_id"])
    assert missing == gap


def test_select_jobs_omite_ventanas_anteriores_a_la_fuente_y_sin_slug():
    from stockpredictor.extraction import yahoo_tickers as yt

    jobs, skipped = bs.select_jobs(
        bs.load_slug_table(),
        yt.membership_windows(today=D(2026, 11, 26)),
        purposes={"gap_fill"},
        as_of=D(2026, 11, 26),
        comparison_end=D(2014, 12, 31),
    )
    why = dict(skipped)
    assert "antes del inicio de la fuente" in why["es_cepsa"]
    assert why["es_fadesa"] == "sin slug conocido"
    assert {j.company_id for j in jobs}.isdisjoint(why)
    assert all(j.start >= bm.SOURCE_FLOOR for j in jobs)


# ---- informe ----


def test_diagnostico_del_cociente_detecta_el_escalon_del_split():
    bolsa = pl.DataFrame(
        {
            "company_id": ["c"] * 4,
            "slug": ["S"] * 4,
            "date": [D(2007, 7, d) for d in (19, 20, 23, 24)],
            "close_raw": [66.05, 64.05, 13.04, 12.90],
        }
    )
    # Yahoo ya ajustado por el split 5:1 y por otros eventos: cociente constante 1,0 antes,
    # 5,0 después de 2007-07-23.
    yahoo = pl.DataFrame(
        {
            "company_id": ["c"] * 4,
            "date": [D(2007, 7, d) for d in (19, 20, 23, 24)],
            "adj_close": [13.21, 12.81, 2.608, 2.58],
            "close_split_adjusted": [13.21, 12.81, 2.608, 2.58],
        }
    )
    summary, steps = br.ratio_diagnostic(bolsa, yahoo)
    assert summary["n_common_dates"][0] == 4 and summary["n_steps"][0] == 0
    # Con cociente 5 constante en todo el periodo no hay escalón: se introduce uno en la fecha 23.
    yahoo2 = yahoo.with_columns(
        pl.when(pl.col("date") >= D(2007, 7, 23))
        .then(pl.col("adj_close") * 2)
        .otherwise(pl.col("adj_close"))
        .alias("adj_close")
    )
    summary2, steps2 = br.ratio_diagnostic(bolsa, yahoo2)
    assert steps2["date"].to_list() == [D(2007, 7, 23)]
    assert summary2["n_steps"][0] == 1
    assert abs(steps2["log_step_adj"][0]) > 0.5


def test_cobertura_antes_y_despues_suma_empresas():
    from stockpredictor.universe import membership as m

    day = D(2012, 6, 30)
    members = sorted(m.members_at(day, "ibex35"))
    yahoo = pl.DataFrame(
        {
            "company_id": members[:-1] * 2,
            "date": [D(2005, 1, 3)] * (len(members) - 1) + [D(2020, 1, 3)] * (len(members) - 1),
        }
    )
    bolsa = pl.DataFrame({"company_id": [members[-1]] * 2, "date": [D(2010, 1, 4), D(2015, 1, 4)]})
    out = br.coverage_by_year_before_after(yahoo, bolsa, last_year=2012).filter(
        pl.col("year") == 2012
    )
    assert out["n_priced_after"][0] == out["n_priced_before"][0] + 1
