"""Dedicated NexusOS reminder worker process."""

from __future__ import annotations

import logging
import signal
import time

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.tasks.worker import process_due_reminders
from app.modules.host_actions.worker import process_host_actions

_running = True
_logger = logging.getLogger(__name__)


def _stop(_signum, _frame) -> None:
    global _running
    _running = False


def main() -> int:
    """Poll due reminders with bounded batches until shutdown."""
    settings = get_settings()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    while _running:
        session = get_session_factory()()
        try:
            process_due_reminders(session, batch_size=settings.task_worker_batch_size)
            process_host_actions(session, data_dir=settings.data_dir, database_url=settings.database_url, batch_size=10)
        except Exception:
            # A malformed item must not terminate the scheduler. Each module
            # owns durable leases/retries; the process-level restart policy is
            # still available for unrecoverable failures.
            session.rollback()
            _logger.exception("worker cycle failed")
        finally:
            session.close()
        time.sleep(settings.task_worker_interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
