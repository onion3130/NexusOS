"""Provider-neutral, bounded assistant gateway."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import AsyncNetworkBackend, AsyncNetworkStream

from app.core.config import Settings
from app.modules.assistant.schemas import (
    GatewayCompletion,
    GatewayMessage,
    ProposedToolCall,
    ProviderDisabledError,
    ProviderRequestError,
    ProviderTimeoutError,
    ToolDefinition,
)


class ModelGateway(ABC):
    """Interface implemented by server-selected model providers."""

    @abstractmethod
    async def complete(self, messages: list[GatewayMessage], tools: list[ToolDefinition]) -> GatewayCompletion:
        """Return one bounded normalized completion."""


class DisabledGateway(ModelGateway):
    """Explicit no-provider gateway used by the safe default configuration."""

    async def complete(self, messages: list[GatewayMessage], tools: list[ToolDefinition]) -> GatewayCompletion:
        """Reject calls without contacting any upstream service."""
        raise ProviderDisabledError()


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


async def _validate_provider_target(url: str) -> str:
    """Resolve a provider hostname and return one safe address to pin."""
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if not hostname or hostname.lower() in {"localhost", "localhost.localdomain", "metadata.google.internal"}:
        raise ProviderRequestError()
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if _unsafe_address(str(literal)):
            raise ProviderRequestError()
        return str(literal)
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except (OSError, ValueError, socket.gaierror) as exc:
        raise ProviderRequestError() from exc
    addresses = {record[4][0] for record in records if record[4]}
    if not addresses or any(_unsafe_address(address) for address in addresses):
        raise ProviderRequestError()
    return sorted(addresses)[0]


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
                if len(body) + len(chunk) > self._max_response_bytes:
                    raise ProviderRequestError()
                body.extend(chunk)
            if not 200 <= core_response.status < 300:
                raise ProviderRequestError()
            return httpx.Response(
                status_code=core_response.status,
                headers=core_response.headers,
                content=bytes(body),
                request=request,
            )
        finally:
            await core_response.aclose()

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._pool.aclose()


class OpenAICompatibleGateway(ModelGateway):
    """Call a fixed, server-configured OpenAI-compatible chat endpoint."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(self, messages: list[GatewayMessage], tools: list[ToolDefinition]) -> GatewayCompletion:
        """Send a bounded request and normalize only the supported response fields."""
        if not self.settings.ai_base_url or not self.settings.ai_api_key or not self.settings.ai_api_key.get_secret_value().strip():
            raise ProviderRequestError()
        address = await _validate_provider_target(self.settings.ai_base_url)
        payload: dict[str, Any] = {
            "model": self.settings.ai_model,
            "messages": [
                {
                    "role": item.role,
                    "content": item.content,
                    **({"tool_call_id": item.tool_call_id} if item.tool_call_id else {}),
                    **({"tool_calls": item.tool_calls} if item.tool_calls else {}),
                }
                for item in messages
            ],
            "temperature": 0.2,
            "max_tokens": self.settings.ai_max_output_tokens,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.key,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {self.settings.ai_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            timeout = httpx.Timeout(self.settings.ai_timeout_seconds)
            transport = _PinnedTransport(address, self.settings.ai_max_response_bytes)
            async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False, trust_env=False) as client:
                response = await client.post(self.settings.ai_base_url, json=payload, headers=headers)
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProviderRequestError() from exc
        return self._normalize(body)

    def _normalize(self, body: dict[str, Any]) -> GatewayCompletion:
        """Normalize a compatible response without retaining the raw payload."""
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderRequestError()
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderRequestError()
        content = message.get("content")
        normalized_content = content if isinstance(content, str) else ""
        proposed: list[ProposedToolCall] = []
        raw_calls = message.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            raise ProviderRequestError()
        for raw_call in raw_calls[:8]:
            if not isinstance(raw_call, dict):
                continue
            function = raw_call.get("function")
            if not isinstance(function, dict) or not isinstance(function.get("name"), str):
                continue
            raw_arguments = function.get("arguments", {})
            if isinstance(raw_arguments, str):
                try:
                    raw_arguments = json.loads(raw_arguments)
                except ValueError as exc:
                    raise ProviderRequestError() from exc
            if not isinstance(raw_arguments, dict):
                raise ProviderRequestError()
            proposed.append(
                ProposedToolCall(
                    provider_id=str(raw_call.get("id", "provider-call"))[:128],
                    tool_key=function["name"][:96],
                    arguments=raw_arguments,
                )
            )
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        return GatewayCompletion(
            content=normalized_content[:16000],
            tool_calls=proposed,
            provider=self.settings.ai_provider,
            model=self.settings.ai_model,
            input_tokens=usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None,
            output_tokens=usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None,
        )


def gateway_from_settings(settings: Settings) -> ModelGateway:
    """Construct only an approved provider from validated server configuration."""
    if settings.ai_provider == "disabled":
        return DisabledGateway()
    if settings.ai_provider in {"openai", "openai_compatible", "nvidia_nim"}:
        return OpenAICompatibleGateway(settings)
    raise ProviderRequestError()
