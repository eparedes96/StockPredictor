"""Composición histórica del IBEX 35 sobre los CSV versionados de data/reference/."""

import datetime as dt

import polars as pl
import pytest

from stockpredictor.universe import membership as m

D = dt.date

# Fechas con un número de miembros distinto de 35, tal como sale del PDF: huecos entre una baja
# extraordinaria y su sustitución, más dos casos que el PDF no cuadra (33 y 36). Ver el PR.
EXPECTED_NOT_35 = {
    D(2001, 4, 10): 34, D(2002, 2, 9): 34, D(2002, 12, 30): 34, D(2003, 1, 2): 34,
    D(2003, 7, 24): 34, D(2003, 12, 15): 34, D(2005, 6, 28): 34, D(2005, 7, 1): 34,
    D(2006, 7, 6): 34, D(2006, 7, 25): 33, D(2006, 8, 1): 34, D(2007, 3, 9): 34,
    D(2008, 5, 12): 34, D(2009, 4, 15): 34, D(2009, 12, 7): 34, D(2011, 1, 21): 34,
    D(2011, 7, 11): 34, D(2012, 1, 2): 36, D(2013, 1, 2): 34, D(2015, 6, 24): 34,
    D(2015, 11, 27): 34, D(2016, 7, 18): 34, D(2017, 6, 7): 34, D(2018, 5, 9): 34,
    D(2020, 9, 14): 34, D(2020, 9, 21): 34, D(2022, 12, 14): 34, D(2022, 12, 19): 34,
}  # fmt: skip


@pytest.fixture(scope="module")
def events() -> pl.DataFrame:
    return m.load_events("ibex35")


@pytest.fixture(scope="module")
def code_map() -> pl.DataFrame:
    return m.load_code_map()


def at(d: dt.date, events, code_map) -> list[str]:
    return m.members_at(d, "ibex35", events=events, code_map=code_map)


def test_every_event_code_resolves_to_a_company(events, code_map):
    resolved = m.resolve_company_ids(events, code_map)
    assert resolved.height == events.height
    assert resolved["company_id"].null_count() == 0


def test_member_count_is_35_except_documented_dates(events, code_map):
    dates = sorted(set(events["effective_date"].to_list()))
    for d in dates:
        expected = EXPECTED_NOT_35.get(d, 35)
        assert len(at(d, events, code_map)) == expected, d


def test_initial_composition_has_35_members(events, code_map):
    first = at(D(1989, 12, 29), events, code_map)
    assert len(first) == 35
    assert at(D(1989, 12, 28), events, code_map) == []


def test_current_composition_has_35_members_and_known_names(events, code_map):
    now = at(D(2026, 11, 26), events, code_map)
    assert len(now) == 35
    for cid in ("es_telefonica", "es_unicaja", "es_puig", "es_redeia", "es_inditex"):
        assert cid in now


def test_add_delete_coherence_each_deletion_was_member_and_each_addition_was_not(events, code_map):
    # _apply_revisions lanza ValueError ante baja de no miembro o alta de miembro.
    resolved = m.resolve_company_ids(events, code_map)
    assert len(m._apply_revisions(resolved, None)) == 35


def test_event_dates_are_sorted_by_revision_except_known_inversion(events):
    revs = (
        events.filter(pl.col("revision_id") > 0)
        .group_by("revision_id")
        .agg(pl.col("effective_date").first())
        .sort("revision_id")
    )
    inversions = revs.filter(pl.col("effective_date") < pl.col("effective_date").shift(1))
    # El PDF numera la 109 (2018-05-09) tras la 108 (2018-07-02): único caso conocido.
    assert inversions["revision_id"].to_list() == [109]


# --- casos conocidos -------------------------------------------------------------------------


def test_bankia_entered_exited_and_reentered(events, code_map):
    assert "es_bankia" not in at(D(2011, 10, 2), events, code_map)
    assert "es_bankia" in at(D(2011, 10, 3), events, code_map)
    assert "es_bankia" not in at(D(2013, 1, 2), events, code_map)  # salida temporal
    assert "es_bankia" in at(D(2013, 12, 23), events, code_map)
    assert "es_bankia" in at(D(2021, 3, 28), events, code_map)
    assert "es_bankia" not in at(D(2021, 3, 29), events, code_map)  # absorbida por CaixaBank
    assert "es_caixabank" in at(D(2021, 3, 29), events, code_map)


