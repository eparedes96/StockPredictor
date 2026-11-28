"""Punto de entrada de terminal. Cada etapa del pipeline es un subcomando (ADR 0015)."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from stockpredictor import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stockpredictor",
        description="Predicción de retorno absoluto a N días (investigación cuantitativa).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    ext = sub.add_parser(
        "extract-prices-yahoo",
        help="Descarga los precios diarios de Yahoo de las empresas del IBEX 35 a data/raw.",
    )
    ext.add_argument("--snapshot", help="id de la instantánea (por defecto, la fecha UTC de hoy)")
    ext.add_argument("--raw-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    ext.add_argument("--tickers", nargs="+", help="solo estos tickers o company_id")
    ext.add_argument("--limit", type=int, help="solo los N primeros (pruebas)")
    ext.add_argument("--min-interval", type=float, default=2.0, help="segundos entre peticiones")
    ext.add_argument("--max-retries", type=int, default=4)
    ext.add_argument("--dry-run", action="store_true", help="lista lo que se pediría y sale")

    rep = sub.add_parser(
        "report-prices-yahoo",
        help="Tablas Parquet e informe de cobertura de una instantánea (sin red).",
    )
    rep.add_argument("--snapshot", required=True)
    rep.add_argument("--compare", help="otra instantánea para la regresión de retornos")
    rep.add_argument("--raw-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    rep.add_argument(
        "--as-of", type=dt.date.fromisoformat, help="fecha de la descarga (AAAA-MM-DD)"
    )

    bol = sub.add_parser(
        "extract-prices-bolsamania",
        help="Descarga el Close real de Bolsamanía (huecos de Yahoo y comparación) a data/raw.",
    )
    bol.add_argument("--snapshot", help="id de la instantánea (por defecto, la fecha UTC de hoy)")
    bol.add_argument("--raw-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    bol.add_argument(
        "--group",
        choices=["gap_fill", "comparison", "all"],
        default="gap_fill",
        help="gap_fill: empresas sin datos en Yahoo; comparison: empresas con las dos series",
    )
    bol.add_argument("--only", nargs="+", help="solo estos company_id o slugs")
    bol.add_argument("--comparison-end", type=dt.date.fromisoformat, default=dt.date(2014, 12, 31))
    bol.add_argument("--min-interval", type=float, default=2.0, help="segundos entre peticiones")
    bol.add_argument("--max-retries", type=int, default=4)
    bol.add_argument("--dry-run", action="store_true", help="lista los trabajos y sale")

    brep = sub.add_parser(
        "report-prices-bolsamania",
        help="Tabla Parquet, cobertura y diagnóstico del cociente real/Yahoo (sin red).",
    )
    brep.add_argument("--snapshot", required=True)
    brep.add_argument("--yahoo-snapshot", required=True, help="instantánea de Yahoo a comparar")
    brep.add_argument("--raw-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    brep.add_argument("--yahoo-raw-dir", type=Path, help="raw de Yahoo si es otro directorio")
    brep.add_argument("--as-of", type=dt.date.fromisoformat, help="fecha de la descarga")
    brep.add_argument("--comparison-end", type=dt.date.fromisoformat, default=dt.date(2014, 12, 31))
    return parser


def _setup_logging(logfile: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if logfile:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(logfile, encoding="utf8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def session_may_be_open(now: dt.datetime | None = None) -> bool:
    """¿Está (o puede estar) abierta la sesión de Madrid? Lunes a viernes, 08:55 a 17:40 locales."""
    from zoneinfo import ZoneInfo

    local = (now or dt.datetime.now(dt.UTC)).astimezone(ZoneInfo("Europe/Madrid"))
    minutes = local.hour * 60 + local.minute
    return local.weekday() < 5 and 8 * 60 + 55 <= minutes <= 17 * 60 + 40


def _cmd_extract(args: argparse.Namespace) -> int:
    from stockpredictor.extraction import yahoo, yahoo_tickers

    snapshot = args.snapshot or dt.datetime.now(dt.UTC).date().isoformat()
    sdir = yahoo.snapshot_dir(args.raw_dir, snapshot)
    _setup_logging(None if args.dry_run else sdir / "run.log")
    table = yahoo_tickers.load_ticker_table()
    windows = yahoo_tickers.membership_windows()
    targets, no_ticker = yahoo_tickers.select_targets(
        table, windows, set(args.tickers) if args.tickers else None
    )
    if args.limit:
        targets = targets[: args.limit]
    log = logging.getLogger("stockpredictor.cli")
    if session_may_be_open():
        log.warning(
            "La Bolsa de Madrid puede estar abierta: Yahoo entrega la barra del día en curso "
            "sin cerrar. Mejor lanzar después de las 18:00 (hora de Madrid)."
        )
    log.info(
        "instantánea %s: %d tickers (%d empresas sin ticker conocido) -> %s",
        snapshot, len(targets), no_ticker.height, sdir,
    )  # fmt: skip
    if args.dry_run:
        for t in targets:
            print(f"{t.ticker}\t{t.company_id}")
        return 0
    client = yahoo.YahooClient(
        settings=yahoo.YahooSettings(min_interval=args.min_interval, max_retries=args.max_retries)
    )
    try:
        summary = yahoo.download_snapshot(targets, args.raw_dir, snapshot, client)
    except yahoo.RunAborted as exc:
        log.error("%s", exc)
        return 2
    log.info(
        "terminado: %d pedidos, %d en caché, %d ok, %d 404, %d fallos",
        summary.requested, summary.cached, summary.ok, summary.not_found, summary.failed,
    )  # fmt: skip
    return 0 if summary.failed == 0 else 1


def _cmd_report(args: argparse.Namespace) -> int:
    from stockpredictor.extraction import yahoo, yahoo_report, yahoo_tables, yahoo_tickers

    _setup_logging(None)
    log = logging.getLogger("stockpredictor.cli")
    info = yahoo_tables.build_tables(args.raw_dir, args.snapshot)
    log.info("tablas: %s", info)
    as_of = args.as_of or dt.date.today()
    table = yahoo_tickers.load_ticker_table()
    windows = yahoo_tickers.membership_windows(today=as_of)
    cov, no_ticker, summary = yahoo_report.coverage(
        args.raw_dir, args.snapshot, table, windows, as_of=as_of
    )
    compare = None
    if args.compare:
        yahoo_tables.build_tables(args.raw_dir, args.compare)
        per, csum = yahoo_report.compare_snapshots(args.raw_dir, args.compare, args.snapshot)
        compare = (args.compare, per, csum)
        per.write_csv(yahoo.snapshot_dir(args.raw_dir, args.snapshot) / "regression.csv")
    sdir = yahoo.snapshot_dir(args.raw_dir, args.snapshot)
    cov.write_csv(sdir / "coverage.csv")
    import polars as pl

    prices = pl.read_parquet(sdir / yahoo_tables.PRICES_FILE)
    by_year = yahoo_report.member_coverage_by_year(prices, last_year=as_of.year)
    by_year.write_csv(sdir / "member_coverage_by_year.csv")
    md = yahoo_report.render_markdown(args.snapshot, cov, no_ticker, summary, compare, by_year)
    (sdir / "coverage_report.md").write_text(md, encoding="utf8")
    print(md)
    return 0


def _cmd_extract_bolsamania(args: argparse.Namespace) -> int:
    from stockpredictor.extraction import bolsamania as bm
    from stockpredictor.extraction import bolsamania_slugs as bs
    from stockpredictor.extraction import yahoo_tickers

    snapshot = args.snapshot or dt.datetime.now(dt.UTC).date().isoformat()
    sdir = bm.snapshot_dir(args.raw_dir, snapshot)
    _setup_logging(None if args.dry_run else sdir / "run.log")
    log = logging.getLogger("stockpredictor.cli")
    as_of = dt.datetime.now(dt.UTC).date()
    purposes = {"gap_fill", "comparison"} if args.group == "all" else {args.group}
    jobs, skipped = bs.select_jobs(
        bs.load_slug_table(),
        yahoo_tickers.membership_windows(today=as_of),
        purposes=purposes,
        as_of=as_of,
        comparison_end=args.comparison_end,
        only=set(args.only) if args.only else None,
    )
    log.info(
        "instantánea %s: %d trabajos, %d omitidos -> %s", snapshot, len(jobs), len(skipped), sdir
    )
    for cid, why in skipped:
        log.info("omitida %s: %s", cid, why)
    if args.dry_run:
        for j in jobs:
            print(f"{j.company_id}\t{j.slug}\t{j.start}\t{j.end}\t{j.purpose}")
        return 0
    client = bm.BolsamaniaClient(
        settings=bm.BolsamaniaSettings(min_interval=args.min_interval, max_retries=args.max_retries)
    )
    try:
        summary = bm.download_snapshot(jobs, args.raw_dir, snapshot, client)
    except bm.RunAborted as exc:
        log.error("%s", exc)
        return 2
    log.info(
        "terminado: %d pedidos, %d en caché, %d ok, %d vacíos, %d partidos, %d slug inexistente, "
        "%d sin históricos, %d fallos",
        summary.requested, summary.cached, summary.ok, summary.empty, summary.split,
        summary.slug_not_found, summary.no_history, summary.failed,
    )  # fmt: skip
    return 0 if summary.failed == 0 else 1


def _cmd_report_bolsamania(args: argparse.Namespace) -> int:
    import polars as pl

    from stockpredictor.extraction import bolsamania as bm
    from stockpredictor.extraction import bolsamania_report as br
    from stockpredictor.extraction import bolsamania_slugs as bs
    from stockpredictor.extraction import yahoo, yahoo_tickers
    from stockpredictor.extraction.bolsamania_tables import build_tables

    _setup_logging(None)
    log = logging.getLogger("stockpredictor.cli")
    info = build_tables(args.raw_dir, args.snapshot)
    log.info("tablas: %s", info)
    as_of = args.as_of or dt.date.today()
    sdir = bm.snapshot_dir(args.raw_dir, args.snapshot)
    bolsa = br.load_prices(sdir)
    ydir = yahoo.snapshot_dir(args.yahoo_raw_dir or args.raw_dir, args.yahoo_snapshot)
    yprices = pl.read_parquet(ydir / "prices.parquet")
    windows = yahoo_tickers.membership_windows(today=as_of)
    slugs = bs.load_slug_table()
    jobs = slugs.select("company_id", pl.col("bolsamania_slug").alias("slug"), "purpose")
    jobs = jobs.filter(pl.col("company_id").is_in(windows["company_id"].to_list()))
    cov = br.coverage(bolsa, windows, sdir, jobs, as_of=as_of)
    gap = bolsa.filter(
        pl.col("company_id").is_in(slugs.filter(pl.col("purpose") == "gap_fill")["company_id"])
    )
    by_year = br.coverage_by_year_before_after(yprices, gap, last_year=as_of.year)
    summary, steps = br.ratio_diagnostic(
        bolsa.filter(pl.col("date") <= args.comparison_end), yprices
    )
    cov.write_csv(sdir / "coverage.csv")
    by_year.write_csv(sdir / "member_coverage_by_year.csv")
    summary.write_csv(sdir / "ratio_summary.csv")
    steps.write_csv(sdir / "ratio_steps.csv")
    md = br.render_markdown(args.snapshot, cov, by_year, (summary, steps, args.yahoo_snapshot))
    (sdir / "coverage_report.md").write_text(md, encoding="utf8")
    print(md)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "extract-prices-yahoo":
        return _cmd_extract(args)
    if args.command == "report-prices-yahoo":
        return _cmd_report(args)
    if args.command == "extract-prices-bolsamania":
        return _cmd_extract_bolsamania(args)
    if args.command == "report-prices-bolsamania":
        return _cmd_report_bolsamania(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
