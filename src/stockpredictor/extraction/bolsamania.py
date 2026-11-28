"""Descarga de históricos de precios de Bolsamanía (``/accion/<slug>/historico-precios``) a ``raw``.

Complementa a Yahoo (ADR 0034): da el ``Close`` real sin ajustar (columna ``Precio``), sin volumen,
desde 2006-11-30 como pronto, para las empresas que Yahoo no tiene (deslistadas) y para el
diagnóstico del cociente real/Yahoo. Reglas de ``raw`` como en Yahoo (ADR 0033): límite de tasa,
backoff ante 429/5xx, parada ante respuestas anómalas (sin evasión de controles), caché por
instantánea y archivos inmutables con manifiesto y sha256.

Unidad de descarga: un **tramo** ``(slug, desde, hasta)``. La web devuelve como mucho ~85 filas
(las más recientes del rango), así que se piden tramos de ``CHUNK_DAYS`` días; un tramo que
devuelva ``>= ROW_CAP`` filas se parte por la mitad (nunca se acepta un tramo posiblemente
truncado). El HTML de cada respuesta se guarda comprimido (gzip determinista, ``html/``).
"""

from __future__ import annotations

import datetime as dt
import gzip
import logging
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import requests

from stockpredictor.extraction.bolsamania_parse import BolsamaniaParseError, parse_history
from stockpredictor.extraction.manifest import (
    MANIFEST_NAME,
    ManifestRow,
    append_row,
    latest_by_ticker,
    sha256_bytes,
    write_immutable,
)
from stockpredictor.extraction.yahoo import HttpResult, RunAborted

log = logging.getLogger("stockpredictor.extraction.bolsamania")

PROVIDER = "bolsamania_historico"
BASE_URL = "https://www.bolsamania.com/accion/{slug}/historico-precios"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)
SOURCE_FLOOR = dt.date(2006, 11, 1)  # la serie más antigua observada empieza el 2006-11-30
CHUNK_DAYS = 92  # ~63 sesiones; muy por debajo del tope de ~85 filas
ROW_CAP = 80  # observado: 79-83 filas en rangos largos; >= ROW_CAP se considera posible truncado
MIN_SPLIT_DAYS = 2
DONE_STATUSES = {
    "ok",
    "empty",
    "slug_not_found",
    "no_history",
}  # no se vuelven a pedir en la instantánea

Transport = Callable[[str, dict[str, str]], HttpResult]


@dataclass(frozen=True)
class BolsamaniaSettings:
    min_interval: float = 2.0
    jitter: float = 0.3
    max_retries: int = 4
    backoff_base: float = 30.0
    backoff_max: float = 300.0
    max_consecutive_errors: int = 3


@dataclass(frozen=True)
class Job:
    """Un slug con su ventana de descarga. ``purpose`` es ``gap_fill`` o ``comparison``."""

    company_id: str
    slug: str
    start: dt.date
    end: dt.date
    purpose: str = "gap_fill"


@dataclass
class FetchOutcome:
    status: str  # ok | error | rate_limited
    http_status: int | None
    body: bytes
    attempts: int
    error: str = ""


def requests_transport(timeout: float = 30.0) -> Transport:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})

    def post(url: str, form: dict[str, str]) -> HttpResult:
        resp = session.post(url, data=form, timeout=timeout)
        return HttpResult(resp.status_code, resp.content, dict(resp.headers))

    return post


def history_url(slug: str) -> str:
    return BASE_URL.format(slug=quote(slug, safe="-"))


def chunk_key(slug: str, start: dt.date, end: dt.date) -> str:
    return f"{slug}@{start.isoformat()}..{end.isoformat()}"


def plan_chunks(
    start: dt.date, end: dt.date, days: int = CHUNK_DAYS
) -> list[tuple[dt.date, dt.date]]:
    """Tramos contiguos y disjuntos que cubren ``[start, end]`` (extremos incluidos)."""
    out: list[tuple[dt.date, dt.date]] = []
    cur = start
    while cur <= end:
        stop = min(cur + dt.timedelta(days=days - 1), end)
        out.append((cur, stop))
        cur = stop + dt.timedelta(days=1)
    return out


def snapshot_dir(raw_dir: Path, snapshot_id: str) -> Path:
    return raw_dir / "prices" / "bolsamania" / snapshot_id


