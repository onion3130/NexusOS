#!/usr/bin/env python3
"""Validate NexusOS configuration without exposing secret values.

The application runtime is not implemented yet, so this script is the current
executable configuration contract. It reads the process environment by
 default, or a local dotenv-style file supplied with ``--env-file``.
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
