"""Tabla de tickers de Yahoo por ``company_id`` y comprobación de identidad.

Los tickers se reutilizan (``GAM.MC`` hoy es General de Alquiler de Maquinaria, no Gamesa;
``MVC.MC`` es la Metrovacesa de 2018, no la de 1991). Por eso la tabla
``data/reference/yahoo_tickers.csv`` es manual y versionada, y cada ticker nace como
``candidate``: solo pasa a ``verified`` tras una descarga real que cumpla ``check_identity``, es
decir, con un tramo de fechas que solape la ventana en que la empresa fue miembro del índice. Un
ticker sin solape se marca ``reused_ticker``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from stockpredictor.extraction.yahoo import Target
from stockpredictor.universe import membership as m

TICKERS_CSV = m.REFERENCE_DIR / "yahoo_tickers.csv"
TICKER_COLUMNS = [
    "company_id",
    "yahoo_ticker",
    "ticker_status",
    "known_reused_ticker",
    "source",
    "source_ref",
    "source_date",
    "confidence",
    "reviewed",
    "notes",
]
# candidate: propuesto, sin descarga real. verified: descarga real con identidad coherente.
# not_found: Yahoo da 404 (empresa deslistada o ticker erróneo). reused_ticker: datos de otra
# empresa (MVC.MC). none: no se conoce ticker. unresolved: empresa sin identificar en la
# composición.
TICKER_STATUSES = {"candidate", "verified", "not_found", "reused_ticker", "none", "unresolved"}
TOLERANCE_DAYS = 10


def load_ticker_table(path: Path = TICKERS_CSV) -> pl.DataFrame:
    df = pl.read_csv(path, infer_schema_length=0)  # todo texto: ningún tipo se infiere
    missing = [c for c in TICKER_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: faltan columnas {missing}")
    bad = set(df["ticker_status"].unique().to_list()) - TICKER_STATUSES
    if bad:
        raise ValueError(f"{path}: ticker_status no válido {sorted(bad)}")
    return df.with_columns(pl.col(pl.String).fill_null(""))


def membership_windows(
    index_id: str = "ibex35",
    *,
    today: dt.date | None = None,
    reference_dir: Path = m.REFERENCE_DIR,
) -> pl.DataFrame:
    """Ventana de pertenencia por empresa dentro del periodo usable (desde ``usable_from``).

    ``window_start`` = primer día miembro con fecha ≥ ``usable_from``; ``window_end`` = fin del
    último intervalo (``today`` si sigue vigente). Empresas que salieron antes de ``usable_from``
    no aparecen.
    """
    today = today or dt.date.today()
    start = m.usable_from(index_id)
    iv = m.build_membership_intervals(
        m.load_events(index_id, reference_dir), m.load_code_map(reference_dir), index_id
    )
    iv = iv.filter(pl.col("valid_to").is_null() | (pl.col("valid_to") > start))
    return (
        iv.group_by("company_id")
        .agg(
            pl.col("valid_from").min().alias("first_member"),
            pl.col("valid_to").fill_null(today).max().alias("window_end"),
            pl.col("valid_to").is_null().any().alias("current_member"),
        )
        .with_columns(
            pl.when(pl.col("first_member") < start)
            .then(pl.lit(start))
            .otherwise(pl.col("first_member"))
            .alias("window_start")
        )
        .select("company_id", "window_start", "window_end", "current_member")
        .sort("company_id")
    )


def select_targets(
    table: pl.DataFrame, windows: pl.DataFrame, only: set[str] | None = None
) -> tuple[list[Target], pl.DataFrame]:
    """Tickers a descargar (en orden estable) y empresas del periodo usable sin ticker."""
    in_scope = windows["company_id"].to_list()
    usable = table.filter(
        pl.col("company_id").is_in(in_scope)
        & (pl.col("yahoo_ticker") != "")
        & pl.col("ticker_status").is_in(["candidate", "verified", "not_found"])
    ).sort(["company_id", "yahoo_ticker"])
    targets = [Target(t, c) for c, t in usable.select("company_id", "yahoo_ticker").iter_rows()]
    if only:
        targets = [t for t in targets if t.ticker in only or t.company_id in only]
    with_ticker = {t.company_id for t in targets}
    no_ticker = windows.filter(~pl.col("company_id").is_in(list(with_ticker)))
    return targets, no_ticker


@dataclass(frozen=True)
class Identity:
    verdict: str  # ok | partial_start | partial_end | partial_both | no_overlap | no_data
    detail: str


def check_identity(
    first: dt.date | None,
    last: dt.date | None,
    window_start: dt.date,
    window_end: dt.date,
    *,
    tolerance_days: int = TOLERANCE_DAYS,
    history_floor: dt.date | None = None,
) -> Identity:
    """¿Los datos de Yahoo cubren la ventana en que la empresa fue miembro?

    ``no_overlap`` (sin solape alguno) delata un ticker reutilizado. ``partial_*`` son huecos de
    cobertura (p. ej. Yahoo empieza en 2000 y la empresa entró en 1995), no un error de identidad.
    ``history_floor`` es la primera fecha con datos de cualquier ticker del mismo mercado en la
    instantánea (en Madrid, 2000-01-03): si la ventana acaba antes, no hay forma de comprobar la
    identidad con fechas y el veredicto es ``before_history`` (no ``no_overlap``).
    """
    if first is None or last is None:
        return Identity("no_data", "sin filas de precio")
    if history_floor is not None and window_end < history_floor:
        return Identity(
            "before_history",
            f"ventana {window_start}..{window_end} anterior a la historia de Yahoo "
            f"({history_floor}); identidad por revisar con longName",
        )
    if last < window_start or first > window_end:
        return Identity(
            "no_overlap",
            f"datos {first}..{last} fuera de la ventana {window_start}..{window_end}",
        )
    tol = dt.timedelta(days=tolerance_days)
    late_start = first > window_start + tol
    early_end = last < window_end - tol
    if late_start and early_end:
        return Identity(
            "partial_both", f"datos {first}..{last}, ventana {window_start}..{window_end}"
        )
    if late_start:
        return Identity("partial_start", f"Yahoo empieza el {first}; miembro desde {window_start}")
    if early_end:
        return Identity("partial_end", f"Yahoo acaba el {last}; miembro hasta {window_end}")
    return Identity("ok", "")
