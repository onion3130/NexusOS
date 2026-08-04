"""Encrypted runtime configuration for browser-managed provider credentials."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field, field_validator
from pydantic.types import SecretStr

RUNTIME_DIRECTORY = "runtime"
RUNTIME_FILENAME = "nvidia-nim.enc"
ACTIVE_FILENAME = "nvidia-nim.active"
DISABLE_FILENAME = "nvidia-nim.disable"
_RUNTIME_VERSION = 1
_AAD = b"nexusos-runtime-nvidia-nim-v1"


class RuntimeNimConfig(BaseModel):
    """Validated, transient NIM settings never returned to the browser."""

    api_key: SecretStr
    model: str = Field(min_length=1, max_length=160)
    embeddings_enabled: bool = False
    embedding_model: str | None = Field(default=None, max_length=160)

    @field_validator("model", "embedding_model")
    @classmethod
    def validate_model_name(cls, value: str | None) -> str | None:
        """Allow provider model identifiers without arbitrary control characters."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or any(character.isspace() for character in normalized) or any(character in normalized for character in ('"', "'", "\\")):
            raise ValueError("model identifier is invalid")
        return normalized


def runtime_path(data_dir: Path) -> Path:
    """Return the private encrypted runtime configuration path."""
    return data_dir.expanduser().resolve() / RUNTIME_DIRECTORY / RUNTIME_FILENAME


def _encryption_key(jwt_secret: str) -> bytes:
    """Derive a dedicated AES-256 key from the existing server secret."""
    return hashlib.sha256(b"nexusos-runtime-key-v1\x00" + jwt_secret.encode("utf-8")).digest()


def _payload(config: RuntimeNimConfig) -> bytes:
    """Serialize only the minimum encrypted provider configuration."""
    return json.dumps(
        {
            "version": _RUNTIME_VERSION,
            "api_key": config.api_key.get_secret_value(),
            "model": config.model,
            "embeddings_enabled": config.embeddings_enabled,
            "embedding_model": config.embedding_model,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def write_runtime_nim(data_dir: Path, jwt_secret: str, config: RuntimeNimConfig) -> None:
    """Atomically write encrypted NIM configuration with owner-only permissions."""
    target = runtime_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_encryption_key(jwt_secret)).encrypt(nonce, _payload(config), _AAD)
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(nonce + ciphertext)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def read_runtime_nim(data_dir: Path, jwt_secret: str) -> RuntimeNimConfig | None:
    """Read and decrypt browser-managed NIM settings, failing closed on corruption."""
    target = runtime_path(data_dir)
    try:
        raw = target.read_bytes()
        if len(raw) < 29:
            return None
        decoded: dict[str, Any] = json.loads(AESGCM(_encryption_key(jwt_secret)).decrypt(raw[:12], raw[12:], _AAD))
        if decoded.get("version") != _RUNTIME_VERSION:
            return None
        return RuntimeNimConfig(
            api_key=SecretStr(str(decoded["api_key"])),
            model=str(decoded["model"]),
            embeddings_enabled=bool(decoded.get("embeddings_enabled", False)),
            embedding_model=str(decoded["embedding_model"]) if decoded.get("embedding_model") else None,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, InvalidTag):
        return None


def active_runtime_path(data_dir: Path) -> Path:
    """Return the worker activation marker path."""
    return data_dir.expanduser().resolve() / RUNTIME_DIRECTORY / ACTIVE_FILENAME


def disable_runtime_path(data_dir: Path) -> Path:
    """Return the pending-disable marker path."""
    return data_dir.expanduser().resolve() / RUNTIME_DIRECTORY / DISABLE_FILENAME


def mark_runtime_nim_active(data_dir: Path) -> None:
    """Record that the worker loaded the current encrypted configuration."""
    source = runtime_path(data_dir)
    marker = active_runtime_path(data_dir)
    pending_disable = disable_runtime_path(data_dir)
    if not source.is_file():
        try:
            pending_disable.unlink()
        except FileNotFoundError:
            pass
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        pending_disable.unlink()
    except FileNotFoundError:
        pass
    marker.write_text(hashlib.sha256(source.read_bytes()).hexdigest(), encoding="ascii")
    try:
        os.chmod(marker, 0o600)
    except OSError:
        pass


def runtime_nim_restart_required(data_dir: Path) -> bool:
    """Return whether the worker marker does not match the saved configuration."""
    source = runtime_path(data_dir)
    marker = active_runtime_path(data_dir)
    if not source.is_file():
        return disable_runtime_path(data_dir).is_file()
    try:
        return marker.read_text(encoding="ascii").strip() != hashlib.sha256(source.read_bytes()).hexdigest()
    except OSError:
        return True


def delete_runtime_nim(data_dir: Path) -> bool:
    """Remove browser-managed NIM settings without touching environment configuration."""
    target = runtime_path(data_dir)
    marker = active_runtime_path(data_dir)
    pending_disable = disable_runtime_path(data_dir)
    removed = False
    for path in (target, marker):
        try:
            path.unlink()
            removed = True
        except FileNotFoundError:
            pass
    pending_disable.parent.mkdir(parents=True, exist_ok=True)
    pending_disable.write_text("restart-required", encoding="ascii")
    try:
        os.chmod(pending_disable, 0o600)
    except OSError:
        pass
    return removed


def has_runtime_nim(data_dir: Path) -> bool:
    """Return whether a browser-managed configuration artifact exists."""
    return runtime_path(data_dir).is_file()
