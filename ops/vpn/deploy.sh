#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
XUI_OPS_DIR="$REPO_ROOT/ops/xui"
XUI_ENV_FILE="$XUI_OPS_DIR/.env.local"
XUI_COMPOSE_FILE="$XUI_OPS_DIR/compose.yml"
ADMIN_DIR="$REPO_ROOT/ops/admin"
ADMIN_ENV_FILE="$ADMIN_DIR/.env.local"
ADMIN_COMPOSE_FILE="$ADMIN_DIR/compose.yml"
XUI_INSTALL_RESULT="/etc/x-ui/install-result.env"
XUI_INSTALL_URL="https://raw.githubusercontent.com/MHSanaei/3x-ui/master/install.sh"
DEFAULT_REALITY_TARGET="www.amazon.com:443"
DEFAULT_REALITY_SNI="www.amazon.com"
DEFAULT_CLIENTS="main partner shared"
DEFAULT_ADMIN_PORT="8090"

log() {
  printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    die "run as root: sudo $0"
  fi
}

detect_runtime_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER:-}" != "root" ]] && id "$SUDO_USER" >/dev/null 2>&1; then
    printf '%s\n' "$SUDO_USER"
    return
  fi
  if id mirage >/dev/null 2>&1; then
    printf 'mirage\n'
    return
  fi
  printf 'root\n'
}

user_home() {
  local user="$1"
  getent passwd "$user" | cut -d: -f6
}

user_uid() {
  local user="$1"
  id -u "$user"
}

user_gid() {
  local user="$1"
  id -g "$user"
}

detect_public_host() {
  local host="${MIRAGE_VPN_PUBLIC_HOST:-${1:-}}"
  if [[ -n "$host" && "$host" != "SERVER_IP" && "$host" != "SERVER_HOST_OR_DOMAIN" ]]; then
    printf '%s\n' "$host"
    return
  fi

  if have curl; then
    host="$(curl -fsS --max-time 5 https://api.ipify.org || true)"
    if [[ -n "$host" ]]; then
      printf '%s\n' "$host"
      return
    fi
  fi

  die "public host was not detected; pass it explicitly: sudo $0 SERVER_IP"
}

random_hex() {
  local bytes="$1"
  if have openssl; then
    openssl rand -hex "$bytes"
    return
  fi
  od -An -N"$bytes" -tx1 /dev/urandom | tr -d ' \n'
  printf '\n'
}

env_file_value() {
  local file="$1"
  local key="$2"
  [[ -f "$file" ]] || return 0
  awk -F= -v key="$key" '$1 == key {print substr($0, length(key) + 2); exit}' "$file"
}

random_port() {
  shuf -i 10000-60000 -n 1
}

normalize_path_part() {
  local value="$1"
  value="${value#/}"
  value="${value%/}"
  printf '%s\n' "$value"
}

install_packages() {
  log "Installing base packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl jq openssl python3 ufw docker.io

  if ! docker compose version >/dev/null 2>&1; then
    apt-get install -y docker-compose-v2 || apt-get install -y docker-compose-plugin
  fi

  systemctl enable --now docker
  docker compose version >/dev/null 2>&1 || die "docker compose is not available"
}

configure_firewall() {
  log "Configuring VPN-only firewall"
  ufw allow 22/tcp
  ufw allow 443/tcp
  for port in 8388 8443 9443 2096; do
    ufw delete allow "${port}/tcp" >/dev/null 2>&1 || true
  done
  ufw --force enable
  ufw status
}

cleanup_proxy_containers() {
  log "Removing old proxy containers if present"
  docker rm -f mirage-mtproxy mirage-tg-ws-proxy >/dev/null 2>&1 || true
}

