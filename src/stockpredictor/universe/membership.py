"""Composición point-in-time de un índice a partir de los CSV de referencia.

Convención de fechas: un alta con ``effective_date = d`` hace miembro a la empresa desde la
sesión de ``d`` (inclusive); una baja con ``effective_date = d`` la excluye desde la sesión de
``d``. Es una suposición sobre la semántica del PDF de BME,
sin verificar (ver ``docs/limitaciones.md``).

La reconstrucción trabaja por ``company_id``: una revisión que da de baja un código y de alta otro
de la misma empresa (cambio de código) no cuenta como salida.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import yaml

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"
UNIVERSE_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "universe.yaml"
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
EVENT_COLUMNS = ["revision_id", "effective_date", "event_type", "bme_code", "confidence"]
MAP_COLUMNS = ["bme_code", "company_id", "valid_from", "valid_to", "confidence"]
INTERVAL_COLUMNS = [
    "company_id",
    "index_id",
    "valid_from",
    "valid_to",
    "announcement_date",
    "effective_date",
    "revision_id",
    "exit_revision_id",
    "source",
    "source_ref",
    "source_date",
    "confidence",
    "reviewed",
    "notes",
]


def load_events(index_id: str = "ibex35", reference_dir: Path = REFERENCE_DIR) -> pl.DataFrame:
    path = reference_dir / "index_membership" / f"{index_id}_events.csv"
    df = pl.read_csv(path, try_parse_dates=True, schema_overrides={"notes": pl.String})
    missing = [c for c in EVENT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: faltan columnas {missing}")
    return df.filter(pl.col("index_id") == index_id)


def load_code_map(reference_dir: Path = REFERENCE_DIR) -> pl.DataFrame:
    path = reference_dir / "bme_code_map.csv"
    df = pl.read_csv(
        path,
        try_parse_dates=True,
        schema_overrides={"valid_from": pl.Date, "valid_to": pl.Date, "notes": pl.String},
    )
    missing = [c for c in MAP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: faltan columnas {missing}")
    return df


def resolve_company_ids(events: pl.DataFrame, code_map: pl.DataFrame) -> pl.DataFrame:
    """Añade ``company_id`` y ``map_confidence`` a cada evento; falla si un código no se resuelve.

    Un código puede denotar empresas distintas en épocas distintas: se usa la ventana
    ``valid_from``/``valid_to`` (vacía = abierta) que contiene la fecha del evento.
    """
    joined = (
        events.join(
            code_map.select(
                "bme_code",
                "company_id",
                "valid_from",
                "valid_to",
                pl.col("confidence").alias("map_confidence"),
            ),
            on="bme_code",
            how="left",
        )
        .filter(
            pl.col("company_id").is_not_null()
            & (pl.col("valid_from").is_null() | (pl.col("valid_from") <= pl.col("effective_date")))
            & (pl.col("valid_to").is_null() | (pl.col("effective_date") <= pl.col("valid_to")))
        )
        .drop("valid_from", "valid_to")
    )
    key = ["revision_id", "event_type", "bme_code"]
    counts = joined.group_by(key).len()
    if counts.filter(pl.col("len") > 1).height:
        raise ValueError("códigos con más de una empresa en la misma fecha")
    if joined.height != events.height:
        lost = events.join(joined.select(key), on=key, how="anti")
        raise ValueError(f"códigos sin empresa en bme_code_map: {lost['bme_code'].to_list()}")
    return joined


def _apply_revisions(resolved: pl.DataFrame, as_of: dt.date | None) -> set[str]:
    """Reproduce los eventos con ``effective_date <= as_of`` y devuelve los miembros."""
    members: set[str] = set()
    sel = resolved if as_of is None else resolved.filter(pl.col("effective_date") <= as_of)
    for (_, rev), group in sel.sort(["effective_date", "revision_id"]).group_by(
        ["effective_date", "revision_id"], maintain_order=True
    ):
        by_type = {
            t: set(group.filter(pl.col("event_type") == t)["company_id"].to_list())
            for t in ("initial", "deletion", "addition")
        }
        gone = by_type["deletion"] - by_type["addition"]  # cambio de código: ni sale ni entra
        new = by_type["addition"] - by_type["deletion"]
        stale = gone - members
        if stale:
            raise ValueError(f"revisión {rev}: baja de no miembros {sorted(stale)}")
        dup = (new | by_type["initial"]) & members
        if dup:
            raise ValueError(f"revisión {rev}: alta de empresas ya miembros {sorted(dup)}")
        members = (members - gone) | new | by_type["initial"]
    return members


def usable_from(index_id: str = "ibex35", config_path: Path = UNIVERSE_CONFIG) -> dt.date:
    """Primera fecha desde la que se usa la composición (``configs/universe.yaml``)."""
    cfg = yaml.safe_load(config_path.read_text(encoding="utf8"))
    value = cfg["index_membership"][index_id]["usable_from"]
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def prices_from(index_id: str = "ibex35", config_path: Path = UNIVERSE_CONFIG) -> dt.date:
    """Primera fecha con precios gratuitos (``configs/universe.yaml``); P1-0 empieza aquí."""
    cfg = yaml.safe_load(config_path.read_text(encoding="utf8"))
    value = cfg["index_membership"][index_id]["prices_from"]
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def members_at(
    date: dt.date,
    index_id: str = "ibex35",
    *,
    events: pl.DataFrame | None = None,
    code_map: pl.DataFrame | None = None,
    usable_only: bool = False,
) -> list[str]:
    """``company_id`` de los miembros de ``index_id`` en ``date`` (orden alfabético).

    Solo usa eventos con ``effective_date <= date``. Antes de la fecha base del índice devuelve
    una lista vacía. Con ``usable_only=True`` falla si ``date`` es anterior a ``usable_from``.
    """
    if usable_only and date < usable_from(index_id):
        raise ValueError(f"{date} es anterior a usable_from ({usable_from(index_id)})")
    ev = load_events(index_id) if events is None else events
    cm = load_code_map() if code_map is None else code_map
    # Se filtra antes de resolver códigos: ningún evento posterior a `date` puede influir, ni
    # siquiera haciendo fallar la resolución (anti look-ahead, test en tests/leakage/).
    past = ev.filter((pl.col("index_id") == index_id) & (pl.col("effective_date") <= date))
    return sorted(_apply_revisions(resolve_company_ids(past, cm), date))


def build_membership_intervals(
    events: pl.DataFrame, code_map: pl.DataFrame, index_id: str = "ibex35"
) -> pl.DataFrame:
    """Intervalos ``[valid_from, valid_to)`` por empresa; ``valid_to`` nulo = vigente al final."""
    resolved = resolve_company_ids(events, code_map)
    open_rows: dict[str, dict[str, object]] = {}
    out: list[dict[str, object]] = []

    def conf(*values: str) -> str:
        return min(values, key=lambda v: CONFIDENCE_ORDER[v])

    for (date, rev), group in resolved.sort(["effective_date", "revision_id"]).group_by(
        ["effective_date", "revision_id"], maintain_order=True
    ):
        rows = group.to_dicts()
        dels = {r["company_id"] for r in rows if r["event_type"] == "deletion"}
        adds = {r["company_id"] for r in rows if r["event_type"] == "addition"}
        for r in rows:
            cid = r["company_id"]
            is_start = r["event_type"] in ("initial", "addition") and cid not in dels
            is_end = r["event_type"] == "deletion" and cid not in adds
            if is_start:
                open_rows[cid] = {
                    "company_id": cid,
                    "valid_from": date,
                    "revision_id": rev,
                    "confidence": conf(r["confidence"], r["map_confidence"]),
                    "source": r["source"],
                    "source_ref": r["source_ref"],
                    "source_date": r["source_date"],
                    "notes": r["notes"] or "",
                    "_start_reviewed": bool(r.get("reviewed")),
                }
            elif is_end:
                row = open_rows.pop(cid)
                row.update(
                    valid_to=date,
                    exit_revision_id=rev,
                    reviewed=bool(row["_start_reviewed"]) and bool(r.get("reviewed")),
                    confidence=conf(str(row["confidence"]), r["confidence"], r["map_confidence"]),
                )
                out.append(row)
    for row in open_rows.values():
        row.update(valid_to=None, exit_revision_id=None, reviewed=bool(row["_start_reviewed"]))
        out.append(row)
    for row in out:
        row.pop("_start_reviewed", None)
    df = pl.DataFrame(
        out,
        schema_overrides={
            "valid_from": pl.Date,
            "valid_to": pl.Date,
            "revision_id": pl.Int32,
            "exit_revision_id": pl.Int32,
        },
    )
    return (
        df.with_columns(
            pl.lit(index_id).alias("index_id"),
            pl.lit(None, dtype=pl.Date).alias("announcement_date"),
            pl.col("valid_from").alias("effective_date"),
        )
        .sort(["valid_from", "company_id"])
        .select(INTERVAL_COLUMNS)
    )
