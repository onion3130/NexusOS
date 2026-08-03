"""Bootstrap the first NexusOS owner account explicitly."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.db.session import get_session_factory, reset_database_caches
from app.modules.identity.service import bootstrap_owner


def migrate() -> None:
    """Apply checked-in migrations; startup never mutates schema automatically."""
    root = Path(__file__).resolve().parents[2]
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        database_path = settings.database_url.removeprefix("sqlite:///")
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def main() -> int:
    """Run migrations and create the first owner without default credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Initial owner username")
    args = parser.parse_args()
    first = getpass.getpass("Owner password: ")
    second = getpass.getpass("Repeat owner password: ")
    if first != second:
        raise SystemExit("Passwords do not match")
    get_settings()
    migrate()
    reset_database_caches()
    db = get_session_factory()()
    try:
        user = bootstrap_owner(db, args.username, first)
    except ValueError as exc:
        db.rollback()
        raise SystemExit(str(exc)) from exc
    finally:
        db.close()
    print(f"Created owner account: {user.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
