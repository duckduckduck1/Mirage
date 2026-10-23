"""Private host settings and bounded subprocess/Telegram helpers."""

import hashlib
import http.client
import json
import os
import re
import stat
import subprocess
from pathlib import Path


class SafeError(Exception):
    """An error safe to show without paths, credentials or subprocess output."""


def private_file(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise SafeError("A private file must be owned by this account and mode 0600.")
    return path


def private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise SafeError("A private directory must be owned by this account and mode 0700.")
    return path


def load_config(path):
    config = json.loads(private_file(path).read_text())
    required = {"project_dir", "env_file", "state_dir", "acme_dir", "age_recipient",
                "telegram_token", "telegram_chat_id", "public_host", "ca_file"}
    if set(config) != required:
        raise SafeError("Host settings have missing or unknown fields.")
    for field in ("project_dir", "env_file", "state_dir", "acme_dir"):
        value = config[field]
        if not isinstance(value, str) or not Path(value).is_absolute() or Path(value) == Path("/"):
            raise SafeError("Host settings require absolute, non-root paths.")
    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", config["public_host"]):
        raise SafeError("A DNS hostname is required.")
    private_dir(config["state_dir"])
    private_file(config["env_file"])
    config["config_file"] = str(Path(path).resolve())
    return config


def run(command, *, cwd=None, timeout=120, output=None):
    try:
        result = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=output if output is not None else subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=True)
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise SafeError("An external command failed; its output was suppressed.") from None


def compose(config, *arguments, timeout=120):
    return run(["docker", "compose", "--env-file", config["env_file"],
                "-f", str(Path(config["project_dir"]) / "compose.yaml"), *arguments],
               cwd=config["project_dir"], timeout=timeout)


def read_env(config):
    result = {}
    for line in Path(config["env_file"]).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in result or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise SafeError("Use unique KEY=value entries in the private Compose environment.")
        if "$" in value or "`" in value or not value or value[0] in "\"'":
            raise SafeError("Use literal, unquoted Compose environment values.")
        result[key] = value
    state = Path(config["state_dir"])
    if (result.get("DB_DIR") != str(state / "db")
            or result.get("TLS_DIR") != str(state / "tls")
            or result.get("PUBLIC_HOST") != config["public_host"]):
        raise SafeError("Host settings and Compose paths/hostname do not agree.")
    for field, service in (("XUI_IMAGE", "x-ui"), ("CADDY_IMAGE", "caddy")):
        reference = result.get(field, "")
        pinned = re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", reference)
        recovery = re.fullmatch(r"mirage-recovery/" + service + r":[0-9a-f]{64}", reference)
        if not (pinned or recovery):
            raise SafeError("Use digest-pinned images or verified recovery image-ID tags.")
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".new")
    with temporary.open("w", encoding="utf-8") as target:
        os.chmod(temporary, 0o600)
        json.dump(value, target, indent=2)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def telegram_settings(config):
    if (not re.fullmatch(r"[0-9]{6,20}:[A-Za-z0-9_-]{20,}", config["telegram_token"])
            or not re.fullmatch(r"[1-9][0-9]*", str(config["telegram_chat_id"]))):
        raise SafeError("Configure a bot token and a positive private admin chat ID.")


def telegram_request(config, method, prefix, file_path=None, suffix=b""):
    telegram_settings(config)
    connection = http.client.HTTPSConnection("api.telegram.org", timeout=120)
    size = len(prefix) + len(suffix) + (Path(file_path).stat().st_size if file_path else 0)
    try:
        connection.putrequest("POST", "/bot" + config["telegram_token"] + "/" + method)
        content_type = ("multipart/form-data; boundary=mirage-recovery-boundary"
                        if file_path else "application/json")
        connection.putheader("Content-Type", content_type)
        connection.putheader("Content-Length", str(size))
        connection.endheaders()
        connection.send(prefix)
        if file_path:
            with Path(file_path).open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    connection.send(block)
        connection.send(suffix)
        response = connection.getresponse()
        result = json.loads(response.read(1024 * 1024))
        if (response.status != 200 or result.get("ok") is not True
                or str(result["result"]["chat"]["id"]) != str(config["telegram_chat_id"])):
            raise SafeError("Telegram delivery failed; response values were suppressed.")
        return result["result"]["message_id"]
    except SafeError:
        raise
    except Exception:
        raise SafeError("Telegram delivery failed; credentials and response were suppressed.") from None
    finally:
        connection.close()


def send_document(config, path, caption):
    path = Path(path)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", path.name):
        raise SafeError("Invalid recovery part filename.")
    boundary = "mirage-recovery-boundary"
    prefix = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
              f"{config['telegram_chat_id']}\r\n"
              f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n"
              f"{caption}\r\n"
              f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; "
              f"filename=\"{path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    return telegram_request(config, "sendDocument", prefix, path,
                            f"\r\n--{boundary}--\r\n".encode())


def notify(config, text):
    return telegram_request(config, "sendMessage", json.dumps({
        "chat_id": config["telegram_chat_id"], "text": text,
    }).encode())
