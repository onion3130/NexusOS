"""Allowlisted assistant tool registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.modules.assistant.schemas import ProposedToolCall, ToolDefinition, ToolValidationError
from app.modules.system.service import SystemService


@dataclass(frozen=True)
class RegisteredTool:
    """A fixed tool definition, permission, and read-only executor."""

    definition: ToolDefinition
    required_permission: str
    execute: Callable[[], dict[str, Any]]


class ToolRegistry:
    """Resolve only server-defined tools; never evaluate model-provided code."""

    def __init__(self, system_service: SystemService) -> None:
        self._tools = {
            "system.get_overview": RegisteredTool(
                definition=ToolDefinition(
                    key="system.get_overview",
                    description="Read the current Raspberry Pi system telemetry.",
                    parameters={"type": "object", "properties": {}, "additionalProperties": False},
                ),
                required_permission="system.read_overview",
                execute=lambda: system_service.collect().model_dump(mode="json"),
            )
        }

    def definitions(self, permissions: set[str]) -> list[ToolDefinition]:
        """Return only definitions the authenticated user may execute."""
        return [tool.definition for tool in self._tools.values() if tool.required_permission in permissions]

    def execute(self, proposed: ProposedToolCall, permissions: set[str]) -> dict[str, Any]:
        """Validate permission/input and execute the fixed no-argument adapter."""
        tool = self._tools.get(proposed.tool_key)
        if tool is None or proposed.arguments or tool.required_permission not in permissions:
            raise ToolValidationError()
        return tool.execute()