install_xui_if_needed() {
  if [[ -x /usr/local/x-ui/x-ui && -f "$XUI_INSTALL_RESULT" ]]; then
    log "3x-ui is already installed"
    return
  fi

  log "Installing 3x-ui in non-interactive mode"
  local install_script="/tmp/3x-ui-install.sh"
  local panel_port="${MIRAGE_XUI_PANEL_PORT:-$(random_port)}"
  local web_base_path="${MIRAGE_XUI_WEB_BASE_PATH:-s-$(random_hex 4)}"
  local username="${MIRAGE_XUI_USERNAME:-admin_$(random_hex 4)}"
  local password="${MIRAGE_XUI_PASSWORD:-$(random_hex 18)}"

  curl -fsSL "$XUI_INSTALL_URL" -o "$install_script"
  chmod +x "$install_script"

  XUI_NONINTERACTIVE=1 \
  XUI_DB_TYPE=sqlite \
  XUI_SSL_MODE=none \
  XUI_PANEL_PORT="$panel_port" \
  XUI_WEB_BASE_PATH="$web_base_path" \
  XUI_USERNAME="$username" \
  XUI_PASSWORD="$password" \
  XUI_SERVER_IP="$PUBLIC_HOST" \
    bash "$install_script"
}

load_xui_result() {
  [[ -f "$XUI_INSTALL_RESULT" ]] || die "$XUI_INSTALL_RESULT was not found after 3x-ui install"
  # shellcheck disable=SC1090
  source "$XUI_INSTALL_RESULT"

  XUI_PANEL_PORT="${XUI_PANEL_PORT:-}"
  XUI_WEB_BASE_PATH="${XUI_WEB_BASE_PATH:-}"
  XUI_USERNAME="${XUI_USERNAME:-}"
  XUI_PASSWORD="${XUI_PASSWORD:-}"
  XUI_API_TOKEN="${XUI_API_TOKEN:-}"

  if [[ -z "$XUI_PANEL_PORT" || -z "$XUI_WEB_BASE_PATH" ]]; then
    local settings
    settings="$(/usr/local/x-ui/x-ui setting -show true 2>/dev/null || true)"
    XUI_PANEL_PORT="${XUI_PANEL_PORT:-$(printf '%s\n' "$settings" | awk -F': ' '/^port:/ {print $2; exit}')}"
    XUI_WEB_BASE_PATH="${XUI_WEB_BASE_PATH:-$(printf '%s\n' "$settings" | awk -F': ' '/^webBasePath:/ {print $2; exit}')}"
  fi

  [[ -n "$XUI_PANEL_PORT" ]] || die "3x-ui panel port was not detected"
  [[ -n "$XUI_WEB_BASE_PATH" ]] || die "3x-ui web base path was not detected"
  XUI_WEB_BASE_PATH="$(normalize_path_part "$XUI_WEB_BASE_PATH")"
}

configure_xui_local_panel() {
  log "Binding 3x-ui panel to localhost"
  /usr/local/x-ui/x-ui setting -listenIP 127.0.0.1 >/dev/null 2>&1 || true
  systemctl enable --now x-ui
  systemctl restart x-ui
  sleep 3
}

write_xui_env() {
  log "Writing xui-ops env"
  local auth_block
  if [[ -n "$XUI_API_TOKEN" ]]; then
    auth_block="MIRAGE_XUI_API_TOKEN=$XUI_API_TOKEN"
  elif [[ -n "$XUI_USERNAME" && -n "$XUI_PASSWORD" ]]; then
    auth_block=$'MIRAGE_XUI_API_TOKEN=\n'"MIRAGE_XUI_USERNAME=$XUI_USERNAME"$'\n'"MIRAGE_XUI_PASSWORD=$XUI_PASSWORD"
  else
    die "neither XUI_API_TOKEN nor panel username/password are available"
  fi

  cat > "$XUI_ENV_FILE" <<EOF
MIRAGE_XUI_BASE_URL=http://127.0.0.1:${XUI_PANEL_PORT}/${XUI_WEB_BASE_PATH}
${auth_block}
MIRAGE_XUI_PUBLIC_HOST=${PUBLIC_HOST}
MIRAGE_XUI_TUNNEL_LOCAL_PORT=2096
MIRAGE_SSH_HOST=${PUBLIC_HOST}
MIRAGE_SSH_USER=${RUNTIME_USER}
MIRAGE_SSH_KEY=\$HOME\\.ssh\\mirage_ed25519
MIRAGE_XUI_VLESS_PORT=443
MIRAGE_XUI_VLESS_REMARK=vless-reality-vision
MIRAGE_XUI_REALITY_TARGET=${MIRAGE_XUI_REALITY_TARGET:-$DEFAULT_REALITY_TARGET}
MIRAGE_XUI_REALITY_SNI=${MIRAGE_XUI_REALITY_SNI:-$DEFAULT_REALITY_SNI}
EOF
  chmod 600 "$XUI_ENV_FILE"
}

