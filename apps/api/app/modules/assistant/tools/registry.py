"""Allowlisted assistant tools with explicit task mutation confirmation."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.db.models import Task
from app.modules.assistant.schemas import ProposedToolCall, ToolDefinition, ToolValidationError
from app.modules.system.service import SystemService
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import complete_task, create_task, delete_task, get_task, list_tasks, update_task
from app.modules.notes.search import search_notes
from app.modules.notes.service import get_note
from app.modules.host_actions.schemas import ActionProposalCreate
from app.modules.host_actions.service import create_proposal
from app.modules.workspace_views.service import WorkspaceViewService


@dataclass(frozen=True)
class RegisteredTool:
    """A fixed tool definition, permission, executor, and risk policy."""

    definition: ToolDefinition
    required_permission: str
    requires_confirmation: bool
    execute: Callable[[ProposedToolCall], dict[str, Any]]


class ToolRegistry:
    """Resolve only server-defined tools; never evaluate model-provided code."""

    def __init__(self, system_service: SystemService, db: OrmSession | None = None, user_id: str | None = None, workspace_service: WorkspaceViewService | None = None) -> None:
        self._tools: dict[str, RegisteredTool] = {
            "system.get_overview": RegisteredTool(
                definition=ToolDefinition(key="system.get_overview", description="Read the current Raspberry Pi system telemetry.", parameters={"type": "object", "properties": {}, "additionalProperties": False}),
                required_permission="system.read_overview", requires_confirmation=False,
                execute=lambda _call: system_service.collect().model_dump(mode="json"),
            )
        }
        if db is not None and user_id is not None:
            self._register_task_tools(db, user_id)
            self._register_plugin_tools(db, user_id)
        if workspace_service is not None:
            self._register_workspace_tools(workspace_service)

    def _register_task_tools(self, db: OrmSession, user_id: str) -> None:
        """Register task tools against the current authenticated user context."""
        self._tools.update({
            "maintenance.request_backup": RegisteredTool(
                definition=ToolDefinition(key="maintenance.request_backup", description="Request a user-confirmed NexusOS database backup. The user must separately confirm the host action before it runs.", parameters={"type": "object", "properties": {}, "additionalProperties": False}),
                required_permission="system.host_actions", requires_confirmation=True,
                execute=lambda call: {"proposal_id": create_proposal(db, user_id, ActionProposalCreate(action_key="maintenance.create_backup", input={}), f"assistant:{call.provider_id}").id},
            ),
            "notes.search": RegisteredTool(
                definition=ToolDefinition(key="notes.search", description="Search the user's notes and return bounded source-aware excerpts.", parameters={"type": "object", "properties": {"query": {"type": "string", "maxLength": 200}, "tag": {"type": "string", "maxLength": 64}, "limit": {"type": "integer", "maximum": 10}}, "required": ["query"], "additionalProperties": False}),
                required_permission="notes.read", requires_confirmation=False,
                execute=lambda call: {"results": [item.model_dump(mode="json") for item in search_notes(db, user_id, str(call.arguments.get("query", "")), tag=call.arguments.get("tag") if isinstance(call.arguments.get("tag"), str) else None, limit=min(int(call.arguments.get("limit", 5)), 10))]},
            ),
            "notes.read": RegisteredTool(
                definition=ToolDefinition(key="notes.read", description="Read one owned note as bounded, untrusted source material.", parameters={"type": "object", "properties": {"note_id": {"type": "string"}}, "required": ["note_id"], "additionalProperties": False}),
                required_permission="notes.read", requires_confirmation=False,
                execute=lambda call: _read_note(db, user_id, call),
            ),
            "tasks.list": RegisteredTool(
                definition=ToolDefinition(key="tasks.list", description="List the user's open tasks with optional filters.", parameters={"type": "object", "properties": {"status": {"type": "string"}, "priority": {"type": "string"}, "limit": {"type": "integer", "maximum": 50}}, "additionalProperties": False}),
                required_permission="tasks.read", requires_confirmation=False,
                execute=lambda call: {"tasks": [task.id for task in list_tasks(db, user_id, status=call.arguments.get("status") if isinstance(call.arguments.get("status"), str) else None, priority=call.arguments.get("priority") if isinstance(call.arguments.get("priority"), str) else None, limit=int(call.arguments.get("limit", 20)))]},
            ),
            "tasks.create": RegisteredTool(
                definition=ToolDefinition(key="tasks.create", description="Create a task after the user confirms the proposed details.", parameters={"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "due_at": {"type": "string"}, "priority": {"type": "string"}, "category": {"type": "string"}, "tags": {"type": "array"}}, "required": ["title"], "additionalProperties": False}),
                required_permission="tasks.write", requires_confirmation=True,
                execute=lambda call: {"task_id": create_task(db, user_id, TaskCreate.model_validate(call.arguments), f"assistant:{call.provider_id}").id},
            ),
            "tasks.update": RegisteredTool(
                definition=ToolDefinition(key="tasks.update", description="Update an owned task after the user confirms the proposed changes.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "due_at": {"type": "string"}, "priority": {"type": "string"}, "status": {"type": "string"}, "category": {"type": "string"}, "tags": {"type": "array"}}, "required": ["task_id"], "additionalProperties": False}),
                required_permission="tasks.write", requires_confirmation=True,
                execute=lambda call: _update_task(db, user_id, call),
            ),
            "tasks.complete": RegisteredTool(
                definition=ToolDefinition(key="tasks.complete", description="Complete an owned task after the user confirms.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False}),
                required_permission="tasks.write", requires_confirmation=True,
                execute=lambda call: _complete_task(db, user_id, call),
            ),
            "tasks.delete": RegisteredTool(
                definition=ToolDefinition(key="tasks.delete", description="Soft-delete an owned task after explicit confirmation.", parameters={"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False}),
                required_permission="tasks.delete", requires_confirmation=True,
                execute=lambda call: _delete_task(db, user_id, call),
            ),
        })

    def _register_plugin_tools(self, db: OrmSession, user_id: str) -> None:
        """Register the always-confirmed out-of-process plugin invocation tool."""
        self._tools["plugins.invoke"] = RegisteredTool(
            definition=ToolDefinition(key="plugins.invoke", description="Invoke a declared capability of an enabled out-of-process plugin after the user explicitly confirms the plugin, method, and bounded arguments.", parameters={"type": "object", "properties": {"plugin": {"type": "string", "maxLength": 64}, "method": {"type": "string", "maxLength": 64}, "arguments": {"type": "object"}}, "required": ["plugin", "method"], "additionalProperties": False}),
            required_permission="plugins.write", requires_confirmation=True,
            execute=lambda call: _invoke_plugin(db, user_id, call),
        )

    def _register_workspace_tools(self, service: WorkspaceViewService) -> None:
        """Register read-only workspace views against the configured host boundary."""
        self._tools.update({
            "files.recent": RegisteredTool(
                definition=ToolDefinition(key="files.recent", description="List bounded recent file metadata beneath approved workspace roots.", parameters={"type": "object", "properties": {"limit": {"type": "integer", "maximum": 20}}, "additionalProperties": False}),
                required_permission="workspace_views.read", requires_confirmation=False,
                execute=lambda call: service.recent_files(min(int(call.arguments.get("limit", 10)), 20)).model_dump(mode="json"),
            ),
            "projects.list": RegisteredTool(
                definition=ToolDefinition(key="projects.list", description="List safe project metadata beneath approved workspace roots.", parameters={"type": "object", "properties": {}, "additionalProperties": False}),
                required_permission="workspace_views.read", requires_confirmation=False,
                execute=lambda _call: service.projects().model_dump(mode="json"),
            ),
            "git.repositories": RegisteredTool(
                definition=ToolDefinition(key="git.repositories", description="Read bounded Git repository status beneath approved workspace roots.", parameters={"type": "object", "properties": {}, "additionalProperties": False}),
                required_permission="workspace_views.read", requires_confirmation=False,
                execute=lambda _call: service.repositories().model_dump(mode="json"),
            ),
            "docker.containers": RegisteredTool(
                definition=ToolDefinition(key="docker.containers", description="Read sanitized Docker container metadata when the optional read-only boundary is available.", parameters={"type": "object", "properties": {}, "additionalProperties": False}),
                required_permission="workspace_views.read", requires_confirmation=False,
                execute=lambda _call: service.containers().model_dump(mode="json"),
            ),
        })

    def definitions(self, permissions: set[str]) -> list[ToolDefinition]:
        """Return only definitions the authenticated user may execute."""
        return [tool.definition for tool in self._tools.values() if tool.required_permission in permissions]

    def requires_confirmation(self, tool_key: str) -> bool:
        """Return whether a valid tool call must wait for explicit approval."""
        tool = self._tools.get(tool_key)
        return tool.requires_confirmation if tool else True

    def execute(self, proposed: ProposedToolCall, permissions: set[str]) -> dict[str, Any]:
        """Validate permission/input and execute one fixed adapter."""
        tool = self._tools.get(proposed.tool_key)
        if tool is None or tool.required_permission not in permissions:
            raise ToolValidationError()
        if proposed.tool_key == "system.get_overview" and proposed.arguments:
            raise ToolValidationError()
        if not isinstance(proposed.arguments, dict) or len(proposed.arguments) > 32:
            raise ToolValidationError()
        try:
            return tool.execute(proposed)
        except (ValueError, TypeError, KeyError) as exc:
            raise ToolValidationError() from exc


def _read_note(db: OrmSession, user_id: str, call: ProposedToolCall) -> dict[str, Any]:
    note_id = call.arguments.get("note_id")
    if not isinstance(note_id, str) or not note_id:
        raise ToolValidationError()
    note = get_note(db, user_id, note_id)
    if note is None:
        raise ToolValidationError()
    return {"source_type": "note", "source_id": note.id, "title": note.title, "content": note.content[:8000], "content_version": note.content_version, "updated_at": note.updated_at.isoformat(), "tags": [tag.name for tag in note.tags]}


def _task_id(call: ProposedToolCall) -> str:
    task_id = call.arguments.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ToolValidationError()
    return task_id


def _update_task(db: OrmSession, user_id: str, call: ProposedToolCall) -> dict[str, Any]:
    task_id = _task_id(call)
    values = dict(call.arguments)
    values.pop("task_id", None)
    task = update_task(db, user_id, task_id, TaskUpdate.model_validate(values), f"assistant:{call.provider_id}")
    if task is None:
        raise ToolValidationError()
    return {"task_id": task.id, "status": task.status}


def _complete_task(db: OrmSession, user_id: str, call: ProposedToolCall) -> dict[str, Any]:
    task, next_task = complete_task(db, user_id, _task_id(call), f"assistant:{call.provider_id}")
    if task is None:
        raise ToolValidationError()
    return {"task_id": task.id, "next_task_id": next_task.id if next_task else None}


def _delete_task(db: OrmSession, user_id: str, call: ProposedToolCall) -> dict[str, Any]:
    task = delete_task(db, user_id, _task_id(call), f"assistant:{call.provider_id}")
    if task is None:
        raise ToolValidationError()
    return {"task_id": task.id, "deleted": True}


def _invoke_plugin(db: OrmSession, user_id: str, call: ProposedToolCall) -> dict[str, Any]:
    """Invoke one allowlisted plugin capability out-of-process after confirmation."""
    from app.modules.plugins.service import PluginError, invoke_plugin

    plugin = call.arguments.get("plugin")
    method = call.arguments.get("method")
    arguments = call.arguments.get("arguments")
    if not isinstance(plugin, str) or not plugin or len(plugin) > 64:
        raise ToolValidationError()
    if not isinstance(method, str) or not method or len(method) > 64:
        raise ToolValidationError()
    if not isinstance(arguments, dict):
        arguments = {}
    if len(arguments) > 16:
        raise ToolValidationError()
    try:
        return {"result": invoke_plugin(db, user_id, plugin, method, arguments)}
    except PluginError as exc:
        raise ToolValidationError() from exc
