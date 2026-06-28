#!/usr/bin/env python3
"""Operator CLI for 3x-ui API automation."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import secrets
import string
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import error, parse, request


DEFAULT_ENV_FILE = Path(__file__).with_name(".env.local")
DEFAULT_CONFIG_FILE = Path(__file__).with_name("config.local.json")
DEFAULT_BACKUP_DIR = Path("backups") / "x-ui"
DEFAULT_USERS_FILE = Path(__file__).with_name("users.local.json")
DEFAULT_USERS_EXAMPLE_FILE = Path(__file__).with_name("users.example.json")
DEFAULT_INBOUND = {"protocol": "vless", "port": 443}
DEFAULT_TUNNEL_LOCAL_PORT = 2096
LOWER_NUM = string.ascii_lowercase + string.digits


class ApiError(RuntimeError):
    """Raised when the panel API rejects a request."""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_json_file(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def choose_config_path(raw: str | None) -> Path | None:
    if raw:
        return Path(raw)
    if DEFAULT_CONFIG_FILE.exists():
        return DEFAULT_CONFIG_FILE
    return None


def choose_users_path(raw: str | None) -> Path:
    if raw:
        return Path(raw)
    if DEFAULT_USERS_FILE.exists():
        return DEFAULT_USERS_FILE
    return DEFAULT_USERS_EXAMPLE_FILE


def normalize_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if not url:
        raise SystemExit("Set MIRAGE_XUI_BASE_URL or pass --base-url.")
    if not url.startswith(("http://", "https://")):
        raise SystemExit("Panel base URL must start with http:// or https://.")
    return url


def config_get(config: dict[str, Any], key: str, default: Any = None) -> Any:
    value = config.get(key)
    return default if value is None else value


def option_value(args: argparse.Namespace, config: dict[str, Any], attr: str, env_name: str, default: Any = None) -> Any:
    value = getattr(args, attr, None)
    if value not in (None, ""):
        return value
    env_value = os.environ.get(env_name)
    if env_value not in (None, ""):
        return env_value
    return config_get(config, attr, default)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def random_lower_num(length: int) -> str:
    return "".join(secrets.choice(LOWER_NUM) for _ in range(length))


def gib_to_bytes(value: float | int | str) -> int:
    number = float(value)
    if number < 0:
        raise SystemExit("Traffic limit cannot be negative.")
    return int(number * 1024 * 1024 * 1024)


def build_endpoint(base_url: str, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return base_url.rstrip("/") + path


def parse_panel_response(body: bytes, url: str) -> Any:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(f"Non-JSON response from {url}: {exc}") from exc


class XuiClient:
    def __init__(
        self,
        base_url: str,
        api_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        two_factor_code: str = "",
        timeout: int = 30,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_token = api_token
        self.username = username
        self.password = password
        self.two_factor_code = two_factor_code
        self.timeout = timeout
        self.logged_in = False
        self.csrf_token: str | None = None
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookie_jar))

    def login_if_needed(self) -> None:
        if self.api_token:
            return
        if self.logged_in:
            return
        if not self.username or not self.password:
            raise SystemExit("Set MIRAGE_XUI_API_TOKEN or MIRAGE_XUI_USERNAME/MIRAGE_XUI_PASSWORD.")
        self.request_json(
            "POST",
            "/login",
            {
                "username": self.username,
                "password": self.password,
                "twoFactorCode": self.two_factor_code or "",
            },
        )
        self.logged_in = True
        csrf_payload = self.request_json("GET", "/csrf-token", expect_success=False)
        csrf_value = extract_obj(csrf_payload)
        if isinstance(csrf_value, str) and csrf_value:
            self.csrf_token = csrf_value

    def request_json(self, method: str, path: str, data: Any | None = None, expect_success: bool = True) -> Any:
        url = build_endpoint(self.base_url, path)
        headers = {"Accept": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.csrf_token and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = self.csrf_token

        req = request.Request(url, data=body, method=method.upper(), headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = parse_panel_response(response.read(), url)
        except error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = parse_panel_response(raw, url)
            except ApiError:
                payload = raw.decode("utf-8", errors="replace")
            raise ApiError(f"{method.upper()} {url} failed with HTTP {exc.code}: {payload}") from exc
        except error.URLError as exc:
            raise ApiError(f"{method.upper()} {url} failed: {exc.reason}") from exc

        if expect_success and isinstance(payload, dict) and payload.get("success") is False:
            raise ApiError(str(payload.get("msg") or payload))
        return payload

    def download(self, path: str) -> bytes:
        self.login_if_needed()
        url = build_endpoint(self.base_url, path)
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        req = request.Request(url, method="GET", headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                return response.read()
        except error.HTTPError as exc:
            raise ApiError(f"GET {url} failed with HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
        except error.URLError as exc:
            raise ApiError(f"GET {url} failed: {exc.reason}") from exc

    def api(self, method: str, path: str, data: Any | None = None, expect_success: bool = True) -> Any:
        self.login_if_needed()
        return self.request_json(method, path, data, expect_success=expect_success)


def api_from_args(args: argparse.Namespace, config: dict[str, Any]) -> XuiClient:
    base_url = option_value(args, config, "base_url", "MIRAGE_XUI_BASE_URL")
    api_token = option_value(args, config, "api_token", "MIRAGE_XUI_API_TOKEN")
    username = option_value(args, config, "username", "MIRAGE_XUI_USERNAME")
    password = option_value(args, config, "password", "MIRAGE_XUI_PASSWORD")
    two_factor_code = option_value(args, config, "two_factor_code", "MIRAGE_XUI_2FA_CODE", "")
    timeout = int(option_value(args, config, "timeout", "MIRAGE_XUI_TIMEOUT", 30))
    return XuiClient(
        base_url=base_url,
        api_token=api_token,
        username=username,
        password=password,
        two_factor_code=two_factor_code,
        timeout=timeout,
    )


def extract_obj(payload: Any) -> Any:
    if isinstance(payload, dict) and "obj" in payload:
        return payload["obj"]
    return payload


def list_inbound_options(api: XuiClient) -> list[dict[str, Any]]:
    payload = api.api("GET", "/panel/api/inbounds/options")
    obj = extract_obj(payload)
    return obj if isinstance(obj, list) else []


def parse_inbound_ids(value: Any) -> list[int]:
    if value in (None, ""):
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    return [int(item) for item in value]


def resolve_inbound_ids(args: argparse.Namespace, config: dict[str, Any], api: XuiClient) -> list[int]:
    explicit = parse_inbound_ids(getattr(args, "inbound_id", None) or os.environ.get("MIRAGE_XUI_INBOUND_ID"))
    if explicit:
        return explicit

    default_inbound = dict(DEFAULT_INBOUND)
    default_inbound.update(config.get("default_inbound") or {})
    remark = getattr(args, "inbound_remark", None) or os.environ.get("MIRAGE_XUI_INBOUND_REMARK") or default_inbound.get("remark")
    protocol = getattr(args, "protocol", None) or os.environ.get("MIRAGE_XUI_INBOUND_PROTOCOL") or default_inbound.get("protocol")
    port = getattr(args, "port", None) or os.environ.get("MIRAGE_XUI_INBOUND_PORT") or default_inbound.get("port")
    port = int(port) if port not in (None, "") else None

    options = list_inbound_options(api)
    matches = []
    for inbound in options:
        if remark and inbound.get("remark") != remark:
            continue
        if protocol and inbound.get("protocol") != protocol:
            continue
        if port and int(inbound.get("port") or 0) != port:
            continue
        matches.append(inbound)

    if not matches:
        raise SystemExit("No inbound matched the requested filters. Run: xui_api.py inbounds")
    if len(matches) > 1:
        ids = ", ".join(str(item.get("id")) for item in matches)
        raise SystemExit(f"More than one inbound matched ({ids}). Pass --inbound-id explicitly.")
    return [int(matches[0]["id"])]


def get_client(api: XuiClient, email: str) -> dict[str, Any] | None:
    payload = api.api("GET", f"/panel/api/clients/get/{parse.quote(email, safe='')}", expect_success=False)
    if not isinstance(payload, dict) or not payload.get("success"):
        return None
    obj = payload.get("obj")
    return obj if isinstance(obj, dict) else None


def public_host_value(args: argparse.Namespace, config: dict[str, Any]) -> str | None:
    host = option_value(args, config, "public_host", "MIRAGE_XUI_PUBLIC_HOST")
    if not host:
        return None
    host = str(host).strip()
    if not host or host.startswith("SERVER_"):
        return None
    if "://" in host:
        parsed = parse.urlsplit(host)
        host = parsed.hostname or host
    elif "/" in host or ":" in host:
        parsed = parse.urlsplit("//" + host)
        host = parsed.hostname or host.split("/", 1)[0]
    return host


def panel_url_parts(base_url: str) -> dict[str, Any]:
    parsed = parse.urlsplit(normalize_base_url(base_url))
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/"):
        path += "/"
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname or "127.0.0.1",
        "port": port,
        "path": path,
    }


def format_host(host: str) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def rewrite_link_host(link: str, public_host: str | None) -> str:
    if not public_host:
        return link
    parsed = parse.urlsplit(link)
    if parsed.scheme not in {"vless", "trojan", "ss", "hysteria", "hy2"} or not parsed.netloc:
        return link

    if "@" in parsed.netloc:
        userinfo, _hostport = parsed.netloc.rsplit("@", 1)
        prefix = userinfo + "@"
    else:
        prefix = ""

    port = f":{parsed.port}" if parsed.port else ""
    netloc = prefix + format_host(public_host) + port
    return parse.urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def get_links(api: XuiClient, email: str, public_host: str | None = None) -> list[str]:
    payload = api.api("GET", f"/panel/api/clients/links/{parse.quote(email, safe='')}")
    obj = extract_obj(payload)
    links = obj if isinstance(obj, list) else []
    return [rewrite_link_host(str(item), public_host) for item in links]


def build_client_payload(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    defaults = config.get("default_client") or {}
    total_gb = getattr(args, "total_gb", None)
    if total_gb is None:
        total_gb = defaults.get("total_gb", 0)

    expiry_time_ms = getattr(args, "expiry_time_ms", None)
    expiry_days = getattr(args, "expiry_days", None)
    if expiry_time_ms is None and expiry_days is not None:
        expiry_time_ms = int((time.time() + int(expiry_days) * 86400) * 1000)
    if expiry_time_ms is None:
        expiry_time_ms = int(defaults.get("expiry_time_ms", 0))

    return {
        "email": args.email.strip(),
        "subId": getattr(args, "sub_id", None) or random_lower_num(16),
        "id": getattr(args, "uuid", None) or str(uuid.uuid4()),
        "password": getattr(args, "password", None) or random_lower_num(16),
        "auth": getattr(args, "auth", None) or random_lower_num(16),
        "flow": getattr(args, "flow", None) or defaults.get("flow", "xtls-rprx-vision"),
        "security": getattr(args, "security", None) or defaults.get("security", "auto"),
        "totalGB": gib_to_bytes(total_gb),
        "expiryTime": int(expiry_time_ms),
        "reset": int(getattr(args, "reset_days", None) if getattr(args, "reset_days", None) is not None else defaults.get("reset_days", 0)),
        "limitIp": int(getattr(args, "limit_ip", None) if getattr(args, "limit_ip", None) is not None else defaults.get("limit_ip", 0)),
        "tgId": int(getattr(args, "tg_id", None) if getattr(args, "tg_id", None) is not None else defaults.get("tg_id", 0)),
        "group": getattr(args, "group", None) if getattr(args, "group", None) is not None else defaults.get("group", ""),
        "comment": getattr(args, "comment", None) if getattr(args, "comment", None) is not None else defaults.get("comment", ""),
        "enable": bool(defaults.get("enable", True)),
    }


def cmd_inbounds(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    rows = list_inbound_options(api)
    if args.json:
        print_json(rows)
        return 0
    for row in rows:
        print(
            f"{row.get('id')}\t{row.get('protocol')}\t{row.get('port')}\t"
            f"{row.get('remark')}\t{row.get('tag')}"
        )
    return 0


def cmd_create_token(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    payload = api.api("POST", "/panel/api/setting/apiTokens/create", {"name": args.name})
    print_json(extract_obj(payload))
    return 0


def ensure_client(args: argparse.Namespace, config: dict[str, Any], api: XuiClient) -> dict[str, Any]:
    existing = get_client(api, args.email)
    if existing:
        return {"changed": False, "email": args.email, "client": existing.get("client"), "inboundIds": existing.get("inboundIds", [])}

    inbound_ids = resolve_inbound_ids(args, config, api)
    client = build_client_payload(args, config)
    payload = api.api("POST", "/panel/api/clients/add", {"client": client, "inboundIds": inbound_ids})
    return {"changed": True, "email": args.email, "api": payload, "inboundIds": inbound_ids}


def cmd_ensure_client(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    result = ensure_client(args, config, api)
    if args.json:
        output: dict[str, Any] = dict(result)
        if args.print_links:
            output["links"] = get_links(api, args.email, public_host_value(args, config))
        print_json(output)
        return 0

    state = "created" if result["changed"] else "exists"
    print(f"{args.email}: {state}")
    if args.print_links:
        for link in get_links(api, args.email, public_host_value(args, config)):
            print(link)
    return 0


def cmd_sync_users(args: argparse.Namespace, config: dict[str, Any]) -> int:
    users = load_json_file(choose_users_path(args.users))
    clients = users.get("clients", [])
    if not isinstance(clients, list):
        raise SystemExit("users file must contain a clients array.")

    api = api_from_args(args, config)
    results = []
    for item in clients:
        if not isinstance(item, dict) or not item.get("email"):
            raise SystemExit("Every client item must contain email.")
        merged = argparse.Namespace(**vars(args))
        for key, value in item.items():
            setattr(merged, key, value)
        result = ensure_client(merged, config, api)
        if args.print_links:
            result["links"] = get_links(api, merged.email, public_host_value(args, config))
        results.append(result)

    if args.json:
        print_json(results)
        return 0
    for result in results:
        state = "created" if result["changed"] else "exists"
        print(f"{result['email']}: {state}")
        for link in result.get("links", []):
            print(link)
    return 0


def cmd_links(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    links = get_links(api, args.email, public_host_value(args, config))
    if args.json:
        print_json(links)
    else:
        for link in links:
            print(link)
    return 0


def cmd_sub_links(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    client = get_client(api, args.email)
    if not client or not isinstance(client.get("client"), dict):
        raise SystemExit(f"Client not found: {args.email}")
    sub_id = client["client"].get("subId")
    if not sub_id:
        raise SystemExit(f"Client has no subId: {args.email}")
    payload = api.api("GET", f"/panel/api/clients/subLinks/{parse.quote(str(sub_id), safe='')}")
    links = [rewrite_link_host(str(item), public_host_value(args, config)) for item in (extract_obj(payload) or [])]
    if args.json:
        print_json({"email": args.email, "subId": sub_id, "links": links})
    else:
        for link in links:
            print(link)
    return 0


def cmd_enable_state(args: argparse.Namespace, config: dict[str, Any], enabled: bool) -> int:
    api = api_from_args(args, config)
    path = "/panel/api/clients/bulkEnable" if enabled else "/panel/api/clients/bulkDisable"
    payload = api.api("POST", path, {"emails": args.email})
    print_json(payload if args.json else extract_obj(payload))
    return 0


def cmd_delete_client(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    payload = api.api("POST", "/panel/api/clients/bulkDel", {"emails": args.email, "keepTraffic": args.keep_traffic})
    print_json(payload if args.json else extract_obj(payload))
    return 0


def cmd_backup_db(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    output = Path(args.output) if args.output else DEFAULT_BACKUP_DIR / f"x-ui-{time.strftime('%Y%m%d-%H%M%S')}.db"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(api.download("/panel/api/server/getDb"))
    print(output)
    return 0


def cmd_status(args: argparse.Namespace, config: dict[str, Any]) -> int:
    api = api_from_args(args, config)
    payload = api.api("GET", "/panel/api/server/status")
    print_json(payload if args.json else extract_obj(payload))
    return 0


def cmd_access_info(args: argparse.Namespace, config: dict[str, Any]) -> int:
    base_url = option_value(args, config, "base_url", "MIRAGE_XUI_BASE_URL")
    parts = panel_url_parts(base_url)
    local_port = int(option_value(args, config, "local_port", "MIRAGE_XUI_TUNNEL_LOCAL_PORT", DEFAULT_TUNNEL_LOCAL_PORT))
    ssh_host = option_value(args, config, "ssh_host", "MIRAGE_SSH_HOST", "SERVER_HOST")
    ssh_user = option_value(args, config, "ssh_user", "MIRAGE_SSH_USER", "mirage")
    ssh_key = option_value(args, config, "ssh_key", "MIRAGE_SSH_KEY", "$HOME\\.ssh\\mirage_ed25519")
    local_panel_url = f"http://127.0.0.1:{local_port}{parts['path']}"
    ssh_tunnel_command = (
        f"ssh -i {ssh_key} -N -L {local_port}:127.0.0.1:{parts['port']} "
        f"{ssh_user}@{ssh_host}"
    )
    info = {
        "panel_port": parts["port"],
        "web_base_path": parts["path"],
        "local_panel_url": local_panel_url,
        "ssh_tunnel_command": ssh_tunnel_command,
        "docker_commands": {
            "inbounds": "docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds",
            "sync_users": "docker compose -f ops/xui/compose.yml run --rm xui-ops sync-users --print-links",
            "backup_db": "docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db",
        },
    }
    if args.json:
        print_json(info)
        return 0

    print("3x-ui access")
    print("------------")
    print(f"Panel port on VPS: {info['panel_port']}")
    print(f"Local browser URL: {info['local_panel_url']}")
    print("")
    print("PowerShell tunnel command:")
    print(info["ssh_tunnel_command"])
    print("")
    print("VPS commands:")
    for command in info["docker_commands"].values():
        print(command)
    return 0


def add_common_client_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--email", required=True)
    parser.add_argument("--comment")
    parser.add_argument("--group")
    parser.add_argument("--inbound-id", nargs="+", type=int)
    parser.add_argument("--inbound-remark")
    parser.add_argument("--protocol")
    parser.add_argument("--port", type=int)
    parser.add_argument("--total-gb", type=float)
    parser.add_argument("--expiry-days", type=int)
    parser.add_argument("--expiry-time-ms", type=int)
    parser.add_argument("--limit-ip", type=int)
    parser.add_argument("--reset-days", type=int)
    parser.add_argument("--tg-id", type=int)
    parser.add_argument("--sub-id")
    parser.add_argument("--uuid")
    parser.add_argument("--password")
    parser.add_argument("--auth")
    parser.add_argument("--flow")
    parser.add_argument("--security")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a 3x-ui panel through its HTTP API.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--config")
    parser.add_argument("--base-url")
    parser.add_argument("--api-token")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--two-factor-code")
    parser.add_argument("--public-host")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--json", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inbounds", help="List inbound options.").set_defaults(func=cmd_inbounds)

    token = sub.add_parser("create-token", help="Create a 3x-ui API token.")
    token.add_argument("--name", required=True)
    token.set_defaults(func=cmd_create_token)

    ensure = sub.add_parser("ensure-client", help="Create a client if it does not exist.")
    add_common_client_args(ensure)
    ensure.add_argument("--print-links", action="store_true")
    ensure.set_defaults(func=cmd_ensure_client)

    sync = sub.add_parser("sync-users", help="Ensure every client from a local users JSON file exists.")
    sync.add_argument("--users")
    sync.add_argument("--print-links", action="store_true")
    sync.set_defaults(func=cmd_sync_users)

    links = sub.add_parser("links", help="Print direct protocol links for a client.")
    links.add_argument("--email", required=True)
    links.set_defaults(func=cmd_links)

    sub_links = sub.add_parser("sub-links", help="Print protocol links resolved through a client's subId.")
    sub_links.add_argument("--email", required=True)
    sub_links.set_defaults(func=cmd_sub_links)

    enable = sub.add_parser("enable-client", help="Enable one or more clients.")
    enable.add_argument("--email", nargs="+", required=True)
    enable.set_defaults(func=lambda args, config: cmd_enable_state(args, config, True))

    disable = sub.add_parser("disable-client", help="Disable one or more clients.")
    disable.add_argument("--email", nargs="+", required=True)
    disable.set_defaults(func=lambda args, config: cmd_enable_state(args, config, False))

    delete = sub.add_parser("delete-client", help="Delete one or more clients.")
    delete.add_argument("--email", nargs="+", required=True)
    delete.add_argument("--keep-traffic", action="store_true")
    delete.set_defaults(func=cmd_delete_client)

    backup = sub.add_parser("backup-db", help="Download a 3x-ui SQLite backup through the API.")
    backup.add_argument("--output")
    backup.set_defaults(func=cmd_backup_db)

    sub.add_parser("status", help="Print panel server status.").set_defaults(func=cmd_status)

    access = sub.add_parser("access-info", help="Print panel URL, SSH tunnel command, and common ops commands.")
    access.add_argument("--local-port", type=int)
    access.add_argument("--ssh-host")
    access.add_argument("--ssh-user")
    access.add_argument("--ssh-key")
    access.set_defaults(func=cmd_access_info)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env_file = Path(args.env_file) if args.env_file else DEFAULT_ENV_FILE
    load_env_file(env_file)
    config = load_json_file(choose_config_path(args.config))
    try:
        return args.func(args, config)
    except ApiError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
