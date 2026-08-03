"""Environment-backed configuration for the NexusOS API."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
_PLACEHOLDER_MARKERS = (
    "your_",
    "replace-",
    "generate_",
    "change-me",
    "changeme",
    "example",
    "<",
    ">",
)


class Settings(BaseSettings):
    """Validated runtime settings loaded from process environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=True,
    )

    nexus_env: Environment = Field(validation_alias="NEXUS_ENV")
    tz: str = Field(validation_alias="TZ")
    data_dir: Path = Field(validation_alias="DATA_DIR")
    db_type: str = Field(validation_alias="DB_TYPE")
    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET")
    session_cookie_secure: bool = Field(validation_alias="SESSION_COOKIE_SECURE")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
    )
    ai_provider: str = Field(validation_alias="AI_PROVIDER")
    ai_base_url: str | None = Field(default=None, validation_alias="AI_BASE_URL")
    ai_api_key: SecretStr | None = Field(default=None, validation_alias="AI_API_KEY")
    ai_model: str | None = Field(default=None, validation_alias="AI_MODEL")
    nvidia_api_key: SecretStr | None = Field(default=None, validation_alias="NVIDIA_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        """Reject wildcard or malformed origins when credentials are enabled."""
        _parse_cors_origins(value)
        return value

    @field_validator("db_type")
    @classmethod
    def validate_db_type(cls, value: str) -> str:
        """Reject unsupported database policies before engine creation."""
        normalized = value.strip().lower()
        if normalized != "sqlite":
            raise ValueError("Milestone 2 supports DB_TYPE=sqlite only")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Require an explicit SQLite URL for the persistence boundary."""
        normalized = value.strip()
        if not normalized or not normalized.startswith("sqlite:"):
            raise ValueError("must be a non-empty sqlite URL")
        return normalized

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        """Reject template, short, or otherwise unsafe signing material."""
        secret = value.get_secret_value().strip()
        normalized = secret.lower()
        if len(secret) < 32 or any(marker in normalized for marker in _PLACEHOLDER_MARKERS):
            raise ValueError("must be a non-placeholder value of at least 32 characters")
        return SecretStr(secret)

    @field_validator("session_cookie_secure")
    @classmethod
    def validate_cookie_mode(cls, value: bool, info) -> bool:
        """Require secure cookies outside local development and tests."""
        if info.data.get("nexus_env") == "production" and not value:
            raise ValueError("must be true when NEXUS_ENV=production")
        return value

    @field_validator("ai_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Normalize provider selection without accepting an empty policy."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


def _parse_cors_origins(value: str) -> list[str]:
    """Parse credential-safe HTTP origins and reject wildcard policies."""
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if not origins:
        raise ValueError("must include at least one HTTP origin")
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ValueError("must contain only HTTP(S) origins")
    return origins


def cors_origins_from_environment() -> list[str]:
    """Parse the process-level CORS origins using the Settings validator rules."""
    raw_origins = os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    return _parse_cors_origins(raw_origins)


def _configuration_error(exc: ValidationError) -> RuntimeError:
    """Convert Pydantic details into a safe, user-facing startup error."""
    fields: list[str] = []
    for error in exc.errors():
        location = error.get("loc", ())
        if location:
            field = str(location[0]).upper()
            if field not in fields:
                fields.append(field)
    missing_or_invalid = ", ".join(fields) or "one or more settings"
    return RuntimeError(
        "NexusOS configuration error: missing or invalid setting(s): "
        f"{missing_or_invalid}. Copy .env.example to .env and configure it."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate environment configuration once per process.

    The process environment is the only runtime source. `.env` loading is kept
    outside the application so Docker, CI, and the host control precedence.
    """
    try:
        return Settings()
    except ValidationError as exc:
        raise _configuration_error(exc) from None
