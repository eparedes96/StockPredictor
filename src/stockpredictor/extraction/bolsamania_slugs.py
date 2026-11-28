"""Tabla de slugs de Bolsamanía por ``company_id`` y construcción de los trabajos de descarga.

El slug es el nombre en la URL (``/accion/<slug>/historico-precios``) y no sigue al ticker
(``BANCO-SANTANDER``; ``POPULAR`` es una acción de EE. UU. en dólares; ``TELECINCO`` no existe y
la empresa es ``MEDIASET-ESPANA``). La tabla ``data/reference/bolsamania_slugs.csv`` es manual y
versionada. ``purpose = gap_fill`` son las empresas que Yahoo no tiene (404); ``comparison`` son
empresas con las dos series, solo para el diagnóstico del cociente.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from stockpredictor.extraction.bolsamania import SOURCE_FLOOR, Job
from stockpredictor.universe import membership as m

SLUGS_CSV = m.REFERENCE_DIR / "bolsamania_slugs.csv"
SLUG_COLUMNS = [
    "company_id",
    "bolsamania_slug",
    "purpose",
    "slug_status",
    "source",
    "source_date",
    "confidence",
    "reviewed",
    "notes",
]
SLUG_STATUSES = {"candidate", "verified", "not_found", "none"}
PURPOSES = {"gap_fill", "comparison"}
SOURCE_START = dt.date(2006, 11, 30)  # primera fecha con datos observada en la fuente
LEAD_IN_DAYS = 400  # historia previa a la entrada en el índice (ventanas de features de un año)


def load_slug_table(path: Path = SLUGS_CSV) -> pl.DataFrame:
    df = pl.read_csv(path, infer_schema_length=0).with_columns(pl.col(pl.String).fill_null(""))
    missing = [c for c in SLUG_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: faltan columnas {missing}")
    for col, valid in (("slug_status", SLUG_STATUSES), ("purpose", PURPOSES)):
        bad = set(df[col].unique().to_list()) - valid
        if bad:
            raise ValueError(f"{path}: {col} no válido {sorted(bad)}")
    return df


def select_jobs(
    table: pl.DataFrame,
    windows: pl.DataFrame,
    *,
    purposes: set[str],
    as_of: dt.date,
    comparison_end: dt.date,
    only: set[str] | None = None,
) -> tuple[list[Job], list[tuple[str, str]]]:
    """Trabajos a descargar y empresas omitidas con el motivo (sin slug o ventana fuera de fuente).

    Ventana: desde 400 días antes de la entrada en el índice (historia para las features; nunca
    antes de ``SOURCE_FLOOR``) hasta el fin de la pertenencia (``as_of`` si sigue vigente). Las
    empresas que salieron antes de ``SOURCE_START`` no tienen nada que pedir. ``comparison`` acaba
    en ``comparison_end``.
    """
    win = {r["company_id"]: r for r in windows.iter_rows(named=True)}
    jobs: list[Job] = []
    skipped: list[tuple[str, str]] = []
    rows = table.filter(pl.col("purpose").is_in(sorted(purposes))).sort(
        ["purpose", "company_id", "bolsamania_slug"]
    )
    for r in rows.iter_rows(named=True):
        cid, slug, purpose = r["company_id"], r["bolsamania_slug"], r["purpose"]
        if only and cid not in only and slug not in only:
            continue
        w = win.get(cid)
        if w is None:
            skipped.append((cid, "fuera del periodo usable"))
            continue
        end = as_of if w["current_member"] else w["window_end"]
        if purpose == "comparison":
            end = min(end, comparison_end)
        if end < SOURCE_START:
            skipped.append((cid, f"ventana acaba el {end}, antes del inicio de la fuente"))
            continue
        if not slug or r["slug_status"] in {"none", "not_found"}:
            skipped.append((cid, "sin slug conocido"))
            continue
        start = max(SOURCE_FLOOR, w["window_start"] - dt.timedelta(days=LEAD_IN_DAYS))
        jobs.append(Job(cid, slug, start, end, purpose))
    return jobs, skipped