xui_ops() {
  docker compose -f "$XUI_COMPOSE_FILE" run --rm xui-ops "$@"
}

build_xui_ops() {
  log "Building xui-ops container"
  docker compose -f "$XUI_COMPOSE_FILE" build
}

write_admin_env() {
  log "Writing Mirage Admin env"
  local admin_token
  if [[ -f "$ADMIN_ENV_FILE" ]]; then
    admin_token="$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_TOKEN || true)"
  fi
  admin_token="${admin_token:-${MIRAGE_ADMIN_TOKEN:-$(random_hex 24)}}"

  local admin_uid admin_gid
  admin_uid="${MIRAGE_ADMIN_UID:-$ADMIN_RUNTIME_UID}"
  admin_gid="${MIRAGE_ADMIN_GID:-$ADMIN_RUNTIME_GID}"

  local backup_retention_days backup_keep_min
  backup_retention_days="${MIRAGE_ADMIN_BACKUP_RETENTION_DAYS:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_BACKUP_RETENTION_DAYS || true)}"
  backup_keep_min="${MIRAGE_ADMIN_BACKUP_KEEP_MIN:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_BACKUP_KEEP_MIN || true)}"

  local alerts_enabled alert_bot_token alert_chat_id alert_interval alert_backup_max_age alert_disk_free_min
  alerts_enabled="${MIRAGE_ALERTS_ENABLED:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERTS_ENABLED || true)}"
  alert_bot_token="${MIRAGE_ALERT_TELEGRAM_BOT_TOKEN:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERT_TELEGRAM_BOT_TOKEN || true)}"
  alert_chat_id="${MIRAGE_ALERT_TELEGRAM_CHAT_ID:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERT_TELEGRAM_CHAT_ID || true)}"
  alert_interval="${MIRAGE_ALERT_INTERVAL_SECONDS:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERT_INTERVAL_SECONDS || true)}"
  alert_backup_max_age="${MIRAGE_ALERT_BACKUP_MAX_AGE_HOURS:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERT_BACKUP_MAX_AGE_HOURS || true)}"
  alert_disk_free_min="${MIRAGE_ALERT_DISK_FREE_MIN_PERCENT:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERT_DISK_FREE_MIN_PERCENT || true)}"

  cat > "$ADMIN_ENV_FILE" <<EOF
MIRAGE_ADMIN_HOST=127.0.0.1
MIRAGE_ADMIN_PORT=${MIRAGE_ADMIN_PORT:-$DEFAULT_ADMIN_PORT}
MIRAGE_ADMIN_TOKEN=${admin_token}
MIRAGE_ADMIN_UID=${admin_uid}
MIRAGE_ADMIN_GID=${admin_gid}
MIRAGE_ADMIN_BACKUP_DIR_HOST=$BACKUP_DIR
MIRAGE_ADMIN_BACKUP_RETENTION_DAYS=${backup_retention_days:-14}
MIRAGE_ADMIN_BACKUP_KEEP_MIN=${backup_keep_min:-3}
MIRAGE_ALERTS_ENABLED=${alerts_enabled:-false}
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=${alert_bot_token:-}
MIRAGE_ALERT_TELEGRAM_CHAT_ID=${alert_chat_id:-}
MIRAGE_ALERT_INTERVAL_SECONDS=${alert_interval:-60}
MIRAGE_ALERT_BACKUP_MAX_AGE_HOURS=${alert_backup_max_age:-36}
MIRAGE_ALERT_DISK_FREE_MIN_PERCENT=${alert_disk_free_min:-10}
MIRAGE_ALERT_STATE_DIR_HOST=$OUTPUT_DIR/alerts
EOF
  chmod 600 "$ADMIN_ENV_FILE"
}

