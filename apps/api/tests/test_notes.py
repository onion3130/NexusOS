"""Milestone 7 notes, search, ownership, and retrieval tests."""

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Role, User
from app.db.session import get_session_factory
from app.modules.assistant.schemas import ProposedToolCall
from app.modules.assistant.tools.registry import ToolRegistry
from app.modules.identity.service import bootstrap_owner
from app.modules.system.service import SystemService
from app.modules.notes.schemas import NoteCreate
from app.modules.notes.service import create_note


def _bootstrap_and_login(client, username="owner", password="correct horse battery staple"):
    db = get_session_factory()()
    try:
        bootstrap_owner(db, username, password)
    finally:
        db.close()
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response


def _create_additional_user(username: str, password: str) -> None:
    db = get_session_factory()()
    try:
        role = db.scalar(select(Role).where(Role.key == "owner"))
        db.add(User(username=username, password_hash=hash_password(password), roles=[role]))
        db.commit()
    finally:
        db.close()


def test_notes_require_authentication(client):
    assert client.get("/api/v1/notes").status_code == 401
    assert client.post("/api/v1/notes", json={"title": "x", "content": "y"}).status_code == 401


def test_note_crud_search_archive_restore_and_chunks(client):
    _bootstrap_and_login(client)
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "note-create-1"}
    created = client.post("/api/v1/notes", headers=headers, json={"title": "Pi planning", "content": "Move the database backup to the external SSD.\n\nReview the Raspberry Pi deployment.", "tags": ["work", "pi"]})
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["content_version"] == 1
    chunks = client.get(f"/api/v1/notes/{note['id']}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()["items"]
    searched = client.get("/api/v1/search", params={"q": "external SSD"})
    assert searched.status_code == 200
    assert searched.json()["items"][0]["source_id"] == note["id"]
    updated = client.patch(f"/api/v1/notes/{note['id']}", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "note-update-1"}, json={"content": "A completely different release checklist.", "tags": ["release"]})
    assert updated.status_code == 200
    assert updated.json()["content_version"] == 2
    assert client.get("/api/v1/search", params={"q": "external SSD"}).json()["items"] == []
    archived = client.post(f"/api/v1/notes/{note['id']}/archive", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "note-archive-1"})
    assert archived.status_code == 200
    assert client.get("/api/v1/search", params={"q": "release checklist"}).json()["items"] == []
    assert client.get("/api/v1/search", params={"q": "release checklist", "include_archived": "true"}).json()["items"]
    assert client.post(f"/api/v1/notes/{note['id']}/restore", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "note-restore-1"}).status_code == 200
    assert client.delete(f"/api/v1/notes/{note['id']}", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "note-delete-1"}).status_code == 204
    assert client.get(f"/api/v1/notes/{note['id']}").status_code == 404


def test_notes_csrf_and_idempotency_mismatch(client):
    _bootstrap_and_login(client)
    csrf = client.cookies.get("nexus_csrf")
    response = client.post("/api/v1/notes", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "same"}, json={"title": "One", "content": "First"})
    assert response.status_code == 201
    mismatch = client.post("/api/v1/notes", headers={"X-CSRF-Token": csrf, "Idempotency-Key": "same"}, json={"title": "Two", "content": "Second"})
    assert mismatch.status_code == 422
    assert client.post("/api/v1/notes", json={"title": "No csrf", "content": "blocked"}).status_code == 403


def test_assistant_note_tools_are_read_only_and_scoped(client, tmp_path):
    _bootstrap_and_login(client)
    db = get_session_factory()()
    try:
        user = db.scalar(select(User).where(User.username == "owner"))
        note = create_note(db, user.id, NoteCreate(title="Assistant source", content="Private source material", tags=["reference"]))
        registry = ToolRegistry(SystemService(tmp_path, tmp_path / "proc", tmp_path / "sys"), db, user.id)
        definitions = {item.key for item in registry.definitions({"notes.read"})}
        assert definitions == {"notes.search", "notes.read"}
        result = registry.execute(ProposedToolCall(provider_id="test", tool_key="notes.read", arguments={"note_id": note.id}), {"notes.read"})
        assert result["source_type"] == "note"
        assert result["content"] == "Private source material"
        assert registry.requires_confirmation("notes.read") is False
    finally:
        db.close()


def test_note_search_does_not_leak_between_users(client):
    _bootstrap_and_login(client, "first", "first password long enough")
    csrf = client.cookies.get("nexus_csrf")
    created = client.post("/api/v1/notes", headers={"X-CSRF-Token": csrf}, json={"title": "Private", "content": "secret phrase"})
    assert created.status_code == 201
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    _create_additional_user("second", "second password long enough")
    login = client.post("/api/v1/auth/login", json={"username": "second", "password": "second password long enough"})
    assert login.status_code == 200
    assert client.get("/api/v1/search", params={"q": "secret phrase"}).json()["items"] == []
    assert client.get(f"/api/v1/notes/{created.json()['id']}").status_code == 404