class BolsamaniaClient:
    def __init__(
        self,
        transport: Transport | None = None,
        settings: BolsamaniaSettings | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.transport = transport or requests_transport()
        self.settings = settings or BolsamaniaSettings()
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

    def fetch(self, slug: str, start: dt.date, end: dt.date) -> FetchOutcome:
        """POST del formulario de fechas con límite de tasa y backoff; no lanza por errores HTTP."""
        form = {"startDate": start.isoformat(), "endDate": end.isoformat(), "output": ""}
        url = history_url(slug)
        attempts = 0
        last_status: int | None = None
        last_body = b""
        last_error = ""
        while attempts <= self.settings.max_retries:
            self._throttle()
            attempts += 1
            retry_after: str | None = None
            try:
                res = self.transport(url, form)
            except requests.RequestException as exc:
                last_status, last_body, last_error = None, b"", f"red: {type(exc).__name__}"
            else:
                last_status, last_body = res.status, res.body
                if res.status == 200:
                    return FetchOutcome("ok", 200, res.body, attempts)
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


@dataclass
class RunSummary:
    requested: int = 0
    cached: int = 0
    ok: int = 0
    empty: int = 0
    slug_not_found: int = 0
    no_history: int = 0
    split: int = 0
    failed: int = 0
    aborted: str = ""
    skipped_jobs: list[str] = field(default_factory=list)


def _manifest_row(
    snapshot_id: str,
    job: Job,
    start: dt.date,
    end: dt.date,
    outcome: FetchOutcome,
    rel_file: str,
    stored: bytes,
    status: str,
    n_rows: int | None,
    first: str,
    last: str,
    error: str,
) -> ManifestRow:
    return ManifestRow(
        snapshot_id=snapshot_id,
        ticker=chunk_key(job.slug, start, end),  # clave del tramo (la última fila manda)
        company_id=job.company_id,
        provider=PROVIDER,
        url=history_url(job.slug),
        downloaded_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        http_status=outcome.http_status,
        status=status,
        file=rel_file,
        sha256=sha256_bytes(stored) if rel_file else "",
        bytes=len(stored) if rel_file else None,
        n_rows=n_rows,
        first_date=first,
        last_date=last,
        currency="EUR" if n_rows else "",
        exchange="",
        long_name="",
        attempts=outcome.attempts,
        error=error,
    )


def _classify(outcome: FetchOutcome) -> tuple[str, int | None, str, str, str]:
    """(estado, filas, primera fecha, última fecha, error) a partir de la respuesta."""
    if outcome.status != "ok":
        return outcome.status, None, "", "", outcome.error
    try:
        parsed = parse_history(outcome.body.decode("utf8", errors="replace"))
    except BolsamaniaParseError as exc:
        return "error", None, "", "", f"respuesta anómala: {exc}"
    if parsed.page_status != "ok":
        return parsed.page_status, 0, "", "", ""
    return (
        "ok",
        parsed.n_rows,
        str(parsed.prices["date"].min()),
        str(parsed.prices["date"].max()),
        "",
    )


def download_snapshot(
    jobs: Sequence[Job],
    raw_dir: Path,
    snapshot_id: str,
    client: BolsamaniaClient,
    *,
    row_cap: int = ROW_CAP,
) -> RunSummary:
    """Descarga los tramos de cada ``Job`` (reanudable). Para ante bloqueo (``RunAborted``)."""
    sdir = snapshot_dir(raw_dir, snapshot_id)
    manifest = sdir / MANIFEST_NAME
    done = latest_by_ticker(manifest)
    summary = RunSummary()
    consecutive_errors = 0
    for j_idx, job in enumerate(jobs, 1):
        pending = list(plan_chunks(job.start, job.end))
        pending.reverse()  # pila: se procesa en orden cronológico
        slug_missing = False
        while pending:
            start, end = pending.pop()
            key = chunk_key(job.slug, start, end)
            prev = done.get(key)
            if prev and prev["status"] in DONE_STATUSES:
                summary.cached += 1
                if prev["status"] in {"slug_not_found", "no_history"}:
                    slug_missing = True
                    break
                continue
            summary.requested += 1
            outcome = client.fetch(job.slug, start, end)
            status, n_rows, first, last, error = _classify(outcome)
            if status == "ok" and (n_rows or 0) >= row_cap and (end - start).days >= MIN_SPLIT_DAYS:
                # Posible truncado: no se guarda como bueno; se parte por la mitad.
                mid = start + (end - start) // 2
                summary.split += 1
                log.info("%s: %s filas (>= %d), se parte en dos", key, n_rows, row_cap)
                pending.append((mid + dt.timedelta(days=1), end))
                pending.append((start, mid))
                continue
            rel = ""
            stored = b""
            if outcome.body:
                stored = gzip.compress(outcome.body, mtime=0)
                rel = f"html/{job.slug}.{start.isoformat()}.{end.isoformat()}.{status}.html.gz"
                try:
                    write_immutable(sdir / rel, stored)
                except FileExistsError:
                    rel = rel.replace(".html.gz", f".{sha256_bytes(stored)[:8]}.html.gz")
                    write_immutable(sdir / rel, stored)
            append_row(
                manifest,
                _manifest_row(
                    snapshot_id,
                    job,
                    start,
                    end,
                    outcome,
                    rel,
                    stored,
                    status,
                    n_rows,
                    first,
                    last,
                    error,
                ),
            )
            if status in DONE_STATUSES:
                consecutive_errors = 0
                setattr(summary, status, getattr(summary, status) + 1)
                log.info("[job %d/%d] %s: %s (%s filas)", j_idx, len(jobs), key, status, n_rows)
                if status in {"slug_not_found", "no_history"}:
                    slug_missing = True
                    break
            else:
                summary.failed += 1
                consecutive_errors += 1
                log.error("[job %d/%d] %s: %s (%s)", j_idx, len(jobs), key, status, error)
                if status == "rate_limited" or consecutive_errors >= (
                    client.settings.max_consecutive_errors
                ):
                    summary.aborted = error or status
                    raise RunAborted(
                        f"parada tras {status} en {key} ({error}); "
                        f"relanzar con --snapshot {snapshot_id} para reanudar",
                        summary,  # type: ignore[arg-type]
                    )
        if slug_missing:
            summary.skipped_jobs.append(f"{job.company_id}:{job.slug}")
    return summary