start_admin_api() {
  log "Starting Mirage Admin API"
  docker compose --env-file "$ADMIN_ENV_FILE" -f "$ADMIN_COMPOSE_FILE" up -d --build
}

ensure_api_token() {
  if [[ -n "$XUI_API_TOKEN" ]]; then
    return
  fi

  log "Creating 3x-ui API token"
  local token_json token
  token_json="$(xui_ops create-token --name mirage-deploy)"
  token="$(printf '%s\n' "$token_json" | jq -r 'if type == "string" then . else (.token // .accessToken // .apiToken // .key // .value // .tokenValue // empty) end')"
  [[ -n "$token" ]] || die "could not parse API token from: $token_json"
  XUI_API_TOKEN="$token"
  write_xui_env
}

bootstrap_vpn() {
  log "Creating VLESS Reality inbound and default clients"
  if [[ "${MIRAGE_VPN_RESET_INBOUND:-false}" == "true" ]]; then
    xui_ops bootstrap-vpn \
      --reset-inbound \
      --reality-target "${MIRAGE_XUI_REALITY_TARGET:-$DEFAULT_REALITY_TARGET}" \
      --reality-sni "${MIRAGE_XUI_REALITY_SNI:-$DEFAULT_REALITY_SNI}" \
      --print-links | tee "$OUTPUT_DIR/bootstrap.log"
    return
  fi

  xui_ops bootstrap-vpn \
    --reality-target "${MIRAGE_XUI_REALITY_TARGET:-$DEFAULT_REALITY_TARGET}" \
    --reality-sni "${MIRAGE_XUI_REALITY_SNI:-$DEFAULT_REALITY_SNI}" \
    --print-links | tee "$OUTPUT_DIR/bootstrap.log"
}

collect_client_links() {
  log "Collecting client links"
  mkdir -p "$OUTPUT_DIR/links"
  for client in $DEFAULT_CLIENTS; do
    xui_ops links --email "$client" > "$OUTPUT_DIR/links/${client}.txt"
    xui_ops sub-links --email "$client" > "$OUTPUT_DIR/links/${client}.subscription.txt" 2>/dev/null || true
    xui_ops subscriptions --email "$client" > "$OUTPUT_DIR/links/${client}.profile.txt"
    xui_ops subscriptions --email "$client" --json > "$OUTPUT_DIR/links/${client}.profile.json"
    chmod 600 "$OUTPUT_DIR/links/${client}.txt" \
      "$OUTPUT_DIR/links/${client}.subscription.txt" \
      "$OUTPUT_DIR/links/${client}.profile.txt" \
      "$OUTPUT_DIR/links/${client}.profile.json" 2>/dev/null || true
  done
}

