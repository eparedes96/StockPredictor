"""Lectura del HTML de ``/accion/<slug>/historico-precios`` de Bolsamanía (sin red, sin pandas).

Solo se leen las columnas de precio (``Precio``, ``Máximo``, ``Mínimo``, ``Apertura``). La columna
``Variación %`` está ajustada por agrupaciones y splits (P2.1: en el día del split dice 0,00 %) y
**no se extrae nunca**. ``Precio`` es el cierre real sin ajustar (P1.2 ronda 11, P2.1). Sin volumen.

Formato observado el 2026-11-28: fechas ``16-jul-07``, importes ``66,250€`` (coma decimal).
Un slug inexistente devuelve HTTP 200 con ``<h1>Página no encontrada</h1>``; un rango sin datos
devuelve una fila ``No se han encontrado resultados``; una ficha sin sección de históricos
(h1 ``Cotización ...`` pero sin tabla) se marca ``no_history``. Cualquier otra página es anómala.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import polars as pl

MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip
HISTORY_COLUMNS = ["Fecha", "Precio", "Variación %", "Máximo", "Mínimo", "Apertura"]
PRICE_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "date": pl.Date,
    "close_raw": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "open": pl.Float64,
}
_DATE_RE = re.compile(r"^(\d{1,2})-([a-z]{3})-(\d{2})$")
_NUM_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+(,\d+)?$")


class BolsamaniaParseError(ValueError):
    """El HTML no tiene la estructura esperada de la tabla de históricos."""


@dataclass
class ParsedHistory:
    prices: pl.DataFrame
    page_status: str  # ok | empty | slug_not_found | no_history
    n_rows: int


class _TableParser(HTMLParser):
    """Extrae el primer ``<h1>`` y las filas de la tabla con la clase ``table-bm``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.h1 = ""
        self.rows: list[list[str]] = []
        self._in_h1 = False
        self._table_depth = 0
        self._cell: list[str] | None = None
        self._row: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "h1" and not self.h1:
            self._in_h1 = True
        elif tag == "table":
            if self._table_depth:
                self._table_depth += 1
            elif "table-bm" in (a.get("class") or "").split():
                self._table_depth = 1
        elif self._table_depth and tag == "tr":
            self._row = []
        elif self._table_depth and tag in {"td", "th"}:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._in_h1 = False
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
        elif self._table_depth and tag in {"td", "th"} and self._cell is not None:
            if self._row is not None:
                self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif self._table_depth and tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._in_h1:
            self.h1 += data
        if self._cell is not None:
            self._cell.append(data)


def parse_date(text: str) -> dt.date:
    m = _DATE_RE.match(text.strip().lower())
    if not m or m.group(2) not in MONTHS:
        raise BolsamaniaParseError(f"fecha no reconocida: {text!r}")
    year = int(m.group(3))
    # La serie empieza en 2006: dos dígitos 00-69 -> 20xx (no hay datos de 1900s en la fuente).
    return dt.date(2000 + year if year < 70 else 1900 + year, MONTHS[m.group(2)], int(m.group(1)))


def parse_price(text: str) -> float | None:
    t = text.replace("€", "").replace("\xa0", "").strip()
    if t in {"", "-", "--", "n/d"}:
        return None
    if not _NUM_RE.match(t):
        raise BolsamaniaParseError(f"importe no reconocido: {text!r}")
    return float(t.replace(".", "").replace(",", "."))


def parse_history(html: str) -> ParsedHistory:
    parser = _TableParser()
    parser.feed(html)
    empty = pl.DataFrame(schema=PRICE_SCHEMA)
    if "no encontrada" in parser.h1.lower():
        return ParsedHistory(empty, "slug_not_found", 0)
    if not parser.rows:
        if parser.h1.strip().lower().startswith("cotización"):
            # Ficha de un valor sin sección de históricos (p. ej. una ficha antigua o vacía).
            return ParsedHistory(empty, "no_history", 0)
        raise BolsamaniaParseError(
            f"sin tabla de históricos 'table-bm' ni ficha reconocible (h1={parser.h1.strip()!r})"
        )
    header = parser.rows[0]
    if header != HISTORY_COLUMNS:
        raise BolsamaniaParseError(f"cabecera inesperada: {header}")
    body = parser.rows[1:]
    if not body or (len(body) == 1 and body[0][0].lower().startswith("no se han encontrado")):
        return ParsedHistory(empty, "empty", 0)  # sin filas: tabla vacía o aviso de la web
    idx = {name: header.index(name) for name in ("Fecha", "Precio", "Máximo", "Mínimo", "Apertura")}
    out: list[dict[str, object]] = []
    for row in body:
        if len(row) != len(header):
            raise BolsamaniaParseError(f"fila con {len(row)} celdas: {row}")
        out.append(
            {
                "date": parse_date(row[idx["Fecha"]]),
                "close_raw": parse_price(row[idx["Precio"]]),
                "high": parse_price(row[idx["Máximo"]]),
                "low": parse_price(row[idx["Mínimo"]]),
                "open": parse_price(row[idx["Apertura"]]),
            }
        )
    df = pl.DataFrame(out, schema=PRICE_SCHEMA).sort("date")
    return ParsedHistory(df, "ok", df.height)
