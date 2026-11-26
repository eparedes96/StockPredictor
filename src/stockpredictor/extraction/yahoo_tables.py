"""Tablas tidy (Parquet) derivadas de una instantánea de Yahoo, con comprobación de sha256.

``prices.parquet`` y ``events.parquet`` son una vista regenerable del JSON de ``raw``: antes de
leer cada archivo se comprueba su sha256 contra el manifiesto (un archivo editado a mano se
rechaza). Esquemas en ``yahoo_parse``.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from stockpredictor.extraction.manifest import MANIFEST_NAME, latest_by_ticker, sha256_file
from stockpredictor.extraction.yahoo import snapshot_dir
from stockpredictor.extraction.yahoo_parse import EVENT_SCHEMA, PRICE_SCHEMA, parse_chart

PRICES_FILE = "prices.parquet"
EVENTS_FILE = "events.parquet"
TABLES_MANIFEST = "tables_manifest.json"
KEY_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "snapshot_id": pl.String,
    "company_id": pl.String,
    "ticker": pl.String,
}


class IntegrityError(RuntimeError):
    """Un archivo de ``raw`` no coincide con el sha256 del manifiesto."""


def build_tables(raw_dir: Path, snapshot_id: str) -> dict[str, object]:
    """Reconstruye ``prices.parquet`` y ``events.parquet`` de la instantánea (solo filas ``ok``)."""
    sdir = snapshot_dir(raw_dir, snapshot_id)
    latest = latest_by_ticker(sdir / MANIFEST_NAME)
    prices: list[pl.DataFrame] = []
    events: list[pl.DataFrame] = []
    for ticker, row in sorted(latest.items()):
        if row["status"] != "ok":
            continue
        path = sdir / row["file"]
        if sha256_file(path) != row["sha256"]:
            raise IntegrityError(f"{path}: sha256 distinto del manifiesto (raw modificado)")
        parsed = parse_chart(path.read_bytes())
        keys = [
            pl.lit(snapshot_id).alias("snapshot_id"),
            pl.lit(row["company_id"]).alias("company_id"),
            pl.lit(ticker).alias("ticker"),
        ]
        prices.append(parsed.prices.with_columns(keys))
        events.append(parsed.events.with_columns(keys))
    order = list(KEY_SCHEMA)
    p_schema = {**KEY_SCHEMA, **PRICE_SCHEMA}
    e_schema = {**KEY_SCHEMA, **EVENT_SCHEMA}
    p_all = (
        pl.concat(prices).select(order + list(PRICE_SCHEMA))
        if prices
        else pl.DataFrame(schema=p_schema)
    )
    e_all = (
        pl.concat(events).select(order + list(EVENT_SCHEMA))
        if events
        else pl.DataFrame(schema=e_schema)
    )
    p_all = p_all.sort(["company_id", "ticker", "date"])
    e_all = e_all.sort(["company_id", "ticker", "date", "event_type"])
    p_all.write_parquet(sdir / PRICES_FILE)
    e_all.write_parquet(sdir / EVENTS_FILE)
    info: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "source_manifest_sha256": sha256_file(sdir / MANIFEST_NAME),
        "prices": {
            "file": PRICES_FILE,
            "rows": p_all.height,
            "sha256": sha256_file(sdir / PRICES_FILE),
        },
        "events": {
            "file": EVENTS_FILE,
            "rows": e_all.height,
            "sha256": sha256_file(sdir / EVENTS_FILE),
        },
        "derived": "regenerable desde chart/*.json; no es fuente de verdad",
    }
    (sdir / TABLES_MANIFEST).write_text(json.dumps(info, indent=2), encoding="utf8")
    return info
