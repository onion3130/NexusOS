"""Milestone 11 Phase C media index, thumbnail, rescan, and streaming tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db.models import MediaItem
from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner
from app.modules.media.service import configured_media_roots, process_media_rescans, queue_media_rescan, resolve_media_path, scan_media_library


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def _make_image(path: Path) -> None:
    from PIL import Image

    image = Image.new("RGB", (64, 48), (200, 60, 90))
    image.save(path, "PNG")


@pytest.fixture
def media_roots(tmp_path: Path) -> list[tuple[str, Path]]:
    from app.core.config import get_settings

    root = tmp_path / "photos"
    root.mkdir(exist_ok=True)
    (root / "vacation").mkdir(exist_ok=True)
    _make_image(root / "vacation" / "beach.png")
    (root / "notes.txt").write_text("plain text", encoding="utf-8")
    (root / "ignored.env").write_text("SECRET=1", encoding="utf-8")
    # Match the MEDIA_ROOTS configured in conftest so routes resolve the same root.
    return configured_media_roots(get_settings()) or [("root-1", root)]


def test_scan_indexes_media_and_skips_sensitive_files(configured_app, media_roots, tmp_path) -> None:
    """Scanning indexes images and text, skipping credential-named files."""
    db = get_session_factory()()
    summary = scan_media_library(db, data_dir=tmp_path, media_roots=media_roots, max_size_bytes=10 * 1024 * 1024, max_dimension=96)
    db.close()
    assert summary["indexed"] == 2
    db = get_session_factory()()
    items = db.query(MediaItem).all()
    db.close()
    names = {item.file_name for item in items}
    assert "beach.png" in names
    assert "notes.txt" in names
    assert "ignored.env" not in names


def test_scan_creates_bounded_thumbnail(configured_app, media_roots, tmp_path) -> None:
    """Image items receive a bounded JPEG thumbnail beneath the data volume."""
    db = get_session_factory()()
    scan_media_library(db, data_dir=tmp_path, media_roots=media_roots, max_size_bytes=10 * 1024 * 1024, max_dimension=96)
    image_item = db.query(MediaItem).filter(MediaItem.extension == "png").one()
    db.close()
    assert image_item.thumbnail_path is not None
    assert image_item.width == 64 and image_item.height == 48
    from app.modules.media.service import resolve_thumbnail_path

    thumbnail = resolve_thumbnail_path(tmp_path, image_item)
    assert thumbnail is not None and thumbnail.is_file()
    from PIL import Image

    with Image.open(thumbnail) as rendered:
        assert rendered.width <= 96 and rendered.height <= 96


def test_rescan_idempotent_queuing_and_worker_run(configured_app, media_roots, tmp_path) -> None:
    """Rescan queues exactly one job; the worker executes it once."""
    db = get_session_factory()()
    first_queued, first_job = queue_media_rescan(db)
    second_queued, _ = queue_media_rescan(db)
    assert first_queued is True
    assert second_queued is False
    processed = process_media_rescans(db, data_dir=tmp_path, media_roots=media_roots, max_size_bytes=10 * 1024 * 1024, max_dimension=96)
    db.close()
    assert processed == 1
    db = get_session_factory()()
    assert db.query(MediaItem).count() == 2
    db.close()


def test_rescan_without_roots_is_noop(configured_app, tmp_path) -> None:
    """No roots configured means no jobs run and nothing is indexed."""
    db = get_session_factory()()
    assert process_media_rescans(db, data_dir=tmp_path, media_roots=[], max_size_bytes=1024, max_dimension=96) == 0
    db.close()


def test_media_routes_require_auth_and_permission(client, configured_app, media_roots, tmp_path) -> None:
    """Media reads require auth; rescan requires CSRF and the media.write permission."""
    assert client.get("/api/v1/media/items").status_code == 401
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    blocked = client.post("/api/v1/media/rescan", headers={"X-CSRF-Token": csrf})
    assert blocked.status_code in (200, 403)
    db = get_session_factory()()
    scan_media_library(db, data_dir=tmp_path, media_roots=media_roots, max_size_bytes=10 * 1024 * 1024, max_dimension=96)
    db.close()
    listing = client.get("/api/v1/media/items")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 2


def test_stream_resolves_only_confined_paths(client, configured_app, media_roots, tmp_path) -> None:
    """Streaming resolves only indexed items inside approved roots; missing items 404."""
    _bootstrap_owner()
    _login(client)
    db = get_session_factory()()
    scan_media_library(db, data_dir=tmp_path, media_roots=media_roots, max_size_bytes=10 * 1024 * 1024, max_dimension=96)
    image_item = db.query(MediaItem).filter(MediaItem.extension == "png").one()
    db.close()
    response = client.get(f"/api/v1/media/items/{image_item.id}/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert client.get("/api/v1/media/items/not-a-real-id/stream").status_code == 404
    assert client.get(f"/api/v1/media/items/{image_item.id}/thumbnail").status_code == 200


def test_resolve_media_path_confinement(configured_app, media_roots, tmp_path) -> None:
    """Items resolve only when their real path stays inside the approved root."""
    db = get_session_factory()()
    scan_media_library(db, data_dir=tmp_path, media_roots=media_roots, max_size_bytes=10 * 1024 * 1024, max_dimension=96)
    item = db.query(MediaItem).filter(MediaItem.extension == "txt").one()
    db.close()
    resolved = resolve_media_path(db, item.id, media_roots)
    assert resolved is not None
    path, _ = resolved
    assert media_roots[0][1].resolve() in path.parents
    outside = db.get(MediaItem, item.id)
    assert resolve_media_path(db, "not-a-real-id", media_roots) is None
    db.close()


def test_configured_media_roots_parse(configured_app, tmp_path) -> None:
    """configured_media_roots resolves the server-configured approved root."""
    from app.core.config import get_settings

    root = tmp_path / "photos"
    root.mkdir(exist_ok=True)
    roots = configured_media_roots(get_settings())
    assert len(roots) == 1
    assert roots[0][0] == "root-1"
    assert roots[0][1] == root.resolve()
