#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
ENV_FILE="${MIRAGE_MTPROXY_ENV:-$SCRIPT_DIR/.env.local}"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
CONFIG_FILE="${MIRAGE_MTPROXY_CONFIG:-$SCRIPT_DIR/config.local.toml}"
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"
DEFAULT_IMAGE="nineseconds/mtg:2.2.8"

usage() {
  cat <<'USAGE'
Usage:
  mtproxy.sh init [PUBLIC_HOST]
  mtproxy.sh install [PUBLIC_HOST]
  mtproxy.sh render
  mtproxy.sh firewall
  mtproxy.sh up
  mtproxy.sh down
  mtproxy.sh restart
  mtproxy.sh rotate-secret [FRONT_DOMAIN]
  mtproxy.sh status
  mtproxy.sh logs
  mtproxy.sh doctor
  mtproxy.sh links

Commands:
  init       Create .env.local, detect or set PUBLIC_HOST, generate FakeTLS secret.
  install    Init, open UFW port, start container, print links.
  render     Render config.local.toml from .env.local.
  firewall   Allow MTProxy public TCP port in UFW.
  up         Render config and start MTProxy with Docker Compose.
  down       Stop and remove the MTProxy container.
  restart    Render config and recreate the MTProxy container.
  rotate-secret
             Generate a new FakeTLS secret, optionally for another front domain.
  status     Show Docker Compose service status.
  logs       Follow MTProxy logs.
  doctor     Run mtg doctor against the rendered config.
  links      Print tg:// and https://t.me/proxy links.

PUBLIC_HOST is the VPS public IP or domain used by Telegram clients.
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

is_ipv4() {
  local regex='^([0-9]{1,3}\.){3}[0-9]{1,3}$'
  [[ "${1:-}" =~ $regex ]]
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

trim() {
  local value="$*"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

toml_escape() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "$value"
}

toml_string_list_from_csv() {
  local raw="${1:-}"
  local item
  local first=1
  local old_ifs="$IFS"
  IFS=','
  for item in $raw; do
    IFS="$old_ifs"
    item="$(trim "$item")"
    [[ -n "$item" ]] || continue
    if [[ "$first" -eq 0 ]]; then
      printf ',\n'
    fi
    printf '  "%s"' "$(toml_escape "$item")"
    first=0
    IFS=','
  done
  IFS="$old_ifs"
  printf '\n'
}

bool_value() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON)
      printf 'true'
      ;;
    0|false|FALSE|no|NO|off|OFF|'')
      printf 'false'
      ;;
    *)
      return 1
      ;;
  esac
}

generate_secret() {
  local image="${MTG_IMAGE:-$DEFAULT_IMAGE}"
  local front_domain="${MTG_FRONT_DOMAIN:-vk.ru}"
  docker_cmd run --rm "$image" generate-secret --hex "$front_domain" | tr -d '\r\n'
}

ensure_secret() {
  load_env
  if [[ -n "${MTG_SECRET:-}" ]]; then
    return
  fi

  local secret
  secret="$(generate_secret)"
  [[ -n "$secret" ]] || die "failed to generate MTProxy secret"
  set_env_var MTG_SECRET "$secret"
}

cmd_init() {
  local requested_host="${1:-}"
  copy_env_if_needed
  load_env

  local public_host="$requested_host"
  if is_placeholder_host "$public_host"; then
    public_host="${MTG_PUBLIC_HOST:-}"
  fi
  if is_placeholder_host "$public_host"; then
    public_host="$(detect_public_host)"
  fi
  is_placeholder_host "$public_host" && die "pass PUBLIC_HOST explicitly: $0 init SERVER_HOST_OR_DOMAIN"

  set_env_var MTG_PUBLIC_HOST "$public_host"
  if is_ipv4 "$public_host"; then
    set_env_var MTG_PUBLIC_IPV4 "$public_host"
  fi

  load_env
  if [[ -z "${MTG_SECRET:-}" ]]; then
    local secret
    secret="$(generate_secret)"
    [[ -n "$secret" ]] || die "failed to generate MTProxy secret"
    set_env_var MTG_SECRET "$secret"
  fi

  cmd_render
  printf 'MTProxy initialized\n'
  printf 'env: %s\n' "$ENV_FILE"
  printf 'config: %s\n' "$CONFIG_FILE"
  printf '\n'
  printf 'Next commands on VPS:\n'
  printf '  %s firewall\n' "$0"
  printf '  %s up\n' "$0"
  printf '  %s links\n' "$0"
}

