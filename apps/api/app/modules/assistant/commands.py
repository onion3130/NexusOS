"""In-chat slash commands for the Nexus Assistant."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.runtime_config import RuntimeNimConfig, read_runtime_nim, write_runtime_nim, mark_runtime_nim_active
from app.modules.system.nim_setup import CHAT_PRESETS

_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:+-]{0,159}$")


@dataclass(frozen=True)
class SlashCommandResult:
    """Local assistant reply produced without calling the model provider."""

    content: str
    handled: bool = True


def parse_slash_command(content: str) -> tuple[str, list[str]] | None:
    """Return (command, args) for leading slash commands, else None."""
    text = content.strip()
    if not text.startswith("/"):
        return None
    parts = text.split()
    if not parts:
        return None
    command = parts[0].lower()
    return command, parts[1:]


def _current_model_line(settings: Settings) -> str:
    if settings.ai_provider == "disabled":
        return "Provider: **disabled** (no model active)"
    model = settings.ai_model or "(unset)"
    provider = settings.ai_provider
    label = {
        "nvidia_nim": "NVIDIA NIM",
        "openai": "OpenAI",
        "openai_compatible": "OpenAI-compatible",
    }.get(provider, provider)
    return f"Provider: **{label}**\nModel: `{model}`"


def _list_models_text() -> str:
    lines = ["**Chat model presets**", ""]
    for preset in CHAT_PRESETS:
        mark = " · recommended" if preset.recommended else ""
        lines.append(f"- `{preset.id}` — {preset.label}{mark}")
        if preset.description:
            lines.append(f"  {preset.description}")
    lines.extend(
        [
            "",
            "Switch with `/model set <id>` (owner only, browser-managed NIM).",
            "Example: `/model set meta/llama-3.1-8b-instruct`",
        ]
    )
    return "\n".join(lines)


def _help_text(settings: Settings) -> str:
    return "\n".join(
        [
            "**`/model` commands**",
            "",
            _current_model_line(settings),
            "",
            "- `/model` — show the active model",
            "- `/model list` — list common NVIDIA chat presets",
            "- `/model set <id>` — switch the active model (owner, browser-managed NIM)",
            "- `/model help` — this help",
        ]
    )


def _set_model(settings: Settings, model_id: str, permissions: set[str]) -> SlashCommandResult:
    if "admin.manage_users" not in permissions:
        return SlashCommandResult(
            content="Only the owner can switch models with `/model set`. Use Admin → AI, or ask the owner."
        )
    candidate = model_id.strip()
    if not candidate or not _MODEL_ID_RE.match(candidate):
        return SlashCommandResult(
            content="That model id looks invalid. Use something like `meta/llama-3.1-8b-instruct` (no spaces)."
        )

    runtime = read_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value())
    if runtime is None:
        if settings.ai_provider == "disabled":
            return SlashCommandResult(
                content="AI is disabled. Connect NVIDIA NIM in **Admin → AI**, then try `/model set` again."
            )
        return SlashCommandResult(
            content=(
                f"Current model is `{settings.ai_model or 'unset'}` from environment configuration.\n"
                "Slash-command switching only updates **browser-managed** NIM settings.\n"
                "Open **Admin → AI** to change the model, or save NIM from the browser once so `/model set` can update it."
            )
        )

    if runtime.model == candidate:
        return SlashCommandResult(content=f"Already using `{candidate}`.")

    try:
        updated = RuntimeNimConfig(
            api_key=runtime.api_key,
            model=candidate,
            embeddings_enabled=runtime.embeddings_enabled,
            embedding_model=runtime.embedding_model,
        )
        write_runtime_nim(settings.data_dir, settings.jwt_secret.get_secret_value(), updated)
        mark_runtime_nim_active(settings.data_dir)
        get_settings.cache_clear()
    except Exception:
        return SlashCommandResult(content="Could not update the model configuration. Check Admin → AI and try again.")

    refreshed = get_settings()
    return SlashCommandResult(
        content=(
            f"Model set to `{refreshed.ai_model}`.\n"
            "New messages use this model immediately in this API process.\n"
            "If answers look stale, wait a moment or open Admin → AI to confirm."
        )
    )


def handle_slash_command(content: str, settings: Settings, permissions: set[str]) -> SlashCommandResult | None:
    """Handle known slash commands; return None when the message is normal chat."""
    parsed = parse_slash_command(content)
    if parsed is None:
        return None
    command, args = parsed

    if command not in {"/model", "/models"}:
        if command.startswith("/"):
            return SlashCommandResult(
                content=(
                    f"Unknown command `{command}`.\n"
                    "Available: `/model` — show or switch the chat model. Try `/model help`."
                )
            )
        return None

    if not args or args[0].lower() in {"status", "show", "current"}:
        return SlashCommandResult(content=_current_model_line(settings) + "\n\nTry `/model list` or `/model help`.")

    sub = args[0].lower()
    if sub in {"help", "?", "h"}:
        return SlashCommandResult(content=_help_text(settings))
    if sub in {"list", "ls", "presets"}:
        return SlashCommandResult(content=_list_models_text())
    if sub in {"set", "use", "switch"}:
        if len(args) < 2:
            return SlashCommandResult(content="Usage: `/model set <model-id>`\nExample: `/model set meta/llama-3.1-8b-instruct`")
        return _set_model(settings, args[1], permissions)
    # Bare model id after /model
    if _MODEL_ID_RE.match(args[0]) and ("/" in args[0] or len(args[0]) > 8):
        return _set_model(settings, args[0], permissions)

    return SlashCommandResult(
        content=f"Unknown `/model` option `{args[0]}`.\n\n{_help_text(settings)}"
    )
