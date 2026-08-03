"""Optional read-only Docker metadata adapter."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from urllib.parse import unquote
from pathlib import Path

from app.modules.workspace_views.schemas import DockerContainerView

_MAX_RESPONSE = 1_000_000


def _request(socket_path: Path) -> list[dict[str, object]]:
    """Read Docker container metadata through a configured Unix socket only."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(2.0)
    try:
        client.connect(str(socket_path))
        client.sendall(b"GET /containers/json?all=1 HTTP/1.0\r\nHost: docker\r\nConnection: close\r\n\r\n")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_RESPONSE:
                raise ValueError("docker_response_too_large")
            chunks.append(chunk)
    finally:
        client.close()
    raw = b"".join(chunks)
    body = raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else raw
    if b" 200 " not in raw.split(b"\r\n", 1)[0]:
        raise ValueError("docker_request_failed")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, list):
        raise ValueError("docker_response_invalid")
    return [item for item in value if isinstance(item, dict)]


def list_containers(socket_path: Path | None, *, limit: int = 100) -> list[DockerContainerView]:
    """Return redacted container metadata, or an empty list when unavailable."""
    if socket_path is None or not socket_path.is_socket():
        return []
    containers = _request(socket_path)
    result: list[DockerContainerView] = []
    for item in containers[: max(1, min(limit, 100))]:
        names = item.get("Names")
        name = unquote(str(names[0]).lstrip("/")) if isinstance(names, list) and names else "unknown"
        labels = item.get("Labels") if isinstance(item.get("Labels"), dict) else {}
        state = str(item.get("State", "unknown"))
        if state not in {"running", "exited", "created", "paused", "restarting", "removing", "dead"}:
            state = "unknown"
        created: datetime | None = None
        raw_created = item.get("Created")
        if isinstance(raw_created, (int, float)):
            created = datetime.fromtimestamp(raw_created, UTC)
        ports: list[str] = []
        raw_ports = item.get("Ports")
        if isinstance(raw_ports, list):
            for port in raw_ports[:32]:
                if isinstance(port, dict) and isinstance(port.get("PublicPort"), int) and isinstance(port.get("PrivatePort"), int):
                    ports.append(f"{port.get('PublicPort')}:{port.get('PrivatePort')}/{port.get('Type', 'tcp')}")
        result.append(DockerContainerView(id=str(item.get("Id", ""))[:20], name=name[:160], image=str(item.get("Image", ""))[:240], state=state, health=None, created_at=created, ports=ports, restart_policy=None, compose_service=str(labels.get("com.docker.compose.service"))[:128] if labels.get("com.docker.compose.service") else None))
    return result
