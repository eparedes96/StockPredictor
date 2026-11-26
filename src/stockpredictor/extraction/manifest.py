"""Manifiesto de descargas ``raw``: proveedor, URL, fecha de descarga y sha256 por archivo.

Un archivo ``raw`` nunca se sobrescribe (``write_immutable`` abre con ``xb``). El manifiesto es un
CSV de solo añadir: la última fila de cada ``ticker`` manda, de modo que un reintento tras un
error deja constancia del fallo previo.
"""

from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

MANIFEST_NAME = "manifest.csv"


@dataclass(frozen=True)
class ManifestRow:
    snapshot_id: str
    ticker: str
    company_id: str
    provider: str
    url: str
    downloaded_at: str  # UTC, ISO 8601
    http_status: int | None
    status: str  # ok | not_found | error | rate_limited
    file: str  # ruta relativa al directorio de la instantánea; vacío si no hay respuesta
    sha256: str
    bytes: int | None
    n_rows: int | None
    first_date: str
    last_date: str
    currency: str
    exchange: str
    long_name: str
    attempts: int
    error: str


MANIFEST_COLUMNS = [f.name for f in fields(ManifestRow)]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_immutable(path: Path, data: bytes) -> None:
    """Escribe ``data`` en ``path``; falla si ya existe (``raw`` no se edita)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with tmp.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        try:
            os.link(tmp, path)  # falla con FileExistsError si ya existe
        except FileExistsError:
            raise
        except OSError:  # sistema de archivos sin enlaces duros (montajes de red)
            with path.open("xb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
    finally:
        tmp.unlink(missing_ok=True)


def append_row(manifest_path: Path, row: ManifestRow) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    new = not manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({k: ("" if v is None else v) for k, v in asdict(row).items()})
        fh.flush()
        os.fsync(fh.fileno())


def read_rows(manifest_path: Path) -> list[dict[str, str]]:
    if not manifest_path.exists():
        return []
    with manifest_path.open(newline="", encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def latest_by_ticker(manifest_path: Path) -> dict[str, dict[str, str]]:
    """Última fila del manifiesto por ``ticker`` (la más reciente manda)."""
    return {r["ticker"]: r for r in read_rows(manifest_path)}
