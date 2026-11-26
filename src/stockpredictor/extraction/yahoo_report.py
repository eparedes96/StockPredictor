"""Informe de cobertura de una instantánea de Yahoo y regresión de retornos entre dos.

Cobertura: empresas con precios, 404 (deslistadas o ticker erróneo), identidad del ticker frente a
la ventana de pertenencia, huecos de fechas y cierres nulos. Regresión: los retornos logarítmicos
diarios de ``adj_close`` de las fechas comunes deben coincidir entre dos descargas (un dividendo
nuevo reescala el nivel anterior pero no los retornos ya pasados); lo que cambie se lista.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from stockpredictor.extraction.manifest import MANIFEST_NAME, latest_by_ticker
from stockpredictor.extraction.yahoo import snapshot_dir
from stockpredictor.extraction.yahoo_tables import PRICES_FILE
from stockpredictor.extraction.yahoo_tickers import check_identity, select_targets
from stockpredictor.universe import membership as m

GAP_DAYS = 7  # un hueco entre sesiones consecutivas de más de 7 días naturales se lista
RETURN_TOL = 1e-5  # ruido de redondeo de adj_close observado: hasta 1,9e-6 entre dos descargas


def price_stats(prices: pl.DataFrame) -> pl.DataFrame:
    """Por ticker: filas, cierres nulos, huecos de fechas y duplicados."""
    gaps = (
        prices.sort(["ticker", "date"])
        .with_columns(
            (pl.col("date") - pl.col("date").shift(1).over("ticker")).dt.total_days().alias("gap")
        )
        .group_by("ticker")
        .agg(
            (pl.col("gap") > GAP_DAYS).sum().alias("n_gaps"),
            pl.col("gap").max().alias("max_gap_days"),
        )
    )
    base = prices.group_by("ticker").agg(
        pl.len().alias("n_rows"),
        pl.col("date").min().alias("first_date"),
        pl.col("date").max().alias("last_date"),
        pl.col("adj_close").is_null().sum().alias("n_null_adj_close"),
        pl.col("close_split_adjusted").is_null().sum().alias("n_null_close"),
        (pl.col("date").len() - pl.col("date").n_unique()).alias("n_duplicate_dates"),
        (pl.col("adj_close") <= 0).sum().alias("n_nonpositive_adj_close"),
    )
    return base.join(gaps, on="ticker", how="left").sort("ticker")


def coverage(
    raw_dir: Path,
    snapshot_id: str,
    table: pl.DataFrame,
    windows: pl.DataFrame,
    *,
    as_of: dt.date | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Cobertura por (empresa, ticker), empresas sin ticker y resumen en cifras."""
    sdir = snapshot_dir(raw_dir, snapshot_id)
    latest = latest_by_ticker(sdir / MANIFEST_NAME)
    prices = pl.read_parquet(sdir / PRICES_FILE)
    stats = price_stats(prices) if prices.height else pl.DataFrame()
    as_of = as_of or dt.date.today()
    win = {r["company_id"]: r for r in windows.iter_rows(named=True)}
    rows: list[dict[str, object]] = []
    targets, no_ticker = select_targets(table, windows)
    st = {r["ticker"]: r for r in stats.iter_rows(named=True)} if stats.height else {}
    floor = min((r["first_date"] for r in st.values() if r["first_date"]), default=None)
    for t in targets:
        m = latest.get(t.ticker)
        w = win[t.company_id]
        end = as_of if w["current_member"] else w["window_end"]
        status = m["status"] if m else "pending"
        s = st.get(t.ticker, {})
        verdict = check_identity(
            s.get("first_date"), s.get("last_date"), w["window_start"], end, history_floor=floor
        )
        rows.append(
            {
                "company_id": t.company_id,
                "ticker": t.ticker,
                "status": status,
                "long_name": m["long_name"] if m else "",
                "currency": m["currency"] if m else "",
                "window_start": w["window_start"],
                "window_end": end,
                "first_date": s.get("first_date"),
                "last_date": s.get("last_date"),
                "n_rows": s.get("n_rows"),
                "n_null_close": s.get("n_null_close"),
                "n_null_adj_close": s.get("n_null_adj_close"),
                "n_duplicate_dates": s.get("n_duplicate_dates"),
                "n_gaps": s.get("n_gaps"),
                "max_gap_days": s.get("max_gap_days"),
                "identity": verdict.verdict if status == "ok" else status,
                "identity_detail": verdict.detail if status == "ok" else "",
            }
        )
    cov = pl.DataFrame(rows, infer_schema_length=None)
    per_company = cov.group_by("company_id").agg(
        (pl.col("identity").is_in(["ok", "partial_start", "partial_end", "partial_both"]))
        .any()
        .alias("priced"),
        (pl.col("status") == "not_found").all().alias("all_404"),
    )
    summary = {
        "companies_in_scope": windows.height,
        "companies_with_ticker": cov["company_id"].n_unique(),
        "companies_without_ticker": no_ticker.height,
        "companies_with_prices": int(per_company["priced"].sum()),
        "companies_404": int(per_company["all_404"].sum()),
        "tickers": cov.height,
        "tickers_ok": int((cov["status"] == "ok").sum()),
        "tickers_404": int((cov["status"] == "not_found").sum()),
        "tickers_failed": int(cov["status"].is_in(["error", "rate_limited"]).sum()),
        "tickers_pending": int((cov["status"] == "pending").sum()),
        "tickers_no_overlap": int((cov["identity"] == "no_overlap").sum()),
    }
    return cov, no_ticker, summary


