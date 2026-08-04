"""NexusOS persistence models for identity, assistant, and tasks."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


def new_id() -> str:
    """Return a string UUID suitable for SQLite and PostgreSQL."""
    return str(uuid4())


user_roles = Table(
    "user_roles", Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

task_tags = Table(
    "task_tags", Base.metadata,
    Column("task_id", String(36), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

note_tags = Table(
    "note_tags", Base.metadata,
    Column("note_id", String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    """A local NexusOS account."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users")
    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(Base):
    """A named collection of permissions."""

    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(Base):
    """An action-oriented permission key."""

    __tablename__ = "permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


class Session(Base):
    """A revocable browser session with rotated refresh material."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user: Mapped[User] = relationship(back_populates="sessions")


class Conversation(Base):
    """An assistant conversation owned by one local user."""

    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    messages: Mapped[list[AssistantMessage]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    model_runs: Mapped[list[AssistantModelRun]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class AssistantModelRun(Base):
    """Bounded provider execution metadata without raw provider payloads."""

    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conversation: Mapped[Conversation] = relationship(back_populates="model_runs")
    messages: Mapped[list[AssistantMessage]] = relationship(back_populates="model_run")
    tool_calls: Mapped[list[AssistantToolCall]] = relationship(back_populates="model_run", cascade="all, delete-orphan")


class AssistantMessage(Base):
    """A bounded user, assistant, or tool message."""

    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer)
    model_run_id: Mapped[str | None] = mapped_column(ForeignKey("model_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    model_run: Mapped[AssistantModelRun | None] = relationship(back_populates="messages")
    source_references: Mapped[list[AssistantSourceReference]] = relationship(back_populates="message", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("conversation_id", "sequence", name="uq_messages_conversation_sequence"),)


class AssistantSourceReference(Base):
    """Derived provenance for sources used in one assistant response."""

    __tablename__ = "assistant_source_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(24))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("note_chunks.id", ondelete="CASCADE"), nullable=True, index=True)
    external_source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=True, index=True)
    external_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("source_chunks.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    source_version: Mapped[int] = mapped_column(Integer)
    retrieval_mode: Mapped[str] = mapped_column(String(16))
    rank: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lexical_score: Mapped[float | None] = mapped_column(nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    message: Mapped[AssistantMessage] = relationship(back_populates="source_references")
    __table_args__ = (UniqueConstraint("message_id", "chunk_id", name="uq_assistant_source_message_chunk"),)


class AssistantToolCall(Base):
    """Sanitized metadata for an allowlisted assistant tool call or proposal."""

    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    model_run_id: Mapped[str] = mapped_column(ForeignKey("model_runs.id", ondelete="CASCADE"), index=True)
    tool_key: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(32))
    input_json: Mapped[str] = mapped_column(Text)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_run: Mapped[AssistantModelRun] = relationship(back_populates="tool_calls")


class TaskCategory(Base):
    """A user-owned task category."""

    __tablename__ = "task_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    normalized_name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    tasks: Mapped[list[Task]] = relationship(back_populates="category")
    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_task_categories_user_name"),)


class Tag(Base):
    """A user-owned task tag."""

    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    normalized_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    tasks: Mapped[list[Task]] = relationship(secondary=task_tags, back_populates="tags")
    notes: Mapped[list[Note]] = relationship(secondary=note_tags, back_populates="tags")
    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_tags_user_name"),)


class TaskSeries(Base):
    """A constrained recurring task definition."""

    __tablename__ = "task_series"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recurrence_json: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    tasks: Mapped[list[Task]] = relationship(back_populates="series", cascade="all, delete-orphan")


class Task(Base):
    """A user-owned task occurrence."""

    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    series_id: Mapped[str | None] = mapped_column(ForeignKey("task_series.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("task_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    category: Mapped[TaskCategory | None] = relationship(back_populates="tasks")
    tags: Mapped[list[Tag]] = relationship(secondary=task_tags, back_populates="tasks")
    series: Mapped[TaskSeries | None] = relationship(back_populates="tasks")
    reminders: Mapped[list[Reminder]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Reminder(Base):
    """A task reminder that the worker converts to a notification."""

    __tablename__ = "reminders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    task: Mapped[Task] = relationship(back_populates="reminders")


class Notification(Base):
    """A persistent user-owned in-app notification."""

    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(512))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    reminder_id: Mapped[str | None] = mapped_column(ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deliveries: Mapped[list[NotificationChannelDelivery]] = relationship(back_populates="notification", cascade="all, delete-orphan")


class NotificationChannelDelivery(Base):
    """One bounded outbound channel delivery attempt for a persisted notification."""

    __tablename__ = "notification_channel_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    notification: Mapped[Notification] = relationship(back_populates="deliveries")
    __table_args__ = (UniqueConstraint("notification_id", "channel", name="uq_notification_deliveries_notification_channel"),)


class Job(Base):
    """Durable bounded worker job metadata."""

    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Note(Base):
    """A user-authored note and canonical source for derived retrieval data."""

    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list[Tag]] = relationship(secondary=note_tags, back_populates="notes")
    search_document: Mapped[NoteSearchDocument | None] = relationship(back_populates="note", cascade="all, delete-orphan", uselist=False)
    chunks: Mapped[list[NoteChunk]] = relationship(back_populates="note", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("user_id", "updated_at", "id", name="uq_notes_user_updated_id"),)


class NoteSearchDocument(Base):
    """Derived searchable projection for one canonical note."""

    __tablename__ = "note_search_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    tags_text: Mapped[str] = mapped_column(Text, default="")
    indexed_version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    note: Mapped[Note] = relationship(back_populates="search_document")


class NoteChunk(Base):
    """A deterministic, provenance-preserving retrieval chunk."""

    __tablename__ = "note_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    source_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    note: Mapped[Note] = relationship(back_populates="chunks")
    embeddings: Mapped[list[NoteChunkEmbedding]] = relationship(back_populates="chunk", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("note_id", "source_version", "chunk_index", name="uq_note_chunks_version_index"),)


class NoteChunkEmbedding(Base):
    """A private, provider-scoped serialized vector for one note chunk."""

    __tablename__ = "note_chunk_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("note_chunks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    chunk: Mapped[NoteChunk] = relationship(back_populates="embeddings")
    __table_args__ = (UniqueConstraint("chunk_id", "provider", "model", name="uq_note_chunk_embeddings_provider_model"),)


class Source(Base):
    """A user-owned external text source stored beneath the Nexus data volume."""

    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="upload")
    title: Mapped[str] = mapped_column(String(160))
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(128), unique=True)
    mime_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="processing", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    versions: Mapped[list[SourceVersion]] = relationship(back_populates="source", cascade="all, delete-orphan")
    chunks: Mapped[list[SourceChunk]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceVersion(Base):
    """An immutable parsed snapshot of an external source."""

    __tablename__ = "source_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    content_length: Mapped[int] = mapped_column(Integer)
    parser: Mapped[str] = mapped_column(String(32))
    parser_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source: Mapped[Source] = relationship(back_populates="versions")
    chunks: Mapped[list[SourceChunk]] = relationship(back_populates="version", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("source_id", "version", name="uq_source_versions_source_version"),)


class SourceChunk(Base):
    """A deterministic, source-aware retrieval chunk."""

    __tablename__ = "source_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    source_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source: Mapped[Source] = relationship(back_populates="chunks")
    version: Mapped[SourceVersion] = relationship(back_populates="chunks")
    __table_args__ = (UniqueConstraint("source_version_id", "chunk_index", name="uq_source_chunks_version_index"),)


class AuditEvent(Base):
    """A bounded security, identity, or data-change event."""

    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(96), index=True)
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    __table_args__ = (UniqueConstraint("id", name="uq_audit_events_id"),)


class HostActionProposal(Base):
    """A durable, user-confirmed proposal for one catalogued host action."""

    __tablename__ = "host_action_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action_key: Mapped[str] = mapped_column(String(96), index=True)
    risk_level: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)


class BackupRecord(Base):
    """Metadata for a NexusOS-owned SQLite backup on the configured data volume."""

    __tablename__ = "backup_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    relative_path: Mapped[str] = mapped_column(String(256), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), index=True)
    integrity_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    encryption_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    encrypted_relative_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    encrypted_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    encrypted_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    replication_status: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    replicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replication_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    pruned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class CalendarCategory(Base):
    """A user-owned calendar category."""

    __tablename__ = "calendar_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    normalized_name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    events: Mapped[list[CalendarEvent]] = relationship(back_populates="category")
    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_calendar_categories_user_name"),)


class CalendarEvent(Base):
    """A user-owned calendar event occurrence."""

    __tablename__ = "calendar_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("calendar_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    category: Mapped[CalendarCategory | None] = relationship(back_populates="events")
    reminders: Mapped[list[CalendarEventReminder]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Plugin(Base):
    """A registered out-of-process plugin declared in an operator-approved directory."""

    __tablename__ = "plugins"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    version: Mapped[str] = mapped_column(String(32))
    entrypoint: Mapped[str] = mapped_column(String(256))
    manifest_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    runs: Mapped[list[PluginRun]] = relationship(back_populates="plugin", cascade="all, delete-orphan")


class PluginRun(Base):
    """Bounded execution metadata for one plugin method invocation."""

    __tablename__ = "plugin_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), index=True)
    error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    plugin: Mapped[Plugin] = relationship(back_populates="runs")


class MediaItem(Base):
    """A derived, rebuildable index entry for one file in an approved media root."""

    __tablename__ = "media_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    root_key: Mapped[str] = mapped_column(String(24))
    relative_path: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(16), index=True)
    mime_type: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    __table_args__ = (UniqueConstraint("root_key", "relative_path", name="uq_media_items_root_path"),)


class FinanceAccount(Base):
    """A user-owned finance account (integer-cent ledger)."""

    __tablename__ = "finance_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    account_type: Mapped[str] = mapped_column(String(24), default="checking")
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    transactions: Mapped[list[FinanceTransaction]] = relationship(back_populates="account", cascade="all, delete-orphan")


class FinanceCategory(Base):
    """A user-owned finance category."""

    __tablename__ = "finance_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    normalized_name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    transactions: Mapped[list[FinanceTransaction]] = relationship(back_populates="category")
    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_finance_categories_user_name"),)


class FinanceTransaction(Base):
    """One integer-cent transaction on a user-owned finance account."""

    __tablename__ = "finance_transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("finance_accounts.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    account: Mapped[FinanceAccount] = relationship(back_populates="transactions")
    category: Mapped[FinanceCategory | None] = relationship(back_populates="transactions")


class CalendarEventReminder(Base):
    """A calendar event reminder that the worker converts to a notification."""

    __tablename__ = "calendar_event_reminders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("calendar_events.id", ondelete="CASCADE"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    event: Mapped[CalendarEvent] = relationship(back_populates="reminders")
