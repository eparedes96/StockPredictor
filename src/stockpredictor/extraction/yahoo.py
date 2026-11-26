"""Descarga de precios diarios de Yahoo (endpoint ``chart``) a ``data/raw``.

Reglas (CLAUDE.md §1, ADR 0010 y 0033): límite de tasa, reintentos con backoff ante 429, parada ante
respuestas anómalas (sin reintentos infinitos, sin rotar IP, sin saltarse controles), caché por
instantánea (lo ya descargado no se vuelve a pedir) y ``raw`` inmutable con manifiesto.

Diseño: una instantánea es el directorio ``<raw>/prices/yahoo/<snapshot_id>/`` con la respuesta
JSON de cada ticker (``chart/<ticker>.json``, byte a byte) y ``manifest.csv``. La descarga es
reanudable: se relanza con el mismo ``snapshot_id``.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

from stockpredictor.extraction.manifest import (
    MANIFEST_NAME,
    ManifestRow,
    append_row,
    latest_by_ticker,
    sha256_bytes,
    write_immutable,
)
from stockpredictor.extraction.yahoo_parse import ChartParseError, parse_chart

log = logging.getLogger("stockpredictor.extraction.yahoo")

PROVIDER = "yahoo_chart_v8"
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)
DONE_STATUSES = {"ok", "not_found"}  # no se vuelven a pedir en la misma instantánea


class RunAborted(RuntimeError):
    """Parada deliberada ante bloqueo o respuestas anómalas; la instantánea queda reanudable."""

    def __init__(self, message: str, summary: RunSummary | None = None) -> None:
        super().__init__(message)
        self.summary = summary


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


Transport = Callable[[str], HttpResult]


def requests_transport(timeout: float = 30.0) -> Transport:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    def get(url: str) -> HttpResult:
        resp = session.get(url, timeout=timeout)
        return HttpResult(resp.status_code, resp.content, dict(resp.headers))

    return get


@dataclass(frozen=True)
class YahooSettings:
    min_interval: float = 2.0  # segundos entre peticiones (la prueba previa aguantó ~40 a ~2 s)
    jitter: float = 0.3
    max_retries: int = 4  # reintentos por ticker ante 429, 5xx o error de red
    backoff_base: float = 30.0
    backoff_max: float = 300.0
    max_consecutive_errors: int = 3  # errores seguidos (tras reintentos) que detienen la ejecución
    period2: int | None = None  # fin de la ventana (epoch); None = ahora


@dataclass(frozen=True)
class Target:
    ticker: str
    company_id: str


@dataclass
class FetchOutcome:
    status: str  # ok | not_found | error | rate_limited
    http_status: int | None
    body: bytes
    attempts: int
    error: str = ""


def chart_url(ticker: str, period2: int) -> str:
    params = {
        "period1": 0,
        "period2": period2,
        "interval": "1d",
        "events": "div,split",  # 'split' en singular: con 'splits' no devuelve nada (P1.2)
        "includeAdjustedClose": "true",
    }
    return f"{BASE_URL}{quote(ticker, safe='')}?{urlencode(params)}"


def safe_name(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", ticker)


class YahooClient:
    def __init__(
        self,
        transport: Transport | None = None,
        settings: YahooSettings | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.transport = transport or requests_transport()
        self.settings = settings or YahooSettings()
        self._sleep = sleep
        self._monotonic = monotonic
        self._rng = rng or random.Random(0)
        self._last_request: float | None = None

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.settings.min_interval + self._rng.uniform(0, self.settings.jitter)
            remaining = wait - (self._monotonic() - self._last_request)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request = self._monotonic()

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        delay = min(self.settings.backoff_base * 2**attempt, self.settings.backoff_max)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), self.settings.backoff_max))
        return delay

    def fetch(self, url: str) -> FetchOutcome:
        """Pide ``url`` con límite de tasa y backoff. No lanza por 404 ni por errores agotados."""
        attempts = 0
        last_status: int | None = None
        last_body = b""
        last_error = ""
        while attempts <= self.settings.max_retries:
            self._throttle()
            attempts += 1
            retry_after: str | None = None
            try:
                res = self.transport(url)
            except requests.RequestException as exc:
                last_status, last_body, last_error = None, b"", f"red: {type(exc).__name__}"
            else:
                last_status, last_body = res.status, res.body
                if res.status == 200:
                    return FetchOutcome("ok", 200, res.body, attempts)
                if res.status == 404:
                    return FetchOutcome("not_found", 404, res.body, attempts)
                retry_after = res.headers.get("Retry-After")
                last_error = f"HTTP {res.status}"
                if res.status != 429 and res.status < 500:
                    return FetchOutcome("error", res.status, res.body, attempts, last_error)
            if attempts > self.settings.max_retries:
                break
            delay = self._backoff(attempts - 1, retry_after)
            log.warning("%s; reintento %d en %.0f s", last_error, attempts, delay)
            self._sleep(delay)
        status = "rate_limited" if last_status == 429 else "error"
        return FetchOutcome(status, last_status, last_body, attempts, last_error)


def _row_from_outcome(
    snapshot_id: str, target: Target, url: str, outcome: FetchOutcome, rel_file: str
) -> ManifestRow:
    n_rows: int | None = None
    first = last = currency = exchange = long_name = ""
    status, error = outcome.status, outcome.error
    if outcome.status == "ok":
        try:
            parsed = parse_chart(outcome.body)
        except ChartParseError as exc:
            status, error = "error", f"respuesta anómala: {exc}"
        else:
            if parsed.error_code == "Not Found":
                status = "not_found"
            elif parsed.error_code:
                status, error = "error", f"chart.error: {parsed.error_code}"
            else:
                n_rows = parsed.prices.height
                if n_rows:
                    first = str(parsed.prices["date"].min())
                    last = str(parsed.prices["date"].max())
                meta = parsed.meta
                currency = str(meta.get("currency") or "")
                exchange = str(meta.get("exchangeName") or "")
                long_name = str(meta.get("longName") or meta.get("shortName") or "")
    return ManifestRow(
        snapshot_id=snapshot_id,
        ticker=target.ticker,
        company_id=target.company_id,
        provider=PROVIDER,
        url=url,
        downloaded_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        http_status=outcome.http_status,
        status=status,
        file=rel_file,
        sha256=sha256_bytes(outcome.body) if rel_file else "",
        bytes=len(outcome.body) if rel_file else None,
        n_rows=n_rows,
        first_date=first,
        last_date=last,
        currency=currency,
        exchange=exchange,
        long_name=long_name,
        attempts=outcome.attempts,
        error=error,
    )


def snapshot_dir(raw_dir: Path, snapshot_id: str) -> Path:
    return raw_dir / "prices" / "yahoo" / snapshot_id


@dataclass
class RunSummary:
    requested: int = 0
    cached: int = 0
    ok: int = 0
    not_found: int = 0
    failed: int = 0
    aborted: str = ""


def download_snapshot(
    targets: Sequence[Target],
    raw_dir: Path,
    snapshot_id: str,
    client: YahooClient,
    *,
    now: Callable[[], float] = time.time,
) -> RunSummary:
    """Descarga ``targets`` a la instantánea; salta los ya hechos y para ante bloqueo.

    Lanza ``RunAborted`` (con la instantánea intacta y reanudable) si Yahoo sigue dando 429 tras
    los reintentos, o tras ``max_consecutive_errors`` errores seguidos.
    """
    sdir = snapshot_dir(raw_dir, snapshot_id)
    manifest = sdir / MANIFEST_NAME
    done = latest_by_ticker(manifest)
    period2 = client.settings.period2 or int(now())
    summary = RunSummary()
    consecutive_errors = 0
    total = len(targets)
    for i, target in enumerate(targets, 1):
        prev = done.get(target.ticker)
        if prev and prev["status"] in DONE_STATUSES:
            summary.cached += 1
            log.info(
                "[%d/%d] %s: ya descargado (%s), se omite", i, total, target.ticker, prev["status"]
            )
            continue
        url = chart_url(target.ticker, period2)
        summary.requested += 1
        outcome = client.fetch(url)
        rel = ""
        if outcome.body:
            rel = f"chart/{safe_name(target.ticker)}.{snapshot_id}.{outcome.status}.json"
            try:
                write_immutable(sdir / rel, outcome.body)
            except FileExistsError:
                rel = rel.replace(".json", f".{sha256_bytes(outcome.body)[:8]}.json")
                write_immutable(sdir / rel, outcome.body)
        row = _row_from_outcome(snapshot_id, target, url, outcome, rel)
        append_row(manifest, row)
        if row.status == "ok":
            summary.ok += 1
            consecutive_errors = 0
            log.info(
                "[%d/%d] %s ok: %s filas, %s a %s (%s)",
                i, total, target.ticker, row.n_rows, row.first_date, row.last_date, row.long_name,
            )  # fmt: skip
        elif row.status == "not_found":
            summary.not_found += 1
            consecutive_errors = 0
            log.info("[%d/%d] %s: 404 (sin datos en Yahoo)", i, total, target.ticker)
        else:
            summary.failed += 1
            consecutive_errors += 1
            log.error("[%d/%d] %s: %s (%s)", i, total, target.ticker, row.status, row.error)
            if row.status == "rate_limited" or consecutive_errors >= (
                client.settings.max_consecutive_errors
            ):
                summary.aborted = row.error or row.status
                raise RunAborted(
                    f"parada tras {row.status} en {target.ticker} ({row.error}); "
                    f"relanzar con --snapshot {snapshot_id} para reanudar",
                    summary,
                )
    return summary