def member_coverage_by_year(
    prices: pl.DataFrame, index_id: str = "ibex35", *, last_year: int | None = None
) -> pl.DataFrame:
    """Miembros del índice a 30 de junio de cada año con precio ese día (aprox. por tramo).

    Se usa el tramo ``[primera, última fecha]`` de cada empresa (suma de sus tickers), sin mirar
    huecos internos. Es el denominador del sesgo de supervivencia: umbral provisional del 80 %.
    """
    spans = prices.group_by("company_id").agg(
        pl.col("date").min().alias("first"), pl.col("date").max().alias("last")
    )
    span = {r["company_id"]: (r["first"], r["last"]) for r in spans.iter_rows(named=True)}
    events, code_map = m.load_events(index_id), m.load_code_map()
    start = m.usable_from(index_id)
    last_year = last_year or dt.date.today().year
    rows = []
    for year in range(start.year, last_year + 1):
        day = max(dt.date(year, 6, 30), start)
        members = m.members_at(day, index_id, events=events, code_map=code_map)
        priced = [c for c in members if c in span and span[c][0] <= day <= span[c][1]]
        rows.append(
            {
                "year": year,
                "date": day,
                "n_members": len(members),
                "n_priced": len(priced),
                "share_priced": len(priced) / len(members) if members else None,
            }
        )
    return pl.DataFrame(rows)


def compare_snapshots(
    raw_dir: Path, snapshot_a: str, snapshot_b: str, tol: float = RETURN_TOL
) -> tuple[pl.DataFrame, dict[str, int]]:
    """Regresión de retornos: ``adj_close`` de dos descargas, por ticker y fechas comunes."""
    a = pl.read_parquet(snapshot_dir(raw_dir, snapshot_a) / PRICES_FILE)
    b = pl.read_parquet(snapshot_dir(raw_dir, snapshot_b) / PRICES_FILE)
    # La última barra de la instantánea antigua puede ser una sesión sin cerrar (Yahoo entrega la
    # barra del día en curso): no se compara.
    a_last = a.group_by("ticker").agg(pl.col("date").max().alias("a_last"))

    def returns(df: pl.DataFrame) -> pl.DataFrame:
        return (
            df.filter(pl.col("adj_close") > 0)
            .sort(["ticker", "date"])
            .with_columns(pl.col("adj_close").log().diff().over("ticker").alias("ret"))
            .select("ticker", "date", "ret")
        )

    ra, rb = returns(a), returns(b)
    joined = (
        ra.join(rb, on=["ticker", "date"], how="inner", suffix="_b")
        .join(a_last, on="ticker")
        .filter(pl.col("date") < pl.col("a_last"))
        .drop("a_last")
    )
    # El retorno de la primera fecha común depende de la fecha previa: solo se comparan pares con
    # retorno en ambas descargas, y la fecha previa debe ser la misma en las dos.
    prev_a = (
        a.sort(["ticker", "date"])
        .with_columns(pl.col("date").shift(1).over("ticker").alias("prev"))
        .select("ticker", "date", "prev")
    )
    prev_b = (
        b.sort(["ticker", "date"])
        .with_columns(pl.col("date").shift(1).over("ticker").alias("prev"))
        .select("ticker", "date", "prev")
    )
    joined = (
        joined.join(prev_a, on=["ticker", "date"])
        .join(prev_b, on=["ticker", "date"], suffix="_b")
        .filter(pl.col("prev") == pl.col("prev_b"))
        .with_columns((pl.col("ret") - pl.col("ret_b")).abs().alias("abs_diff"))
        .drop_nulls("abs_diff")
    )
    per = joined.group_by("ticker").agg(
        pl.len().alias("n_compared"),
        pl.col("abs_diff").max().alias("max_abs_diff"),
        (pl.col("abs_diff") > tol).sum().alias("n_changed"),
        pl.col("date").filter(pl.col("abs_diff") > tol).min().alias("first_changed_date"),
    )
    dates_a = a.select("ticker", "date")
    dates_b = b.select("ticker", "date")
    added = (
        dates_b.join(dates_a, on=["ticker", "date"], how="anti")
        .group_by("ticker")
        .agg(pl.len().alias("dates_added"))
    )
    removed = (
        dates_a.join(dates_b, on=["ticker", "date"], how="anti")
        .group_by("ticker")
        .agg(pl.len().alias("dates_removed"))
    )
    tickers = pl.DataFrame({"ticker": sorted(set(a["ticker"]) | set(b["ticker"]))})
    out = (
        tickers.join(per, on="ticker", how="left")
        .join(added, on="ticker", how="left")
        .join(removed, on="ticker", how="left")
        .with_columns(
            pl.col("ticker").is_in(a["ticker"].unique().to_list()).alias("in_a"),
            pl.col("ticker").is_in(b["ticker"].unique().to_list()).alias("in_b"),
        )
        .with_columns(pl.col("dates_added", "dates_removed", "n_changed").fill_null(0))
        .sort("ticker")
    )
    both = out.filter(pl.col("in_a") & pl.col("in_b"))
    summary = {
        "tickers_in_both": both.height,
        "tickers_only_a": int((out["in_a"] & ~out["in_b"]).sum()),
        "tickers_only_b": int((~out["in_a"] & out["in_b"]).sum()),
        "tickers_with_changed_returns": int((both["n_changed"] > 0).sum()),
        "tickers_with_removed_dates": int((both["dates_removed"] > 0).sum()),
        "returns_compared": int(both["n_compared"].fill_null(0).sum()),
        "returns_changed": int(both["n_changed"].sum()),
    }
    return out, summary


