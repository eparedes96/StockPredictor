"""Lectura de las tablas de es.wikipedia.org/wiki/IBEX_35 (fuente secundaria de la composición).

Dos tablas: miembros actuales (ticker, empresa, año de entrada, ISIN) y componentes históricos
(ticker, empresa, año de abandono). Sirven para contrastar nombre y año de salida de cada código
BME del PDF oficial. Es una fuente de la comunidad: no sustituye a BME y puede tener errores.
"""

from __future__ import annotations

from html.parser import HTMLParser

import polars as pl

SOURCE_URL = "https://es.wikipedia.org/wiki/IBEX_35"


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in ("style", "script"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append(self._row)
            self._row = None
        elif tag in ("style", "script") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None and not self._skip:
            self._cell.append(data)


def _tables(html: str) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.tables


def parse_wikipedia_ibex(html: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Devuelve ``(actuales, historicos)``.

    actuales: ``ticker, company_name, since_year, isin``; historicos: ``ticker, company_name,
    exit_year``. Falla si no encuentra las dos tablas con las cabeceras esperadas.
    """
    current: list[dict[str, object]] = []
    historic: list[dict[str, object]] = []
    for table in _tables(html):
        if not table:
            continue
        header = table[0]
        if header[:2] == ["Ticker", "Empresa"] and "Abandono" in header:
            col = header.index("Abandono")
            for r in table[1:]:
                if len(r) > col and r[col].isdigit():
                    historic.append(
                        {"ticker": r[0], "company_name": r[1], "exit_year": int(r[col])}
                    )
        elif header[:2] == ["Ticker", "Empresa"] and "ISIN" in header:
            c_year = next(i for i, h in enumerate(header) if h.startswith("Año") or h == "Entrada")
            c_isin = header.index("ISIN")
            for r in table[1:]:
                if len(r) > c_isin and r[c_year].isdigit():
                    current.append(
                        {
                            "ticker": r[0],
                            "company_name": r[1],
                            "since_year": int(r[c_year]),
                            "isin": r[c_isin],
                        }
                    )
    if not current or not historic:
        raise ValueError("no se encontraron las tablas de componentes actuales e históricos")
    return pl.DataFrame(current), pl.DataFrame(historic)


def isin_is_valid(isin: str) -> bool:
    """Comprueba formato y dígito de control (Luhn sobre las letras expandidas a números)."""
    if len(isin) != 12 or not isin[:2].isalpha() or not isin.isalnum():
        return False
    digits = "".join(str(int(c, 36)) for c in isin.upper())
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
    return total % 10 == 0
