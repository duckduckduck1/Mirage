#!/usr/bin/env python3
"""Local Mirage Admin API and static UI.

The service is intentionally small and dependency-free. It exposes a localhost
JSON API and a static admin page while reusing xui-ops for all 3x-ui behavior.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib import parse, request as urlrequest

CURRENT_DIR = Path(__file__).resolve().parent
XUI_DIR = CURRENT_DIR.parent / "xui"
if str(XUI_DIR) not in sys.path:
    sys.path.insert(0, str(XUI_DIR))

import xui_api  # noqa: E402


PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}$")
BACKUP_RE = re.compile(r"^x-ui-\d{8}-\d{6}(?:-\d{3})?\.db$")
RESTORE_JOB_RE = re.compile(r"^restore-\d{8}-\d{6}-[a-f0-9]{12}$")
DEFAULT_ADMIN_HOST = "127.0.0.1"
DEFAULT_ADMIN_PORT = 8090
DEFAULT_BACKUP_DIR = Path("/data/backups")
DEFAULT_RESTORE_REQUEST_DIR = Path("/data/restore-requests")
DEFAULT_RESTORE_STATUS_DIR = Path("/data/restore-status")
DEFAULT_BACKUP_RETENTION_DAYS = 14
DEFAULT_BACKUP_KEEP_MIN = 3
DEFAULT_BACKUP_IMPORT_MAX_MB = 64
DEFAULT_JSON_BODY_MAX_BYTES = 64 * 1024
DEFAULT_ALERT_INTERVAL_SECONDS = 60
DEFAULT_ALERT_STATE_FILE = Path("/data/alerts/state.json")
DEFAULT_ALERT_BACKUP_MAX_AGE_HOURS = 36
DEFAULT_ALERT_DISK_FREE_MIN_PERCENT = 10
STATIC_DIR = CURRENT_DIR / "static"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}
WEAK_ADMIN_TOKENS = {
    "change_me",
    "change_me_long_random_token",
    "changeme",
    "password",
    "secret",
    "token",
}
MIN_ADMIN_TOKEN_LENGTH = 32
ERROR_URL_RE = re.compile(r"https?://[^\s'\"<>]+")
ERROR_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
ERROR_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?token|token|password|secret|webbasepath|web_base_path)\s*[:=]\s*[^,\s;]+"
)


class AdminError(RuntimeError):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def validate_profile_name(value: str) -> str:
    name = value.strip()
    if not PROFILE_RE.fullmatch(name):
        raise AdminError(
            HTTPStatus.BAD_REQUEST,
            "profile name must be 1-64 chars: letters, digits, dot, underscore, at or dash",
        )
    return name


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def safe_error_message(exc: BaseException, fallback: str = "operation failed") -> str:
    if isinstance(exc, xui_api.ApiError):
        return "upstream 3x-ui API request failed"
    if isinstance(exc, (OSError, TimeoutError)):
        return fallback
    return fallback


def redact_error_text(value: Any) -> str:
    text = str(value or "")
    text = ERROR_URL_RE.sub("<redacted-url>", text)
    text = ERROR_BEARER_RE.sub("Bearer <redacted>", text)
    return ERROR_SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)


def validate_admin_token(token: str) -> str:
    normalized = token.strip()
    if not normalized:
        raise AdminError(HTTPStatus.INTERNAL_SERVER_ERROR, "MIRAGE_ADMIN_TOKEN is required")
    if len(normalized) < MIN_ADMIN_TOKEN_LENGTH:
        raise AdminError(HTTPStatus.INTERNAL_SERVER_ERROR, "MIRAGE_ADMIN_TOKEN is too short")
    if normalized.lower() in WEAK_ADMIN_TOKENS:
        raise AdminError(HTTPStatus.INTERNAL_SERVER_ERROR, "MIRAGE_ADMIN_TOKEN uses a placeholder value")
    return normalized


def env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be greater than or equal to {minimum}")
    return value


def load_runtime_env() -> None:
    xui_env = os.environ.get("MIRAGE_XUI_ENV_FILE")
    admin_env = os.environ.get("MIRAGE_ADMIN_ENV_FILE")
    if xui_env:
        xui_api.load_env_file(Path(xui_env))
    else:
        xui_api.load_env_file(XUI_DIR / ".env.local")
    if admin_env:
        xui_api.load_env_file(Path(admin_env))
    else:
        xui_api.load_env_file(CURRENT_DIR / ".env.local")


def env_namespace() -> argparse.Namespace:
    return argparse.Namespace(
        base_url=None,
        api_token=None,
        username=None,
        password=None,
        two_factor_code=None,
        timeout=None,
        public_host=None,
        vless_port=None,
        vless_remark=None,
    )


def client_namespace(email: str, payload: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        email=email,
        comment=payload.get("comment"),
        group=None,
        inbound_id=None,
        inbound_remark=None,
        protocol=None,
        port=None,
        total_gb=None,
        expiry_days=None,
        expiry_time_ms=None,
        limit_ip=None,
        reset_days=None,
        tg_id=None,
        sub_id=None,
        uuid=None,
        password=None,
        auth=None,
        flow=None,
        security=None,
    )


def json_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def static_path_for_request(raw_path: str, static_dir: Path = STATIC_DIR) -> Path:
    path = parse.unquote(parse.urlsplit(raw_path).path)
    relative = "index.html" if path in {"", "/"} else path.lstrip("/")
    candidate = (static_dir / relative).resolve()
    root = static_dir.resolve()
    if candidate != root and root not in candidate.parents:
        raise AdminError(HTTPStatus.BAD_REQUEST, "invalid static path")
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def backup_policy() -> dict[str, int]:
    return {
        "retentionDays": env_int("MIRAGE_ADMIN_BACKUP_RETENTION_DAYS", DEFAULT_BACKUP_RETENTION_DAYS, minimum=1),
        "keepMin": env_int("MIRAGE_ADMIN_BACKUP_KEEP_MIN", DEFAULT_BACKUP_KEEP_MIN, minimum=1),
    }


def backup_import_max_bytes() -> int:
    return env_int("MIRAGE_ADMIN_BACKUP_IMPORT_MAX_MB", DEFAULT_BACKUP_IMPORT_MAX_MB, minimum=1) * 1024 * 1024


def backup_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"name": path.name, "size": stat.st_size, "mtime": int(stat.st_mtime)}


def backup_policy_value(payload: dict[str, Any], key: str, default: int) -> int:
    raw = payload.get(key, default)
    if raw is None or raw == "":
        raw = default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, "retentionDays and keepMin must be integers") from exc


def validate_sqlite_backup(path: Path) -> None:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, "backup file is not readable") from exc
    if size <= 0:
        raise AdminError(HTTPStatus.BAD_REQUEST, "backup file is empty")
    try:
        header = path.read_bytes()[:16]
    except OSError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, "backup file is not readable") from exc
    if header != b"SQLite format 3\x00":
        raise AdminError(HTTPStatus.BAD_REQUEST, "backup file must be a SQLite database")
    try:
        connection = sqlite3.connect(str(path))
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, "backup SQLite integrity check failed") from exc
    if not row or str(row[0]).lower() != "ok":
        raise AdminError(HTTPStatus.BAD_REQUEST, "backup SQLite integrity check failed")


def new_restore_job_id() -> str:
    return f"restore-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(6)}"


def restore_status_info(path: Path) -> dict[str, Any] | None:
    if not RESTORE_JOB_RE.fullmatch(path.stem):
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload["jobId"] = path.stem
    return payload


def json_path_inside(root: Path, name: str) -> Path:
    if not RESTORE_JOB_RE.fullmatch(name):
        raise AdminError(HTTPStatus.BAD_REQUEST, "invalid restore job id")
    path = (root / f"{name}.json").resolve()
    resolved_root = root.resolve()
    if resolved_root not in path.parents:
        raise AdminError(HTTPStatus.BAD_REQUEST, "invalid restore job path")
    return path


class AdminService:
    def __init__(
        self,
        api: xui_api.XuiClient,
        config: dict[str, Any] | None = None,
        backup_dir: Path = DEFAULT_BACKUP_DIR,
        restore_request_dir: Path = DEFAULT_RESTORE_REQUEST_DIR,
        restore_status_dir: Path = DEFAULT_RESTORE_STATUS_DIR,
        notifier_factory: Callable[[str, str], "TelegramNotifier"] | None = None,
    ) -> None:
        self.api = api
        self.config = config or {}
        self.args = env_namespace()
        self.backup_dir = backup_dir
        self.restore_request_dir = restore_request_dir
        self.restore_status_dir = restore_status_dir
        self.notifier_factory = notifier_factory or TelegramNotifier

    def public_host(self) -> str | None:
        return xui_api.public_host_value(self.args, self.config)

    def access(self) -> dict[str, Any]:
        base_url = xui_api.option_value(self.args, self.config, "base_url", "MIRAGE_XUI_BASE_URL")
        parts = xui_api.panel_url_parts(base_url)
        admin_port = int(os.environ.get("MIRAGE_ADMIN_PORT", DEFAULT_ADMIN_PORT))
        ssh_host = os.environ.get("MIRAGE_SSH_HOST", "SERVER_HOST")
        ssh_user = os.environ.get("MIRAGE_SSH_USER", "mirage")
        ssh_key = os.environ.get("MIRAGE_SSH_KEY", "$HOME\\.ssh\\mirage_ed25519")
        return {
            "admin": {
                "localUrl": f"http://127.0.0.1:{admin_port}/",
                "sshTunnelCommand": f"ssh -i {ssh_key} -N -L {admin_port}:127.0.0.1:{admin_port} {ssh_user}@{ssh_host}",
            },
            "panel": {
                "localUrl": f"http://127.0.0.1:2096{parts['path']}",
                "sshTunnelCommand": f"ssh -i {ssh_key} -N -L 2096:127.0.0.1:{parts['port']} {ssh_user}@{ssh_host}",
            },
        }

    def _inbound(self) -> dict[str, Any]:
        filters = xui_api.vless_inbound_filters(self.args, self.config)
        option = xui_api.find_vless_inbound(self.api, filters["port"], filters["remark"])
        if not option or not option.get("id"):
            raise AdminError(HTTPStatus.NOT_FOUND, "default VLESS inbound was not found")
        full = xui_api.get_inbound(self.api, int(option["id"]))
        if not full:
            raise AdminError(HTTPStatus.NOT_FOUND, "default VLESS inbound details were not found")
        return full

    def list_profiles(self) -> dict[str, Any]:
        inbound = self._inbound()
        settings = xui_api.json_object(inbound.get("settings"))
        clients = settings.get("clients") if isinstance(settings.get("clients"), list) else []
        profiles = []
        for client in clients:
            if not isinstance(client, dict) or not client.get("email"):
                continue
            profiles.append(
                {
                    "email": client.get("email"),
                    "enabled": client.get("enable"),
                    "flow": client.get("flow"),
                    "totalGB": client.get("totalGB"),
                    "expiryTime": client.get("expiryTime"),
                    "limitIp": client.get("limitIp"),
                    "group": client.get("group"),
                    "comment": client.get("comment"),
                }
            )
        return {
            "inbound": {
                "id": inbound.get("id"),
                "remark": inbound.get("remark"),
                "port": inbound.get("port"),
                "protocol": inbound.get("protocol"),
            },
            "profiles": sorted(profiles, key=lambda item: str(item["email"])),
        }

    def profile_bundle(self, email: str) -> dict[str, Any]:
        return xui_api.build_subscription_bundle(self.api, validate_profile_name(email), self.public_host())

    def create_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        email = validate_profile_name(str(payload.get("email") or ""))
        args = client_namespace(email, payload)
        xui_api.ensure_client(args, self.config, self.api)
        return self.profile_bundle(email)

    def set_profile_enabled(self, email: str, enabled: bool) -> dict[str, Any]:
        email = validate_profile_name(email)
        path = "/panel/api/clients/bulkEnable" if enabled else "/panel/api/clients/bulkDisable"
        self.api.api("POST", path, {"emails": [email]})
        return {"email": email, "enabled": enabled}

    def health(self) -> dict[str, Any]:
        checks: dict[str, dict[str, Any]] = {}

        try:
            self.api.api("GET", "/panel/api/server/status")
            checks["xuiApi"] = {"ok": True}
        except Exception as exc:  # noqa: BLE001 - returned as health detail.
            checks["xuiApi"] = {"ok": False, "error": safe_error_message(exc, "x-ui API check failed")}

        try:
            self._inbound()
            checks["vlessInbound"] = {"ok": True}
        except Exception as exc:  # noqa: BLE001
            checks["vlessInbound"] = {"ok": False, "error": safe_error_message(exc, "VLESS inbound check failed")}

        try:
            with socket.create_connection(("127.0.0.1", 443), timeout=2):
                checks["vpnPort443"] = {"ok": True}
        except OSError as exc:
            checks["vpnPort443"] = {"ok": False, "error": safe_error_message(exc, "VPN port 443 check failed")}

        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            checks["backupDir"] = {"ok": os.access(self.backup_dir, os.R_OK | os.W_OK)}
        except OSError as exc:
            checks["backupDir"] = {"ok": False, "error": safe_error_message(exc, "backup directory check failed")}

        return {
            "status": "ok" if all(item.get("ok") for item in checks.values()) else "degraded",
            "checks": checks,
        }

    def diagnostics(self) -> dict[str, Any]:
        return xui_api.build_vpn_diagnostics(self.args, self.config, self.api)

    def overview(self) -> dict[str, Any]:
        profiles = self.list_profiles()
        health = self.health()
        diagnostics = self.diagnostics()
        return {
            "status": health["status"],
            "publicHost": self.public_host(),
            "profilesCount": len(profiles["profiles"]),
            "inbound": profiles["inbound"],
            "warnings": diagnostics.get("warnings") or [],
        }

    def create_backup(self) -> dict[str, Any]:
        return self.store_backup_bytes(self.api.download("/panel/api/server/getDb"))

    def allocate_backup_path(self) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.chmod(0o700)
        base_name = f"x-ui-{time.strftime('%Y%m%d-%H%M%S')}"
        path = self.backup_dir / f"{base_name}.db"
        for index in range(1000):
            if not path.exists():
                break
            path = self.backup_dir / f"{base_name}-{index:03d}.db"
        else:
            raise AdminError(HTTPStatus.CONFLICT, "could not allocate a unique backup name")
        return path

    def store_backup_bytes(self, data: bytes) -> dict[str, Any]:
        path = self.allocate_backup_path()
        temp_path = path.with_name(f".{path.name}.uploading")
        try:
            temp_path.write_bytes(data)
            validate_sqlite_backup(temp_path)
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        path.chmod(0o600)
        stat = path.stat()
        return {"name": path.name, "size": stat.st_size, "mtime": int(stat.st_mtime)}

    def import_backup(self, data: bytes) -> dict[str, Any]:
        if not data:
            raise AdminError(HTTPStatus.BAD_REQUEST, "backup upload is empty")
        if len(data) > backup_import_max_bytes():
            raise AdminError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "backup upload is too large")
        return self.store_backup_bytes(data)

    def backup_files(self) -> list[Path]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.chmod(0o700)
        backups = []
        for path in self.backup_dir.glob("x-ui-*.db"):
            if BACKUP_RE.fullmatch(path.name) and path.is_file():
                backups.append(path)
        return sorted(backups, key=lambda item: item.stat().st_mtime, reverse=True)

    def list_backups(self) -> dict[str, Any]:
        backups = [backup_info(path) for path in self.backup_files()]
        return {
            "backups": backups,
            "policy": backup_policy(),
            "totalSize": sum(item["size"] for item in backups),
        }

    def backup_path(self, name: str) -> Path:
        if not BACKUP_RE.fullmatch(name):
            raise AdminError(HTTPStatus.BAD_REQUEST, "invalid backup name")
        path = (self.backup_dir / name).resolve()
        root = self.backup_dir.resolve()
        if root not in path.parents and path != root:
            raise AdminError(HTTPStatus.BAD_REQUEST, "invalid backup path")
        if not path.is_file():
            raise AdminError(HTTPStatus.NOT_FOUND, "backup was not found")
        return path

    def delete_backup(self, name: str, confirm_name: str | None = None) -> dict[str, Any]:
        if confirm_name != name:
            raise AdminError(HTTPStatus.BAD_REQUEST, "confirmName must match backup name")
        path = self.backup_path(name)
        if len(self.backup_files()) <= 1:
            raise AdminError(HTTPStatus.CONFLICT, "cannot delete the last backup")
        deleted = backup_info(path)
        path.unlink()
        return {"deleted": deleted}

    def queue_restore(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("confirmName") != name:
            raise AdminError(HTTPStatus.BAD_REQUEST, "confirmName must match backup name")
        if payload.get("confirm") != "restore":
            raise AdminError(HTTPStatus.BAD_REQUEST, "confirm must be restore for backup restore")
        if payload.get("ackDowntime") is not True:
            raise AdminError(HTTPStatus.BAD_REQUEST, "ackDowntime must be true")

        path = self.backup_path(name)
        info = backup_info(path)
        self.restore_request_dir.mkdir(parents=True, exist_ok=True)
        self.restore_request_dir.chmod(0o700)
        job_id = new_restore_job_id()
        now = int(time.time())
        job = {
            "jobId": job_id,
            "status": "queued",
            "backupName": info["name"],
            "backupSize": info["size"],
            "backupMtime": info["mtime"],
            "createdAt": now,
            "updatedAt": now,
        }
        path_obj = json_path_inside(self.restore_request_dir, job_id)
        temp_path = path_obj.with_name(f".{path_obj.name}.tmp")
        try:
            temp_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.chmod(0o600)
            temp_path.replace(path_obj)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return job

    def restore_jobs(self) -> dict[str, Any]:
        jobs: dict[str, dict[str, Any]] = {}
        for root in [self.restore_request_dir, self.restore_status_dir]:
            try:
                paths = list(root.glob("restore-*.json"))
            except OSError:
                continue
            for path in paths:
                payload = restore_status_info(path)
                if payload:
                    jobs[payload["jobId"]] = payload
        ordered = sorted(jobs.values(), key=lambda item: int(item.get("updatedAt") or 0), reverse=True)
        return {"jobs": ordered}

    def restore_job(self, job_id: str) -> dict[str, Any]:
        json_path_inside(self.restore_status_dir, job_id)
        for root in [self.restore_status_dir, self.restore_request_dir]:
            path = json_path_inside(root, job_id)
            payload = restore_status_info(path)
            if payload:
                return payload
        raise AdminError(HTTPStatus.NOT_FOUND, "restore job was not found")

    def prune_backups(self, payload: dict[str, Any]) -> dict[str, Any]:
        policy = backup_policy()
        retention_days = backup_policy_value(payload, "retentionDays", policy["retentionDays"])
        keep_min = backup_policy_value(payload, "keepMin", policy["keepMin"])
        dry_run = payload.get("dryRun", True) is not False
        if retention_days < 1:
            raise AdminError(HTTPStatus.BAD_REQUEST, "retentionDays must be greater than or equal to 1")
        if keep_min < 1:
            raise AdminError(HTTPStatus.BAD_REQUEST, "keepMin must be greater than or equal to 1")
        if not dry_run and payload.get("confirm") != "prune":
            raise AdminError(HTTPStatus.BAD_REQUEST, "confirm must be prune for destructive backup cleanup")

        backups = self.backup_files()
        cutoff = time.time() - retention_days * 24 * 3600
        candidates = [path for path in backups[keep_min:] if path.stat().st_mtime < cutoff]
        pruned = [backup_info(path) for path in candidates]
        if not dry_run and len(backups) - len(candidates) < keep_min:
            raise AdminError(HTTPStatus.CONFLICT, "backup cleanup would violate keepMin")
        if not dry_run:
            for path in candidates:
                path.unlink()
        return {
            "dryRun": dry_run,
            "retentionDays": retention_days,
            "keepMin": keep_min,
            "pruned": pruned,
            "remaining": len(backups) if dry_run else len(self.backup_files()),
        }

    def alert_status(self) -> dict[str, Any]:
        config = alert_config()
        state = load_alert_state(config["stateFile"])
        return {
            "enabled": config["enabled"],
            "configured": config["configured"],
            "intervalSeconds": config["intervalSeconds"],
            "maxBackupAgeHours": config["maxBackupAgeHours"],
            "minDiskFreePercent": config["minDiskFreePercent"],
            "state": {
                "status": state.get("status"),
                "updatedAt": state.get("updatedAt"),
            },
            "health": alert_health(self, config["maxBackupAgeHours"], config["minDiskFreePercent"]),
        }

    def send_test_alert(self) -> dict[str, Any]:
        config = alert_config()
        if not config["configured"]:
            raise AdminError(HTTPStatus.BAD_REQUEST, "telegram alerts are not configured")
        notifier = self.notifier_factory(config["botToken"], config["chatId"])
        notifier.send("Mirage VPN: тестовое уведомление")
        return {"sent": True}


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timeout: int = 10) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, text: str) -> None:
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = parse.urlencode(
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request_obj = urlrequest.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlrequest.urlopen(request_obj, timeout=self.timeout) as response:
            if response.status >= 400:
                raise RuntimeError(f"telegram returned HTTP {response.status}")


def backup_freshness_check(backup_dir: Path, max_age_hours: int) -> dict[str, Any]:
    try:
        backups = [path for path in backup_dir.glob("x-ui-*.db") if BACKUP_RE.fullmatch(path.name)]
    except OSError as exc:
        return {"ok": False, "error": safe_error_message(exc, "backup freshness check failed")}
    if not backups:
        return {"ok": False, "error": "no backup files found", "maxAgeHours": max_age_hours}
    latest = max(backups, key=lambda path: path.stat().st_mtime)
    age_seconds = max(0, int(time.time() - latest.stat().st_mtime))
    max_age_seconds = max_age_hours * 3600
    payload = {
        "ok": age_seconds <= max_age_seconds,
        "latest": latest.name,
        "ageSeconds": age_seconds,
        "maxAgeHours": max_age_hours,
    }
    if not payload["ok"]:
        payload["error"] = f"latest backup is older than {max_age_hours}h"
    return payload


def alert_config() -> dict[str, Any]:
    token = os.environ.get("MIRAGE_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("MIRAGE_ALERT_TELEGRAM_CHAT_ID", "").strip()
    configured = bool(token and chat_id)
    return {
        "enabled": env_flag("MIRAGE_ALERTS_ENABLED", configured),
        "configured": configured,
        "botToken": token,
        "chatId": chat_id,
        "intervalSeconds": env_int("MIRAGE_ALERT_INTERVAL_SECONDS", DEFAULT_ALERT_INTERVAL_SECONDS, minimum=5),
        "maxBackupAgeHours": env_int(
            "MIRAGE_ALERT_BACKUP_MAX_AGE_HOURS",
            DEFAULT_ALERT_BACKUP_MAX_AGE_HOURS,
            minimum=0,
        ),
        "minDiskFreePercent": env_int(
            "MIRAGE_ALERT_DISK_FREE_MIN_PERCENT",
            DEFAULT_ALERT_DISK_FREE_MIN_PERCENT,
            minimum=0,
        ),
        "stateFile": Path(os.environ.get("MIRAGE_ALERT_STATE_FILE", str(DEFAULT_ALERT_STATE_FILE))),
    }


def disk_space_check(path: Path, min_free_percent: int) -> dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"ok": False, "error": safe_error_message(exc, "disk space check failed")}
    free_percent = int((usage.free / usage.total) * 100) if usage.total else 0
    payload = {
        "ok": free_percent >= min_free_percent,
        "freePercent": free_percent,
        "minFreePercent": min_free_percent,
    }
    if not payload["ok"]:
        payload["error"] = f"free disk space is below {min_free_percent}%"
    return payload


def alert_health(
    service: AdminService,
    max_backup_age_hours: int,
    min_disk_free_percent: int = DEFAULT_ALERT_DISK_FREE_MIN_PERCENT,
) -> dict[str, Any]:
    health = service.health()
    checks = dict(health.get("checks") or {})
    if max_backup_age_hours > 0:
        checks["backupFreshness"] = backup_freshness_check(service.backup_dir, max_backup_age_hours)
    if min_disk_free_percent > 0:
        checks["diskFree"] = disk_space_check(service.backup_dir, min_disk_free_percent)
    return {
        "status": "ok" if all(item.get("ok") for item in checks.values()) else "degraded",
        "checks": checks,
    }


def alert_fingerprint(health: dict[str, Any]) -> str:
    failed = sorted(name for name, item in (health.get("checks") or {}).items() if not item.get("ok"))
    return "ok" if not failed else "degraded:" + ",".join(failed)


def short_error(item: dict[str, Any]) -> str:
    error = redact_error_text(item.get("error") or "")
    if len(error) > 160:
        return error[:157] + "..."
    return error


def format_alert_text(health: dict[str, Any]) -> str:
    status = health.get("status")
    title = "Mirage VPN: восстановлен" if status == "ok" else "Mirage VPN: деградация"
    lines = [title]
    for name, item in sorted((health.get("checks") or {}).items()):
        marker = "OK" if item.get("ok") else "FAIL"
        line = f"[{marker}] {name}"
        if not item.get("ok") and item.get("error"):
            line += f": {short_error(item)}"
        lines.append(line)
    return "\n".join(lines)


def load_alert_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_alert_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(0o600)


def alert_tick(
    service: AdminService,
    notifier: TelegramNotifier,
    state_file: Path,
    max_backup_age_hours: int,
    min_disk_free_percent: int = DEFAULT_ALERT_DISK_FREE_MIN_PERCENT,
) -> int:
    health = alert_health(service, max_backup_age_hours, min_disk_free_percent)
    fingerprint = alert_fingerprint(health)
    previous = load_alert_state(state_file).get("fingerprint")
    should_notify = (previous is None and fingerprint != "ok") or (previous is not None and previous != fingerprint)

    if should_notify:
        notifier.send(format_alert_text(health))

    save_alert_state(
        state_file,
        {
            "fingerprint": fingerprint,
            "status": health["status"],
            "updatedAt": int(time.time()),
        },
    )
    return 0 if health["status"] == "ok" else 2


def run_alert_monitor(
    service: AdminService,
    notifier: TelegramNotifier,
    state_file: Path,
    interval_seconds: int,
    max_backup_age_hours: int,
    min_disk_free_percent: int,
    once: bool = False,
) -> int:
    while True:
        try:
            exit_code = alert_tick(service, notifier, state_file, max_backup_age_hours, min_disk_free_percent)
        except Exception as exc:  # noqa: BLE001 - monitor must stay alive between attempts.
            print(f"Mirage Telegram alert check failed: {exc}", file=sys.stderr, flush=True)
            if once:
                return 1
            time.sleep(interval_seconds)
            continue
        if once:
            return exit_code
        time.sleep(interval_seconds)


def read_json_body(handler: BaseHTTPRequestHandler, max_bytes: int = DEFAULT_JSON_BODY_MAX_BYTES) -> dict[str, Any]:
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, "invalid Content-Length") from exc
    if length < 0:
        raise AdminError(HTTPStatus.BAD_REQUEST, "invalid Content-Length")
    if length == 0:
        return {}
    if length > max_bytes:
        raise AdminError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "JSON body is too large")
    raw = handler.rfile.read(length)
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, f"invalid JSON body: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AdminError(HTTPStatus.BAD_REQUEST, "JSON body must be an object")
    return parsed


def read_raw_body(handler: BaseHTTPRequestHandler, max_bytes: int) -> bytes:
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, "invalid Content-Length") from exc
    if length <= 0:
        raise AdminError(HTTPStatus.BAD_REQUEST, "request body is empty")
    if length > max_bytes:
        raise AdminError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body is too large")
    return handler.rfile.read(length)


def make_handler(service: AdminService, token: str) -> type[BaseHTTPRequestHandler]:
    class MirageAdminHandler(BaseHTTPRequestHandler):
        server_version = "MirageAdmin/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

        def _authorized(self) -> bool:
            bearer = self.headers.get("Authorization", "")
            header_token = self.headers.get("X-Mirage-Token", "")
            bearer_prefix = "Bearer "
            bearer_token = bearer[len(bearer_prefix) :] if bearer.startswith(bearer_prefix) else ""
            bearer_ok = secrets.compare_digest(bearer_token, token)
            header_ok = secrets.compare_digest(header_token, token)
            return bearer_ok or header_ok

        def _send_json(self, status: HTTPStatus, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json(status, {"error": message})

        def _send_static(self) -> None:
            path_obj = static_path_for_request(self.path)
            if not path_obj.is_file():
                raise AdminError(HTTPStatus.NOT_FOUND, "not found")
            data = path_obj.read_bytes()
            content_type = CONTENT_TYPES.get(path_obj.suffix.lower(), "application/octet-stream")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _route(self, method: str) -> None:
            parsed = parse.urlsplit(self.path)
            path = parsed.path.rstrip("/") or "/"
            parts = [parse.unquote(item) for item in path.split("/") if item]

            if method == "GET" and parts == ["healthz"]:
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if method == "GET" and parts[:2] != ["api", "v0"]:
                self._send_static()
                return

            if parts[:2] != ["api", "v0"]:
                raise AdminError(HTTPStatus.NOT_FOUND, "not found")
            if not self._authorized():
                raise AdminError(HTTPStatus.UNAUTHORIZED, "missing or invalid admin token")

            route = parts[2:]

            if method == "GET" and route == ["health"]:
                self._send_json(HTTPStatus.OK, service.health())
                return
            if method == "GET" and route == ["overview"]:
                self._send_json(HTTPStatus.OK, service.overview())
                return
            if method == "GET" and route == ["access"]:
                self._send_json(HTTPStatus.OK, service.access())
                return
            if method == "GET" and route == ["vpn", "diagnostics"]:
                self._send_json(HTTPStatus.OK, service.diagnostics())
                return
            if method == "GET" and route == ["alerts"]:
                self._send_json(HTTPStatus.OK, service.alert_status())
                return
            if method == "POST" and route == ["alerts", "test"]:
                self._send_json(HTTPStatus.OK, service.send_test_alert())
                return

            if method == "GET" and route == ["profiles"]:
                self._send_json(HTTPStatus.OK, service.list_profiles())
                return
            if method == "POST" and route == ["profiles"]:
                self._send_json(HTTPStatus.CREATED, service.create_profile(read_json_body(self)))
                return
            if method == "GET" and len(route) == 2 and route[:1] == ["profiles"]:
                self._send_json(HTTPStatus.OK, service.profile_bundle(route[1]))
                return
            if method == "POST" and len(route) == 3 and route[:1] == ["profiles"] and route[2] in {"enable", "disable"}:
                self._send_json(HTTPStatus.OK, service.set_profile_enabled(route[1], route[2] == "enable"))
                return

            if method == "GET" and route == ["backups"]:
                self._send_json(HTTPStatus.OK, service.list_backups())
                return
            if method == "POST" and route == ["backups"]:
                self._send_json(HTTPStatus.CREATED, service.create_backup())
                return
            if method == "POST" and route == ["backups", "import"]:
                self._send_json(HTTPStatus.CREATED, service.import_backup(read_raw_body(self, backup_import_max_bytes())))
                return
            if method == "POST" and route == ["backups", "prune"]:
                self._send_json(HTTPStatus.OK, service.prune_backups(read_json_body(self)))
                return
            if method == "POST" and len(route) == 3 and route[:1] == ["backups"] and route[2] == "restore":
                self._send_json(HTTPStatus.ACCEPTED, service.queue_restore(route[1], read_json_body(self)))
                return
            if method == "GET" and len(route) == 2 and route[:1] == ["backups"]:
                path_obj = service.backup_path(route[1])
                data = path_obj.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{path_obj.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if method == "DELETE" and len(route) == 2 and route[:1] == ["backups"]:
                query = parse.parse_qs(parsed.query)
                confirm_name = (query.get("confirmName") or [""])[0]
                self._send_json(HTTPStatus.OK, service.delete_backup(route[1], confirm_name))
                return
            if method == "GET" and route == ["restore-requests"]:
                self._send_json(HTTPStatus.OK, service.restore_jobs())
                return
            if method == "GET" and len(route) == 2 and route[:1] == ["restore-requests"]:
                self._send_json(HTTPStatus.OK, service.restore_job(route[1]))
                return

            raise AdminError(HTTPStatus.NOT_FOUND, "not found")

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

        def do_DELETE(self) -> None:  # noqa: N802
            self._handle("DELETE")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
            self.end_headers()

        def _handle(self, method: str) -> None:
            try:
                self._route(method)
            except AdminError as exc:
                self._send_error(exc.status, exc.message)
            except xui_api.ApiError as exc:
                self._send_error(HTTPStatus.BAD_GATEWAY, "upstream 3x-ui API request failed")
            except Exception as exc:  # noqa: BLE001
                message = safe_error_message(exc, "admin API request failed")
                self.log_error("Unhandled admin API error: %s", message)
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, message)

    return MirageAdminHandler


def build_service() -> AdminService:
    load_runtime_env()
    args = env_namespace()
    api = xui_api.api_from_args(args, {})
    backup_dir = Path(os.environ.get("MIRAGE_ADMIN_BACKUP_DIR", str(DEFAULT_BACKUP_DIR)))
    restore_request_dir = Path(os.environ.get("MIRAGE_ADMIN_RESTORE_REQUEST_DIR", str(DEFAULT_RESTORE_REQUEST_DIR)))
    restore_status_dir = Path(os.environ.get("MIRAGE_ADMIN_RESTORE_STATUS_DIR", str(DEFAULT_RESTORE_STATUS_DIR)))
    config: dict[str, Any] = {}
    public_host = xui_api.public_host_value(args, config)
    if public_host:
        config["public_host"] = public_host
    return AdminService(
        api=api,
        config=config,
        backup_dir=backup_dir,
        restore_request_dir=restore_request_dir,
        restore_status_dir=restore_status_dir,
    )


def serve() -> None:
    service = build_service()
    try:
        token = validate_admin_token(os.environ.get("MIRAGE_ADMIN_TOKEN", ""))
    except AdminError as exc:
        raise SystemExit(exc.message) from exc
    host = os.environ.get("MIRAGE_ADMIN_HOST", DEFAULT_ADMIN_HOST)
    if not is_loopback_host(host) and os.environ.get("MIRAGE_ADMIN_ALLOW_PUBLIC") != "1":
        raise SystemExit("MIRAGE_ADMIN_HOST must be loopback unless MIRAGE_ADMIN_ALLOW_PUBLIC=1 is set")
    port = int(os.environ.get("MIRAGE_ADMIN_PORT", DEFAULT_ADMIN_PORT))
    server = ThreadingHTTPServer((host, port), make_handler(service, token))
    print(f"Mirage Admin API listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def monitor(once: bool = False) -> int:
    load_runtime_env()
    try:
        config = alert_config()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    token = config["botToken"]
    chat_id = config["chatId"]
    interval_seconds = config["intervalSeconds"]
    enabled = config["enabled"]
    if not enabled:
        print("Mirage Telegram alerts are disabled", flush=True)
        if once:
            return 0
        while True:
            time.sleep(interval_seconds)
    if not token or not chat_id:
        raise SystemExit("MIRAGE_ALERT_TELEGRAM_BOT_TOKEN and MIRAGE_ALERT_TELEGRAM_CHAT_ID are required")

    service = build_service()
    state_file = config["stateFile"]
    max_backup_age_hours = config["maxBackupAgeHours"]
    min_disk_free_percent = config["minDiskFreePercent"]
    notifier = TelegramNotifier(token, chat_id)
    return run_alert_monitor(
        service,
        notifier,
        state_file,
        interval_seconds,
        max_backup_age_hours,
        min_disk_free_percent,
        once=once,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirage local admin service.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run local admin API and static UI.")
    monitor_parser = sub.add_parser("monitor", help="Run Telegram health alerts loop.")
    monitor_parser.add_argument("--once", action="store_true", help="Run one alert check and exit.")
    args = parser.parse_args(argv)

    if args.command in {None, "serve"}:
        serve()
        return 0
    if args.command == "monitor":
        return monitor(once=args.once)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
