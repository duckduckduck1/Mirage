#!/usr/bin/env python3
"""Root helper for applying queued Mirage 3x-ui restore jobs."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any


BACKUP_RE = re.compile(r"^x-ui-\d{8}-\d{6}(?:-\d{3})?\.db$")
RESTORE_JOB_RE = re.compile(r"^restore-\d{8}-\d{6}-[a-f0-9]{12}$")


class RestoreError(RuntimeError):
    pass


def env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).resolve()


def env_int(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    return int(value) if value else None


def path_inside(root: Path, name: str, pattern: re.Pattern[str]) -> Path:
    if not pattern.fullmatch(name):
        raise RestoreError(f"invalid name: {name}")
    path = (root / name).resolve()
    if root not in path.parents:
        raise RestoreError(f"path escapes root: {name}")
    return path


def validate_sqlite(path: Path) -> None:
    if path.read_bytes()[:16] != b"SQLite format 3\x00":
        raise RestoreError("backup is not a SQLite database")
    try:
        connection = sqlite3.connect(str(path))
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError(f"SQLite integrity check failed: {exc}") from exc
    if not row or str(row[0]).lower() != "ok":
        raise RestoreError("SQLite integrity check failed")


def write_json(path: Path, payload: dict[str, Any], gid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if gid is not None:
        os.chown(temp_path, 0, gid)
        temp_path.chmod(0o640)
    else:
        temp_path.chmod(0o644)
    temp_path.replace(path)


def status_payload(job: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    now = int(time.time())
    payload = {
        "jobId": job["jobId"],
        "status": status,
        "backupName": job["backupName"],
        "backupSize": job.get("backupSize"),
        "backupMtime": job.get("backupMtime"),
        "createdAt": job.get("createdAt") or now,
        "updatedAt": now,
    }
    payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def allocate_pre_restore_backup(backup_dir: Path) -> Path:
    base_name = f"x-ui-{time.strftime('%Y%m%d-%H%M%S')}"
    path = backup_dir / f"{base_name}.db"
    for index in range(1000):
        if not path.exists():
            return path
        path = backup_dir / f"{base_name}-{index:03d}.db"
    raise RestoreError("could not allocate a pre-restore backup name")


def chown_optional(path: Path, uid: int | None, gid: int | None) -> None:
    if uid is not None or gid is not None:
        os.chown(path, -1 if uid is None else uid, -1 if gid is None else gid)


def load_job(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RestoreError("restore job must be a JSON object")
    if payload.get("jobId") != path.stem or not RESTORE_JOB_RE.fullmatch(path.stem):
        raise RestoreError("restore job id does not match file name")
    backup_name = str(payload.get("backupName") or "")
    if not BACKUP_RE.fullmatch(backup_name):
        raise RestoreError("restore job has invalid backupName")
    return payload


def process_job(path: Path, config: dict[str, Any]) -> None:
    backup_dir = config["backup_dir"]
    status_dir = config["status_dir"]
    staging_dir = config["staging_dir"]
    live_db = config["live_db"]
    admin_uid = config["admin_uid"]
    admin_gid = config["admin_gid"]
    status_gid = config["status_gid"]

    job = load_job(path)
    status_path = status_dir / f"{job['jobId']}.json"
    write_json(status_path, status_payload(job, "running"), gid=status_gid)

    staged = staging_dir / f"{job['jobId']}.db"
    pre_restore_backup: Path | None = None
    live_replaced = False
    stopped = False
    old_stat = None
    try:
        backup_path = path_inside(backup_dir, job["backupName"], BACKUP_RE)
        if not backup_path.is_file():
            raise RestoreError("backup file was not found")

        staging_dir.mkdir(parents=True, exist_ok=True)
        staging_dir.chmod(0o700)
        shutil.copy2(backup_path, staged)
        staged.chmod(0o600)
        validate_sqlite(staged)

        old_stat = live_db.stat() if live_db.exists() else None
        run(["systemctl", "stop", "x-ui"])
        stopped = True

        if live_db.exists():
            pre_restore_backup = allocate_pre_restore_backup(backup_dir)
            shutil.copy2(live_db, pre_restore_backup)
            pre_restore_backup.chmod(0o600)
            chown_optional(pre_restore_backup, admin_uid, admin_gid)

        live_db.parent.mkdir(parents=True, exist_ok=True)
        temp_live = live_db.with_name(f".{live_db.name}.{job['jobId']}.tmp")
        shutil.copy2(staged, temp_live)
        if old_stat:
            os.chown(temp_live, old_stat.st_uid, old_stat.st_gid)
            temp_live.chmod(old_stat.st_mode & 0o777)
        else:
            temp_live.chmod(0o600)
        temp_live.replace(live_db)
        live_replaced = True

        run(["systemctl", "start", "x-ui"])
        stopped = False
        run(["systemctl", "is-active", "--quiet", "x-ui"])
        write_json(
            status_path,
            status_payload(
                job,
                "success",
                preRestoreBackup=pre_restore_backup.name if pre_restore_backup else None,
            ),
            gid=status_gid,
        )
    except Exception as exc:  # noqa: BLE001 - helper must record failures.
        rollback = False
        rollback_error = None
        if live_replaced and pre_restore_backup and pre_restore_backup.exists():
            try:
                run(["systemctl", "stop", "x-ui"])
                temp_live = live_db.with_name(f".{live_db.name}.{job['jobId']}.rollback")
                shutil.copy2(pre_restore_backup, temp_live)
                if old_stat:
                    os.chown(temp_live, old_stat.st_uid, old_stat.st_gid)
                    temp_live.chmod(old_stat.st_mode & 0o777)
                temp_live.replace(live_db)
                run(["systemctl", "start", "x-ui"])
                rollback = True
                stopped = False
            except Exception as rollback_exc:  # noqa: BLE001
                rollback_error = str(rollback_exc)
        elif stopped:
            try:
                run(["systemctl", "start", "x-ui"])
                stopped = False
            except Exception as start_exc:  # noqa: BLE001
                rollback_error = str(start_exc)

        write_json(
            status_path,
            status_payload(
                job,
                "failed",
                error=str(exc),
                rollback=rollback,
                rollbackError=rollback_error,
                preRestoreBackup=pre_restore_backup.name if pre_restore_backup else None,
            ),
            gid=status_gid,
        )
    finally:
        staged.unlink(missing_ok=True)
        path.unlink(missing_ok=True)


def config_from_env() -> dict[str, Any]:
    return {
        "backup_dir": env_path("MIRAGE_ADMIN_BACKUP_DIR_HOST", "/home/mirage/mirage-vpn/backups"),
        "status_dir": env_path("MIRAGE_ADMIN_RESTORE_STATUS_DIR_HOST", "/home/mirage/mirage-vpn/restore-status"),
        "staging_dir": env_path("MIRAGE_ADMIN_RESTORE_STAGING_DIR", "/var/lib/mirage/restore-staging"),
        "request_dir": env_path("MIRAGE_ADMIN_RESTORE_REQUEST_DIR_HOST", "/home/mirage/mirage-vpn/restore-requests"),
        "live_db": env_path("MIRAGE_ADMIN_RESTORE_LIVE_DB", "/etc/x-ui/x-ui.db"),
        "admin_uid": env_int("MIRAGE_ADMIN_UID"),
        "admin_gid": env_int("MIRAGE_ADMIN_GID"),
        "status_gid": env_int("MIRAGE_ADMIN_GID"),
    }


def main() -> int:
    config = config_from_env()
    request_dir = config["request_dir"]
    request_dir.mkdir(parents=True, exist_ok=True)
    jobs = sorted(request_dir.glob("restore-*.json"), key=lambda item: item.stat().st_mtime)
    for job_path in jobs:
        try:
            process_job(job_path, config)
        except Exception as exc:  # noqa: BLE001 - malformed jobs must not block the queue.
            if RESTORE_JOB_RE.fullmatch(job_path.stem):
                now = int(time.time())
                write_json(
                    config["status_dir"] / f"{job_path.stem}.json",
                    {
                        "jobId": job_path.stem,
                        "status": "failed",
                        "backupName": "unknown",
                        "createdAt": now,
                        "updatedAt": now,
                        "error": str(exc),
                    },
                    gid=config["status_gid"],
                )
            job_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
