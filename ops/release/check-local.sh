#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SKIP_DOCKER=false
PYTHON_CMD=""

usage() {
  cat <<'EOF'
Usage: ops/release/check-local.sh [--skip-docker]

Runs the v0.1 release gate used by GitHub Actions.

Options:
  --skip-docker  Run Python, JavaScript and shell checks only.
EOF
}

log() {
  printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-docker)
      SKIP_DOCKER=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

resolve_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then
    if try_python "$PYTHON_BIN"; then
      return
    fi
    die "PYTHON_BIN does not work: $PYTHON_BIN"
  fi
  if try_python "python"; then
    return
  fi
  if try_python "python3"; then
    return
  fi
  if try_python "py -3"; then
    return
  fi
  die "Python was not found"
}

try_python() {
  local candidate="$1"
  local first_word
  first_word="${candidate%% *}"
  command -v "$first_word" >/dev/null 2>&1 || return 1
  PYTHON_CMD="$candidate"
  run_python --version >/dev/null 2>&1
}

run_python() {
  # shellcheck disable=SC2086
  $PYTHON_CMD "$@"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 was not found"
}

check_no_secrets() {
  run_python - <<'PY'
import re
import subprocess
import sys
from pathlib import Path

tracked = subprocess.check_output(["git", "ls-files", "-z"])
paths = [Path(item.decode("utf-8")) for item in tracked.split(b"\0") if item]
findings: list[str] = []

for path in paths:
    normalized = path.as_posix()
    name = path.name

    if name.startswith(".env") and not name.endswith(".example"):
        findings.append(f"{normalized}: tracked env file")
    if any(part in {"backups", "exports", "secrets"} for part in path.parts):
        findings.append(f"{normalized}: tracked sensitive directory")
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".dump", ".backup", ".key", ".pem", ".p12"}:
        findings.append(f"{normalized}: tracked sensitive file extension")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        findings.append(f"{normalized}: cannot read file: {exc}")
        continue

    if re.search(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----", text):
        findings.append(f"{normalized}: private key marker")

    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        proxy_url = re.search(r"\b(?:vless|ss)://\S+@\S+", stripped)
        if proxy_url:
            lowered = stripped.lower()
            placeholder = any(
                token in lowered
                for token in [
                    "...",
                    "example.",
                    "example/",
                    "server_ip",
                    "server_host",
                    "domain",
                    "домен",
                    "uuid",
                    "panel.local",
                    "vpn.example",
                ]
            )
            real_ip_url = re.search(r"\b(?:vless|ss)://\S+@\d{1,3}(?:\.\d{1,3}){3}\b", stripped)
            if real_ip_url or not placeholder:
                findings.append(f"{normalized}:{line_no}: proxy link")

        assignment = re.match(r"^([A-Z0-9_]*(?:TOKEN|PASSWORD|PRIVATE_KEY|SECRET)[A-Z0-9_]*)=(.+)$", stripped)
        if assignment:
            value = assignment.group(2).strip().strip("\"'")
            safe_value = (
                not value
                or value == "..."
                or value.startswith("${")
                or value.startswith("$")
                or value.startswith("CHANGE_")
                or value.startswith("PASTE_")
                or value.startswith("SERVER_")
                or "example" in value.lower()
            )
            if not safe_value:
                findings.append(f"{normalized}:{line_no}: secret-like assignment")

if findings:
    print("Potential secrets in tracked files:", file=sys.stderr)
    for item in findings:
        print(f"  - {item}", file=sys.stderr)
    sys.exit(1)
PY
}

copy_compose_dir() {
  local src="$1"
  local dest="$2"
  local file
  mkdir -p "$dest"
  while IFS= read -r file; do
    mkdir -p "$dest/$(dirname "$file")"
    cp "$src/$file" "$dest/$file"
  done < <(
    cd "$src"
    find . \
      \( -type d \( -name __pycache__ -o -name output \) -prune \) -o \
      \( -type f ! -name ".env.local" ! -name "*.local.json" -print \)
  )
}

prepare_compose_workspace() {
  COMPOSE_CONFIG_TMP="$(mktemp -d)"
  mkdir -p "$COMPOSE_CONFIG_TMP/ops"
  cp .dockerignore "$COMPOSE_CONFIG_TMP/.dockerignore"
  copy_compose_dir ops/xui "$COMPOSE_CONFIG_TMP/ops/xui"
  copy_compose_dir ops/admin "$COMPOSE_CONFIG_TMP/ops/admin"
  cp ops/xui/.env.example "$COMPOSE_CONFIG_TMP/ops/xui/.env.local"
  cp ops/admin/.env.example "$COMPOSE_CONFIG_TMP/ops/admin/.env.local"
  mkdir -p \
    "$COMPOSE_CONFIG_TMP/backups" \
    "$COMPOSE_CONFIG_TMP/.local/restore-requests" \
    "$COMPOSE_CONFIG_TMP/.local/restore-status" \
    "$COMPOSE_CONFIG_TMP/.local/admin-alerts"
}

cleanup() {
  if [ -n "${COMPOSE_CONFIG_TMP:-}" ]; then
    rm -rf "$COMPOSE_CONFIG_TMP"
  fi
}
trap cleanup EXIT

cd "$REPO_ROOT"
resolve_python

log "Tool versions"
run_python --version
require_command node
node --version
if [ "$SKIP_DOCKER" = false ]; then
  require_command docker
  docker compose version
fi

log "Secret guard"
check_no_secrets

log "Python unit tests"
run_python -m unittest ops.admin.test_admin_api ops.xui.test_xui_api

log "Python syntax"
run_python -m py_compile \
  infra/ansible/roles/marzban/files/apply-a13.py \
  ops/admin/admin_api.py \
  ops/admin/restore_helper.py \
  ops/xui/xui_api.py

log "Admin UI JavaScript syntax"
node --check ops/admin/static/app.js

log "Shell syntax"
require_command bash
bash -n ops/vpn/deploy.sh

if [ "$SKIP_DOCKER" = true ]; then
  log "Docker checks skipped"
  exit 0
fi

log "Docker Compose config"
prepare_compose_workspace
(
  cd "$COMPOSE_CONFIG_TMP"
  docker compose -f ops/xui/compose.yml config > xui-compose.yml
  docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml config > admin-compose.yml
)

log "Docker image builds"
(
  cd "$COMPOSE_CONFIG_TMP"
  docker compose -f ops/xui/compose.yml build
  docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml build
)

log "Release gate passed"
