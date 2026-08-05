#!/usr/bin/env bash
# Link the Pi-hosted Open WebUI container to the Nexus shared filesystem and
# brand it as the Nexus Assistant. Safe to re-run; preserves the open-webui volume.
set -euo pipefail

# Default matches Nexus DATA_DIR/db on the Pi (API data volume) + /shared.
SHARED_HOST="${NEXUS_SHARED_HOST:-/home/pi/nexus-data/db/shared}"
CONTAINER_NAME="${OPENWEBUI_CONTAINER:-open-webui}"
IMAGE="${OPENWEBUI_IMAGE:-ghcr.io/open-webui/open-webui:main}"
HOST_PORT="${OPENWEBUI_PORT:-8080}"
CONTAINER_FS="${OPENWEBUI_FS_MOUNT:-/data/nexus}"

mkdir -p "${SHARED_HOST}"
chmod 755 "${SHARED_HOST}" || true
# Placeholder so the mount is never empty-looking for operators.
if [[ ! -f "${SHARED_HOST}/README-NEXUS.txt" ]]; then
  cat >"${SHARED_HOST}/README-NEXUS.txt" <<'EOF'
NexusOS shared folder
=====================
Files placed here are visible inside Open WebUI at /data/nexus (read-only).

Tips:
- Add documents to Open WebUI Knowledge / attach them in chat for RAG.
- Nexus Files / workspace views can also point at this directory via WORKSPACE_ROOTS.
EOF
fi

if ! docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Container ${CONTAINER_NAME} not found; creating fresh Open WebUI linked to Nexus."
  docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart always \
    -p "${HOST_PORT}:8080" \
    -v open-webui:/app/backend/data \
    -v "${SHARED_HOST}:${CONTAINER_FS}:ro" \
    -e WEBUI_NAME="Nexus Assistant" \
    -e SCARF_NO_ANALYTICS=true \
    -e DO_NOT_TRACK=true \
    -e ANONYMIZED_TELEMETRY=false \
    "${IMAGE}"
else
  echo "Recreating ${CONTAINER_NAME} with Nexus shared mount ${SHARED_HOST} -> ${CONTAINER_FS}"
  # Preserve named volume data; only replace the container shell + mounts.
  docker stop "${CONTAINER_NAME}"
  docker rm "${CONTAINER_NAME}"
  docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart always \
    -p "${HOST_PORT}:8080" \
    -v open-webui:/app/backend/data \
    -v "${SHARED_HOST}:${CONTAINER_FS}:ro" \
    -e WEBUI_NAME="Nexus Assistant" \
    -e SCARF_NO_ANALYTICS=true \
    -e DO_NOT_TRACK=true \
    -e ANONYMIZED_TELEMETRY=false \
    "${IMAGE}"
fi

echo "Waiting for Open WebUI…"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Open WebUI mounts:"
docker inspect "${CONTAINER_NAME}" --format '{{json .Mounts}}' | python3 -m json.tool 2>/dev/null || docker inspect "${CONTAINER_NAME}" --format '{{json .Mounts}}'
echo
echo "Done. Assistant URL: http://$(hostname -I | awk '{print $1}'):${HOST_PORT}"
echo "Shared host path: ${SHARED_HOST}"
echo "Inside Open WebUI: ${CONTAINER_FS}"
