"""Bounded, SSRF-safe URL source ingestion (v1.7).

URL sources are created as inert records; a dedicated ``source_fetch`` worker
job performs the actual fetch using a validated, DNS-rebinding-resistant pinned
transport (the same pattern the assistant and embedding gateways use). The
fetched bytes are stored under a server-generated name and then handed to the
existing ``source_ingest`` pipeline unchanged, so versioning, chunking,
retrieval, and lifecycle rules stay identical to text/Markdown sources.

Fetching is worker-only. The browser never performs the network request, and
every redirect hop is re-validated against the same public-target rules.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import re
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import AsyncNetworkBackend, AsyncNetworkStream
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import Job, Source
from app.modules.identity.service import add_audit_event
from app.modules.sources.schemas import SourceUrlCreate
from app.modules.sources.service import MAX_UPLOAD_BYTES, _safe_name, _source_root

FETCH_JOB_TYPE = "source_fetch"
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 30.0
MAX_URL_LENGTH = 2048
MAX_ATTEMPTS = 3
LEASE_SECONDS = 120
_USER_AGENT = "NexusOS/1.7 source-fetch (private, local-first)"
_ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/xhtml+xml": ".html",
    "text/html": ".html",
    "text/markdown": ".md",
    "text/plain": ".txt",
}
_SENSITIVE_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}


class _FetchTooLarge(Exception):
    """Internal marker raised by the bounded transport when a response is oversized."""


def _unsafe_address(address: str) -> bool:
    """Return whether an address belongs to a local or reserved network."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    return any(
        (
            parsed.is_private,
            parsed.is_loopback,
            parsed.is_link_local,
            parsed.is_multicast,
            parsed.is_reserved,
            parsed.is_unspecified,
        )
    )