install_backup_timer() {
  log "Installing daily 3x-ui backup timer"
  mkdir -p "$BACKUP_DIR"

  cat > /usr/local/bin/mirage-xui-backup <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [ -f "$ADMIN_ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ADMIN_ENV_FILE"
  set +a
fi
mkdir -p "$BACKUP_DIR"
docker compose -f "$XUI_COMPOSE_FILE" run --rm xui-ops backup-db --output "$BACKUP_DIR/x-ui-\$(date +%Y%m%d-%H%M%S).db"
retention_days="\${MIRAGE_ADMIN_BACKUP_RETENTION_DAYS:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_BACKUP_RETENTION_DAYS || printf '14')}"
keep_min="\${MIRAGE_ADMIN_BACKUP_KEEP_MIN:-$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_BACKUP_KEEP_MIN || printf '3')}"
python3 - "$BACKUP_DIR" "\$retention_days" "\$keep_min" <<'PY'
import sys
import time
from pathlib import Path

backup_dir = Path(sys.argv[1])
retention_days = int(sys.argv[2])
keep_min = int(sys.argv[3])
cutoff = time.time() - retention_days * 24 * 3600
backups = sorted(
    backup_dir.glob("x-ui-*.db"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
for path in backups[keep_min:]:
    if path.stat().st_mtime < cutoff:
        path.unlink()
PY
chmod 700 "$BACKUP_DIR"
chmod 600 "$BACKUP_DIR"/x-ui-*.db 2>/dev/null || true
backup_owner_uid="\${MIRAGE_ADMIN_UID:-$ADMIN_RUNTIME_UID}"
backup_owner_gid="\${MIRAGE_ADMIN_GID:-$ADMIN_RUNTIME_GID}"
chown -R "\$backup_owner_uid:\$backup_owner_gid" "$BACKUP_DIR"
EOF
  chmod 700 /usr/local/bin/mirage-xui-backup

  cat > /etc/systemd/system/mirage-xui-backup.service <<'EOF'
[Unit]
Description=Mirage 3x-ui database backup
After=docker.service x-ui.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mirage-xui-backup
EOF

  cat > /etc/systemd/system/mirage-xui-backup.timer <<'EOF'
[Unit]
Description=Run Mirage 3x-ui database backup daily

[Timer]
OnCalendar=*-*-* 04:10:00
Persistent=true
RandomizedDelaySec=20m

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable --now mirage-xui-backup.timer
  /usr/local/bin/mirage-xui-backup
}

render_access_file() {
  log "Writing access bundle"
  local access_file="$OUTPUT_DIR/access.md"
  local tunnel_url="http://127.0.0.1:2096/${XUI_WEB_BASE_PATH}"
  local tunnel_command="ssh -i \$HOME\\.ssh\\mirage_ed25519 -N -L 2096:127.0.0.1:${XUI_PANEL_PORT} ${RUNTIME_USER}@${PUBLIC_HOST}"
  local admin_port="${MIRAGE_ADMIN_PORT:-$DEFAULT_ADMIN_PORT}"
  local admin_url="http://127.0.0.1:${admin_port}/"
  local admin_tunnel_command="ssh -i \$HOME\\.ssh\\mirage_ed25519 -N -L ${admin_port}:127.0.0.1:${admin_port} ${RUNTIME_USER}@${PUBLIC_HOST}"
  local admin_token
  admin_token="$(awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' "$ADMIN_ENV_FILE" || true)"

  {
    printf '# Mirage VPN access\n\n'
    printf 'Generated: %s\n\n' "$(date -Is)"
    printf '## Mirage Admin\n\n'
    printf '- Local URL after SSH tunnel: `%s`\n' "$admin_url"
    printf '- SSH tunnel command from Windows PowerShell: `%s`\n' "$admin_tunnel_command"
    printf '- API token: `%s`\n\n' "${admin_token:-stored in $ADMIN_ENV_FILE}"
    printf '## Panel\n\n'
    printf '- Public host: `%s`\n' "$PUBLIC_HOST"
    printf '- Panel port on VPS: `%s`\n' "$XUI_PANEL_PORT"
    printf '- Web base path: `/%s`\n' "$XUI_WEB_BASE_PATH"
    printf '- Local browser URL after SSH tunnel: `%s`\n' "$tunnel_url"
    printf '- SSH tunnel command from Windows PowerShell: `%s`\n' "$tunnel_command"
    printf '- Username: `%s`\n' "${XUI_USERNAME:-stored in $XUI_INSTALL_RESULT}"
    printf '- Password: `%s`\n' "${XUI_PASSWORD:-stored in $XUI_INSTALL_RESULT}"
    printf '- API token: `%s`\n\n' "${XUI_API_TOKEN:-stored in $XUI_ENV_FILE}"
    printf '## Clients\n\n'
    for client in $DEFAULT_CLIENTS; do
      printf '### %s\n\n' "$client"
      printf 'Direct link file: `%s`\n\n' "$OUTPUT_DIR/links/${client}.txt"
      sed 's/^/- `/' "$OUTPUT_DIR/links/${client}.txt" | sed 's/$/`/'
      printf '\nProfile bundle: `%s`\n' "$OUTPUT_DIR/links/${client}.profile.txt"
      printf 'Profile bundle JSON: `%s`\n' "$OUTPUT_DIR/links/${client}.profile.json"
      if [[ -s "$OUTPUT_DIR/links/${client}.subscription.txt" ]]; then
        printf '\nSubscription-derived links: `%s`\n\n' "$OUTPUT_DIR/links/${client}.subscription.txt"
        sed 's/^/- `/' "$OUTPUT_DIR/links/${client}.subscription.txt" | sed 's/$/`/'
      fi
      printf '\n'
    done
    printf '## Backups\n\n'
    printf '- Backup directory: `%s`\n' "$BACKUP_DIR"
    printf '- Retention days: `%s`\n' "$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_BACKUP_RETENTION_DAYS || printf '14')"
    printf '- Minimum kept backups: `%s`\n' "$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ADMIN_BACKUP_KEEP_MIN || printf '3')"
    printf '- Timer: `mirage-xui-backup.timer`\n'
    printf '- Manual backup: `sudo /usr/local/bin/mirage-xui-backup`\n'
    printf '\n## Telegram alerts\n\n'
    printf '- Enabled: `%s`\n' "$(env_file_value "$ADMIN_ENV_FILE" MIRAGE_ALERTS_ENABLED || printf 'false')"
    printf '- State directory: `%s`\n' "$OUTPUT_DIR/alerts"
    printf '- Service: `mirage-alerts`\n'
  } > "$access_file"

  chmod 600 "$access_file"
  chmod 700 "$OUTPUT_DIR" "$OUTPUT_DIR/links" "$BACKUP_DIR"
}

fix_output_owner() {
  chown -R "$ADMIN_RUNTIME_UID:$ADMIN_RUNTIME_GID" "$OUTPUT_DIR"
}

main() {
  require_root

  PUBLIC_HOST="$(detect_public_host "${1:-}")"
  RUNTIME_USER="$(detect_runtime_user)"
  ADMIN_RUNTIME_UID="${MIRAGE_ADMIN_UID:-}"
  ADMIN_RUNTIME_GID="${MIRAGE_ADMIN_GID:-}"
  if [[ -z "$ADMIN_RUNTIME_UID" ]]; then
    if [[ "$RUNTIME_USER" == "root" ]]; then
      ADMIN_RUNTIME_UID="10001"
    else
      ADMIN_RUNTIME_UID="$(user_uid "$RUNTIME_USER")"
    fi
  fi
  if [[ -z "$ADMIN_RUNTIME_GID" ]]; then
    if [[ "$RUNTIME_USER" == "root" ]]; then
      ADMIN_RUNTIME_GID="10001"
    else
      ADMIN_RUNTIME_GID="$(user_gid "$RUNTIME_USER")"
    fi
  fi
  RUNTIME_HOME="$(user_home "$RUNTIME_USER")"
  [[ -n "$RUNTIME_HOME" ]] || RUNTIME_HOME="/root"
  OUTPUT_DIR="${MIRAGE_VPN_OUTPUT_DIR:-$RUNTIME_HOME/mirage-vpn}"
  BACKUP_DIR="${MIRAGE_VPN_BACKUP_DIR:-$OUTPUT_DIR/backups}"

  mkdir -p "$OUTPUT_DIR" "$BACKUP_DIR"
  mkdir -p "$OUTPUT_DIR/alerts"
  chmod 700 "$OUTPUT_DIR" "$BACKUP_DIR" "$OUTPUT_DIR/alerts"
  fix_output_owner

  log "Deploying Mirage VPN for host: $PUBLIC_HOST"
  log "Access bundle: $OUTPUT_DIR"

  install_packages
  cleanup_proxy_containers
  configure_firewall
  install_xui_if_needed
  load_xui_result
  configure_xui_local_panel
  write_xui_env
  build_xui_ops
  ensure_api_token
  write_admin_env
  start_admin_api
  bootstrap_vpn
  collect_client_links
  install_backup_timer
  render_access_file
  fix_output_owner

  log "Done"
  printf 'Access file: %s\n' "$OUTPUT_DIR/access.md"
  printf 'Links directory: %s\n' "$OUTPUT_DIR/links"
  printf 'Backup directory: %s\n' "$BACKUP_DIR"
}

main "$@"
