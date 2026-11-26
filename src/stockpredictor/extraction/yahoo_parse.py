"""Lectura de la respuesta del endpoint ``chart`` de Yahoo (sin red, sin pandas).

Convención de nombres (docs/convenciones.md): el ``close`` de Yahoo ya viene ajustado por splits
(y, según el caso, por otros eventos que no entrega: ver limitaciones), por eso se guarda como
``close_split_adjusted``; ``adj_close`` es el ``adjclose`` del proveedor. Aquí no hay ``close_raw``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import polars as pl

PRICE_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "date": pl.Date,
    "ts": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close_split_adjusted": pl.Float64,
    "adj_close": pl.Float64,
    "volume": pl.Int64,
}
EVENT_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "date": pl.Date,
    "ts": pl.Int64,
    "event_type": pl.String,  # dividend | split
    "amount": pl.Float64,  # dividendo por acción
    "numerator": pl.Float64,
    "denominator": pl.Float64,
    "split_ratio": pl.String,
}


class ChartParseError(ValueError):
    """La respuesta no tiene la estructura esperada de ``chart``."""


@dataclass
class ParsedChart:
    prices: pl.DataFrame
    events: pl.DataFrame
    meta: dict[str, object] = field(default_factory=dict)
    error_code: str | None = None  # ``chart.error.code`` (p. ej. "Not Found")


def _to_local_date(ts: pl.Expr, tz: str) -> pl.Expr:
    return (
        pl.from_epoch(ts, time_unit="s")
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone(tz)
        .dt.date()
    )


def parse_chart(body: bytes) -> ParsedChart:
    try:
        payload = json.loads(body)
        chart = payload["chart"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ChartParseError(f"respuesta sin objeto 'chart': {exc}") from exc
    error = chart.get("error")
    result = chart.get("result")
    empty_p = pl.DataFrame(schema=PRICE_SCHEMA)
    empty_e = pl.DataFrame(schema=EVENT_SCHEMA)
    if error:
        return ParsedChart(empty_p, empty_e, {}, str(error.get("code") or "unknown"))
    if not result:
        raise ChartParseError("'chart.result' vacío y sin 'chart.error'")
    res = result[0]
    meta = res.get("meta") or {}
    tz = meta.get("exchangeTimezoneName") or "UTC"
    stamps = res.get("timestamp") or []
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    adj = ((res.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")
    n = len(stamps)
    cols = {"open": "open", "high": "high", "low": "low", "close": "close_split_adjusted"}
    data: dict[str, list[object]] = {"ts": list(stamps)}
    for src, dst in cols.items():
        values = quote.get(src)
        if values is not None and len(values) != n:
            raise ChartParseError(f"'{src}' tiene {len(values)} valores y hay {n} fechas")
        data[dst] = list(values) if values is not None else [None] * n
    if adj is not None and len(adj) != n:
        raise ChartParseError(f"'adjclose' tiene {len(adj)} valores y hay {n} fechas")
    data["adj_close"] = list(adj) if adj is not None else [None] * n
    volume = quote.get("volume")
    if volume is not None and len(volume) != n:
        raise ChartParseError(f"'volume' tiene {len(volume)} valores y hay {n} fechas")
    data["volume"] = list(volume) if volume is not None else [None] * n
    prices = (
        pl.DataFrame(data, schema={k: v for k, v in PRICE_SCHEMA.items() if k != "date"})
        .with_columns(_to_local_date(pl.col("ts"), tz).alias("date"))
        .select(list(PRICE_SCHEMA))
    )
    rows: list[dict[str, object]] = []
    ev = res.get("events") or {}
    for item in (ev.get("dividends") or {}).values():
        rows.append({"ts": item["date"], "event_type": "dividend", "amount": item.get("amount")})
    for item in (ev.get("splits") or {}).values():
        rows.append(
            {
                "ts": item["date"],
                "event_type": "split",
                "numerator": item.get("numerator"),
                "denominator": item.get("denominator"),
                "split_ratio": item.get("splitRatio"),
            }
        )
    events = empty_e
    if rows:
        events = (
            pl.DataFrame(rows, schema={k: v for k, v in EVENT_SCHEMA.items() if k != "date"})
            .with_columns(_to_local_date(pl.col("ts"), tz).alias("date"))
            .select(list(EVENT_SCHEMA))
            .sort(["date", "event_type"])
        )
    return ParsedChart(prices, events, dict(meta))
