"""Out-of-process JSON-stdio subprocess broker for approved plugins.

Plugin code never runs inside the API process. A plugin is an executable whose
entrypoint reads one JSON request object per line on stdin and writes exactly
one JSON response object as its final non-empty stdout line::

    {"result": {...}}            on success
    {"error": "bounded_code"}    on failure

The broker spawns the entrypoint with no shell, in a fresh process group, with
POSIX resource limits (CPU, address space, file descriptors) and bounded wall
time and stdout. All entrypoints and capabilities must be declared in the
operator-approved manifest; nothing here is derived from model or plugin input
other than the allowlisted method name and bounded arguments.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

MAX_OUTPUT_BYTES = 256 * 1024
READ_CHUNK = 64 * 1024
MAX_RESPONSE_OBJECT_BYTES = 64 * 1024


class BrokerError(Exception):
    """A bounded, user-safe plugin boundary error."""


class PluginTimeoutError(BrokerError):
    """The plugin exceeded its configured wall-time budget."""


def _apply_process_limits() -> None:
    """Apply bounded POSIX resource limits inside the forked child (Linux/Pi)."""
    if sys.platform == "win32":
        return
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        # Prevent core dumps from leaking host memory to disk.
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ImportError, OSError, ValueError):
        # Non-POSIX or unprivileged environments degrade to wall-time bounds only.
        pass


def _read_stdout_with_cap(stream, cap: int) -> tuple[bytes, bool]:
    """Read stdout until EOF, aborting once the byte cap is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            chunks.append(b"")
            break
        chunks.append(chunk)
    return b"".join(chunks), total > cap


class PluginBroker:
    """Spawn one bounded plugin process per invocation and parse its response."""

    def __init__(self, plugins_dir: Path, timeout_seconds: float = 20.0) -> None:
        self.plugins_dir = plugins_dir.resolve()
        self.timeout_seconds = timeout_seconds

    def resolve_entrypoint(self, plugin_dir: Path, entrypoint: str) -> Path:
        """Resolve and confine an entrypoint strictly inside its plugin directory."""
        root = plugin_dir.resolve()
        candidate = (root / entrypoint).resolve()
        if candidate != root and root not in candidate.parents:
            raise BrokerError("entrypoint_escape")
        if not candidate.is_file():
            raise BrokerError("entrypoint_missing")
        return candidate

    def invoke(
        self,
        plugin_dir: Path,
        entrypoint: str,
        method: str,
        arguments: dict[str, object],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """Run one allowlisted capability and return its bounded result."""
        root = plugin_dir.resolve()
        if root != self.plugins_dir and self.plugins_dir not in root.parents:
            raise BrokerError("plugin_dir_escape")
        executable = self.resolve_entrypoint(plugin_dir, entrypoint)
        payload = json.dumps({"method": method, "arguments": arguments}, separators=(",", ":"), ensure_ascii=True)
        if len(payload.encode("utf-8")) > 32 * 1024:
            raise BrokerError("payload_too_large")
        budget = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        if not 0.1 <= budget <= 300:
            raise BrokerError("invalid_timeout")

        # Never inherit the API environment: it may contain JWT, AI, SMTP, or
        # backup-encryption secrets. Plugins receive only non-sensitive runtime
        # metadata and a minimal execution path.
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": os.environ.get("TZ", "UTC"),
            "PLUGIN_NAME": plugin_dir.name,
            "PLUGIN_METHOD": method,
        }

        command = [str(executable)]
        if executable.suffix.lower() == ".py":
            # Python entrypoints run with the server interpreter, out-of-process,
            # so .py plugins work identically on the Raspberry Pi and on Windows.
            command = [sys.executable, str(executable)]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=str(root),
                env=environment,
                start_new_session=True,
                preexec_fn=_apply_process_limits if sys.platform != "win32" else None,
            )
        except (OSError, ValueError) as exc:
            raise BrokerError("plugin_spawn_failed") from exc

        captured: dict[str, object] = {"bytes": b"", "overflow": False}

        def _reader() -> None:
            data, overflow = _read_stdout_with_cap(process.stdout, MAX_OUTPUT_BYTES)
            captured["bytes"] = data
            captured["overflow"] = overflow

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()
        try:
            process.stdin.write(payload.encode("utf-8") + b"\n")
            process.stdin.flush()
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            _terminate(process)
            raise PluginTimeoutError("plugin_timeout") from None
        reader.join(timeout=5)
        if process.returncode not in (0, None):
            raise BrokerError("plugin_exit_nonzero")
        if captured["overflow"]:
            raise BrokerError("plugin_output_too_large")
        output = captured["bytes"]
        return _parse_response(output)


def _terminate(process: subprocess.Popen) -> None:
    """Kill the plugin process group after a timeout (and after retry)."""
    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(process.pid), 9)
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _parse_response(output: bytes) -> dict[str, object]:
    """Parse the final non-empty stdout line as a bounded JSON object."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise BrokerError("plugin_empty_response")
    if len(lines) > 4096 or len(output) > MAX_OUTPUT_BYTES:
        raise BrokerError("plugin_output_too_large")
    candidate = lines[-1]
    if len(candidate) > MAX_RESPONSE_OBJECT_BYTES:
        raise BrokerError("plugin_response_too_large")
    try:
        response = json.loads(candidate)
    except (TypeError, ValueError):
        raise BrokerError("plugin_invalid_response") from None
    if not isinstance(response, dict):
        raise BrokerError("plugin_invalid_response")
    if "error" in response:
        error = response.get("error")
        if not isinstance(error, str) or not error or len(error) > 96:
            raise BrokerError("plugin_invalid_error")
        raise BrokerError(error)
    result = response.get("result")
    if result is None:
        return {}
    if not isinstance(result, dict):
        raise BrokerError("plugin_invalid_result")
    return result
