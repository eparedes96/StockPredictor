"""Contraste automático del mapa código BME → empresa con una segunda fuente.

Fuente 1: PDF oficial de BME (códigos y fechas). Fuente 2: tablas de es.wikipedia.org/wiki/IBEX_35
(ticker, nombre, año de abandono o miembro actual, ISIN). Una fila de ``bme_code_map.csv`` queda
``reviewed = true`` solo si ambas coinciden:

- código con baja final en el PDF y ticker en la tabla histórica con ``exit_year`` igual al año de
  esa baja (o al de la baja final de la empresa, p. ej. Abengoa); o
- código miembro al final del PDF y ticker en la tabla de miembros actuales; o
- código viejo de un cambio de código marcado por BME (color naranja) cuyo código nuevo está
  verificado por una de las dos reglas anteriores.

Los códigos reutilizados por empresas distintas (AMS, CRI, ENC, UNI) no se verifican
automáticamente. Wikipedia es una fuente de la comunidad y puede errar; la regla solo acepta lo que
coincide con BME.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from pathlib import Path

import polars as pl

from stockpredictor.universe.membership import (
    _apply_revisions,
    build_membership_intervals,
    load_code_map,
    load_events,
    resolve_company_ids,
)
from stockpredictor.universe.wikipedia_ibex import (
    SOURCE_URL,
    isin_is_valid,
    parse_wikipedia_ibex,
)

BME_SOURCE = "bme_composicion_ibex35.pdf"
WIKI_SOURCE = "es.wikipedia.org/IBEX_35"
CNMV_SOURCE = "cnmv_boletin_2026_ii_cuadro4"
AUTO_MARK = " | auto: "
AUTO_SPLIT = re.compile(r"(?:\s\|\s)?auto: ")
WIKI_CURRENT_AS_OF = dt.date(2023, 10, 31)  # fecha que cita la propia tabla de miembros actuales
REUSED_CODES = {"AMS", "CRI", "ENC", "UNI"}
# Decisiones manuales, cada una con su motivo; el resto sale de la regla automática.
MANUAL_COMPANY = {
    # CNMV (Cuadro 4): Catalana de Gas "evolucionó a Gas Natural"; el PDF cambia CTG por GAS el
    # mismo día (revisión 32).
    "CTG": ("es_gas_natural", "Catalana de Gas"),
}
CONFLICTS = {
    # El PDF marca CAR→COL como cambio de código (Colonial); Wikipedia llama a CAR "Carrefour".
    "CAR": "Wikipedia llama a CAR «Carrefour»; BME marca CAR→COL (Colonial). Sin resolver.",
}


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "es_" + re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _window_events(events: pl.DataFrame, row: dict) -> pl.DataFrame:
    ev = events.filter(pl.col("bme_code") == row["bme_code"])
    if row["valid_from"] is not None:
        ev = ev.filter(pl.col("effective_date") >= row["valid_from"])
    if row["valid_to"] is not None:
        ev = ev.filter(pl.col("effective_date") <= row["valid_to"])
    return ev.sort(["effective_date", "revision_id"])


def verify_code_map(
    code_map: pl.DataFrame,
    events: pl.DataFrame,
    wiki_current: pl.DataFrame,
    wiki_historic: pl.DataFrame,
    code_changes: pl.DataFrame,
) -> pl.DataFrame:
    """Devuelve ``code_map`` con nombre, ISIN, fuentes, confianza y ``reviewed`` actualizados."""
    hist = {r["ticker"]: r for r in wiki_historic.iter_rows(named=True)}
    cur = {r["ticker"]: r for r in wiki_current.iter_rows(named=True)}
    # baja final de cada empresa (año), para casos como Abengoa (ABG → ABG.P)
    resolved = resolve_company_ids(events, code_map)
    final_exit_year: dict[str, int] = {}
    members_end = set()
    for cid, grp in resolved.sort(["effective_date", "revision_id"]).group_by(
        "company_id", maintain_order=True
    ):
        last = grp.tail(1).row(0, named=True)
        if last["event_type"] == "deletion":
            final_exit_year[cid[0]] = last["effective_date"].year
        else:
            members_end.add(cid[0])
    members_asof = _apply_revisions(resolved, WIKI_CURRENT_AS_OF)
    rows = code_map.to_dicts()
    verified: dict[tuple[str, str], bool] = {}
    for r in rows:
        code, cid = r["bme_code"], r["company_id"]
        r["_wiki"] = False
        if code in REUSED_CODES:
            verified[(code, cid)] = False
            continue
        ev = _window_events(events, r)
        if ev.height == 0:
            verified[(code, cid)] = False
            continue
        last = ev.tail(1).row(0, named=True)
        ok = False
        if code in hist:
            r["_wiki"] = True
            year = hist[code]["exit_year"]
            same = last["event_type"] == "deletion" and (
                year == last["effective_date"].year or year == final_exit_year.get(cid)
            )
            ok = same
        elif code in cur:
            r["_wiki"] = True
            ok = cid in members_asof or (
                last["event_type"] in ("addition", "initial") and cid in members_end
            )
        verified[(code, cid)] = ok
    new_to_old = {(c["new_code"], c["company_id"]): c for c in code_changes.iter_rows(named=True)}
    flagged = {
        (c["old_code"], c["company_id"]): (c["new_code"], c["company_id"])
        for c in code_changes.iter_rows(named=True)
        if c["flagged_in_pdf"]
    }
    out: list[dict] = []
    for r in rows:
        key = (r["bme_code"], r["company_id"])
        code = r["bme_code"]
        ok = verified[key]
        sources = [BME_SOURCE]
        refs = [BME_SOURCE]
        manual = AUTO_SPLIT.split(r.get("notes") or "")[0]
        notes: list[str] = []
        name = r["company_name"]
        if code in CONFLICTS:
            ok = False
            notes.append(CONFLICTS[code])
        elif key in flagged and verified.get(flagged[key], False) and not ok:
            ok = True
            sources.append(f"{BME_SOURCE}#code-change-flag")
            notes.append("Verificado por la marca de cambio de código de BME y el código nuevo.")
        if code in MANUAL_COMPANY and code not in REUSED_CODES:
            r["company_id"], name = MANUAL_COMPANY[code]
            sources.append(CNMV_SOURCE)
            refs.append("cnmv.es Boletín II/2026, Cuadro 4 (Catalana del Gas)")
            ok = True  # PDF (mismo día CTG→GAS) + CNMV
            notes.append("Identidad por CNMV Cuadro 4 y la sustitución CTG→GAS del PDF (rev. 32).")
        w = hist.get(code) or cur.get(code)
        if w is not None and code not in REUSED_CODES and code not in CONFLICTS:
            sources.append(WIKI_SOURCE)
            refs.append(f"{SOURCE_URL}#ticker={code}")
            name = w["company_name"].rstrip(".")
            name = name[:1].upper() + name[1:]
            if str(r["company_id"]).startswith("es_unresolved_"):
                r["company_id"] = slugify(name)
                manual = ""  # la nota de «sin identificar» ya no aplica
        isin = r.get("isin") or ""
        if code in cur and ok and isin_is_valid(cur[code]["isin"]):
            isin = cur[code]["isin"]
            notes.append("ISIN de Wikipedia (dígito de control válido; una sola fuente).")
        if r["company_id"].startswith("es_unresolved_"):
            confidence, ok = "low", False
        elif ok:
            confidence = "high"
        elif len(sources) > 1:
            confidence = "medium"
            if w is not None and code in hist:
                notes.append(
                    f"Wikipedia da abandono en {hist[code]['exit_year']}; el PDF no coincide."
                )
        else:
            confidence = "medium" if r["confidence"] == "high" else r["confidence"]
        change = new_to_old.get((code, r["company_id"]))
        is_change = change is not None and r["valid_from"] == change["effective_date"]
        out.append(
            {
                **{k: v for k, v in r.items() if not k.startswith("_")},
                "company_name": name or "",
                "isin": isin,
                "source": ";".join(sources) if len(sources) > 1 or name else "unresolved",
                "source_ref": ";".join(refs),
                "source_date": "2026-11-26",
                "confidence": confidence,
                "reviewed": ok,
                "is_code_change": "true" if is_change else "",
                "previous_bme_code": change["old_code"] if change and is_change else "",
                "notes": (manual + AUTO_MARK if manual else "auto: ") + " ".join(notes)
                if notes
                else manual,
            }
        )
    return pl.DataFrame(out, schema_overrides={"valid_from": pl.Date, "valid_to": pl.Date})


def mark_event_review(
    events: pl.DataFrame, verified_map: pl.DataFrame, wiki_current: pl.DataFrame
) -> pl.DataFrame:
    """``reviewed`` en eventos: la baja final (o el alta vigente) de un código verificado.

    Los eventos ``initial`` nunca quedan ``reviewed``: la composición anterior al PDF no se puede
    contrastar con una fuente gratuita. Los 4 miembros que el PDF no menciona suben de confianza
    si Wikipedia los da como miembros desde 1992 (el CNMV también los cita en su lista inicial).
    """
    resolved = resolve_company_ids(events, verified_map.select(load_code_map().columns))
    ok_keys = {
        (r["bme_code"], r["company_id"])
        for r in verified_map.filter(pl.col("reviewed")).iter_rows(named=True)
    }
    flags = []
    last_by_code: dict[str, tuple] = {}
    for r in resolved.sort(["effective_date", "revision_id"]).iter_rows(named=True):
        last_by_code[r["bme_code"]] = (r["revision_id"], r["event_type"], r["company_id"])
    for r in resolved.iter_rows(named=True):
        is_last = last_by_code[r["bme_code"]][:2] == (r["revision_id"], r["event_type"])
        flags.append(
            is_last and r["event_type"] != "initial" and (r["bme_code"], r["company_id"]) in ok_keys
        )
    since = {r["ticker"]: r["since_year"] for r in wiki_current.iter_rows(named=True)}
    extra = (pl.col("source") == "inference") & pl.col("bme_code").is_in(
        [c for c, y in since.items() if y <= 1992]
    )
    return events.with_columns(
        pl.Series("reviewed", flags),
        pl.when(extra).then(pl.lit("medium")).otherwise(pl.col("confidence")).alias("confidence"),
        pl.when(extra)
        .then(pl.lit(f"inference;{WIKI_SOURCE};{CNMV_SOURCE}"))
        .otherwise(pl.col("source"))
        .alias("source"),
        pl.when(extra)
        .then(
            pl.lit(
                "No aparece en el PDF. Wikipedia lo da como miembro desde 1992 y el CNMV lo cita "
                "en la lista inicial; la fecha 1989-12-29 es la base del índice, sin contrastar."
            )
        )
        .otherwise(pl.col("notes"))
        .alias("notes"),
    )


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Contrasta bme_code_map.csv con Wikipedia.")
    ap.add_argument("wiki_html", type=Path)
    ap.add_argument("--reference-dir", type=Path, default=Path("data/reference"))
    args = ap.parse_args()
    ref = args.reference_dir
    cur, hist = parse_wikipedia_ibex(args.wiki_html.read_text(encoding="utf8"))
    events = load_events("ibex35", ref)
    code_map = load_code_map(ref)
    changes = pl.read_csv(ref / "bme_code_changes.csv", try_parse_dates=True)
    new_map = verify_code_map(code_map, events, cur, hist, changes)
    new_map.write_csv(ref / "bme_code_map.csv")
    new_events = mark_event_review(events, new_map, cur)
    new_events.write_csv(ref / "index_membership" / "ibex35_events.csv")
    intervals = build_membership_intervals(new_events, new_map, "ibex35")
    intervals.write_csv(ref / "index_membership" / "ibex35.csv")
    unresolved = new_map.filter(pl.col("company_id").str.starts_with("es_unresolved_")).height
    print(
        f"verificadas: {new_map['reviewed'].sum()} de {new_map.height}; sin resolver: {unresolved}"
    )


if __name__ == "__main__":
    main()
