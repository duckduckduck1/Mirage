#!/usr/bin/env bash
#
# CLI trigger for the Mirage 3x-ui restore helper.
#
#   sudo bash ops/admin/mirage-restore.sh /path/to/x-ui-backup.db [--timeout 180]
#
# It reuses the existing root helper (mirage-admin-restore.path): it places the
# backup into the backup directory, enqueues a restore-request JSON, and waits
# for the helper to stop x-ui, swap the database (with a pre-restore backup and
# rollback on failure), and start x-ui again. No new privileged code.
set -euo pipefail

ENV_FILE="${MIRAGE_RESTORE_ENV:-/etc/mirage/admin-restore.env}"
TIMEOUT=180
FILE=""

log() { printf '\n[restore] %s\n' "$*"; }
die() { printf '[restore] error: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout) TIMEOUT="${2:?}"; shift 2 ;;
    --env) ENV_FILE="${2:?}"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^#\{1,2\} \{0,1\}//'; exit 0 ;;
    -*) die "unknown option: $1" ;;
    *) [[ -z "$FILE" ]] && FILE="$1" || die "unexpected argument: $1"; shift ;;
  esac
done

[[ "$(id -u)" -eq 0 ]] || die "run as root"
[[ -n "$FILE" ]] || die "usage: $0 /path/to/backup.db [--timeout N]"
[[ -f "$FILE" ]] || die "backup file not found: $FILE"
[[ -f "$ENV_FILE" ]] || die "restore env not found: $ENV_FILE (run the deploy first)"

set -a; . "$ENV_FILE"; set +a
BACKUP_DIR="${MIRAGE_ADMIN_BACKUP_DIR_HOST:?}"
REQ_DIR="${MIRAGE_ADMIN_RESTORE_REQUEST_DIR_HOST:?}"
STAT_DIR="${MIRAGE_ADMIN_RESTORE_STATUS_DIR_HOST:?}"

# Must be a real SQLite database (same guard the helper enforces).
head -c 16 "$FILE" | grep -q 'SQLite format 3' || die "not a SQLite database: $FILE"

# The helper only restores backups that live in BACKUP_DIR and match its naming.
name_re='^x-ui-[0-9]{8}-[0-9]{6}(-[0-9]{3})?\.db$'
base="$(basename "$FILE")"
if [[ "$base" =~ $name_re && -f "$BACKUP_DIR/$base" && "$FILE" -ef "$BACKUP_DIR/$base" ]]; then
  backup_name="$base"
else
  backup_name="x-ui-$(date +%Y%m%d-%H%M%S).db"
  i=0
  while [[ -e "$BACKUP_DIR/$backup_name" ]]; do
    i=$((i + 1)); backup_name="x-ui-$(date +%Y%m%d-%H%M%S)-$(printf '%03d' "$i").db"
  done
  install -m 600 "$FILE" "$BACKUP_DIR/$backup_name"
  log "staged backup as $backup_name"
fi

rand_hex() { openssl rand -hex 6 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(6))'; }
job="restore-$(date +%Y%m%d-%H%M%S)-$(rand_hex)"
size="$(stat -c %s "$BACKUP_DIR/$backup_name")"
mtime="$(stat -c %Y "$BACKUP_DIR/$backup_name")"

mkdir -p "$REQ_DIR"
tmp="$REQ_DIR/.${job}.json.tmp"
printf '{"jobId":"%s","backupName":"%s","backupSize":%s,"backupMtime":%s}\n' \
  "$job" "$backup_name" "$size" "$mtime" > "$tmp"
mv "$tmp" "$REQ_DIR/$job.json"   # atomic create -> triggers mirage-admin-restore.path
log "enqueued restore job $job for $backup_name; waiting up to ${TIMEOUT}s"

status_file="$STAT_DIR/$job.json"
read_status() { python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get(sys.argv[2],""))
except Exception: print("")' "$status_file" "$1" 2>/dev/null; }

st=""
for ((i = 0; i < TIMEOUT; i++)); do
  if [[ -f "$status_file" ]]; then
    st="$(read_status status)"
    case "$st" in
      success)
        rm -f "$REQ_DIR/$job.json"
        log "restore applied ($backup_name); pre-restore backup: $(read_status preRestoreBackup)"
        exit 0 ;;
      failed)
        die "restore failed: $(read_status error)" ;;
    esac
  fi
  sleep 1
done
die "restore timed out after ${TIMEOUT}s (last status: ${st:-none}); check: journalctl -u mirage-admin-restore.service"
