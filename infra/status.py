#!/usr/bin/env python3
"""Send one small host-side status message; never restart or change the VPN."""

import argparse
import contextlib
import copy
import http.client
import json
import os
import re
import socket
import sqlite3
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from host import SafeError, compose, load_config, notify, private_file, read_env, run

TRANSPORTS = {"TCP_PORT": "tcp", "GRPC_PORT": "grpc", "XHTTP_PORT": "xhttp", "TROJAN_PORT": "trojan"}
PROBE_URL = "https://www.gstatic.com/generate_204"
MAX_SUBSCRIPTION = 1024 * 1024


def subscription_profiles(config, environment):
    database = private_file(Path(config["state_dir"]) / "db" / "x-ui.db")
    with contextlib.closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=3)) as db:
        row = db.execute("SELECT sub_id FROM clients WHERE enable=1 ORDER BY id LIMIT 1").fetchone()
    if not row or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", row[0]):
        raise SafeError("No eligible subscription is available for a server check.")
    connection = http.client.HTTPSConnection(config["public_host"], int(environment["SUB_HTTPS_PORT"]), timeout=8)

    def connect():
        raw = socket.create_connection(("127.0.0.1", int(environment["SUB_HTTPS_PORT"])), timeout=8)
        try:
            connection.sock = ssl.create_default_context(cafile=config["ca_file"]).wrap_socket(
                raw, server_hostname=config["public_host"])
        except Exception:
            raw.close()
            raise

    connection.connect = connect
    try:
        connection.request("GET", "/json/" + row[0])
        response = connection.getresponse()
        body = response.read(MAX_SUBSCRIPTION + 1)
        if response.status != 200 or len(body) > MAX_SUBSCRIPTION:
            raise SafeError("The subscription check failed.")
        return parse_profiles(json.loads(body), environment)
    finally:
        connection.close()


def parse_profiles(configs, environment):
    expected = {int(environment[key]): name for key, name in TRANSPORTS.items()}
    profiles = {}
    if not isinstance(configs, list) or len(configs) != 4 or len(expected) != 4:
        raise SafeError("The subscription must contain the four expected transports.")
    for config in configs:
        proxies = [o for o in config.get("outbounds", []) if o.get("protocol") in {"vless", "trojan"}]
        if len(proxies) != 1:
            raise SafeError("The subscription has unexpected proxy settings.")
        outbound = copy.deepcopy(proxies[0])
        settings = outbound["settings"]
        if "port" in settings:
            server = settings
        else:
            servers = settings.get("vnext", settings.get("servers", []))
            if len(servers) != 1:
                raise SafeError("The subscription has unexpected server settings.")
            server = servers[0]
        name = expected.get(server.get("port"))
        if not name or name in profiles:
            raise SafeError("The subscription has unexpected or duplicate ports.")
        server["address"] = "127.0.0.1"
        profiles[name] = outbound
    return profiles


def probe(outbound, binary):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    config = {"log": {"loglevel": "none"},
              "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "socks",
                            "settings": {"auth": "noauth", "udp": False}}],
              "outbounds": [outbound]}
    child = subprocess.Popen(["nice", "-n", "15", str(binary), "run", "-format", "json", "-config", "/dev/stdin"],
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env=dict(os.environ, GOMEMLIMIT="24MiB", GOGC="50", GODEBUG="multipathtcp=0"))
    try:
        child.stdin.write(json.dumps(config).encode())
        child.stdin.close()
        ready = False
        for _ in range(40):
            if child.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                    ready = True
                    break
            except OSError:
                time.sleep(0.05)
        if not ready:
            return False
        result = subprocess.run(["curl", "--silent", "--max-time", "8", "--socks5-hostname",
                                 "127.0.0.1:" + str(port), "--output", "/dev/null", "--write-out", "%{http_code}", PROBE_URL],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=10)
        return child.poll() is None and result.returncode == 0 and result.stdout == b"204"
    finally:
        if child.stdin and not child.stdin.closed:
            try:
                child.stdin.close()
            except OSError:
                pass
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=2)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("Unexpected panel redirect")


