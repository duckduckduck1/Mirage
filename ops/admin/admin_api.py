#!/usr/bin/env python3
"""Local Mirage Admin API.

The service is intentionally small and dependency-free. It exposes a localhost
JSON API for the future admin UI while reusing xui-ops for all 3x-ui behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import parse

CURRENT_DIR = Path(__file__).resolve().parent
XUI_DIR = CURRENT_DIR.parent / "xui"
if str(XUI_DIR) not in sys.path:
    sys.path.insert(0, str(XUI_DIR))

import xui_api  # noqa: E402


PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}$")
BACKUP_RE = re.compile(r"^x-ui-\d{8}-\d{6}\.db$")
DEFAULT_ADMIN_HOST = "127.0.0.1"
DEFAULT_ADMIN_PORT = 8090
DEFAULT_BACKUP_DIR = Path("/data/backups")


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
        group=payload.get("group"),
        inbound_id=None,
        inbound_remark=None,
        protocol=None,
        port=None,
        total_gb=payload.get("totalGb"),
        expiry_days=payload.get("expiryDays"),
        expiry_time_ms=payload.get("expiryTimeMs"),
        limit_ip=payload.get("limitIp"),
        reset_days=payload.get("resetDays"),
        tg_id=payload.get("tgId"),
        sub_id=payload.get("subId"),
        uuid=payload.get("uuid"),
        password=None,
        auth=None,
        flow=None,
        security=None,
    )


def json_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class AdminService:
    def __init__(
        self,
        api: xui_api.XuiClient,
        config: dict[str, Any] | None = None,
        backup_dir: Path = DEFAULT_BACKUP_DIR,
    ) -> None:
        self.api = api
        self.config = config or {}
        self.args = env_namespace()
        self.backup_dir = backup_dir

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
                    "subId": client.get("subId"),
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
            checks["xuiApi"] = {"ok": False, "error": str(exc)}

        try:
            self._inbound()
            checks["vlessInbound"] = {"ok": True}
        except Exception as exc:  # noqa: BLE001
            checks["vlessInbound"] = {"ok": False, "error": str(exc)}

        try:
            with socket.create_connection(("127.0.0.1", 443), timeout=2):
                checks["vpnPort443"] = {"ok": True}
        except OSError as exc:
            checks["vpnPort443"] = {"ok": False, "error": str(exc)}

        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            checks["backupDir"] = {"ok": os.access(self.backup_dir, os.R_OK | os.W_OK)}
        except OSError as exc:
            checks["backupDir"] = {"ok": False, "error": str(exc)}

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
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        path = self.backup_dir / f"x-ui-{time.strftime('%Y%m%d-%H%M%S')}.db"
        path.write_bytes(self.api.download("/panel/api/server/getDb"))
        path.chmod(0o600)
        stat = path.stat()
        return {"name": path.name, "size": stat.st_size, "mtime": int(stat.st_mtime)}

    def list_backups(self) -> dict[str, Any]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backups = []
        for path in sorted(self.backup_dir.glob("x-ui-*.db"), reverse=True):
            if not BACKUP_RE.fullmatch(path.name):
                continue
            stat = path.stat()
            backups.append({"name": path.name, "size": stat.st_size, "mtime": int(stat.st_mtime)})
        return {"backups": backups}

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


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise AdminError(HTTPStatus.BAD_REQUEST, f"invalid JSON body: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AdminError(HTTPStatus.BAD_REQUEST, "JSON body must be an object")
    return parsed


def make_handler(service: AdminService, token: str) -> type[BaseHTTPRequestHandler]:
    class MirageAdminHandler(BaseHTTPRequestHandler):
        server_version = "MirageAdmin/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

        def _authorized(self) -> bool:
            bearer = self.headers.get("Authorization", "")
            header_token = self.headers.get("X-Mirage-Token", "")
            return bearer == f"Bearer {token}" or header_token == token

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

        def _route(self, method: str) -> None:
            parsed = parse.urlsplit(self.path)
            path = parsed.path.rstrip("/") or "/"
            parts = [parse.unquote(item) for item in path.split("/") if item]

            if method == "GET" and parts == ["healthz"]:
                self._send_json(HTTPStatus.OK, {"status": "ok"})
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

            raise AdminError(HTTPStatus.NOT_FOUND, "not found")

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self.end_headers()

        def _handle(self, method: str) -> None:
            try:
                self._route(method)
            except AdminError as exc:
                self._send_error(exc.status, exc.message)
            except xui_api.ApiError as exc:
                self._send_error(HTTPStatus.BAD_GATEWAY, str(exc))
            except Exception as exc:  # noqa: BLE001
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    return MirageAdminHandler


def build_service() -> AdminService:
    load_runtime_env()
    args = env_namespace()
    api = xui_api.api_from_args(args, {})
    backup_dir = Path(os.environ.get("MIRAGE_ADMIN_BACKUP_DIR", str(DEFAULT_BACKUP_DIR)))
    config: dict[str, Any] = {}
    public_host = xui_api.public_host_value(args, config)
    if public_host:
        config["public_host"] = public_host
    return AdminService(api=api, config=config, backup_dir=backup_dir)


def serve() -> None:
    service = build_service()
    token = os.environ.get("MIRAGE_ADMIN_TOKEN", "").strip()
    if not token:
        raise SystemExit("MIRAGE_ADMIN_TOKEN is required")
    host = os.environ.get("MIRAGE_ADMIN_HOST", DEFAULT_ADMIN_HOST)
    port = int(os.environ.get("MIRAGE_ADMIN_PORT", DEFAULT_ADMIN_PORT))
    server = ThreadingHTTPServer((host, port), make_handler(service, token))
    print(f"Mirage Admin API listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve()
