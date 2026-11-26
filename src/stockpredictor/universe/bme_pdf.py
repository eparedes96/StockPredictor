"""Parser del PDF oficial de BME con la composición histórica del IBEX 35.

El PDF lista, por revisión, los códigos BME que entran y los que salen, con su fecha de
efecto. No trae la composición inicial ni nombres ni ISIN. La leyenda de color de la celda de
fecha distingue revisión extraordinaria y cambio de código; se lee de los rectángulos de
relleno de la página (en texto plano esa información se pierde).

Solo polars. ``pdfplumber`` (extra ``pdf``) se importa al leer el PDF, no al importar el módulo.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")
NUMBER_RE = re.compile(r"\d+")
EMPTY_MARKS = {"-", "—", "–"}

# Rellenos CMYK de la celda de fecha (verificados contra la leyenda del PDF de septiembre de 2026).
COLOR_EXTRAORDINARY = (0.149, 0.13, 0.0, 0.0)
COLOR_CODE_CHANGE = (0.048, 0.176, 0.285, 0.0)

EVENT_SCHEMA = {
    "revision_id": pl.Int32,
    "effective_date": pl.Date,
    "event_type": pl.String,
    "bme_code": pl.String,
    "is_extraordinary": pl.Boolean,
    "is_code_change_row": pl.Boolean,
}


@dataclass(frozen=True)
class Revision:
    """Una fila del PDF: una revisión con sus altas y bajas (puede venir vacía)."""

    revision_id: int
    effective_date: dt.date
    additions: tuple[str, ...]
    deletions: tuple[str, ...]
    is_extraordinary: bool
    is_code_change_row: bool
    page: int


def _close(a: Sequence[float], b: Sequence[float], tol: float = 0.01) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def _color_flags(color: Any) -> tuple[bool, bool]:
    if not isinstance(color, (tuple, list)):  # sin color o gris escalar
        return False, False
    return _close(color, COLOR_EXTRAORDINARY), _close(color, COLOR_CODE_CHANGE)


def _mid_y(word: Mapping[str, Any]) -> float:
    return (float(word["top"]) + float(word["bottom"])) / 2


def _mid_x(word: Mapping[str, Any]) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2


def parse_page(
    words: Iterable[Mapping[str, Any]],
    rects: Iterable[Mapping[str, Any]],
    page: int = 1,
) -> list[Revision]:
    """Lee una página ya extraída (palabras con x0/x1/top/bottom/text y rectángulos rellenos).

    La frontera entre altas y bajas es el punto medio entre los centros de las cabeceras
    "Inclusiones" y "Exclusiones" de la página (el ancho de columnas cambia entre páginas).
    """
    ws = list(words)
    inc = [w for w in ws if str(w["text"]).startswith("Inclusiones")]
    exc = [w for w in ws if str(w["text"]).startswith("Exclusiones")]
    if not inc or not exc:
        return []  # página sin tabla
    split = (_mid_x(inc[0]) + _mid_x(exc[0])) / 2
    fills = [r for r in rects if any(_color_flags(r.get("non_stroking_color")))]
    out: list[Revision] = []
    for d in (w for w in ws if DATE_RE.fullmatch(str(w["text"]))):
        cy = _mid_y(d)
        row = [w for w in ws if abs(_mid_y(w) - cy) < 4]
        numbers = [w for w in row if w["x1"] < d["x0"] and NUMBER_RE.fullmatch(str(w["text"]))]
        if len(numbers) != 1:
            raise ValueError(f"fila sin número de revisión único junto a {d['text']}")
        extra = code = False
        for r in fills:
            if r["x0"] <= d["x0"] <= r["x1"] and r["top"] <= cy <= r["bottom"]:
                e, c = _color_flags(r["non_stroking_color"])
                extra, code = extra or e, code or c
        cells = [w for w in row if w["x0"] > d["x1"] and str(w["text"]) not in EMPTY_MARKS]
        out.append(
            Revision(
                revision_id=int(numbers[0]["text"]),
                effective_date=dt.datetime.strptime(str(d["text"]), "%d/%m/%Y").date(),
                additions=tuple(str(w["text"]) for w in cells if _mid_x(w) < split),
                deletions=tuple(str(w["text"]) for w in cells if _mid_x(w) >= split),
                is_extraordinary=extra,
                is_code_change_row=code,
                page=page,
            )
        )
    return out


def parse_pdf(path: str | Path) -> list[Revision]:
    """Devuelve las revisiones del PDF ordenadas por número de revisión."""
    import pdfplumber  # extra opcional `pdf`

    revisions: list[Revision] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            revisions.extend(parse_page(page.extract_words(), page.rects, page=i))
    revisions.sort(key=lambda r: r.revision_id)
    ids = [r.revision_id for r in revisions]
    if ids != list(range(1, len(ids) + 1)):
        raise ValueError("numeración de revisiones no consecutiva; revisar el parseo")
    return revisions


def revisions_to_events(revisions: Iterable[Revision]) -> pl.DataFrame:
    """Una fila por alta o baja de código. No incluye la composición inicial (no está en el PDF)."""
    rows: list[dict[str, Any]] = []
    for r in revisions:
        for event_type, codes in (("deletion", r.deletions), ("addition", r.additions)):
            for code in codes:
                rows.append(
                    {
                        "revision_id": r.revision_id,
                        "effective_date": r.effective_date,
                        "event_type": event_type,
                        "bme_code": code,
                        "is_extraordinary": r.is_extraordinary,
                        "is_code_change_row": r.is_code_change_row,
                    }
                )
    return pl.DataFrame(rows, schema=EVENT_SCHEMA)


def infer_initial_codes(events: pl.DataFrame) -> list[str]:
    """Códigos que ya eran miembros antes de la primera revisión y salen después.

    Una baja de un código que no está vigente solo es posible si ya era miembro: se reconstruye
    así la composición inicial parcial. Los miembros que nunca se tocan en el PDF no se pueden
    deducir de él (ver ``membership.py``).
    """
    state: set[str] = set()
    initial: set[str] = set()
    for _, group in events.sort(["effective_date", "revision_id"]).group_by(
        ["effective_date", "revision_id"], maintain_order=True
    ):
        for row in group.filter(pl.col("event_type") == "deletion").iter_rows(named=True):
            if row["bme_code"] not in state:
                initial.add(row["bme_code"])
            state.discard(row["bme_code"])
        for row in group.filter(pl.col("event_type") == "addition").iter_rows(named=True):
            state.add(row["bme_code"])
    return sorted(initial)


# --- Regeneración del CSV de eventos --------------------------------------------------------

INDEX_ID = "ibex35"
SOURCE = "bme_composicion_ibex35.pdf"
SOURCE_DATE = "2026-09-21"  # fecha de la última revisión del PDF descargado
INITIAL_DATE = dt.date(1989, 12, 29)  # fecha base del índice (BME, ficha técnica)
EVENTS_COLUMNS = [
    "index_id",
    "revision_id",
    "effective_date",
    "event_type",
    "bme_code",
    "is_extraordinary",
    "is_code_change_row",
    "source",
    "source_ref",
    "source_date",
    "confidence",
    "reviewed",
    "notes",
]


def events_csv_frame(
    revisions: Sequence[Revision],
    extra_initial: Mapping[str, str],
) -> pl.DataFrame:
    """Tabla final de eventos: miembros iniciales + altas y bajas del PDF, con fuente por fila.

    ``extra_initial`` son los miembros iniciales que el PDF nunca menciona (código → nota).
    """
    events = revisions_to_events(revisions)
    parsed_initial = infer_initial_codes(events)
    rows: list[dict[str, Any]] = []
    for code in parsed_initial:
        rows.append(
            {
                "revision_id": 0,
                "effective_date": INITIAL_DATE,
                "event_type": "initial",
                "bme_code": code,
                "is_extraordinary": False,
                "is_code_change_row": False,
                "source": SOURCE,
                "source_ref": f"{SOURCE}#inferred-from-first-deletion",
                "confidence": "medium",
                "notes": "Miembro inicial inferido: el PDF lo da de baja sin alta previa.",
            }
        )
    for code, note in sorted(extra_initial.items()):
        rows.append(
            {
                "revision_id": 0,
                "effective_date": INITIAL_DATE,
                "event_type": "initial",
                "bme_code": code,
                "is_extraordinary": False,
                "is_code_change_row": False,
                "source": "inference",
                "source_ref": "inferred-from-2026-membership-count",
                "confidence": "low",
                "notes": note,
            }
        )
    for r in events.iter_rows(named=True):
        rows.append(
            {
                **r,
                "source": SOURCE,
                "source_ref": f"{SOURCE}#rev={r['revision_id']}",
                "confidence": "high",
                "notes": "",
            }
        )
    base = pl.DataFrame(
        rows,
        schema_overrides={
            "revision_id": pl.Int32,
            "effective_date": pl.Date,
            "notes": pl.String,
        },
    )
    order = (
        pl.when(pl.col("event_type") == "initial")
        .then(-1)
        .when(pl.col("event_type") == "deletion")
        .then(0)
        .otherwise(1)
    )
    return (
        base.with_columns(
            pl.lit(INDEX_ID).alias("index_id"),
            pl.lit(SOURCE_DATE).alias("source_date"),
            pl.lit(False).alias("reviewed"),
            order.alias("_order"),
        )
        .sort(["effective_date", "revision_id", "_order", "bme_code"])
        .select(EVENTS_COLUMNS)
    )


# Miembros iniciales que el PDF nunca menciona: son los 4 miembros de 2026 sin ningún evento, y el
# recuento de 35 al inicio exige exactamente 4 (31 inferidos de las bajas + 4). Identidad por
# conocimiento previo, sin fuente: queda con confianza baja hasta revisar.
EXTRA_INITIAL_NOTE = (
    "No aparece en el PDF; es miembro en 2026 y el recuento de 35 al inicio exige 4 miembros "
    "nunca tocados. Identidad inferida, sin fuente."
)
EXTRA_INITIAL = {code: EXTRA_INITIAL_NOTE for code in ("BKT", "IBE", "REP", "TEF")}


def main(argv: Sequence[str] | None = None) -> None:
    """``python -m stockpredictor.universe.bme_pdf PDF SALIDA.csv``: regenera el CSV de eventos."""
    import argparse

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args(argv)
    frame = events_csv_frame(parse_pdf(args.pdf), EXTRA_INITIAL)
    frame.write_csv(args.out)
    print(f"{frame.height} eventos escritos en {args.out}")


if __name__ == "__main__":
    main()