def render_markdown(
    snapshot_id: str,
    cov: pl.DataFrame,
    no_ticker: pl.DataFrame,
    summary: dict[str, int],
    compare: tuple[str, pl.DataFrame, dict[str, int]] | None = None,
    by_year: pl.DataFrame | None = None,
) -> str:
    lines = [f"# Informe de cobertura: precios de Yahoo, instantánea `{snapshot_id}`", ""]
    lines += [
        "Todo resultado con estos datos lleva la etiqueta **con sesgo de supervivencia**.",
        "",
    ]
    lines += ["## Resumen", "", "| Medida | Valor |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    if by_year is not None:
        lines += ["", "## Miembros con precio a 30 de junio de cada año", ""]
        lines += ["| Año | Miembros | Con precio | Cuota |", "|---|---|---|---|"]
        for r in by_year.iter_rows(named=True):
            share = "" if r["share_priced"] is None else f"{r['share_priced']:.0%}"
            lines.append(f"| {r['year']} | {r['n_members']} | {r['n_priced']} | {share} |")
    lines += ["", "## Empresas del periodo usable sin ticker", ""]
    lines += [f"- `{r}`" for r in no_ticker["company_id"].to_list()] or ["- (ninguna)"]
    problems = cov.filter(~pl.col("identity").is_in(["ok"]))
    lines += ["", "## Tickers que no cubren la ventana de pertenencia", ""]
    lines += ["| Empresa | Ticker | Estado | Detalle |", "|---|---|---|---|"]
    for r in problems.iter_rows(named=True):
        lines.append(
            f"| {r['company_id']} | {r['ticker']} | {r['identity']} | {r['identity_detail']} |"
        )
    gaps = cov.filter(pl.col("n_gaps") > 0)
    lines += ["", f"## Huecos de fechas (> {GAP_DAYS} días naturales entre sesiones)", ""]
    lines += [
        "| Ticker | Huecos | Máximo (días) | Cierres nulos | Fechas duplicadas |",
        "|---|---|---|---|---|",
    ]
    for r in gaps.iter_rows(named=True):
        lines.append(
            f"| {r['ticker']} | {r['n_gaps']} | {r['max_gap_days']} | {r['n_null_close']} "
            f"| {r['n_duplicate_dates']} |"
        )
    if compare:
        other, per, csum = compare
        lines += ["", f"## Regresión de retornos frente a `{other}`", ""]
        lines += ["| Medida | Valor |", "|---|---|"] + [f"| {k} | {v} |" for k, v in csum.items()]
        changed = per.filter(pl.col("n_changed") > 0)
        lines += ["", f"Tickers con retornos distintos (> {RETURN_TOL:.0e}):", ""]
        lines += [
            "| Ticker | Retornos distintos | Diferencia máxima | Primera fecha |",
            "|---|---|---|---|",
        ]
        for r in changed.iter_rows(named=True):
            lines.append(
                f"| {r['ticker']} | {r['n_changed']} | {r['max_abs_diff']:.3g} "
                f"| {r['first_changed_date']} |"
            )
    return "\n".join(lines) + "\n"
