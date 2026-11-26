"""Tabla de tickers de Yahoo, ventanas de pertenencia y comprobación de identidad."""

import datetime as dt

import polars as pl
import pytest

from stockpredictor.extraction import yahoo_tickers as yt

D = dt.date


@pytest.fixture(scope="module")
def table():
    return yt.load_ticker_table()


@pytest.fixture(scope="module")
def windows():
    return yt.membership_windows(today=D(2026, 11, 26))


def test_toda_empresa_del_periodo_usable_tiene_fila_en_la_tabla(table, windows):
    missing = set(windows["company_id"]) - set(table["company_id"])
    assert not missing, f"empresas sin fila en yahoo_tickers.csv: {sorted(missing)}"
    extra = set(table["company_id"]) - set(windows["company_id"])
    assert not extra, f"filas de empresas fuera del periodo usable: {sorted(extra)}"


def test_ningun_ticker_activo_es_un_ticker_reutilizado_conocido(table):
    traps = {t for t in table["known_reused_ticker"].to_list() if t}
    assert {"GAM.MC", "MVC.MC"} <= traps
    assert not traps & set(table["yahoo_ticker"].to_list())


def test_gamesa_no_usa_gam_mc(table):
    row = table.filter(pl.col("company_id") == "es_gamesa")
    assert "GAM.MC" not in row["yahoo_ticker"].to_list()
    assert row["known_reused_ticker"][0] == "GAM.MC"


def test_un_ticker_no_pertenece_a_dos_empresas(table):
    t = table.filter(pl.col("yahoo_ticker") != "")
    assert t["yahoo_ticker"].is_unique().all()


def test_no_unresolved_con_ticker(table):
    u = table.filter(pl.col("company_id").str.starts_with("es_unresolved"))
    assert (u["yahoo_ticker"] == "").all()
    assert (u["ticker_status"] == "unresolved").all()


def test_ventanas_acotadas_a_usable_from(windows):
    assert windows["window_start"].min() >= D(1993, 1, 4)
    ibe = windows.filter(pl.col("company_id") == "es_iberdrola").row(0, named=True)
    assert ibe["window_start"] == D(1993, 1, 4) and ibe["current_member"]
    assert ibe["window_end"] == D(2026, 11, 26)
    # Salió del índice antes de usable_from: no entra en el alcance.
    assert "es_ercros" not in windows["company_id"].to_list()


def test_select_targets_orden_estable_y_sin_ticker(table, windows):
    targets, no_ticker = yt.select_targets(table, windows)
    assert targets == sorted(targets, key=lambda t: (t.company_id, t.ticker))
    assert {t.company_id for t in targets}.isdisjoint(no_ticker["company_id"])
    assert "es_unresolved_cub" in no_ticker["company_id"].to_list()
    only, _ = yt.select_targets(table, windows, {"SAN.MC"})
    assert [t.ticker for t in only] == ["SAN.MC"]


@pytest.mark.parametrize(
    ("first", "last", "window", "verdict"),
    [
        (D(1993, 1, 5), D(2026, 11, 25), (D(1993, 1, 4), D(2026, 11, 26)), "ok"),
        (D(2000, 1, 3), D(2026, 11, 25), (D(2000, 1, 3), D(2026, 11, 26)), "ok"),
        (D(1993, 1, 4), D(2012, 5, 1), (D(1993, 1, 4), D(2026, 11, 26)), "partial_end"),
        (D(2000, 1, 3), D(2026, 11, 26), (D(1993, 1, 4), D(2026, 11, 26)), "partial_start"),
        (D(2005, 1, 3), D(2012, 5, 1), (D(1993, 1, 4), D(2026, 11, 26)), "partial_both"),
        (D(2018, 3, 1), D(2026, 11, 26), (D(1993, 1, 4), D(2007, 7, 2)), "no_overlap"),
        (D(1990, 1, 2), D(1992, 12, 30), (D(1993, 1, 4), D(2000, 1, 3)), "no_overlap"),
        (None, None, (D(1993, 1, 4), D(2000, 1, 3)), "no_data"),
        # Ventana anterior a la historia de Yahoo: no se puede distinguir reutilización de
        # empresa viva (Amper, Tubacex).
        (D(2000, 1, 3), D(2026, 11, 26), (D(1995, 7, 2), D(1999, 7, 1)), "before_history"),
    ],
)
def test_check_identity(first, last, window, verdict):
    got = yt.check_identity(first, last, *window, history_floor=D(2000, 1, 3))
    assert got.verdict == verdict


def test_reutilizado_se_detecta_con_ventana_historica():
    # Metrovacesa: miembro 1993-1998; el MVC.MC actual cotiza desde 2018.
    got = yt.check_identity(D(2018, 3, 1), D(2026, 11, 25), D(1993, 1, 4), D(2007, 7, 2))
    assert got.verdict == "no_overlap"
