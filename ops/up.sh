#!/usr/bin/env bash
#
# Mirage one-command bring-up.
#
# Run as root on a fresh Ubuntu/Debian VPS from a checkout of this repo:
#
#   sudo bash ops/up.sh SERVER_HOST_OR_DOMAIN
#
# It chains the whole stack: Ansible bootstrap (admin user, firewall,
# base security) -> ops/vpn/deploy.sh (Docker, 3x-ui/Xray, Mirage Admin,
# pinned Xray, port 443 freed, VLESS Reality inbound + profiles + access.md).
#
# Migration (bring everything up, then restore an old VPS backup so the same
# keys / profiles / links survive):
#
#   sudo bash ops/up.sh SERVER_HOST_OR_DOMAIN --restore /path/to/x-ui-backup.db
#
# Flags:
#   --restore FILE        After deploy, restore this 3x-ui backup (old keys and
#                         profiles) and refresh links/access for the new host.
#   --app-only            Skip bootstrap; run only the deploy layer. Idempotent
#                         and safe to re-run on an already-provisioned server.
#   --with-hardening      Apply SSH hardening after a key-login self-check.
#   --admin-pubkey VALUE  Operator public key (path or literal) for the mirage
#                         user. Default: /root/.ssh/mirage_ed25519.pub, else the
#                         first key already in /root/.ssh/authorized_keys.
#   --dry-run             Validate and preview; run Ansible in --check and print
#                         the deploy command without changing anything.
#   -h, --help            Show this help.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ANSIBLE_DIR="$REPO_ROOT/infra/ansible"
DEPLOY="$REPO_ROOT/ops/vpn/deploy.sh"

HOST=""
APP_ONLY=false
WITH_HARDENING=false
DRY_RUN=false
ADMIN_PUBKEY=""
RESTORE_FILE=""

log()  { printf '\n\033[1;36m[up]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[up] warning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[up] error:\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
run()  { if $DRY_RUN; then printf '  [dry-run] %s\n' "$*"; else eval "$@"; fi; }

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --app-only|--skip-bootstrap) APP_ONLY=true; shift ;;
      --with-hardening) WITH_HARDENING=true; shift ;;
      --restore) RESTORE_FILE="${2:-}"; shift 2 ;;
      --dry-run) DRY_RUN=true; shift ;;
      --admin-pubkey) ADMIN_PUBKEY="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      -*) die "unknown option: $1" ;;
      *) [[ -z "$HOST" ]] && HOST="$1" || die "unexpected argument: $1"; shift ;;
    esac
  done
}

require_root() { [[ "$(id -u)" -eq 0 ]] || die "run as root: sudo bash $0 ..."; }

detect_host() {
  [[ -n "$HOST" ]] && return
  if have curl; then HOST="$(curl -fsS --max-time 5 https://api.ipify.org || true)"; fi
  [[ -n "$HOST" ]] || die "public host not detected; pass it: sudo bash $0 SERVER_HOST_OR_DOMAIN"
  log "auto-detected public host: $HOST"
}

resolve_admin_pubkey() {
  local v="$ADMIN_PUBKEY"
  if [[ -n "$v" ]]; then
    if [[ -f "$v" ]]; then cat "$v"; return; fi
    printf '%s\n' "$v"; return
  fi
  local f="${MIRAGE_ADMIN_PUBLIC_KEY_FILE:-/root/.ssh/mirage_ed25519.pub}"
  [[ -f "$f" ]] && { cat "$f"; return; }
  # Fall back to the key you are logged in with.
  if [[ -f /root/.ssh/authorized_keys ]]; then
    grep -m1 -E '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-|sk-ssh-ed25519|sk-ecdsa-sha2-) ' \
      /root/.ssh/authorized_keys && return
  fi
  return 1
}

preflight() {
  [[ -f /etc/os-release ]] && grep -qiE 'debian|ubuntu' /etc/os-release \
    || die "this bootstrap targets Ubuntu/Debian"
  [[ -x "$DEPLOY" ]] || die "deploy script not found: $DEPLOY"
}

ensure_ansible() {
  have ansible-playbook && have git && return
  log "Installing ansible + git"
  run "export DEBIAN_FRONTEND=noninteractive"
  run "apt-get update"
  run "apt-get install -y ansible git"
}