cmd_render() {
  ensure_secret
  load_env

  local bind="${MTG_BIND:-0.0.0.0:3128}"
  local metrics_bind="${MTG_METRICS_BIND:-0.0.0.0:3129}"
  local front_port="${MTG_FRONT_PORT:-443}"
  local prefer_ip="${MTG_PREFER_IP:-prefer-ipv4}"
  local dns="${MTG_DNS:-https://1.1.1.1/dns-query}"
  local auto_update="${MTG_AUTO_UPDATE:-false}"
  local extra_defenses_enabled="${MTG_EXTRA_DEFENSES_ENABLED:-false}"
  local doppelganger_urls="${MTG_DOPPELGANGER_URLS:-https://vk.ru/}"
  local blocklist_enabled="${MTG_BLOCKLIST_ENABLED:-false}"
  local blocklist_urls="${MTG_BLOCKLIST_URLS:-https://iplists.firehol.org/files/firehol_level1.netset}"
  local auto_update_toml
  local extra_defenses_enabled_toml
  local blocklist_enabled_toml

  [[ "$front_port" =~ ^[0-9]+$ ]] || die "MTG_FRONT_PORT must be numeric"
  [[ -n "${MTG_SECRET:-}" ]] || die "MTG_SECRET is empty"
  auto_update_toml="$(bool_value "$auto_update")" || die "MTG_AUTO_UPDATE must be true or false"
  extra_defenses_enabled_toml="$(bool_value "$extra_defenses_enabled")" || die "MTG_EXTRA_DEFENSES_ENABLED must be true or false"
  blocklist_enabled_toml="$(bool_value "$blocklist_enabled")" || die "MTG_BLOCKLIST_ENABLED must be true or false"

  {
    printf '# Generated by ops/mtproxy/mtproxy.sh. Do not edit manually.\n'
    printf 'debug = false\n'
    printf 'secret = "%s"\n' "$(toml_escape "$MTG_SECRET")"
    printf 'bind-to = "%s"\n' "$(toml_escape "$bind")"
    printf 'concurrency = 8192\n'
    printf 'prefer-ip = "%s"\n' "$(toml_escape "$prefer_ip")"
    if [[ -n "${MTG_PUBLIC_IPV4:-}" ]]; then
      printf 'public-ipv4 = "%s"\n' "$(toml_escape "$MTG_PUBLIC_IPV4")"
    fi
    printf 'auto-update = %s\n' "$auto_update_toml"
    printf '\n'
    printf '[domain-fronting]\n'
    printf 'port = %s\n' "$front_port"
    printf '\n'
    printf '[network]\n'
    printf 'dns = "%s"\n' "$(toml_escape "$dns")"
    printf 'proxies = []\n'
    printf '\n'
    if [[ "$extra_defenses_enabled_toml" == "true" ]]; then
      printf '[defense.doppelganger]\n'
      printf 'urls = [\n'
      toml_string_list_from_csv "$doppelganger_urls"
      printf ']\n'
      printf 'repeats-per-raid = 10\n'
      printf 'raid-each = "6h"\n'
      printf 'drs = false\n'
      printf '\n'
      printf '[defense.anti-replay]\n'
      printf 'enabled = true\n'
      printf 'max-size = "1mib"\n'
      printf 'error-rate = 0.001\n'
      printf '\n'
      printf '[defense.blocklist]\n'
      printf 'enabled = %s\n' "$blocklist_enabled_toml"
      printf 'download-concurrency = 2\n'
      printf 'urls = [\n'
      toml_string_list_from_csv "$blocklist_urls"
      printf ']\n'
      printf 'update-each = "24h"\n'
      printf '\n'
      printf '[defense.allowlist]\n'
      printf 'enabled = false\n'
      printf 'download-concurrency = 2\n'
      printf 'urls = []\n'
      printf 'update-each = "24h"\n'
      printf '\n'
    fi
    printf '[stats.prometheus]\n'
    printf 'enabled = true\n'
    printf 'bind-to = "%s"\n' "$(toml_escape "$metrics_bind")"
    printf 'http-path = "/"\n'
    printf 'metric-prefix = "mtg"\n'
  } > "$CONFIG_FILE"

  chmod 600 "$CONFIG_FILE" 2>/dev/null || true
  printf 'rendered: %s\n' "$CONFIG_FILE"
}

cmd_up() {
  cmd_render >/dev/null
  compose_cmd up -d
}

cmd_firewall() {
  load_env
  local port="${MTG_PUBLIC_PORT:-8443}"
  [[ "$port" =~ ^[0-9]+$ ]] || die "MTG_PUBLIC_PORT must be numeric"

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
  local public_host="${1:-}"
  cmd_init "$public_host"
  cmd_firewall
  cmd_up
  cmd_status
  cmd_links
}

cmd_down() {
  load_env
  compose_cmd down
}

cmd_restart() {
  cmd_render >/dev/null
  compose_cmd up -d --force-recreate
}

cmd_rotate_secret() {
  local front_domain="${1:-}"
  load_env

  if [[ -n "$front_domain" ]]; then
    set_env_var MTG_FRONT_DOMAIN "$front_domain"
  fi

  load_env
  local secret
  secret="$(generate_secret)"
  [[ -n "$secret" ]] || die "failed to generate MTProxy secret"
  set_env_var MTG_SECRET "$secret"

  cmd_render
  printf 'secret rotated for front domain: %s\n' "${MTG_FRONT_DOMAIN:-vk.ru}"
  cmd_links
}

cmd_status() {
  load_env
  compose_cmd ps
}

cmd_logs() {
  load_env
  compose_cmd logs -f --tail=100 mtproxy
}

cmd_doctor() {
  cmd_render >/dev/null
  load_env
  docker_cmd run --rm -v "$CONFIG_FILE:/config/config.toml:ro" "${MTG_IMAGE:-$DEFAULT_IMAGE}" doctor /config/config.toml
}

cmd_links() {
  load_env
  local host="${MTG_PUBLIC_HOST:-}"
  local port="${MTG_PUBLIC_PORT:-8443}"
  local secret="${MTG_SECRET:-}"

  is_placeholder_host "$host" && die "MTG_PUBLIC_HOST is not set; run: $0 init PUBLIC_HOST"
  [[ -n "$secret" ]] || die "MTG_SECRET is empty; run: $0 init PUBLIC_HOST"

  printf 'tg://proxy?server=%s&port=%s&secret=%s\n' "$host" "$port" "$secret"
  printf 'https://t.me/proxy?server=%s&port=%s&secret=%s\n' "$host" "$port" "$secret"
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
    render)
      cmd_render
      ;;
    firewall)
      cmd_firewall
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
    rotate-secret)
      shift
      cmd_rotate_secret "${1:-}"
      ;;
    status)
      cmd_status
      ;;
    logs)
      cmd_logs
      ;;
    doctor)
      cmd_doctor
      ;;
    links)
      cmd_links
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
