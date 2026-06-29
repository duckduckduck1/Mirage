#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
ENV_FILE="${MIRAGE_TG_WS_ENV:-$SCRIPT_DIR/.env.local}"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"

usage() {
  cat <<'USAGE'
Usage:
  tg-ws-proxy.sh init [PUBLIC_HOST]
  tg-ws-proxy.sh install [PUBLIC_HOST]
  tg-ws-proxy.sh build
  tg-ws-proxy.sh up
  tg-ws-proxy.sh down
  tg-ws-proxy.sh restart
  tg-ws-proxy.sh firewall
  tg-ws-proxy.sh status
  tg-ws-proxy.sh logs
  tg-ws-proxy.sh links
  tg-ws-proxy.sh rotate-secret

Commands:
  init          Create .env.local, set PUBLIC_HOST, generate a dd-secret.
  install       Init, build image, open UFW port, start container, print links.
  build         Build Docker image from Flowseal/tg-ws-proxy v1.6.5.
  up            Start container.
  down          Stop container.
  restart       Recreate container.
  firewall      Allow public TCP port in UFW.
  status        Show Docker Compose service status.
  logs          Follow container logs.
  links         Print Telegram proxy links.
  rotate-secret Generate a new secret and print fresh links.
USAGE
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

is_placeholder_host() {
  local value="${1:-}"
  [[ -z "$value" || "$value" == "SERVER_HOST_OR_DOMAIN" || "$value" == "SERVER_IP" ]]
}

docker_cmd() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
    return
  fi

  if have sudo; then
    sudo docker "$@"
    return
  fi

  docker "$@"
}

compose_cmd() {
  docker_cmd compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

copy_env_if_needed() {
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
  fi
}

load_env() {
  [[ -f "$ENV_FILE" ]] || die "missing $ENV_FILE; run: $0 init PUBLIC_HOST"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

set_env_var() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"

  if [[ -f "$ENV_FILE" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { prefix = key "="; written = 0 }
      index($0, prefix) == 1 { print prefix value; written = 1; next }
      { print }
      END { if (written == 0) print prefix value }
    ' "$ENV_FILE" > "$tmp"
  else
    printf '%s=%s\n' "$key" "$value" > "$tmp"
  fi

  mv "$tmp" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}

detect_public_host() {
  if have curl; then
    curl -fsS --max-time 5 https://api.ipify.org || true
  fi
}

generate_secret() {
  if have openssl; then
    openssl rand -hex 16
    return
  fi

  if have python3; then
    python3 - <<'PY'
import secrets
print(secrets.token_hex(16))
PY
    return
  fi

  die "openssl or python3 is required to generate secret"
}

hex_encode() {
  local value="$1"
  if have od; then
    printf '%s' "$value" | od -An -tx1 -v | tr -d ' \n'
    return
  fi

  if have python3; then
    VALUE_TO_HEX="$value" python3 - <<'PY'
import os
print(os.environ["VALUE_TO_HEX"].encode("utf-8").hex())
PY
    return
  fi

  die "od or python3 is required to encode FakeTLS domain"
}

cmd_init() {
  local requested_host="${1:-}"
  copy_env_if_needed
  load_env

  local public_host="$requested_host"
  if is_placeholder_host "$public_host"; then
    public_host="${TG_WS_PUBLIC_HOST:-}"
  fi
  if is_placeholder_host "$public_host"; then
    public_host="$(detect_public_host)"
  fi
  is_placeholder_host "$public_host" && die "pass PUBLIC_HOST explicitly: $0 init SERVER_HOST_OR_DOMAIN"

  set_env_var TG_WS_PUBLIC_HOST "$public_host"

  load_env
  if [[ -z "${TG_WS_SECRET:-}" ]]; then
    set_env_var TG_WS_SECRET "$(generate_secret)"
  fi

  printf 'tg-ws-proxy initialized\n'
  printf 'env: %s\n' "$ENV_FILE"
  printf '\n'
  printf 'Next commands on VPS:\n'
  printf '  %s build\n' "$0"
  printf '  %s firewall\n' "$0"
  printf '  %s up\n' "$0"
  printf '  %s links\n' "$0"
}

cmd_build() {
  load_env
  compose_cmd build
}

cmd_up() {
  load_env
  compose_cmd up -d
}

cmd_down() {
  load_env
  compose_cmd down
}

cmd_restart() {
  load_env
  compose_cmd up -d --force-recreate
}

cmd_firewall() {
  load_env
  local port="${TG_WS_PUBLIC_PORT:-9443}"
  [[ "$port" =~ ^[0-9]+$ ]] || die "TG_WS_PUBLIC_PORT must be numeric"

  if ! have ufw; then
    die "ufw is not installed; open ${port}/tcp manually"
  fi

  if [[ "$(id -u)" -eq 0 ]]; then
    ufw allow "${port}/tcp"
    ufw status
    return
  fi

  if have sudo; then
    sudo ufw allow "${port}/tcp"
    sudo ufw status
    return
  fi

  die "run as root or install sudo to open ${port}/tcp"
}

cmd_install() {
  cmd_init "${1:-}"
  cmd_build
  cmd_firewall
  cmd_up
  cmd_status
  cmd_links
}

cmd_status() {
  load_env
  compose_cmd ps
}

cmd_logs() {
  load_env
  compose_cmd logs -f --tail=100 tg-ws-proxy
}

cmd_links() {
  load_env
  local host="${TG_WS_PUBLIC_HOST:-}"
  local port="${TG_WS_PUBLIC_PORT:-9443}"
  local secret="${TG_WS_SECRET:-}"
  local proxy_secret="dd${secret}"

  is_placeholder_host "$host" && die "TG_WS_PUBLIC_HOST is not set; run: $0 init PUBLIC_HOST"
  [[ -n "$secret" ]] || die "TG_WS_SECRET is empty; run: $0 rotate-secret"
  if [[ -n "${TG_WS_FAKE_TLS_DOMAIN:-}" ]]; then
    proxy_secret="ee${secret}$(hex_encode "$TG_WS_FAKE_TLS_DOMAIN")"
  fi

  printf 'tg://proxy?server=%s&port=%s&secret=%s\n' "$host" "$port" "$proxy_secret"
  printf 'https://t.me/proxy?server=%s&port=%s&secret=%s\n' "$host" "$port" "$proxy_secret"
}

cmd_rotate_secret() {
  load_env
  set_env_var TG_WS_SECRET "$(generate_secret)"
  printf 'secret rotated\n'
  cmd_links
}

main() {
  local command="${1:-}"
  case "$command" in
    init)
      shift
      cmd_init "${1:-}"
      ;;
    install)
      shift
      cmd_install "${1:-}"
      ;;
    build)
      cmd_build
      ;;
    up)
      cmd_up
      ;;
    down)
      cmd_down
      ;;
    restart)
      cmd_restart
      ;;
    firewall)
      cmd_firewall
      ;;
    status)
      cmd_status
      ;;
    logs)
      cmd_logs
      ;;
    links)
      cmd_links
      ;;
    rotate-secret)
      cmd_rotate_secret
      ;;
    -h|--help|help|'')
      usage
      ;;
    *)
      usage >&2
      die "unknown command: $command"
      ;;
  esac
}

main "$@"
