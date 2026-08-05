#!/usr/bin/env bash
# NexusOS host update agent — fixed steps only, no request-supplied commands.
#
# Watches the shared data volume for browser-queued update requests and runs:
#   1) git fetch + ff-only pull on the configured repo
#   2) docker compose build
#   3) alembic upgrade head
#   4) docker compose up -d
#
# Required environment:
#   NEXUS_REPO_DIR   Absolute path to the NexusOS git checkout
#   NEXUS_DATA_DIR   Absolute path matching the container DATA_DIR mount
#                    (on the Pi this is usually /home/pi/nexus-data/db)

set -euo pipefail

REPO_DIR="${NEXUS_REPO_DIR:-}"
DATA_DIR="${NEXUS_DATA_DIR:-}"
POLL_SECONDS="${NEXUS_UPDATE_POLL_SECONDS:-10}"
BRANCH="${NEXUS_UPDATE_BRANCH:-main}"
COMPOSE_ENV_FILE="${NEXUS_COMPOSE_ENV_FILE:-.env}"

if [[ -z "$REPO_DIR" || -z "$DATA_DIR" ]]; then
  echo "NEXUS_REPO_DIR and NEXUS_DATA_DIR are required" >&2
  exit 1
fi
if [[ "$REPO_DIR" != /* || "$DATA_DIR" != /* ]]; then
  echo "NEXUS_REPO_DIR and NEXUS_DATA_DIR must be absolute paths" >&2
  exit 1
fi

UPDATE_DIR="$DATA_DIR/runtime/update"
REQUEST_FILE="$UPDATE_DIR/request.json"
STATUS_FILE="$UPDATE_DIR/status.json"
LOG_FILE="$UPDATE_DIR/log.txt"
LOCK_FILE="$UPDATE_DIR/agent.lock"

# Shared with the containerized API (uid 10001). Keep the update handshake dir
# group/world-writable on single-owner Pi deployments so both sides can write.
mkdir -p "$UPDATE_DIR" || true
chmod 777 "$DATA_DIR/runtime" "$UPDATE_DIR" 2>/dev/null || true
if [[ ! -d "$UPDATE_DIR" || ! -w "$UPDATE_DIR" ]]; then
  echo "Cannot write update handshake directory: $UPDATE_DIR" >&2
  echo "Fix once with: sudo mkdir -p $UPDATE_DIR && sudo chmod -R 777 $DATA_DIR/runtime" >&2
  exit 1
fi

log() {
  local line
  line="$(date -u +"%Y-%m-%dT%H:%M:%SZ") $*"
  printf '%s\n' "$line" | tee -a "$LOG_FILE" >/dev/null
  # Keep the log bounded for the Admin UI.
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 200 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
  fi
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])' <<<"$1"
}

write_status() {
  local state="$1"
  local message="$2"
  local request_id="${3:-}"
  local action="${4:-}"
  local current_commit="${5:-}"
  local target_commit="${6:-}"
  local started_at="${7:-}"
  local finished_at="${8:-}"
  local requested_at="${9:-}"
  local now
  now="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  python3 - "$STATUS_FILE" "$state" "$message" "$request_id" "$action" "$current_commit" "$target_commit" "$started_at" "$finished_at" "$requested_at" "$now" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
payload = {
    "state": sys.argv[2],
    "message": sys.argv[3][:400],
    "request_id": sys.argv[4] or None,
    "action": sys.argv[5] or None,
    "current_commit": sys.argv[6] or None,
    "target_commit": sys.argv[7] or None,
    "started_at": sys.argv[8] or None,
    "finished_at": sys.argv[9] or None,
    "requested_at": sys.argv[10] or None,
    "agent_heartbeat_at": sys.argv[11],
    "current_version": None,
}
# Preserve version if present from previous status.
try:
    old = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(old, dict) and old.get("current_version"):
        payload["current_version"] = str(old["current_version"])[:32]
except Exception:
    pass
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

current_commit() {
  git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || true
}

heartbeat_idle() {
  local commit
  commit="$(current_commit)"
  if [[ -f "$STATUS_FILE" ]]; then
    python3 - "$STATUS_FILE" "$commit" <<'PY' || true
import json, pathlib, sys, datetime
path = pathlib.Path(sys.argv[1])
commit = sys.argv[2] or None
now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
try:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {}
except Exception:
    data = {"state": "idle", "message": "Host update agent is online."}
if data.get("state") not in {"queued", "running"}:
    data.setdefault("state", "idle")
    data.setdefault("message", "Host update agent is online.")
data["agent_heartbeat_at"] = now
if commit:
    data["current_commit"] = commit
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
tmp.replace(path)
PY
  else
    write_status "idle" "Host update agent is online." "" "" "$commit" ""
  fi
}

process_request() {
  local raw action request_id requested_at started finished before after msg
  raw="$(cat "$REQUEST_FILE")"
  action="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(d.get("action",""))' "$raw")"
  request_id="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(d.get("id",""))' "$raw")"
  requested_at="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(d.get("requested_at",""))' "$raw")"

  if [[ "$action" != "check" && "$action" != "apply" ]]; then
    write_status "failed" "Invalid update action rejected by host agent." "$request_id" "$action"
    rm -f "$REQUEST_FILE"
    return
  fi
  if [[ ! -d "$REPO_DIR/.git" || ! -f "$REPO_DIR/docker-compose.yml" ]]; then
    write_status "failed" "Configured repository path is not a NexusOS checkout." "$request_id" "$action"
    rm -f "$REQUEST_FILE"
    return
  fi

  : > "$LOG_FILE"
  started="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  before="$(current_commit)"
  write_status "running" "Host agent started ${action}." "$request_id" "$action" "$before" "" "$started" "" "$requested_at"
  log "Starting action=${action} request=${request_id} repo=${REPO_DIR}"

  (
    cd "$REPO_DIR"
    log "git fetch origin ${BRANCH}"
    git fetch --quiet origin "$BRANCH"
    after="$(git rev-parse --short "origin/${BRANCH}")"
    write_status "running" "Fetched origin/${BRANCH}." "$request_id" "$action" "$before" "$after" "$started" "" "$requested_at"

    if [[ "$action" == "check" ]]; then
      if [[ "$before" == "$after" ]]; then
        msg="Already up to date at ${before}."
      else
        msg="Update available: ${before} → ${after}."
      fi
      finished="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      write_status "succeeded" "$msg" "$request_id" "$action" "$before" "$after" "$started" "$finished" "$requested_at"
      log "$msg"
      rm -f "$REQUEST_FILE"
      return
    fi

    log "git merge --ff-only origin/${BRANCH}"
    git merge --ff-only "origin/${BRANCH}"
    after="$(current_commit)"
    write_status "running" "Code updated to ${after}. Building images…" "$request_id" "$action" "$before" "$after" "$started" "" "$requested_at"

    log "docker compose build"
    docker compose --env-file "$COMPOSE_ENV_FILE" build nexus-api nexus-web nexus-worker

    log "alembic upgrade head"
    docker compose --env-file "$COMPOSE_ENV_FILE" run --rm nexus-api python -m alembic upgrade head

    log "docker compose up -d"
    docker compose --env-file "$COMPOSE_ENV_FILE" up -d

    finished="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    msg="Updated to ${after}. Containers rebuilt and restarted."
    write_status "succeeded" "$msg" "$request_id" "$action" "$before" "$after" "$started" "$finished" "$requested_at"
    log "$msg"
    rm -f "$REQUEST_FILE"
  )
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another update agent instance holds the lock" >&2
  exit 0
fi

log "Agent starting poll=${POLL_SECONDS}s repo=${REPO_DIR} data=${DATA_DIR}"
heartbeat_idle

while true; do
  heartbeat_idle
  if [[ -f "$REQUEST_FILE" ]]; then
    if process_request; then
      :
    else
      finished="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      write_status "failed" "Host update agent failed. See log for details." "" "apply" "$(current_commit)" "" "" "$finished"
      log "Update failed"
      rm -f "$REQUEST_FILE"
    fi
  fi
  sleep "$POLL_SECONDS"
done