def check(config):
    environment = read_env(config)
    containers = {}
    for service in ("x-ui", "caddy"):
        identifier = compose(config, "ps", "-q", service, timeout=5).decode().strip()
        if identifier:
            containers[service] = json.loads(run(
                ["docker", "inspect", "--type", "container", identifier], timeout=5))[0]
    flags = {}
    for service in ("x-ui", "caddy"):
        state = containers.get(service, {}).get("State", {})
        flags[service] = bool(state.get("Running")) and state.get("Health", {}).get("Status") not in {"unhealthy", "starting"}
    identifier = containers.get("x-ui", {}).get("Id")
    flags["xray"] = False
    core_binary = None
    if identifier:
        for path in Path("/proc").iterdir():
            if not path.name.isdecimal():
                continue
            try:
                if ((path / "comm").read_text().strip().startswith("xray-linux-")
                        and identifier in (path / "cgroup").read_text()):
                    flags["xray"] = True
                    candidate = Path(environment["DB_DIR"]) / "bin" / Path(os.readlink(path / "exe")).name
                    if candidate.is_file() and os.path.samefile(candidate, path / "exe"):
                        core_binary = candidate
                    break
            except OSError:
                continue
    flags["panel"] = False
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open("http://127.0.0.1:" + environment["PANEL_PORT"] + "/", timeout=5) as response:
            flags["panel"] = response.status == 200
    except Exception:
        pass
    flags["subscription_tls"] = False
    try:
        context = ssl.create_default_context(cafile=config["ca_file"])
        with socket.create_connection(("127.0.0.1", int(environment["SUB_HTTPS_PORT"])), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=config["public_host"]):
                flags["subscription_tls"] = True
    except Exception:
        pass
    ports = 0
    for variable in ("TCP_PORT", "GRPC_PORT", "XHTTP_PORT", "TROJAN_PORT"):
        try:
            with socket.create_connection(("127.0.0.1", int(environment[variable])), timeout=2):
                ports += 1
        except OSError:
            pass
    available = next(int(line.split()[1]) // 1024 for line in
                     Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
    flags["subscription_content"] = False
    traffic = {name: False for name in TRANSPORTS.values()}
    if available >= 128 and flags.get("x-ui") and flags.get("caddy"):
        try:
            profiles = subscription_profiles(config, environment)
            flags["subscription_content"] = True
            # Execute the persisted binary verified against the live inode, not a reusable PID path.
            if core_binary is None:
                raise SafeError("The active persisted VPN core could not be identified.")
            for name, outbound in profiles.items():
                try:
                    traffic[name] = probe(outbound, core_binary)
                except Exception:
                    traffic[name] = False
        except Exception:
            pass
    flags.update({"https_" + name: passed for name, passed in traffic.items()})
    healthy = all(flags.values()) and ports == 4
    if healthy:
        text = "✅ Mirage: серверная проверка пройдена."
    else:
        failed = [key for key, value in flags.items() if not value]
        text = "⚠️ Mirage: серверная проверка требует внимания.\nПроверки: " + ", ".join(failed)
    text += ("\nHTTPS через VPN: " + str(sum(traffic.values())) + "/4. Доступно RAM: " + str(available) + " МиБ."
             "\nПроверка с VPS; доступность в сети телефона она не подтверждает.")
    return {"healthy": healthy, "checks": flags, "ports": ports,
            "available_memory_mib": available}, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--check-only", action="store_true", help="Print safe results without Telegram delivery")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        try:
            result, text = check(config)
        except Exception as error:
            result = {"healthy": False, "check_error_type": type(error).__name__}
            text = "⚠️ Mirage: серверная проверка не завершилась. Требуется проверка сервера."
        if not args.check_only:
            notify(config, text)
        print(json.dumps({"event": "status_checked" if args.check_only else "nightly_status_delivered", **result}), flush=True)
    except Exception as error:
        print(json.dumps({"event": "nightly_status_failed", "error_type": type(error).__name__}),
              file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