bootstrap() {
  local key; key="$(resolve_admin_pubkey || true)"
  [[ -n "$key" ]] || die "no operator public key found (pass --admin-pubkey PATH_OR_KEY)"
  # The Ansible role reads the operator pubkey from a file. Write it there rather
  # than passing it via `-e admin_public_key=...`: extra-vars in key=value form are
  # split on whitespace, which truncates an SSH key ("ssh-ed25519 AAAA... comment")
  # at the first space. Writing the file avoids that entirely.
  local keyfile="${MIRAGE_ADMIN_PUBLIC_KEY_FILE:-/root/.ssh/mirage_ed25519.pub}"
  if [[ ! -s "$keyfile" ]]; then
    install -d -m700 "$(dirname "$keyfile")"
    printf '%s\n' "$key" > "$keyfile"
    chmod 644 "$keyfile"
    log "Wrote operator pubkey to $keyfile"
  fi
  log "Bootstrap (admin user, firewall, base security)"
  ensure_ansible
  if $DRY_RUN; then
    run "ansible-playbook -i '$ANSIBLE_DIR/inventory/localhost.yml' '$ANSIBLE_DIR/site.yml' --syntax-check"
    run "ansible-playbook '$ANSIBLE_DIR/site.yml' --check"
    return
  fi
  ( cd "$ANSIBLE_DIR" && ansible-playbook site.yml )
}

harden() {
  $WITH_HARDENING || return 0
  # Safety: never disable password auth unless the admin key is actually in place.
  if [[ ! -s /home/mirage/.ssh/authorized_keys ]]; then
    warn "skipping hardening: /home/mirage/.ssh/authorized_keys is missing/empty (key-login not confirmed)"
    return
  fi
  log "Applying SSH hardening (key-login confirmed for mirage)"
  if $DRY_RUN; then
    run "ansible-playbook '$ANSIBLE_DIR/site.yml' -e enable_ssh_hardening=true --tags hardening --check"
    return
  fi
  ( cd "$ANSIBLE_DIR" && ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening )
}

deploy() {
  log "Deploy (Docker, 3x-ui/Xray pinned, Mirage Admin, inbound + profiles)"
  if $DRY_RUN; then
    run "bash '$DEPLOY' '$HOST'"
    return
  fi
  bash "$DEPLOY" "$HOST"
}

do_restore() {
  [[ -n "$RESTORE_FILE" ]] || return 0
  [[ -f "$RESTORE_FILE" ]] || die "restore file not found: $RESTORE_FILE"
  log "Migration: restoring 3x-ui database from $RESTORE_FILE"
  if $DRY_RUN; then
    run "bash '$SCRIPT_DIR/admin/mirage-restore.sh' '$RESTORE_FILE'"
    run "bash '$DEPLOY' '$HOST'   # refresh links/access from restored DB"
    return 0
  fi
  bash "$SCRIPT_DIR/admin/mirage-restore.sh" "$RESTORE_FILE"
  # The restored DB carries the old inbound/keys/clients; re-run deploy (idempotent)
  # to regenerate links and access.md for the new host from that database.
  log "Refreshing profiles, links and access for $HOST from the restored database"
  bash "$DEPLOY" "$HOST"
}

verify() {
  $DRY_RUN && return
  log "Verifying"
  local out="/home/mirage/mirage-vpn/access.md"
  systemctl is-active --quiet x-ui && echo "  x-ui:   active" || warn "x-ui not active"
  local ver; ver="$( ( cd /usr/local/x-ui/bin 2>/dev/null && LD_LIBRARY_PATH=. ./xray-linux-amd64 version 2>/dev/null | head -1 ) || true)"
  echo "  xray:   ${ver:-unknown}"
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE ':443$'; then echo "  :443:   listening"; else warn ":443 not listening"; fi
  [[ -f "$out" ]] && echo "  access: $out" || warn "access.md not found at $out"
}

main() {
  parse_args "$@"
  require_root
  preflight
  detect_host

  $DRY_RUN && log "DRY-RUN: no changes will be made"
  if $APP_ONLY; then
    log "Mode: --app-only (skipping bootstrap)"
  else
    bootstrap
    harden
  fi
  deploy
  do_restore
  verify

  log "Done."
  if ! $DRY_RUN; then
    echo "  Save the access bundle: sudo cat /home/mirage/mirage-vpn/access.md"
  fi
}

main "$@"
