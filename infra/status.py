#!/usr/bin/env python3
"""Send one small host-side status message; never restart or change the VPN."""

import argparse
import json
import socket
import ssl
import sys
import urllib.request
from pathlib import Path

from host import compose, load_config, notify, read_env, run


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
    if identifier:
        for path in Path("/proc").iterdir():
            if not path.name.isdecimal():
                continue
            try:
                if ((path / "comm").read_text().strip().startswith("xray-linux-")
                        and identifier in (path / "cgroup").read_text()):
                    flags["xray"] = True
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
    healthy = all(flags.values()) and ports == 4
    if healthy:
        text = "✅ Mirage: серверная проверка пройдена."
    else:
        failed = [key for key, value in flags.items() if not value]
        text = "⚠️ Mirage: серверная проверка требует внимания.\nПроверки: " + ", ".join(failed)
    text += ("\nПорты VPN: " + str(ports) + "/4. Доступно RAM: " + str(available) + " МиБ."
             "\nЭто проверка сервера, без проверки клиентских подключений.")
    return {"healthy": healthy, "checks": flags, "ports": ports,
            "available_memory_mib": available}, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        try:
            result, text = check(config)
        except Exception as error:
            result = {"healthy": False, "check_error_type": type(error).__name__}
            text = "⚠️ Mirage: серверная проверка не завершилась. Требуется проверка сервера."
        notify(config, text)
        print(json.dumps({"event": "nightly_status_delivered", **result}), flush=True)
    except Exception as error:
        print(json.dumps({"event": "nightly_status_failed", "error_type": type(error).__name__}),
              file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
