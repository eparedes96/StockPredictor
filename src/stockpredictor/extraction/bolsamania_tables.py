"""Tabla tidy (Parquet) derivada de una instantánea de Bolsamanía, con comprobación de sha256.

``prices.parquet`` es una vista regenerable del HTML de ``raw``: cada archivo se comprueba contra
el sha256 del manifiesto antes de leerlo. Sin volumen (la fuente no lo da) y sin ``Variación %``
(ajustada; prohibida). Toda fila lleva ``price_quality = close_only`` (``close_raw`` real, sin
``adj_close`` propio) y ``source = bolsamania``.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import polars as pl

from stockpredictor.extraction.bolsamania import PROVIDER, snapshot_dir
from stockpredictor.extraction.bolsamania_parse import PRICE_SCHEMA, parse_history
from stockpredictor.extraction.manifest import MANIFEST_NAME, latest_by_ticker, sha256_file
from stockpredictor.extraction.yahoo_tables import IntegrityError

PRICES_FILE = "prices.parquet"
TABLES_MANIFEST = "tables_manifest.json"
PRICE_QUALITY = "close_only"
SOURCE = "bolsamania"
KEY_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "snapshot_id": pl.String,
    "company_id": pl.String,
    "slug": pl.String,
}
OUT_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    **KEY_SCHEMA,
    **PRICE_SCHEMA,
    "price_quality": pl.String,
    "source": pl.String,
}


def build_tables(raw_dir: Path, snapshot_id: str) -> dict[str, object]:
    sdir = snapshot_dir(raw_dir, snapshot_id)
    latest = latest_by_ticker(sdir / MANIFEST_NAME)
    frames: list[pl.DataFrame] = []
    for key, row in sorted(latest.items()):
        if row["status"] != "ok" or row["provider"] != PROVIDER:
            continue
        path = sdir / row["file"]
        if sha256_file(path) != row["sha256"]:
            raise IntegrityError(f"{path}: sha256 distinto del manifiesto (raw modificado)")
        parsed = parse_history(gzip.decompress(path.read_bytes()).decode("utf8"))
        slug = key.split("@", 1)[0]
        frames.append(
            parsed.prices.with_columns(
                pl.lit(snapshot_id).alias("snapshot_id"),
                pl.lit(row["company_id"]).alias("company_id"),
                pl.lit(slug).alias("slug"),
                pl.lit(PRICE_QUALITY).alias("price_quality"),
                pl.lit(SOURCE).alias("source"),
            )
        )
    cols = list(OUT_SCHEMA)
    out = (pl.concat(frames).select(cols) if frames else pl.DataFrame(schema=OUT_SCHEMA)).sort(
        ["company_id", "slug", "date"]
    )
    out.write_parquet(sdir / PRICES_FILE)
    info: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "source_manifest_sha256": sha256_file(sdir / MANIFEST_NAME),
        "prices": {
            "file": PRICES_FILE,
            "rows": out.height,
            "sha256": sha256_file(sdir / PRICES_FILE),
        },
        "derived": "regenerable desde html/*.html.gz; no es fuente de verdad",
    }
    (sdir / TABLES_MANIFEST).write_text(json.dumps(info, indent=2), encoding="utf8")
    return info