def validate_fetch_url(raw: str) -> str:
    """Validate an HTTPS fetch target and return it normalized.

    HTTPS is required so fetched content cannot be altered or observed by a
    network intermediary; plaintext HTTP would allow a man-in-the-middle to
    inject untrusted material directly into the user's retrieval index. Used at
    request time for fast feedback and re-applied to every redirect hop before
    any bytes are read. Raises ``ValueError`` with a stable code.
    """
    normalized = raw.strip()
    if not normalized or len(normalized) > MAX_URL_LENGTH:
        raise ValueError("url_too_long")
    parsed = urlsplit(normalized)
    if parsed.scheme != "https":
        raise ValueError("url_scheme_not_allowed")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("url_missing_host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url_credentials_not_allowed")
    if hostname.lower() in _SENSITIVE_HOSTS:
        raise ValueError("url_target_not_allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and _unsafe_address(str(address)):
        raise ValueError("url_target_not_allowed")
    return normalized


def content_type_extension(content_type: str) -> str | None:
    """Return the server-owned extension for an allowlisted content type."""
    return _ALLOWED_CONTENT_TYPES.get(content_type.split(";")[0].strip().lower())


class _PinnedNetworkBackend(AsyncNetworkBackend):
    """Connect to a validated IP while httpcore retains the original origin."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._backend = AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ) -> AsyncNetworkStream:
        """Ignore the second DNS lookup and connect to the validated address."""
        return await self._backend.connect_tcp(self._address, port, timeout, local_address, socket_options)


class _PinnedTransport(httpx.AsyncBaseTransport):
    """Small httpx transport backed by a pinned httpcore connection pool."""

    def __init__(self, address: str, max_response_bytes: int) -> None:
        self._max_response_bytes = max_response_bytes
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=_PinnedNetworkBackend(address),
            retries=0,
            max_connections=1,
            max_keepalive_connections=0,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Forward one request while retaining the original URL hostname for TLS."""
        extensions = {}
        timeout = request.extensions.get("timeout")
        if timeout is not None:
            extensions["timeout"] = timeout
        core_request = httpcore.Request(
            method=request.method.encode("ascii"),
            url=httpcore.URL(str(request.url)),
            headers=[(key.encode("ascii"), value.encode("latin-1")) for key, value in request.headers.multi_items()],
            content=request.content,
            extensions=extensions,
        )
        core_response = await self._pool.handle_async_request(core_request)
        return httpx.Response(
            status_code=core_response.status,
            headers=core_response.headers,
            stream=_BoundedResponseStream(core_response, self._max_response_bytes),
            request=request,
        )

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._pool.aclose()


class _BoundedResponseStream(httpx.AsyncByteStream):
    """Bounded streaming adapter from httpcore to httpx."""

    def __init__(self, response: httpcore.Response, max_response_bytes: int) -> None:
        self._response = response
        self._max_response_bytes = max_response_bytes
        self._read = 0

    async def __aiter__(self):
        async for chunk in self._response.aiter_stream():
            self._read += len(chunk)
            if self._read > self._max_response_bytes:
                await self.aclose()
                raise _FetchTooLarge()
            yield chunk

    async def aclose(self) -> None:
        await self._response.aclose()


async def _resolve_public_address(url: str) -> str:
    """Resolve a hostname once and return exactly one safe address to pin."""
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if _unsafe_address(str(literal)):
            raise ValueError("url_target_not_allowed")
        return str(literal)
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except (OSError, ValueError, socket.gaierror) as exc:
        raise ValueError("url_resolve_failed") from exc
    addresses = {record[4][0] for record in records if record[4]}
    if not addresses or any(_unsafe_address(address) for address in addresses):
        raise ValueError("url_target_not_allowed")
    return sorted(addresses)[0]


async def _request_once(url: str, address: str) -> tuple[bytes, str, str | None]:
    """Fetch one hop with a pinned transport and return content, type, redirect."""
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,text/markdown,text/plain,application/pdf;q=0.9,*/*;q=0.1",
    }
    transport = _PinnedTransport(address, MAX_UPLOAD_BYTES)
    timeout = httpx.Timeout(FETCH_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False, trust_env=False) as client:
            async with asyncio.timeout(FETCH_TIMEOUT_SECONDS):
                response = await client.get(url, headers=headers)
                status = response.status_code
                if status in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    await response.aclose()
                    return b"", "", location
                try:
                    content = await response.aread()
                finally:
                    await response.aclose()
                if status != 200:
                    raise ValueError("url_fetch_failed")
                return content, response.headers.get("content-type", ""), None
    except asyncio.TimeoutError as exc:
        raise ValueError("url_fetch_timeout") from exc
    except httpx.TimeoutException as exc:
        raise ValueError("url_fetch_timeout") from exc
    except _FetchTooLarge as exc:
        raise ValueError("url_too_large") from exc
    except httpx.HTTPError as exc:
        raise ValueError("url_fetch_failed") from exc


async def _fetch_public_url(raw_url: str) -> tuple[str, bytes, str]:
    """Fetch one URL with full SSRF validation on every hop.

    Returns ``(final_url, content, content_type)`` or raises ``ValueError``
    with a stable code. The resolved address is pinned for the connection so a
    hostname cannot be re-resolved to an internal address after validation.
    """
    current = validate_fetch_url(raw_url)
    remaining = MAX_REDIRECTS
    while True:
        address = await _resolve_public_address(current)
        content, content_type, location = await _request_once(current, address)
        if location is None:
            return current, content, content_type
        if remaining <= 0:
            raise ValueError("url_too_many_redirects")
        remaining -= 1
        current = validate_fetch_url(urljoin(current, location))


def _extract_html_title(html: str) -> str | None:
    """Return a bounded document title without executing any markup."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"<[^>]+>", "", match.group(1))
    title = title.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    title = re.sub(r"\s+", " ", title).strip()
    return title[:160] if title else None


def _display_name(url: str, extension: str) -> str:
    """Derive a safe display name from the URL without accepting client paths.

    The name always ends in the server-derived extension so the ingestion
    parser can dispatch on it later.
    """
    parsed = urlsplit(url)
    basename = Path(parsed.path or "").name
    if basename and _safe_name(basename):
        return (basename[:255] if basename.lower().endswith(extension) else f"{basename[:240]}{extension}")[:255]
    host = (parsed.hostname or "source").replace(".", "-")[:64]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(parsed.path or "").name or "page")[:48] or "page"
    return f"{host}-{slug}{extension}"[:255]


def create_url_source(db: OrmSession, settings: Settings, user_id: str, payload: SourceUrlCreate) -> Source:
    """Create an inert URL source record and queue a worker fetch.

    The URL is validated at request time for fast feedback; the authoritative
    SSRF-safe fetch happens only in the worker.
    """
    url = validate_fetch_url(payload.url)
    title = (payload.title or "").strip() or None
    if len(url) > MAX_URL_LENGTH:
        raise ValueError("url_too_long")
    if db.query(Source).filter(Source.user_id == user_id, Source.deleted_at.is_(None)).count() >= 500:
        raise ValueError("source_quota_exceeded")
    existing = db.scalar(select(Source).where(Source.user_id == user_id, Source.kind == "url", Source.source_url == url, Source.deleted_at.is_(None)).order_by(Source.created_at.desc()).limit(1))
    if existing is not None:
        return existing
    source = Source(
        user_id=user_id,
        kind="url",
        title=(title or (parsed := urlsplit(url)).hostname or "URL source")[:160],
        original_name="",
        stored_path=f"pending-{user_id[:8]}.fetch",
        mime_type="",
        size_bytes=0,
        sha256="",
        status="processing",
        current_version=0,
        source_url=url,
    )
    db.add(source)
    db.flush()
    db.add(Job(job_type=FETCH_JOB_TYPE, status="queued", payload_json=source.id, available_at=utc_now(), idempotency_key=f"source-url:{source.id}"))
    add_audit_event(db, action="sources.url.create", result="success", actor_user_id=user_id, target=source.id, metadata={"scheme": urlsplit(url).scheme})
    db.commit()
    db.refresh(source)
    return source


def queue_source_fetch(db: OrmSession, source_id: str, *, idempotency_key: str | None = None) -> Job:
    """Queue one worker fetch for an existing URL source."""
    existing = db.scalar(select(Job).where(Job.job_type == FETCH_JOB_TYPE, Job.payload_json == source_id, Job.status.in_(("queued", "processing"))))
    if existing is not None:
        return existing
    job = Job(
        job_type=FETCH_JOB_TYPE,
        status="queued",
        payload_json=source_id,
        available_at=utc_now(),
        idempotency_key=idempotency_key or f"source-url:{source_id}:refetch",
    )
    db.add(job)
    db.flush()
    return job


def _claim_fetch_jobs(db: OrmSession, *, now: datetime, batch_size: int) -> list[Job]:
    jobs = db.scalars(
        select(Job)
        .where(Job.job_type == FETCH_JOB_TYPE, Job.status.in_(("queued", "processing")), Job.available_at <= now, Job.attempts < MAX_ATTEMPTS, (Job.locked_until.is_(None) | (Job.locked_until <= now)))
        .order_by(Job.created_at)
        .limit(max(1, min(batch_size, 4)))
    ).all()
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
        job.locked_until = now + timedelta(seconds=LEASE_SECONDS)
    if jobs:
        db.commit()
    return jobs


def _fetch_one(db: OrmSession, settings: Settings, job: Job, now: datetime) -> None:
    """Fetch one URL source and hand the bytes to the ingestion pipeline."""
    source = db.get(Source, job.payload_json or "")
    if source is None or source.deleted_at is not None or source.status == "archived":
        job.status = "completed"
        job.completed_at = now
        job.locked_until = None
        return
    try:
        if not source.source_url:
            raise ValueError("url_missing")
        final_url, content, content_type = asyncio.run(_fetch_public_url(source.source_url))
        extension = content_type_extension(content_type)
        if extension is None:
            raise ValueError("url_content_type_rejected")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("url_too_large")
        title = None
        if extension == ".html":
            try:
                title = _extract_html_title(content[: 64 * 1024].decode("utf-8", errors="replace"))
            except Exception:
                title = None
        name = _display_name(final_url, extension)
        destination = _source_root(settings) / f"{source.id}{extension}"
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex[:12]}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
        source.stored_path = destination.name
        source.original_name = name
        source.mime_type = content_type.split(";")[0].strip().lower()
        source.size_bytes = len(content)
        source.sha256 = hashlib.sha256(content).hexdigest()
        source.source_url = final_url
        if title:
            source.title = title[:160]
        source.status = "processing"
        source.last_error_code = None
        active_ingest = db.scalar(select(Job).where(Job.job_type == "source_ingest", Job.payload_json == source.id, Job.status.in_(("queued", "processing"))))
        if active_ingest is None:
            db.add(Job(job_type="source_ingest", status="queued", payload_json=source.id, available_at=now - timedelta(seconds=1), idempotency_key=f"source:{source.id}:url:{source.sha256}"))
        job.status = "completed"
        job.completed_at = now
        job.locked_until = None
        add_audit_event(db, action="sources.url.fetch", result="success", actor_user_id=source.user_id, target=source.id, metadata={"size_bytes": len(content), "mime_type": source.mime_type})
    except ValueError as exc:
        code = str(exc) if str(exc).startswith(("url_", "source_")) else "url_fetch_failed"
        _record_fetch_failure(db, job, source, code, now)
    except OSError:
        _record_fetch_failure(db, job, source, "url_store_failed", now)
    except RuntimeError:
        _record_fetch_failure(db, job, source, "url_fetch_failed", now)


def _record_fetch_failure(db: OrmSession, job: Job, source: Source | None, code: str, now: datetime) -> None:
    if source is not None:
        source.status = "failed"
        source.last_error_code = code
    job.last_error_code = code
    job.locked_until = None
    job.status = "failed" if job.attempts >= MAX_ATTEMPTS else "queued"
    job.available_at = now + timedelta(seconds=min(3600, 30 * (2 ** job.attempts)))
    if source is not None:
        add_audit_event(db, action="sources.url.fetch", result="failure", actor_user_id=source.user_id, target=source.id, metadata={"error_code": code})


def process_source_fetching(db: OrmSession, settings: Settings, *, batch_size: int = 2) -> int:
    """Claim and process a bounded set of URL fetch jobs with retry leases."""
    now = datetime.now(UTC)
    jobs = _claim_fetch_jobs(db, now=now, batch_size=batch_size)
    for job in jobs:
        _fetch_one(db, settings, job, now)
        db.commit()
    return len(jobs)