def test_banco_popular_is_member_until_its_extraordinary_exit(events, code_map):
    assert "es_banco_popular" in at(D(2017, 6, 6), events, code_map)
    assert "es_banco_popular" not in at(D(2017, 6, 7), events, code_map)
    assert len(at(D(2017, 6, 7), events, code_map)) == 34  # hasta la entrada de Colonial


def test_abengoa_class_change_is_not_an_exit(events, code_map):
    # ABG -> ABG.P el 2012-10-26 (revisión extraordinaria): la empresa no sale ni entra.
    for d in (D(2012, 10, 25), D(2012, 10, 26), D(2013, 6, 30)):
        assert "es_abengoa" in at(d, events, code_map), d
    assert "es_abengoa" not in at(D(2013, 7, 1), events, code_map)
    assert "es_abengoa" in at(D(2014, 6, 23), events, code_map)
    assert "es_abengoa" not in at(D(2015, 11, 27), events, code_map)


def test_code_change_ree_to_red_is_not_an_exit(events, code_map):
    before, on = at(D(2022, 6, 10), events, code_map), at(D(2022, 6, 13), events, code_map)
    assert "es_redeia" in before and "es_redeia" in on
    assert len(before) == len(on) == 35
    # a nivel de código sí hay una baja y un alta
    day = events.filter(pl.col("effective_date") == D(2022, 6, 13))
    assert set(day["bme_code"]) == {"REE", "RED"}


def test_other_flagged_code_changes_keep_membership(events, code_map):
    for before, after, change in (
        (D(2018, 7, 1), D(2018, 7, 2), "es_gas_natural"),
        (D(2013, 9, 30), D(2013, 10, 1), "es_sacyr"),
        (D(2017, 7, 23), D(2017, 7, 24), "es_gamesa"),
        (D(2001, 10, 31), D(2001, 11, 1), "es_santander"),  # SCH -> SAN, no marcado en el PDF
    ):
        assert change in at(before, events, code_map) and change in at(after, events, code_map)


def test_reused_code_denotes_different_companies(events, code_map):
    assert "es_amadeus_gtd" in at(D(2003, 1, 1), events, code_map)
    assert "es_amadeus_it" not in at(D(2003, 1, 1), events, code_map)
    assert "es_amadeus_it" in at(D(2015, 1, 1), events, code_map)
    assert "es_amadeus_gtd" not in at(D(2015, 1, 1), events, code_map)


def test_every_code_change_row_in_pdf_is_in_changes_table(events, code_map):
    ch = pl.read_csv(m.REFERENCE_DIR / "bme_code_changes.csv", try_parse_dates=True)
    flagged = set(events.filter(pl.col("is_code_change_row"))["revision_id"].unique().to_list())
    assert flagged == set(ch.filter(pl.col("flagged_in_pdf"))["revision_id"].to_list())
    # cada cambio da de baja el código viejo y de alta el nuevo en esa revisión
    for row in ch.iter_rows(named=True):
        rev = events.filter(pl.col("revision_id") == row["revision_id"])
        assert row["old_code"] in rev.filter(pl.col("event_type") == "deletion")["bme_code"]
        assert row["new_code"] in rev.filter(pl.col("event_type") == "addition")["bme_code"]
        assert (
            code_map.filter(
                (pl.col("bme_code") == row["new_code"])
                & (pl.col("company_id") == row["company_id"])
            ).height
            >= 1
        )


def test_committed_intervals_match_replay(events, code_map):
    iv = pl.read_csv(
        m.REFERENCE_DIR / "index_membership" / "ibex35.csv",
        try_parse_dates=True,
        schema_overrides={"notes": pl.String, "announcement_date": pl.Date},
    )
    assert iv.equals(m.build_membership_intervals(events, code_map, "ibex35"))
    for d in (D(1995, 5, 5), D(2008, 8, 8), D(2020, 10, 20), D(2026, 9, 21)):
        from_iv = iv.filter(
            (pl.col("valid_from") <= d) & (pl.col("valid_to").is_null() | (pl.col("valid_to") > d))
        )["company_id"].to_list()
        assert sorted(from_iv) == at(d, events, code_map)
