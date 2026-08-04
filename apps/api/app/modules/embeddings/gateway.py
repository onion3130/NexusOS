"""Provider-neutral, bounded embedding gateway."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import AsyncNetworkBackend, AsyncNetworkStream

from app.core.config import Settings
from app.modules.embeddings.schemas import EmbeddingBatch, EmbeddingDisabledError, EmbeddingProviderError


def _safe_provider_target(url: str) -> str:
    """Reject local/reserved embedding targets and return a validated address."""
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password:
        raise EmbeddingProviderError()
    if hostname.lower() in {"localhost", "localhost.localdomain", "metadata.google.internal"}:
        raise EmbeddingProviderError()
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if any((literal.is_private, literal.is_loopback, literal.is_link_local, literal.is_multicast, literal.is_reserved, literal.is_unspecified)):
            raise EmbeddingProviderError()
        return str(literal)
    try:
        addresses = {record[4][0] for record in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise EmbeddingProviderError() from exc
    if not addresses:
        raise EmbeddingProviderError()
    for address in addresses:
        parsed_address = ipaddress.ip_address(address)
        if any((parsed_address.is_private, parsed_address.is_loopback, parsed_address.is_link_local, parsed_address.is_multicast, parsed_address.is_reserved, parsed_address.is_unspecified)):
            raise EmbeddingProviderError()
    return sorted(addresses)[0]


class _PinnedNetworkBackend(AsyncNetworkBackend):
    """Connect to the address validated before the HTTP request."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._backend = AutoBackend()

    async def connect_tcp(self, host: str, port: int, timeout: float | None = None, local_address: str | None = None, socket_options=None) -> AsyncNetworkStream:
        """Avoid a second DNS lookup that could permit DNS rebinding."""
        return await self._backend.connect_tcp(self._address, port, timeout, local_address, socket_options)


class _PinnedTransport(httpx.AsyncBaseTransport):
    """HTTPX transport that preserves the original URL for Host/SNI."""

    def __init__(self, address: str, max_response_bytes: int) -> None:
        self._max_response_bytes = max_response_bytes
        self._pool = httpcore.AsyncConnectionPool(network_backend=_PinnedNetworkBackend(address), retries=0, max_connections=1, max_keepalive_connections=0)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Read the response through a bounded streaming buffer."""
        core_request = httpcore.Request(
            method=request.method.encode("ascii"),
            url=httpcore.URL(str(request.url)),
            headers=[(key.encode("ascii"), value.encode("latin-1")) for key, value in request.headers.multi_items()],
            content=request.content,
        )
        core_response = await self._pool.handle_async_request(core_request)
        try:
            body = bytearray()
            async for chunk in core_response.aiter_stream():
                body.extend(chunk)
                if len(body) > self._max_response_bytes:
                    raise EmbeddingProviderError()
            if not 200 <= core_response.status < 300:
                raise EmbeddingProviderError()
            return httpx.Response(status_code=core_response.status, headers=core_response.headers, content=bytes(body), request=request)
        finally:
            await core_response.aclose()

    async def aclose(self) -> None:
        """Close the pinned connection pool."""
        await self._pool.aclose()


class EmbeddingGateway:
    """Interface for configured embedding providers."""

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        """Return one vector per bounded input text."""
        raise NotImplementedError


class DisabledEmbeddingGateway(EmbeddingGateway):
    """Safe default that never contacts an upstream service."""

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        raise EmbeddingDisabledError()


class OpenAICompatibleEmbeddingGateway(EmbeddingGateway):
    """Call an OpenAI-compatible embeddings endpoint with bounded payloads."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not self.settings.embedding_base_url or not self.settings.embedding_api_key or not self.settings.embedding_model:
            raise EmbeddingProviderError()
        address = await asyncio.to_thread(_safe_provider_target, self.settings.embedding_base_url)
        payload: dict[str, Any] = {"model": self.settings.embedding_model, "input": texts[: self.settings.embedding_batch_size]}
        headers = {"Authorization": f"Bearer {self.settings.embedding_api_key.get_secret_value()}", "Content-Type": "application/json"}
        try:
            transport = _PinnedTransport(address, self.settings.embedding_max_response_bytes)
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.settings.embedding_timeout_seconds), transport=transport, follow_redirects=False, trust_env=False) as client:
                response = await client.post(self.settings.embedding_base_url, json=payload, headers=headers)
                body = response.json()
        except (httpx.TimeoutException, httpx.HTTPError, ValueError, TypeError) as exc:
            raise EmbeddingProviderError() from exc
        raw_items = body.get("data") if isinstance(body, dict) else None
        if not isinstance(raw_items, list) or len(raw_items) != len(texts):
            raise EmbeddingProviderError()
        vectors: list[list[float]] = []
        for item in raw_items:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or not vector or len(vector) > self.settings.embedding_max_dimensions or not all(isinstance(value, (int, float)) and value == value for value in vector):
                raise EmbeddingProviderError()
            vectors.append([float(value) for value in vector])
        return EmbeddingBatch(vectors=vectors, provider=self.settings.embedding_provider, model=self.settings.embedding_model)


def embedding_gateway_from_settings(settings: Settings) -> EmbeddingGateway:
    """Construct only a configured embedding provider."""
    if settings.embedding_provider == "disabled":
        return DisabledEmbeddingGateway()
    if settings.embedding_provider in {"openai", "openai_compatible", "nvidia_nim"}:
        return OpenAICompatibleEmbeddingGateway(settings)
    raise EmbeddingProviderError()
