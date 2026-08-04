"""Environment-backed configuration for the NexusOS API."""

from __future__ import annotations

import ipaddress
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
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
    ai_timeout_seconds: float = Field(default=20.0, validation_alias="AI_TIMEOUT_SECONDS")
    ai_max_context_messages: int = Field(default=20, validation_alias="AI_MAX_CONTEXT_MESSAGES")
    ai_max_output_tokens: int = Field(default=512, validation_alias="AI_MAX_OUTPUT_TOKENS")
    ai_max_response_bytes: int = Field(default=1_048_576, validation_alias="AI_MAX_RESPONSE_BYTES")
    task_worker_interval_seconds: int = Field(default=30, validation_alias="TASK_WORKER_INTERVAL_SECONDS")
    task_worker_batch_size: int = Field(default=50, validation_alias="TASK_WORKER_BATCH_SIZE")
    workspace_roots: str = Field(default="", validation_alias="WORKSPACE_ROOTS")
    media_roots: str = Field(default="", validation_alias="MEDIA_ROOTS")
    media_thumbnail_max_dimension: int = Field(default=320, validation_alias="MEDIA_THUMBNAIL_MAX_DIMENSION")
    media_index_max_size_mb: int = Field(default=200, validation_alias="MEDIA_INDEX_MAX_SIZE_MB")
    plugins_dir: Path | None = Field(default=None, validation_alias="PLUGINS_DIR")
    plugin_invoke_timeout_seconds: float = Field(default=20.0, validation_alias="PLUGIN_INVOKE_TIMEOUT_SECONDS")
    docker_socket_path: str = Field(default="", validation_alias="DOCKER_SOCKET_PATH")
    backup_replication_destination: Path | None = Field(default=None, validation_alias="BACKUP_REPLICATION_DESTINATION")
    backup_encryption_key: SecretStr | None = Field(default=None, validation_alias="BACKUP_ENCRYPTION_KEY")
    backup_retention_count: int = Field(default=7, validation_alias="BACKUP_RETENTION_COUNT")
    backup_retention_days: int = Field(default=30, validation_alias="BACKUP_RETENTION_DAYS")
    backup_replication_key_previous: SecretStr | None = Field(default=None, validation_alias="BACKUP_REPLICATION_KEY_PREVIOUS")
    notification_email_enabled: bool = Field(default=False, validation_alias="NOTIFICATION_EMAIL_ENABLED")
    notification_email_smtp_host: str | None = Field(default=None, validation_alias="NOTIFICATION_EMAIL_SMTP_HOST")
    notification_email_smtp_port: int = Field(default=587, validation_alias="NOTIFICATION_EMAIL_SMTP_PORT")
    notification_email_smtp_user: str | None = Field(default=None, validation_alias="NOTIFICATION_EMAIL_SMTP_USER")
    notification_email_smtp_password: SecretStr | None = Field(default=None, validation_alias="NOTIFICATION_EMAIL_SMTP_PASSWORD")
    notification_email_from: str | None = Field(default=None, validation_alias="NOTIFICATION_EMAIL_FROM")
    notification_email_to: str | None = Field(default=None, validation_alias="NOTIFICATION_EMAIL_TO")
    notification_email_use_tls: bool = Field(default=True, validation_alias="NOTIFICATION_EMAIL_USE_TLS")
    notification_push_enabled: bool = Field(default=False, validation_alias="NOTIFICATION_PUSH_ENABLED")
    notification_push_url: str | None = Field(default=None, validation_alias="NOTIFICATION_PUSH_URL")
    notification_push_topic: str | None = Field(default=None, validation_alias="NOTIFICATION_PUSH_TOPIC")
    notification_push_token: SecretStr | None = Field(default=None, validation_alias="NOTIFICATION_PUSH_TOKEN")
    notification_delivery_batch_size: int = Field(default=20, validation_alias="NOTIFICATION_DELIVERY_BATCH_SIZE")
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
        if normalized not in {"disabled", "openai", "openai_compatible", "nvidia_nim"}:
            raise ValueError("unsupported provider")
        return normalized

    @field_validator("ai_timeout_seconds")
    @classmethod
    def validate_ai_timeout(cls, value: float) -> float:
        """Keep provider calls bounded for the Pi API process."""
        if not 1 <= value <= 60:
            raise ValueError("must be between 1 and 60 seconds")
        return value

    @field_validator("ai_max_context_messages")
    @classmethod
    def validate_ai_context(cls, value: int) -> int:
        """Bound conversation history sent to an upstream model."""
        if not 1 <= value <= 100:
            raise ValueError("must be between 1 and 100")
        return value

    @field_validator("ai_max_output_tokens")
    @classmethod
    def validate_ai_output(cls, value: int) -> int:
        """Bound model output size and memory use."""
        if not 64 <= value <= 4096:
            raise ValueError("must be between 64 and 4096")
        return value

    @field_validator("ai_max_response_bytes")
    @classmethod
    def validate_ai_response_bytes(cls, value: int) -> int:
        """Bound provider response memory use on the Raspberry Pi."""
        if not 16_384 <= value <= 8_388_608:
            raise ValueError("must be between 16384 and 8388608 bytes")
        return value

    @field_validator("media_thumbnail_max_dimension")
    @classmethod
    def validate_thumbnail_dimension(cls, value: int) -> int:
        """Bound thumbnail memory use on the Raspberry Pi."""
        if not 64 <= value <= 1024:
            raise ValueError("must be between 64 and 1024 pixels")
        return value

    @field_validator("media_index_max_size_mb")
    @classmethod
    def validate_media_index_size(cls, value: int) -> int:
        """Bound the largest file the media indexer will hash."""
        if not 1 <= value <= 1024:
            raise ValueError("must be between 1 and 1024 MB")
        return value

    @field_validator("plugins_dir", mode="before")
    @classmethod
    def validate_plugins_dir(cls, value: Path | str | None) -> Path | None:
        """Require an absolute operator-approved directory for out-of-process plugins."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        path = value if isinstance(value, Path) else Path(value)
        if not path.is_absolute():
            raise ValueError("must be an absolute path")
        return path

    @field_validator("plugin_invoke_timeout_seconds")
    @classmethod
    def validate_plugin_timeout(cls, value: float) -> float:
        """Keep out-of-process plugin calls bounded on the Raspberry Pi."""
        if not 1 <= value <= 120:
            raise ValueError("must be between 1 and 120 seconds")
        return value

    @field_validator("backup_retention_count")
    @classmethod
    def validate_retention_count(cls, value: int) -> int:
        """Bound the number of verified backups always retained."""
        if not 1 <= value <= 100:
            raise ValueError("must be between 1 and 100")
        return value

    @field_validator("backup_retention_days")
    @classmethod
    def validate_retention_days(cls, value: int) -> int:
        """Bound the retention window in days."""
        if not 1 <= value <= 3650:
            raise ValueError("must be between 1 and 3650 days")
        return value

    @field_validator("task_worker_interval_seconds")
    @classmethod
    def validate_worker_interval(cls, value: int) -> int:
        """Bound worker polling for predictable Pi resource use."""
        if not 5 <= value <= 3600:
            raise ValueError("must be between 5 and 3600 seconds")
        return value

    @field_validator("task_worker_batch_size")
    @classmethod
    def validate_worker_batch(cls, value: int) -> int:
        """Bound one reminder batch."""
        if not 1 <= value <= 200:
            raise ValueError("must be between 1 and 200")
        return value

    @field_validator("notification_email_smtp_port")
    @classmethod
    def validate_smtp_port(cls, value: int) -> int:
        """Keep SMTP ports within the valid range."""
        if not 1 <= value <= 65535:
            raise ValueError("must be between 1 and 65535")
        return value

    @field_validator("notification_delivery_batch_size")
    @classmethod
    def validate_delivery_batch(cls, value: int) -> int:
        """Bound one outbound delivery batch for the Pi worker."""
        if not 1 <= value <= 100:
            raise ValueError("must be between 1 and 100")
        return value

    @field_validator("notification_push_url")
    @classmethod
    def validate_push_url(cls, value: str | None) -> str | None:
        """Allow only absolute HTTP(S) push endpoints without embedded credentials."""
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("must be an absolute HTTP(S) URL without credentials")
        hostname = parsed.hostname or ""
        if hostname.lower() in {"localhost", "localhost.localdomain", "metadata.google.internal"}:
            raise ValueError("must not target a local or metadata hostname")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and any((address.is_loopback, address.is_link_local, address.is_multicast, address.is_reserved, address.is_unspecified)):
            raise ValueError("must not target a loopback, link-local, multicast, reserved, or unspecified address")
        return normalized

    @field_validator("notification_push_topic")
    @classmethod
    def validate_push_topic(cls, value: str | None) -> str | None:
        """Bound push topics to the ntfy-safe character set."""
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", normalized):
            raise ValueError("must contain only letters, numbers, dashes, or underscores")
        return normalized

    @field_validator("backup_replication_destination", mode="before")
    @classmethod
    def validate_backup_destination(cls, value: Path | str | None) -> Path | None:
        """Require an absolute operator-owned destination for replication."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        path = value if isinstance(value, Path) else Path(value)
        if not path.is_absolute():
            raise ValueError("must be an absolute path")
        return path

    @field_validator("backup_encryption_key")
    @classmethod
    def validate_backup_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Require a 256-bit hexadecimal key when backup encryption is configured."""
        if value is None:
            return None
        raw = value.get_secret_value().strip()
        if not raw:
            return None
        _require_hex_key(raw, "backup encryption key")
        return SecretStr(raw.lower())

    @field_validator("backup_replication_key_previous")
    @classmethod
    def validate_backup_key_previous(cls, value: SecretStr | None) -> SecretStr | None:
        """Require a 256-bit hexadecimal key when a rotation source key is set."""
        if value is None:
            return None
        raw = value.get_secret_value().strip()
        if not raw:
            return None
        _require_hex_key(raw, "backup replication previous key")
        return SecretStr(raw.lower())

    @model_validator(mode="after")
    def validate_backup_replication(self) -> "Settings":
        """Require both destination and key before enabling replication."""
        destination = self.backup_replication_destination
        key = self.backup_encryption_key
        if (destination is None) != (key is None):
            raise ValueError("backup replication requires both BACKUP_REPLICATION_DESTINATION and BACKUP_ENCRYPTION_KEY")
        previous = self.backup_replication_key_previous
        if previous is not None and key is None:
            raise ValueError("BACKUP_REPLICATION_KEY_PREVIOUS requires BACKUP_ENCRYPTION_KEY")
        if previous is not None and key is not None and previous.get_secret_value().lower() == key.get_secret_value().lower():
            raise ValueError("BACKUP_REPLICATION_KEY_PREVIOUS must differ from BACKUP_ENCRYPTION_KEY")
        return self

    @model_validator(mode="after")
    def validate_notification_channels(self) -> "Settings":
        """Require complete, paired channel configuration only when enabled."""
        if self.notification_email_enabled:
            missing = [
                name
                for name, value in (
                    ("NOTIFICATION_EMAIL_SMTP_HOST", self.notification_email_smtp_host),
                    ("NOTIFICATION_EMAIL_FROM", self.notification_email_from),
                    ("NOTIFICATION_EMAIL_TO", self.notification_email_to),
                )
                if not value or not value.strip()
            ]
            if missing:
                raise ValueError("enabled email channel requires " + ", ".join(missing))
            user = self.notification_email_smtp_user
            password = self.notification_email_smtp_password
            password_value = password.get_secret_value() if password else None
            if bool(user and user.strip()) != bool(password_value and password_value.strip()):
                raise ValueError("email SMTP user and password must be configured together")
            if password_value and any(marker in password_value.lower() for marker in _PLACEHOLDER_MARKERS):
                raise ValueError("email SMTP password must not contain a placeholder value")
        if self.notification_push_enabled:
            missing = [
                name
                for name, value in (
                    ("NOTIFICATION_PUSH_URL", self.notification_push_url),
                    ("NOTIFICATION_PUSH_TOPIC", self.notification_push_topic),
                )
                if not value or not value.strip()
            ]
            if missing:
                raise ValueError("enabled push channel requires " + ", ".join(missing))
            token = self.notification_push_token
            if token and token.get_secret_value() and any(marker in token.get_secret_value().lower() for marker in _PLACEHOLDER_MARKERS):
                raise ValueError("push token must not contain a placeholder value")
        return self

    @field_validator("ai_base_url")
    @classmethod
    def validate_ai_base_url(cls, value: str | None) -> str | None:
        """Allow only absolute HTTP(S) provider URLs without embedded credentials."""
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.path == "":
            raise ValueError("must be an absolute HTTP(S) URL without credentials")
        hostname = parsed.hostname or ""
        if hostname.lower() in {"localhost", "localhost.localdomain", "metadata.google.internal"}:
            raise ValueError("must not target a local or metadata hostname")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and any((address.is_private, address.is_loopback, address.is_link_local, address.is_multicast, address.is_reserved, address.is_unspecified)):
            raise ValueError("must not target a private or reserved address")
        return normalized

    @model_validator(mode="after")
    def validate_active_provider(self) -> "Settings":
        """Require server-side provider configuration only when AI is enabled."""
        if self.ai_provider != "disabled":
            if not self.ai_base_url or not self.ai_model or not self.ai_api_key or not self.ai_api_key.get_secret_value().strip():
                raise ValueError("active AI provider requires AI_BASE_URL, AI_MODEL, and AI_API_KEY")
        return self


def _require_hex_key(raw: str, label: str) -> None:
    """Require a 64-character lowercase-safe hexadecimal AES-256 key."""
    if len(raw) != 64:
        raise ValueError(f"{label} must be a 64-character hexadecimal AES-256 key")
    try:
        bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError(f"{label} must be a 64-character hexadecimal AES-256 key") from exc


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
