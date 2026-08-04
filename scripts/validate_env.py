#!/usr/bin/env python3
"""Validate NexusOS configuration without exposing secret values.

The FastAPI application reads process environment variables only. This script
validates those variables by default, or a local dotenv-style file supplied
with ``--env-file``; it does not export values into the calling shell.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_REQUIRED = (
    "NEXUS_ENV",
    "TZ",
    "DATA_DIR",
    "DB_TYPE",
    "DATABASE_URL",
    "AI_PROVIDER",
)
PLACEHOLDER_MARKERS = (
    "your_",
    "replace-",
    "generate_",
    "change-me",
    "changeme",
    "example",
    "<",
    ">",
)


def read_dotenv(path: Path) -> dict[str, str]:
    """Read a small, safe dotenv subset without requiring third-party packages."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Cannot read environment file '{path}': {exc}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(
                f"Invalid environment file line {line_number}: expected KEY=value"
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise ValueError(f"Invalid environment variable name on line {line_number}")
        values[key] = value
    return values


def is_placeholder(value: str) -> bool:
    """Return whether a value is an obvious template placeholder."""
    normalized = value.strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def validate(values: dict[str, str]) -> list[str]:
    """Return safe, value-free configuration errors."""
    errors: list[str] = []
    missing = [name for name in BASE_REQUIRED if not values.get(name, "").strip()]
    if missing:
        errors.append("Missing required environment variable(s): " + ", ".join(missing))

    environment = values.get("NEXUS_ENV", "").strip().lower()
    provider = values.get("AI_PROVIDER", "").strip().lower()

    if environment not in {"development", "test", "production"}:
        errors.append(
            "NEXUS_ENV must be one of: development, test, production"
        )

    jwt_secret = values.get("JWT_SECRET", "").strip()
    if not jwt_secret:
        errors.append("JWT_SECRET is required in every runtime environment")
    elif is_placeholder(jwt_secret) or len(jwt_secret) < 32:
        errors.append(
            "JWT_SECRET must be a non-placeholder value of at least 32 characters"
        )

    cookie_secure = values.get("SESSION_COOKIE_SECURE", "").strip().lower()
    if cookie_secure not in {"true", "false"}:
        errors.append("SESSION_COOKIE_SECURE must be either true or false")
    elif environment == "production" and cookie_secure != "true":
        errors.append(
            "SESSION_COOKIE_SECURE=true is required when NEXUS_ENV=production"
        )

    replication_destination = values.get("BACKUP_REPLICATION_DESTINATION", "").strip()
    replication_key = values.get("BACKUP_ENCRYPTION_KEY", "").strip()
    if bool(replication_destination) != bool(replication_key):
        errors.append("BACKUP_REPLICATION_DESTINATION and BACKUP_ENCRYPTION_KEY must be configured together")
    if replication_destination:
        if not Path(replication_destination).is_absolute():
            errors.append("BACKUP_REPLICATION_DESTINATION must be an absolute path")
    if replication_key:
        try:
            bytes.fromhex(replication_key)
            if len(replication_key) != 64:
                raise ValueError
        except ValueError:
            errors.append("BACKUP_ENCRYPTION_KEY must be a 64-character hexadecimal AES-256 key")
    previous_key = values.get("BACKUP_REPLICATION_KEY_PREVIOUS", "").strip()
    if previous_key:
        try:
            bytes.fromhex(previous_key)
            if len(previous_key) != 64:
                raise ValueError
        except ValueError:
            errors.append("BACKUP_REPLICATION_KEY_PREVIOUS must be a 64-character hexadecimal AES-256 key")
        if not replication_key:
            errors.append("BACKUP_REPLICATION_KEY_PREVIOUS requires BACKUP_ENCRYPTION_KEY")
        elif previous_key.lower() == replication_key.lower():
            errors.append("BACKUP_REPLICATION_KEY_PREVIOUS must differ from BACKUP_ENCRYPTION_KEY")

    retention_count = values.get("BACKUP_RETENTION_COUNT", "").strip()
    if retention_count:
        try:
            if not 1 <= int(retention_count) <= 100:
                raise ValueError
        except ValueError:
            errors.append("BACKUP_RETENTION_COUNT must be an integer between 1 and 100")
    retention_days = values.get("BACKUP_RETENTION_DAYS", "").strip()
    if retention_days:
        try:
            if not 1 <= int(retention_days) <= 3650:
                raise ValueError
        except ValueError:
            errors.append("BACKUP_RETENTION_DAYS must be an integer between 1 and 3650")

    email_enabled = values.get("NOTIFICATION_EMAIL_ENABLED", "").strip().lower()
    if email_enabled not in {"", "true", "false"}:
        errors.append("NOTIFICATION_EMAIL_ENABLED must be either true or false")
    elif email_enabled == "true":
        for name in ("NOTIFICATION_EMAIL_SMTP_HOST", "NOTIFICATION_EMAIL_FROM", "NOTIFICATION_EMAIL_TO"):
            if not values.get(name, "").strip():
                errors.append(f"{name} is required when NOTIFICATION_EMAIL_ENABLED=true")
        smtp_port = values.get("NOTIFICATION_EMAIL_SMTP_PORT", "").strip()
        if smtp_port:
            try:
                if not 1 <= int(smtp_port) <= 65535:
                    raise ValueError
            except ValueError:
                errors.append("NOTIFICATION_EMAIL_SMTP_PORT must be an integer between 1 and 65535")
        smtp_user = values.get("NOTIFICATION_EMAIL_SMTP_USER", "").strip()
        smtp_password = values.get("NOTIFICATION_EMAIL_SMTP_PASSWORD", "").strip()
        if bool(smtp_user) != bool(smtp_password):
            errors.append("NOTIFICATION_EMAIL_SMTP_USER and NOTIFICATION_EMAIL_SMTP_PASSWORD must be configured together")
        elif smtp_password and is_placeholder(smtp_password):
            errors.append("NOTIFICATION_EMAIL_SMTP_PASSWORD still contains a placeholder value")

    push_enabled = values.get("NOTIFICATION_PUSH_ENABLED", "").strip().lower()
    if push_enabled not in {"", "true", "false"}:
        errors.append("NOTIFICATION_PUSH_ENABLED must be either true or false")
    elif push_enabled == "true":
        push_url = values.get("NOTIFICATION_PUSH_URL", "").strip()
        push_topic = values.get("NOTIFICATION_PUSH_TOPIC", "").strip()
        if not push_url:
            errors.append("NOTIFICATION_PUSH_URL is required when NOTIFICATION_PUSH_ENABLED=true")
        elif not (push_url.startswith("https://") or push_url.startswith("http://")):
            errors.append("NOTIFICATION_PUSH_URL must be an absolute HTTP(S) URL")
        if not push_topic:
            errors.append("NOTIFICATION_PUSH_TOPIC is required when NOTIFICATION_PUSH_ENABLED=true")
        elif not __import__("re").fullmatch(r"[A-Za-z0-9_-]{1,128}", push_topic):
            errors.append("NOTIFICATION_PUSH_TOPIC must contain only letters, numbers, dashes, or underscores")
        push_token = values.get("NOTIFICATION_PUSH_TOKEN", "").strip()
        if push_token and is_placeholder(push_token):
            errors.append("NOTIFICATION_PUSH_TOKEN still contains a placeholder value")

    if provider not in {"", "disabled", "none", "local"}:
        provider_key = {
            "nvidia": "NVIDIA_API_KEY",
            "nim": "NVIDIA_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider, "AI_API_KEY")
        api_key = values.get(provider_key, "").strip()
        if not api_key:
            errors.append(
                f"{provider_key} is required when AI_PROVIDER={values.get('AI_PROVIDER', '')}"
            )
        elif is_placeholder(api_key):
            errors.append(f"{provider_key} still contains a placeholder value")

    return errors


def main() -> int:
    """Validate configuration and return a shell-friendly exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Read a local dotenv file in addition to the process environment",
    )
    args = parser.parse_args()

    values: dict[str, str] = {}
    if args.env_file:
        try:
            values.update(read_dotenv(args.env_file))
        except ValueError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2

    # Explicit process variables are authoritative in containers and CI.
    values.update(os.environ)

    errors = validate(values)
    if errors:
        print("NexusOS configuration is invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("Copy .env.example to .env and configure the required values.", file=sys.stderr)
        return 1

    print("NexusOS configuration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
