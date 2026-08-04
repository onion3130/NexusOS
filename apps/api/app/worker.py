"""Dedicated NexusOS reminder worker process."""

from __future__ import annotations

import logging
import signal
import time

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.tasks.worker import process_due_reminders
from app.modules.calendar.worker import process_due_event_reminders
from app.modules.host_actions.worker import process_host_actions
from app.modules.backup_replication.replicator import process_replication_jobs
from app.modules.notifications.worker import process_notification_deliveries
from app.modules.media.service import configured_media_roots, process_media_rescans
from app.modules.embeddings.service import process_embeddings

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
            process_due_event_reminders(session, batch_size=settings.task_worker_batch_size)
            process_host_actions(
                session,
                data_dir=settings.data_dir,
                database_url=settings.database_url,
                replication_destination=settings.backup_replication_destination,
                encryption_key=settings.backup_encryption_key.get_secret_value() if settings.backup_encryption_key else None,
                retention_count=settings.backup_retention_count,
                retention_days=settings.backup_retention_days,
                previous_encryption_key=settings.backup_replication_key_previous.get_secret_value() if settings.backup_replication_key_previous else None,
                batch_size=10,
            )
            process_replication_jobs(session, data_dir=settings.data_dir, destination=settings.backup_replication_destination, encryption_key=settings.backup_encryption_key.get_secret_value() if settings.backup_encryption_key else None, batch_size=2)
            process_notification_deliveries(session, settings=settings, batch_size=settings.notification_delivery_batch_size)
            process_media_rescans(session, data_dir=settings.data_dir, media_roots=configured_media_roots(settings), max_size_bytes=settings.media_index_max_size_mb * 1024 * 1024, max_dimension=settings.media_thumbnail_max_dimension)
            process_embeddings(session, settings, batch_size=settings.embedding_batch_size)
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
