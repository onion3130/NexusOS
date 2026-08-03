"""Environment-backed configuration for the NexusOS API foundation."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    ai_provider: str = Field(validation_alias="AI_PROVIDER")
    ai_base_url: str | None = Field(default=None, validation_alias="AI_BASE_URL")
    ai_api_key: SecretStr | None = Field(default=None, validation_alias="AI_API_KEY")
    ai_model: str | None = Field(default=None, validation_alias="AI_MODEL")
    nvidia_api_key: SecretStr | None = Field(default=None, validation_alias="NVIDIA_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")

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
