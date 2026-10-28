#!/usr/bin/env python3
"""Consistent SQLite recovery bundles, age encryption and resumable Telegram delivery."""

import argparse
import datetime as dt
import fcntl
import io
import json
import os
import re
import shlex
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from host import (SafeError, compose, load_config, private_dir, read_env, run,
                  send_document, sha256, telegram_settings, write_json)

PART_SIZE = 18 * 1024 * 1024
STARTED = time.monotonic()
CURRENT_STAGE = "startup"


def progress(stage):
    """Log fixed stage names only; never file paths, arguments or data."""
    global CURRENT_STAGE
    CURRENT_STAGE = stage
    print(json.dumps({"event": "backup_stage", "stage": stage,
                      "time_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "elapsed_seconds": round(time.monotonic() - STARTED, 3)}), flush=True)


def log_failure(error):
    record = {"event": "backup_failed", "stage": CURRENT_STAGE,
              "error_type": type(error).__name__,
              "time_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    cause = error
    for _ in range(4):
        nested = cause.__cause__ or cause.__context__
        if nested is None or nested is cause:
            break
        cause = nested
    record["cause_type"] = type(cause).__name__
    for field in ("errno", "returncode"):
        value = getattr(cause, field, None)
        if isinstance(value, int):
            record[field] = value
    print(json.dumps(record), file=sys.stderr, flush=True)


def temporary_name(name):
    return (name.endswith((".tmp", ".temp", ".swp", ".swo", ".new", "~"))
            or name.startswith((".snapshot-", ".images-", ".queue-"))
            or name in {"publish.lock", "backup.lock"})


def source_paths(path):
    """Exclude transient names before stat/open, including entire temp trees."""
    if temporary_name(path.name):
        return
    yield path
    if path.is_dir() and not path.is_symlink():
        for child in sorted(path.iterdir()):
            yield from source_paths(child)


def snapshot_database(source, destination):
    if not source.is_file():
        raise SafeError("The expected panel database is missing.")
    deadline = time.monotonic() + 60

    def progress(*_):
        if time.monotonic() > deadline:
            raise SafeError("SQLite snapshot exceeded its time budget.")

    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as live:
        with sqlite3.connect(destination) as snapshot:
            live.backup(snapshot, pages=256, progress=progress, sleep=0.05)
            if snapshot.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise SafeError("SQLite snapshot integrity check failed.")
    os.chmod(destination, 0o600)


def add_tree(archive, source, name):
    """Archive regular files and contained symlinks only, never devices or sockets."""
    source = Path(source)
    if temporary_name(source.name):
        return
    root = source.resolve() if source.is_dir() else source.parent.resolve()

    def checked(info):
        if info.issym():
            member_source = source / Path(info.name).relative_to(name) if source.is_dir() else source
            target = member_source.resolve(strict=True)
            if not target.is_relative_to(root):
                raise SafeError("A recovery source contains an escaping symlink.")
            info.linkname = os.path.relpath(target, member_source.parent)
        elif not (info.isfile() or info.isdir()):
            raise SafeError("A recovery source contains a special file.")
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        executable = info.isfile() and bool(info.mode & 0o111)
        info.mode = 0o700 if info.isdir() or executable else 0o600
        return info

    for entry in source_paths(source):
        relative = entry.relative_to(source)
        member = name if relative == Path(".") else str(Path(name) / relative)
        archive.add(entry, arcname=member, recursive=False, filter=checked)


def image_inventory(config, environment):
    records = []
    core_folder = "/app/bin"
    for service, variable in (("x-ui", "XUI_IMAGE"), ("caddy", "CADDY_IMAGE")):
        container_id = compose(config, "ps", "-q", service).decode().strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
            raise SafeError("Both expected Compose services must be running.")
        container = json.loads(run(["docker", "inspect", "--type", "container", container_id]))[0]
        if not container["State"]["Running"]:
            raise SafeError("An expected Compose service is not running.")
        mounts = {m["Destination"]: m for m in container["Mounts"]}
        tls = mounts.get("/certs", {})
        if tls.get("Source") != environment["TLS_DIR"] or tls.get("RW") is not False:
            raise SafeError("The running certificate mount differs from host settings.")
        if service == "x-ui" and mounts.get("/etc/x-ui", {}).get("Source") != environment["DB_DIR"]:
            raise SafeError("The running database mount differs from host settings.")
        if service == "x-ui":
            container_env = dict(item.split("=", 1) for item in container["Config"].get("Env", []) if "=" in item)
            core_folder = container_env.get("XUI_BIN_FOLDER", "/app/bin")
            if (core_folder not in {"/app/bin", "/etc/x-ui/bin"}
                    or core_folder != environment.get("XUI_BIN_FOLDER", "/app/bin")):
                raise SafeError("The running core directory differs from the supported host settings.")
        image = json.loads(run(["docker", "image", "inspect", container["Image"]]))[0]
        if environment[variable].startswith("mirage-recovery/"):
            expected = "sha256:" + environment[variable].rsplit(":", 1)[1]
            if image["Id"] != expected:
                raise SafeError("A recovery tag does not match its recorded immutable image ID.")
        else:
            digest = environment[variable].rsplit("@", 1)[1]
            if not any(ref.endswith("@" + digest) for ref in image.get("RepoDigests", [])):
                raise SafeError("A running image does not match its pinned registry digest.")
        records.append({"service": service, "reference": environment[variable],
                        "id": image["Id"], "size": image["Size"],
                        "architecture": image["Architecture"], "repo_digests": image.get("RepoDigests", [])})
    architecture = records[0]["architecture"]
    names = {"amd64": "amd64", "arm64": "arm64", "386": "i386"}
    if architecture not in names:
        raise SafeError("Record the core path for this architecture before using this helper.")
    version = compose(config, "exec", "-T", "x-ui", core_folder + "/xray-linux-" + names[architecture], "version")
    first_line = version.decode().splitlines()[0]
    match = re.match(r"Xray ([0-9]+(?:\.[0-9]+)+)\b", first_line)
    if not match:
        raise SafeError("The running core did not return the expected version format.")
    return records, "Xray " + match[1]


def build_recovery(config, environment, images, core, image_bundle, work):
    state = Path(config["state_dir"])
    acme_root = Path(config["acme_dir"])

    def acme_stamp():
        result = {}
        for path in source_paths(acme_root):
            info = path.lstat()
            # Transient children also change directory mtimes. The path map
            # detects real additions/removals without treating those as renewal.
            stamp = (info.st_ino, info.st_mode)
            if not stat.S_ISDIR(info.st_mode):
                stamp += (info.st_mtime_ns, info.st_size)
            result[str(path.relative_to(acme_root))] = stamp
        return result

    progress("snapshot.acme-baseline")
    before = acme_stamp()
    progress("snapshot.database")
    snapshot = work / "x-ui.db"
    snapshot_database(state / "db" / "x-ui.db", snapshot)
    manifest = {"format": 1, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "images": images, "core_version": core, "image_bundle": image_bundle,
                "database_sha256": sha256(snapshot),
                "restore_note": "Restore matching images and private paths; keep bots, ACME and DNS jobs disabled in clones."}
    archive_path = work / "recovery.tar.gz"
    progress("archive.database")
    with tarfile.open(archive_path, "w:gz", compresslevel=1, dereference=False) as archive:
        payload = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size, info.mode = len(payload), 0o600
        archive.addfile(info, io.BytesIO(payload))
        add_tree(archive, snapshot, "state/db/x-ui.db")
        progress("archive.runtime-state")
        for extra in sorted((state / "db").iterdir()):
            if (temporary_name(extra.name)
                    or extra.name in {"x-ui.db", "x-ui.db-wal", "x-ui.db-shm", "x-ui.db-journal"}):
                continue
            if extra.name == "system_metrics.gob":
                # Upstream publishes this file by atomic rename. Read one pinned
                # inode, then archive its stable copy, avoiding a stat/open race.
                progress("snapshot.panel-metrics")
                stable = work / "system_metrics.gob"
                with os.fdopen(os.open(extra, os.O_RDONLY | os.O_NOFOLLOW), "rb") as live:
                    if not stat.S_ISREG(os.fstat(live.fileno()).st_mode):
                        raise SafeError("Panel metric history must be a regular file.")
                    with stable.open("xb") as target:
                        os.chmod(stable, 0o600)
                        shutil.copyfileobj(live, target, length=1024 * 1024)
                add_tree(archive, stable, "state/db/" + extra.name)
            else:
                add_tree(archive, extra, "state/db/" + extra.name)
        progress("archive.certificates")
        with (state / "tls" / "publish.lock").open("a") as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_SH)
            add_tree(archive, state / "tls", "state/tls")
        if (state / "tls-source").exists():
            add_tree(archive, state / "tls-source", "state/tls-source")
        progress("archive.acme")
        add_tree(archive, acme_root, "acme")
        progress("archive.deployment")
        project = Path(config["project_dir"])
        add_tree(archive, project / "compose.yaml", "deployment/compose.yaml")
        for filename in ("Caddyfile", "host.py", "backup.py", "tls.py", "provision.py",
                         "status.py", "restore-isolated.yaml", "mirage-backup.service",
                         "mirage-backup.timer", "mirage-status.service", "mirage-status.timer"):
            add_tree(archive, project / "infra" / filename, "deployment/infra/" + filename)
        add_tree(archive, project / "docs" / "recovery.md", "RECOVERY.md")
        add_tree(archive, config["env_file"], "deployment/compose.env")
        add_tree(archive, config["config_file"], "deployment/host.json")
        panel_access = Path(config["config_file"]).parent / "panel-access.json"
        if panel_access.exists():
            add_tree(archive, panel_access, "deployment/panel-access.json")
        # Preserve only this ACME job, never unrelated root crontab entries.
        cron = run(["crontab", "-l"]).decode()
        acme_command = str(Path(config["acme_dir"]) / "acme.sh")
        lines = []
        for line in cron.splitlines():
            try:
                words = shlex.split(line, comments=True)
            except ValueError:
                continue
            if acme_command in words and "--cron" in words:
                lines.append(line)
        if not lines:
            raise SafeError("The expected host ACME schedule was not found.")
        payload = ("\n".join(lines) + "\n").encode()
        info = tarfile.TarInfo("host/acme-cron.txt")
        info.size, info.mode = len(payload), 0o600
        archive.addfile(info, io.BytesIO(payload))
    progress("snapshot.validate-acme")
    if acme_stamp() != before:
        raise SafeError("ACME state changed during the snapshot; retry after renewal completes.")
    return archive_path


def queue_archive(config, source, outbox, kind, image_ids=None):
    identifier = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = Path(tempfile.mkdtemp(prefix=".queue-", dir=outbox.parent))
    encrypted = directory / "bundle.age"
    try:
        progress("encrypt." + kind)
        run(["age", "-r", config["age_recipient"], "-o", str(encrypted), str(source)], timeout=3600)
        progress("split." + kind)
        parts = []
        with encrypted.open("rb") as stream:
            number = 0
            while block := stream.read(PART_SIZE):
                number += 1
                part = directory / f"part-{number:05d}.age.part"
                part.write_bytes(block)
                os.chmod(part, 0o600)
                parts.append({"name": part.name, "sha256": sha256(part), "sent": False})
        if not parts:
            raise SafeError("Encryption produced no recovery parts.")
        encrypted.unlink()
        write_json(directory / "delivery.json", {"format": 1, "id": identifier, "kind": kind,
                   "date": dt.datetime.now(ZoneInfo("Europe/Saratov")).date().isoformat(),
                   "image_ids": image_ids or [], "parts": parts})
        os.replace(directory, outbox / identifier)
        return identifier
    except Exception:
        shutil.rmtree(directory)
        raise


def deliver(config, directory):
    progress("delivery.verify")
    metadata_path = directory / "delivery.json"
    metadata = json.loads(metadata_path.read_text())
    for index, part in enumerate(metadata["parts"], 1):
        path = directory / part["name"]
        if path.parent != directory or sha256(path) != part["sha256"]:
            raise SafeError("A queued recovery part failed its checksum.")
        if not part["sent"]:
            caption = (f"Mirage {metadata['kind']} {metadata['id']} "
                       f"part {index}/{len(metadata['parts'])}; SHA256 {part['sha256']}")
            progress("delivery.part")
            part["message_id"] = send_document(config, path, caption)
            part["sent"] = True
            write_json(metadata_path, metadata)
    public = directory / "manifest.json"
    write_json(public, {k: v for k, v in metadata.items() if k != "date"})
    progress("delivery.manifest")
    send_document(config, public, f"Mirage {metadata['kind']} complete: {metadata['id']}. Keep every part and this manifest.")
    return metadata


def drain(config, backup_root):
    outbox, sent = backup_root / "outbox", private_dir(backup_root / "sent")
    for directory in sorted(outbox.iterdir()):
        metadata = deliver(config, directory)
        if metadata["kind"] == "images":
            write_json(backup_root / "images.json", {"bundle": metadata["id"], "image_ids": metadata["image_ids"]})
        else:
            write_json(backup_root / "last-success.json", {"date": metadata["date"], "bundle": metadata["id"]})
        os.replace(directory, sent / directory.name)


def prune_delivered_recovery(backup_root):
    """Keep seven days locally; never remove queued parts or image bundles."""
    sent = backup_root / "sent"
    if not sent.exists():
        return
    cutoff = dt.datetime.now(ZoneInfo("Europe/Saratov")).date() - dt.timedelta(days=7)
    for directory in sent.iterdir():
        if directory.is_symlink() or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", directory.name):
            continue
        metadata_path = directory / "delivery.json"
        metadata = json.loads(metadata_path.read_text())
        if (metadata.get("id") == directory.name and metadata.get("kind") == "recovery"
                and dt.date.fromisoformat(metadata["date"]) < cutoff
                and metadata.get("parts") and all(p.get("sent") is True for p in metadata["parts"])
                and (directory / "manifest.json").is_file()):
            shutil.rmtree(directory)


def backup(config, *, include_images=False, prepare_only=False, force=False):
    progress("validate")
    telegram_settings(config)
    if not re.fullmatch(r"age1[0-9a-z]{58}", config["age_recipient"]):
        raise SafeError("Configure an age public recipient, never an identity/private key.")
    environment = read_env(config)
    root = private_dir(Path(config["state_dir"]) / "backups")
    outbox = private_dir(root / "outbox")
    progress("lock")
    with (root / "backup.lock").open("a") as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafeError("Another recovery job is already running.") from None
        if not prepare_only:
            progress("delivery.pending")
            drain(config, root)
            progress("retention")
            prune_delivered_recovery(root)
        elif any(outbox.iterdir()):
            raise SafeError("Deliver or preserve the existing queue before preparing another bundle.")
        today = dt.datetime.now(ZoneInfo("Europe/Saratov")).date().isoformat()
        success = root / "last-success.json"
        if not force and not include_images and success.exists() and json.loads(success.read_text())["date"] == today:
            progress("skip.already-delivered")
            return
        progress("inventory.images")
        images, core = image_inventory(config, environment)
        identifiers = [record["id"] for record in images]
        image_index = root / "images.json"
        index = json.loads(image_index.read_text()) if image_index.exists() else {}
        if prepare_only or include_images or index.get("image_ids") != identifiers:
            needed = sum(record["size"] for record in images) * 2 + 256 * 1024 * 1024
            if shutil.disk_usage(root).free < needed:
                raise SafeError("Not enough free space for an image recovery bundle.")
            with tempfile.TemporaryDirectory(prefix=".images-", dir=root) as temporary:
                work = Path(temporary)
                source = work / "images.tar"
                progress("export.images")
                with source.open("wb") as output:
                    run(["docker", "image", "save", *identifiers], output=output, timeout=3600)
                source.chmod(0o600)
                bundle = queue_archive(config, source, outbox, "images", identifiers)
            if not prepare_only:
                drain(config, root)
            index = {"bundle": bundle, "image_ids": identifiers}
        if shutil.disk_usage(root).free < 256 * 1024 * 1024:
            raise SafeError("Not enough free space for a database recovery bundle.")
        with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=root) as temporary:
            work = Path(temporary)
            source = build_recovery(config, environment, images, core, index["bundle"], work)
            queue_archive(config, source, outbox, "recovery")
        if not prepare_only:
            drain(config, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--include-images", action="store_true")
    parser.add_argument("--prepare-only", action="store_true", help="Encrypt and queue; do not contact Telegram")
    parser.add_argument("--force", action="store_true", help="Create a fresh recovery copy even if one was delivered today; reuse matching image bundles")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        progress("configuration")
        backup(load_config(args.config), include_images=args.include_images,
               prepare_only=args.prepare_only, force=args.force)
    except Exception as error:
        log_failure(error)
        return 1
    progress("complete.queued" if args.prepare_only else "complete.delivered-or-already-current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
