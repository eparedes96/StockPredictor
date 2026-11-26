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

    p10 = sub.add_parser(
        "report-p1-0",
        help="Informe P1-0: N_eff, error típico del RankIC, MDE y permutación solo con precios.",
    )
    p10.add_argument("--snapshot", required=True, help="instantánea de Yahoo con tablas Parquet")
    p10.add_argument("--raw-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    p10.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "informes" / "p1_0")
    p10.add_argument("--permutations", type=int, default=1000)
    p10.add_argument("--seed", type=int, default=20261126)
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


def _cmd_report_p1_0(args: argparse.Namespace) -> int:
    from stockpredictor.evaluation import p1_0
    from stockpredictor.universe import membership

    _setup_logging(None)
    log = logging.getLogger("stockpredictor.cli")
    prices, sha = p1_0.load_prices_verified(args.raw_dir, args.snapshot)
    intervals = membership.build_membership_intervals(
        membership.load_events(), membership.load_code_map()
    )
    params = p1_0.Params.from_configs(n_perm=args.permutations, seed=args.seed)
    meta = {"snapshot_id": args.snapshot, "prices_sha256": sha}
    res = p1_0.run(prices, intervals, membership.prices_from(), params, meta)
    p1_0.write_outputs(res, args.out_dir)
    log.info("informe en %s", args.out_dir / "informe.md")
    print(res.summary)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "extract-prices-yahoo":
        return _cmd_extract(args)
    if args.command == "report-prices-yahoo":
        return _cmd_report(args)
    if args.command == "report-p1-0":
        return _cmd_report_p1_0(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
