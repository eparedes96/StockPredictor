"""Parser del PDF de BME: palabras sintéticas (CI) y regeneración con el PDF real (local)."""

import datetime as dt
import os
from pathlib import Path

import polars as pl
import pytest

from stockpredictor.universe import bme_pdf as B

REPO = Path(__file__).resolve().parents[2]
REAL_PDF = Path(
    os.environ.get("STOCKPREDICTOR_BME_PDF", REPO / "data/raw/sources/bme_composicion_ibex35.pdf")
)


def w(text: str, x0: float, top: float) -> dict:
    return {"text": text, "x0": x0, "x1": x0 + 8 * len(text), "top": top, "bottom": top + 10}


def rect(color, top: float) -> dict:
    return {"x0": 70, "x1": 125, "top": top - 1, "bottom": top + 11, "non_stroking_color": color}


def synthetic_page():
    words = [
        w("Inclusiones", 200, 10),
        w("Exclusiones", 420, 10),
        # revisión normal con dos altas y dos bajas
        w("1", 40, 50), w("02/01/1991", 76, 50), w("AAA", 170, 50), w("BBB", 230, 50),
        w("CCC", 380, 50), w("DDD", 440, 50),
        # revisión vacía (guion en ambas columnas)
        w("2", 40, 70), w("01/07/1991", 76, 70), w("—", 250, 70), w("-", 480, 70),
        # cambio de código (naranja) con una sola baja y una alta
        w("3", 40, 90), w("02/01/1992", 76, 90), w("NEW", 170, 90), w("OLD", 380, 90),
        # extraordinaria (lila), solo baja
        w("4", 40, 110), w("10/03/1992", 76, 110), w("GONE", 380, 110),
    ]  # fmt: skip
    rects = [
        rect(B.COLOR_CODE_CHANGE, 90),
        rect(B.COLOR_EXTRAORDINARY, 110),
        rect((0.0, 0.0, 0.0, 0.15), 50),  # gris de cabecera: se ignora
        {"x0": 0, "x1": 600, "top": 0, "bottom": 5, "non_stroking_color": 0.5},  # gris escalar
    ]
    return words, rects


def test_parse_page_splits_columns_and_flags():
    revs = B.parse_page(*synthetic_page())
    assert [r.revision_id for r in revs] == [1, 2, 3, 4]
    r1, r2, r3, r4 = revs
    assert r1.additions == ("AAA", "BBB") and r1.deletions == ("CCC", "DDD")
    assert r1.effective_date == dt.date(1991, 1, 2)
    assert r2.additions == () and r2.deletions == ()
    assert r3.is_code_change_row and not r3.is_extraordinary
    assert (r3.additions, r3.deletions) == (("NEW",), ("OLD",))
    assert r4.is_extraordinary and not r4.is_code_change_row
    assert r4.additions == () and r4.deletions == ("GONE",)
    assert not r1.is_extraordinary and not r1.is_code_change_row


def test_parse_page_without_table_is_empty():
    assert B.parse_page([w("hola", 10, 10)], []) == []


def test_infer_initial_codes_from_deletion_without_addition():
    revs = [
        B.Revision(1, dt.date(1991, 1, 2), ("A",), ("X",), False, False, 1),
        B.Revision(2, dt.date(1991, 7, 1), ("X",), ("A",), False, False, 1),
        B.Revision(3, dt.date(1992, 1, 2), (), ("X", "Y"), False, False, 1),
    ]
    events = B.revisions_to_events(revs)
    assert B.infer_initial_codes(events) == ["X", "Y"]  # X sale en la rev. 1, Y en la 3


def test_events_csv_frame_orders_and_marks_sources():
    revs = [B.Revision(1, dt.date(1991, 1, 2), ("A",), ("X",), False, False, 1)]
    df = B.events_csv_frame(revs, {"Z": "nota"})
    assert df.columns == B.EVENTS_COLUMNS
    assert df["event_type"].to_list() == ["initial", "initial", "deletion", "addition"]
    assert df.filter(pl.col("bme_code") == "Z")["source"].item() == "inference"
    assert df.filter(pl.col("bme_code") == "A")["source_ref"].item().endswith("#rev=1")


@pytest.mark.skipif(
    not REAL_PDF.exists(), reason="PDF de BME no disponible (data/raw o STOCKPREDICTOR_BME_PDF)"
)
def test_real_pdf_regenerates_committed_events():
    pytest.importorskip("pdfplumber")
    revs = B.parse_pdf(REAL_PDF)
    assert len(revs) == 137
    assert revs[-1].effective_date == dt.date(2026, 9, 21)
    fresh = B.events_csv_frame(revs, B.EXTRA_INITIAL)
    committed = pl.read_csv(
        REPO / "data/reference/index_membership/ibex35_events.csv",
        try_parse_dates=True,
        schema_overrides={"notes": pl.String},
    )
    # El CSV versionado lleva además el contraste con otras fuentes (reviewed, confianza, notas).
    keys = ["revision_id", "effective_date", "event_type", "bme_code", "is_extraordinary",
            "is_code_change_row"]  # fmt: skip
    assert fresh.select(keys).equals(committed.select(keys))
