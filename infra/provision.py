#!/usr/bin/env python3
"""Deliver GitHub Environment secrets to an already prepared host; never install it."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from host import (SafeError, compose, load_config, private_dir, read_env,
                  telegram_settings, write_json)

TARGETS = {"staging": Path("/etc/mirage-test/host.json"),
           "production": Path("/etc/mirage/host.json")}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SafeError("The local panel unexpectedly redirected a secret request.")


def apply_bot(config, environment):
    # The upstream CLI emits this named token to a captured pipe, never argv/logs.
    output = compose(config, "exec", "-T", "x-ui", "/app/x-ui", "setting", "-getApiToken",
                     "-tokenName", "mirage-secret-delivery", "-tokenScope", "admin").decode()
    match = re.search(r"(?m)^apiToken:\s*(\S+)\s*$", output)
    if not match:
        raise SafeError("The native CLI did not return its temporary API token.")
    token = match[1]
    port = environment.get("PANEL_PORT", "")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise SafeError("Invalid local panel port.")
    base = "http://127.0.0.1:" + port + "/panel/api/setting/"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(endpoint, data=None, method="POST"):
        body = json.dumps(data if data is not None else {}).encode() if method == "POST" else None
        req = urllib.request.Request(base + endpoint, data=body, method=method,
                                     headers={"Authorization": "Bearer " + token,
                                              "Content-Type": "application/json"})
        with opener.open(req, timeout=20) as response:
            value = json.load(response)
        if value.get("success") is not True:
            raise SafeError("The native settings API rejected secret provisioning.")
        return value.get("obj")

    token_id = None
    try:
        rows = request("apiTokens", method="GET")
        matches = [row for row in rows if row.get("name") == "mirage-secret-delivery"]
        if len(matches) != 1:
            raise SafeError("The temporary API token could not be identified.")
        token_id = int(matches[0]["id"])
        settings = request("all")
        if not isinstance(settings, dict) or "webPort" not in settings or "twoFactorEnable" not in settings:
            raise SafeError("The candidate settings API differs from the reviewed schema.")
        settings.update({"tgBotEnable": True, "tgBotToken": config["telegram_token"],
                         "tgBotChatId": str(config["telegram_chat_id"]), "tgBotBackup": False,
                         "tgRunTime": "0 10 * * 0", "tgLang": "ru-RU",
                         "tgEnabledEvents": "xray.crash,cpu.high,memory.high"})
        request("update", settings)
        check = request("all")
        if (check.get("tgBotEnable") is not True or check.get("tgBotBackup") is not False
                or str(check.get("tgBotChatId")) != str(config["telegram_chat_id"])
                or check.get("hasTgBotToken") is not True):
            raise SafeError("The panel did not confirm the expected Telegram settings.")
    finally:
        if token_id is not None:
            request("apiTokens/setEnabled/" + str(token_id), {"enabled": False, "expectedScope": "admin"})


def receive(target, payload):
    if os.geteuid() != 0:
        raise SafeError("Secret delivery must run as root on the prepared host.")
    if set(payload) != {"telegram_token", "telegram_chat_id", "duckdns_token", "apply_bot"}:
        raise SafeError("Secret delivery has unexpected or missing fields.")
    telegram_settings(payload)
    if not isinstance(payload["apply_bot"], bool):
        raise SafeError("The apply-bot switch must be boolean.")
    dns = payload["duckdns_token"]
    if not isinstance(dns, str) or (dns and not re.fullmatch(r"[A-Za-z0-9-]{20,}", dns)):
        raise SafeError("The DNS credential has an invalid format.")
    if target == "staging" and dns:
        raise SafeError("Staging cannot receive production DNS credentials.")
    config_path = TARGETS[target]
    config = load_config(config_path)
    environment = read_env(config)
    expected = "mirage-test" if target == "staging" else "mirage"
    if environment.get("COMPOSE_PROJECT_NAME") != expected:
        raise SafeError("The prepared Compose project differs from the selected target.")
    stored = json.loads(config_path.read_text())
    stored["telegram_token"] = payload["telegram_token"]
    stored["telegram_chat_id"] = str(payload["telegram_chat_id"])
    write_json(config_path, stored)
    if dns:
        folder = private_dir(config_path.parent / "secrets")
        temporary = folder / "duckdns_token.new"
        temporary.write_text(dns + "\n")
        temporary.chmod(0o600)
        os.replace(temporary, folder / "duckdns_token")
    if payload["apply_bot"]:
        apply_bot(load_config(config_path), environment)


def send():
    target = os.environ.get("MIRAGE_TARGET", "")
    if target not in TARGETS:
        raise SafeError("Select staging or production.")
    required = ["SSH_HOST", "SSH_PORT", "SSH_USER", "SSH_KNOWN_HOSTS", "SSH_PRIVATE_KEY",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_ID"]
    if any(not os.environ.get(name) for name in required):
        raise SafeError("Required GitHub Environment secrets are missing.")
    hostname, port, user = (os.environ[name] for name in ("SSH_HOST", "SSH_PORT", "SSH_USER"))
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", hostname)
            or not port.isdigit() or not 1 <= int(port) <= 65535
            or not re.fullmatch(r"[a-z_][a-z0-9_-]*", user)):
        raise SafeError("Invalid SSH destination settings.")
    switch = os.environ.get("MIRAGE_APPLY_BOT", "false")
    if switch not in {"true", "false"}:
        raise SafeError("Invalid apply-bot switch.")
    payload = {"telegram_token": os.environ["TELEGRAM_BOT_TOKEN"],
               "telegram_chat_id": os.environ["TELEGRAM_ADMIN_ID"],
               "duckdns_token": os.environ.get("DUCKDNS_TOKEN", "") if target == "production" else "",
               "apply_bot": switch == "true"}
    telegram_settings(payload)
    with tempfile.TemporaryDirectory(prefix="mirage-secret-delivery-") as temporary:
        directory = Path(temporary)
        key, known = directory / "identity", directory / "known_hosts"
        key.write_text(os.environ["SSH_PRIVATE_KEY"].rstrip() + "\n")
        known.write_text(os.environ["SSH_KNOWN_HOSTS"].rstrip() + "\n")
        key.chmod(0o600)
        known.chmod(0o600)
        command = ["ssh", "-T", "-i", str(key), "-p", port, "-o", "BatchMode=yes",
                   "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
                   "-o", "UserKnownHostsFile=" + str(known), "-o", "ConnectTimeout=15",
                   user + "@" + hostname,
                   "sudo -n /usr/bin/python3 /opt/mirage/infra/provision.py --receive " + target]
        # No secret appears in the command, output or persistent workstation file.
        result = subprocess.run(command, input=json.dumps(payload).encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise SafeError("Secret delivery failed; SSH output was suppressed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--send", action="store_true")
    mode.add_argument("--receive", choices=TARGETS)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.send:
            send()
        else:
            raw = sys.stdin.buffer.read(32769)
            if len(raw) > 32768:
                raise SafeError("The secret payload is too large.")
            receive(args.receive, json.loads(raw))
    except SafeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Secret delivery failed; private values were suppressed.", file=sys.stderr)
        return 1
    print("Runtime secrets delivered. No deployment, renewal or VPN restart was requested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
