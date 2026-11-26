"""Contraste con Wikipedia y reglas de ``reviewed`` sobre los CSV versionados."""

import datetime as dt

import polars as pl

from stockpredictor.universe import ibex_crosscheck as X
from stockpredictor.universe import membership as m
from stockpredictor.universe import wikipedia_ibex as W

REF = m.REFERENCE_DIR

HTML = """
<table><tr><th>Ticker</th><th>Empresa</th><th>Sede</th><th>Año</th><th>Sector</th><th>ISIN</th></tr>
<tr><td>TEF</td><td><a>Telefónica</a></td><td>Madrid</td><td>1992</td><td>x</td><td>ES0178430E18</td></tr>
</table>
<table><tr><th>Ticker</th><th>Empresa</th><th>Sede</th><th>Abandono</th><th>Sector</th></tr>
<tr><td>ABC</td><td>Alfa <b>Beta</b></td><td>Madrid</td><td>2001</td><td>x</td></tr>
<tr><td>XYZ</td><td>Sin año</td><td>Madrid</td><td>n/d</td><td>x</td></tr></table>
"""


def test_parse_wikipedia_tables():
    cur, hist = W.parse_wikipedia_ibex(HTML)
    assert cur.to_dicts() == [
        {"ticker": "TEF", "company_name": "Telefónica", "since_year": 1992, "isin": "ES0178430E18"}
    ]
    assert hist.to_dicts() == [{"ticker": "ABC", "company_name": "Alfa Beta", "exit_year": 2001}]


def test_isin_checksum():
    assert W.isin_is_valid("ES0178430E18")
    assert not W.isin_is_valid("ES0178430E19")
    assert not W.isin_is_valid("ES01784")


def test_verify_code_map_requires_matching_exit_year():
    events = pl.DataFrame(
        {
            "revision_id": [1, 2],
            "effective_date": [dt.date(1991, 1, 2), dt.date(2001, 7, 1)],
            "event_type": ["addition", "deletion"],
            "bme_code": ["ABC", "ABC"],
            "index_id": ["ibex35"] * 2,
            "source": ["bme"] * 2,
            "source_ref": [""] * 2,
            "source_date": [dt.date(2026, 9, 21)] * 2,
            "confidence": ["high"] * 2,
            "notes": [""] * 2,
        }
    )
    cmap = pl.DataFrame(
        {
            "bme_code": ["ABC"],
            "company_id": ["es_abc"],
            "valid_from": [None],
            "valid_to": [None],
            "company_name": [""],
            "isin": [""],
            "confidence": ["low"],
            "notes": [""],
        },
        schema_overrides={"valid_from": pl.Date, "valid_to": pl.Date},
    )
    cur, hist = W.parse_wikipedia_ibex(HTML)
    changes = pl.DataFrame(
        schema={"company_id": pl.String, "old_code": pl.String, "new_code": pl.String,
                "effective_date": pl.String, "flagged_in_pdf": pl.Boolean}
    )  # fmt: skip
    ok = X.verify_code_map(cmap, events, cur, hist, changes)
    assert ok["reviewed"].to_list() == [True] and ok["company_name"].to_list() == ["Alfa Beta"]
    wrong = events.with_columns(
        pl.Series("effective_date", [dt.date(1991, 1, 2), dt.date(2002, 7, 1)])
    )
    assert X.verify_code_map(cmap, wrong, cur, hist, changes)["reviewed"].to_list() == [False]


# --- invariantes de los CSV versionados -----------------------------------------------------


def test_reviewed_rows_cite_two_sources_and_are_high_confidence():
    cm = m.load_code_map()
    rev = cm.filter(pl.col("reviewed"))
    assert rev.height >= 90
    assert (rev["confidence"] == "high").all()
    assert (rev["source"].str.split(";").list.len() >= 2).all()
    assert (rev["company_name"].str.len_chars() > 0).all()


def test_unresolved_rows_are_low_confidence_and_not_reviewed():
    cm = m.load_code_map()
    un = cm.filter(pl.col("company_id").str.starts_with("es_unresolved_"))
    assert un.height == 7 and not un["reviewed"].any() and (un["confidence"] == "low").all()


def test_isins_are_valid_and_only_on_verified_rows():
    cm = m.load_code_map().filter(pl.col("isin").fill_null("").str.len_chars() > 0)
    assert cm.height >= 25
    assert all(W.isin_is_valid(i) for i in cm["isin"])
    assert cm["reviewed"].all()


def test_initial_events_are_never_reviewed():
    ev = m.load_events("ibex35")
    assert not ev.filter(pl.col("event_type") == "initial")["reviewed"].any()


def test_every_file_has_source_per_row():
    for path in (REF / "bme_code_map.csv", REF / "bme_code_changes.csv",
                 REF / "index_membership" / "ibex35_events.csv",
                 REF / "index_membership" / "ibex35_initial_cnmv.csv"):  # fmt: skip
        df = pl.read_csv(path)
        assert df["source"].null_count() == 0, path
        assert df["source_ref"].null_count() == 0 or path.name == "bme_code_map.csv", path
    manifest = pl.read_csv(REF / "sources_manifest.csv")
    ids = set(manifest["source_id"])
    cm = pl.read_csv(REF / "bme_code_map.csv")
    used = {s for cell in cm["source"] for s in cell.split(";") if "#" not in s}
    assert used <= ids | {"unresolved"}


def test_cnmv_initial_list_overlaps_pdf_base_composition_partially():
    # Hallazgo documentado: de las 26 empresas del Cuadro 4 con código identificado, 21 son
    # miembros según el PDF en 1989-12-29. Las otras 5 entran entre 1991 y 1995 (no es una foto).
    cnmv = pl.read_csv(REF / "index_membership" / "ibex35_initial_cnmv.csv")
    ids = set(cnmv["company_id"].drop_nulls().to_list())
    base = set(m.members_at(dt.date(1989, 12, 29)))
    assert cnmv.height == 35 and len(ids) == 26 and len(ids & base) == 21
