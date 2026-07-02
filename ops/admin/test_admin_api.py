import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib import error, request
from urllib.parse import quote as parse_quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import admin_api
import restore_helper

REPO_ROOT = Path(__file__).resolve().parents[2]


def sqlite_backup_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "x-ui.db"
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO settings VALUES ('version', 'test')")
            connection.commit()
        finally:
            connection.close()
        return path.read_bytes()


class FakeApi:
    def __init__(self):
        self.downloaded = sqlite_backup_bytes()
        self.calls = []

    def api(self, method, path, data=None, expect_success=True):
        self.calls.append((method, path, data))
        if path == "/panel/api/inbounds/options":
            return {
                "success": True,
                "obj": [{"id": 5, "protocol": "vless", "port": 443, "remark": "vless-reality-vision"}],
            }
        if path == "/panel/api/inbounds/get/5":
            return {
                "success": True,
                "obj": {
                    "id": 5,
                    "protocol": "vless",
                    "port": 443,
                    "remark": "vless-reality-vision",
                    "settings": {
                        "clients": [
                            {
                                "email": "main",
                                "enable": True,
                                "flow": "xtls-rprx-vision",
                                "totalGB": 0,
                                "expiryTime": 0,
                                "limitIp": 0,
                                "subId": "sub-main",
                                "group": "default",
                                "comment": "owner",
                                "id": "secret-uuid",
                            }
                        ]
                    },
                },
            }
        if path == "/panel/api/server/status":
            return {"success": True, "obj": {"xray": {"state": "running"}}}
        if path == "/panel/api/clients/links/main":
            return {
                "success": True,
                "obj": [
                    "vless://uuid@panel.local:443?"
                    "type=tcp&security=reality&flow=xtls-rprx-vision&sni=www.amazon.com"
                    "&fp=chrome&pbk=public-key&sid=abcd&spx=%2F#main"
                ],
            }
        if path == "/panel/api/clients/get/main":
            return {"success": True, "obj": {"client": {"subId": "sub-main"}}}
        if path == "/panel/api/clients/subLinks/sub-main":
            return {"success": True, "obj": []}
        if path == "/panel/api/clients/bulkDisable":
            return {"success": True}
        raise AssertionError(path)

    def download(self, path):
        if path != "/panel/api/server/getDb":
            raise AssertionError(path)
        return self.downloaded


class FakeNotifier:
    def __init__(self):
        self.messages = []

    def send(self, text):
        self.messages.append(text)


class FailingNotifier:
    def send(self, _text):
        raise RuntimeError("telegram is unavailable")


class FakeAlertService:
    def __init__(self, statuses, backup_dir):
        self.statuses = list(statuses)
        self.backup_dir = backup_dir

    def health(self):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        ok = status == "ok"
        check = {"ok": ok}
        if not ok:
            check["error"] = "x-ui is unavailable"
        return {"status": status, "checks": {"xuiApi": check}}


class AdminApiTests(unittest.TestCase):
    def test_admin_container_uses_non_root_user(self):
        dockerfile = (REPO_ROOT / "ops/admin/Dockerfile").read_text(encoding="utf-8")
        compose = (REPO_ROOT / "ops/admin/compose.yml").read_text(encoding="utf-8")

        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn('user: "${MIRAGE_ADMIN_UID:-10001}:${MIRAGE_ADMIN_GID:-10001}"', compose)
        self.assertIn("MIRAGE_ADMIN_RESTORE_REQUEST_DIR", compose)
        self.assertIn("MIRAGE_ADMIN_RESTORE_STATUS_DIR", compose)

    def test_deploy_writes_admin_uid_gid(self):
        deploy = (REPO_ROOT / "ops/vpn/deploy.sh").read_text(encoding="utf-8")

        self.assertIn("MIRAGE_ADMIN_UID=${admin_uid}", deploy)
        self.assertIn("MIRAGE_ADMIN_GID=${admin_gid}", deploy)
        self.assertIn('ADMIN_RUNTIME_UID="${MIRAGE_ADMIN_UID:-}"', deploy)
        self.assertNotIn('ADMIN_RUNTIME_UID="${MIRAGE_ADMIN_UID:-$(env_file_value', deploy)
        self.assertIn('backup_owner_uid="\\${MIRAGE_ADMIN_UID:-$ADMIN_RUNTIME_UID}"', deploy)
        self.assertIn('chown -R "$ADMIN_RUNTIME_UID:$ADMIN_RUNTIME_GID" "$OUTPUT_DIR"', deploy)
        self.assertIn("install_restore_helper", deploy)
        self.assertIn("mirage-admin-restore.path", deploy)

    def test_validate_profile_name_rejects_path_like_values(self):
        with self.assertRaises(admin_api.AdminError):
            admin_api.validate_profile_name("../secret")

    def test_loopback_guard_rejects_public_bind_by_default(self):
        self.assertTrue(admin_api.is_loopback_host("127.0.0.1"))
        self.assertTrue(admin_api.is_loopback_host("localhost"))
        self.assertFalse(admin_api.is_loopback_host("0.0.0.0"))

    def test_client_namespace_ignores_advanced_secret_fields(self):
        args = admin_api.client_namespace(
            "main",
            {
                "comment": "ok",
                "uuid": "forced-uuid",
                "subId": "forced-sub",
                "totalGb": 999,
                "group": "forced",
            },
        )

        self.assertEqual(args.email, "main")
        self.assertEqual(args.comment, "ok")
        self.assertIsNone(args.uuid)
        self.assertIsNone(args.sub_id)
        self.assertIsNone(args.total_gb)
        self.assertIsNone(args.group)

    def test_list_profiles_hides_client_uuid(self):
        service = admin_api.AdminService(FakeApi(), {"public_host": "vpn.example.net"})

        payload = service.list_profiles()

        self.assertEqual(payload["profiles"][0]["email"], "main")
        self.assertNotIn("secret-uuid", json.dumps(payload))
        self.assertNotIn("sub-main", json.dumps(payload))

    def test_profile_bundle_rewrites_public_host(self):
        service = admin_api.AdminService(FakeApi(), {"public_host": "vpn.example.net"})

        payload = service.profile_bundle("main")

        self.assertIn("vpn.example.net", payload["hiddify"]["directLinks"][0])
        self.assertEqual(payload["v2raytun"]["manual"]["address"], "vpn.example.net")

    def test_overview_uses_sanitized_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(
                FakeApi(),
                {"public_host": "vpn.example.net"},
                backup_dir=Path(tmp),
                restore_request_dir=Path(tmp) / "restore-requests",
                restore_status_dir=Path(tmp) / "restore-status",
            )

            payload = service.overview()

        self.assertEqual(payload["publicHost"], "vpn.example.net")
        self.assertEqual(payload["profilesCount"], 1)
        self.assertNotIn("secret-uuid", json.dumps(payload))

    def test_disable_profile_uses_bulk_disable(self):
        api = FakeApi()
        service = admin_api.AdminService(api)

        payload = service.set_profile_enabled("main", False)

        self.assertEqual(payload, {"email": "main", "enabled": False})
        self.assertIn(("POST", "/panel/api/clients/bulkDisable", {"emails": ["main"]}), api.calls)

    def test_backup_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with self.assertRaises(admin_api.AdminError):
                service.backup_path("../x-ui-20260101-000000.db")

    def test_static_path_rejects_traversal(self):
        with self.assertRaises(admin_api.AdminError):
            admin_api.static_path_for_request("/../admin_api.py")

    def test_create_and_list_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            created = service.create_backup()
            listed = service.list_backups()

        self.assertTrue(created["name"].startswith("x-ui-"))
        self.assertEqual(listed["backups"][0]["name"], created["name"])

    def test_import_backup_accepts_valid_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            imported = service.import_backup(sqlite_backup_bytes())
            stored = Path(tmp) / imported["name"]
            stored_exists = stored.is_file()

        self.assertTrue(imported["name"].startswith("x-ui-"))
        self.assertTrue(imported["name"].endswith(".db"))
        self.assertGreater(imported["size"], 0)
        self.assertTrue(stored_exists)

    def test_import_backup_rejects_invalid_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with self.assertRaises(admin_api.AdminError) as ctx:
                service.import_backup(b"not a sqlite database")
            files_after_import = list(Path(tmp).glob("*"))

        self.assertEqual(ctx.exception.status, admin_api.HTTPStatus.BAD_REQUEST)
        self.assertEqual(files_after_import, [])

    def test_delete_backup_removes_one_valid_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x-ui-20260101-000000.db"
            path.write_bytes(b"backup")
            keep = Path(tmp) / "x-ui-20260102-000000.db"
            keep.write_bytes(b"backup")
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            payload = service.delete_backup(path.name, path.name)
            exists_after_delete = path.exists()

        self.assertEqual(payload["deleted"]["name"], "x-ui-20260101-000000.db")
        self.assertFalse(exists_after_delete)

    def test_delete_backup_requires_matching_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x-ui-20260101-000000.db"
            path.write_bytes(b"backup")
            keep = Path(tmp) / "x-ui-20260102-000000.db"
            keep.write_bytes(b"backup")
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            with self.assertRaises(admin_api.AdminError):
                service.delete_backup(path.name, "wrong-name.db")

    def test_delete_backup_rejects_last_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x-ui-20260101-000000.db"
            path.write_bytes(b"backup")
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            with self.assertRaises(admin_api.AdminError):
                service.delete_backup(path.name, path.name)

    def test_delete_backup_missing_file_returns_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with self.assertRaises(admin_api.AdminError) as ctx:
                service.delete_backup("x-ui-20260101-000000.db", "x-ui-20260101-000000.db")
        self.assertEqual(ctx.exception.status, admin_api.HTTPStatus.NOT_FOUND)

    def test_queue_restore_creates_safe_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_dir = root / "backups"
            request_dir = root / "restore-requests"
            status_dir = root / "restore-status"
            backup_dir.mkdir()
            backup = backup_dir / "x-ui-20260101-000000.db"
            backup.write_bytes(sqlite_backup_bytes())
            service = admin_api.AdminService(
                FakeApi(),
                backup_dir=backup_dir,
                restore_request_dir=request_dir,
                restore_status_dir=status_dir,
            )

            payload = service.queue_restore(
                backup.name,
                {
                    "confirm": "restore",
                    "confirmName": backup.name,
                    "ackDowntime": True,
                    "token": "secret-token",
                    "uuid": "secret-uuid",
                },
            )
            request_files = list(request_dir.glob("restore-*.json"))
            stored = json.loads(request_files[0].read_text(encoding="utf-8"))

        serialized = json.dumps(stored)
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(len(request_files), 1)
        self.assertEqual(stored["backupName"], backup.name)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("secret-uuid", serialized)
        self.assertNotIn(str(backup_dir), serialized)

    def test_queue_restore_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "x-ui-20260101-000000.db"
            backup.write_bytes(sqlite_backup_bytes())
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            with self.assertRaises(admin_api.AdminError) as ctx:
                service.queue_restore(backup.name, {"confirm": "restore", "confirmName": "wrong.db"})

        self.assertEqual(ctx.exception.status, admin_api.HTTPStatus.BAD_REQUEST)

    def test_queue_restore_rejects_path_like_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with self.assertRaises(admin_api.AdminError):
                service.queue_restore("../x-ui-20260101-000000.db", {"confirm": "restore", "ackDowntime": True})

    def test_restore_jobs_merges_request_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_dir = root / "restore-requests"
            status_dir = root / "restore-status"
            request_dir.mkdir()
            status_dir.mkdir()
            queued = {
                "jobId": "restore-20260101-000000-abcdef123456",
                "status": "queued",
                "backupName": "x-ui-20260101-000000.db",
                "createdAt": 1,
                "updatedAt": 1,
            }
            done = {
                "jobId": "restore-20260102-000000-abcdef123456",
                "status": "success",
                "backupName": "x-ui-20260102-000000.db",
                "createdAt": 2,
                "updatedAt": 3,
            }
            (request_dir / f"{queued['jobId']}.json").write_text(json.dumps(queued), encoding="utf-8")
            (status_dir / f"{done['jobId']}.json").write_text(json.dumps(done), encoding="utf-8")
            service = admin_api.AdminService(
                FakeApi(),
                backup_dir=root / "backups",
                restore_request_dir=request_dir,
                restore_status_dir=status_dir,
            )

            payload = service.restore_jobs()

        self.assertEqual([job["jobId"] for job in payload["jobs"]], [done["jobId"], queued["jobId"]])

    def test_restore_helper_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(restore_helper.RestoreError):
                restore_helper.path_inside(
                    Path(tmp).resolve(),
                    "../x-ui-20260101-000000.db",
                    restore_helper.BACKUP_RE,
                )

    def test_restore_helper_marks_malformed_job_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_dir = root / "requests"
            status_dir = root / "status"
            request_dir.mkdir()
            job_id = "restore-20260101-000000-abcdef123456"
            request_file = request_dir / f"{job_id}.json"
            request_file.write_text("{bad json", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "MIRAGE_ADMIN_BACKUP_DIR_HOST": str(root / "backups"),
                    "MIRAGE_ADMIN_RESTORE_REQUEST_DIR_HOST": str(request_dir),
                    "MIRAGE_ADMIN_RESTORE_STATUS_DIR_HOST": str(status_dir),
                    "MIRAGE_ADMIN_RESTORE_STAGING_DIR": str(root / "staging"),
                    "MIRAGE_ADMIN_RESTORE_LIVE_DB": str(root / "x-ui.db"),
                },
                clear=True,
            ):
                restore_helper.main()
            status = json.loads((status_dir / f"{job_id}.json").read_text(encoding="utf-8"))
            request_exists = request_file.exists()

        self.assertFalse(request_exists)
        self.assertEqual(status["status"], "failed")

    def test_prune_backups_keeps_minimum_recent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = time.time()
            for index in range(5):
                path = root / f"x-ui-2026010{index + 1}-000000.db"
                path.write_bytes(b"backup")
                age_days = index
                if index >= 2:
                    age_days = 30 + index
                mtime = now - age_days * 24 * 3600
                os.utime(path, (mtime, mtime))
            service = admin_api.AdminService(FakeApi(), backup_dir=root)

            payload = service.prune_backups({"retentionDays": 14, "keepMin": 2, "dryRun": False, "confirm": "prune"})
            remaining = sorted(path.name for path in root.glob("x-ui-*.db"))

        self.assertEqual(len(payload["pruned"]), 3)
        self.assertEqual(payload["remaining"], 2)
        self.assertEqual(len(remaining), 2)

    def test_prune_backups_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            newest = root / "x-ui-20260102-000000.db"
            newest.write_bytes(b"backup")
            path = root / "x-ui-20260101-000000.db"
            path.write_bytes(b"backup")
            old = time.time() - 40 * 24 * 3600
            os.utime(newest, (time.time(), time.time()))
            os.utime(path, (old, old))
            service = admin_api.AdminService(FakeApi(), backup_dir=root)

            payload = service.prune_backups({"retentionDays": 14, "keepMin": 1, "dryRun": True})
            exists_after_dry_run = path.exists()

        self.assertTrue(exists_after_dry_run)
        self.assertEqual(payload["pruned"][0]["name"], "x-ui-20260101-000000.db")
        self.assertEqual(payload["remaining"], 2)

    def test_prune_backups_defaults_to_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            newest = root / "x-ui-20260102-000000.db"
            newest.write_bytes(b"backup")
            path = root / "x-ui-20260101-000000.db"
            path.write_bytes(b"backup")
            old = time.time() - 40 * 24 * 3600
            os.utime(path, (old, old))
            service = admin_api.AdminService(FakeApi(), backup_dir=root)

            payload = service.prune_backups({"retentionDays": 14, "keepMin": 1})
            exists_after_prune = path.exists()

        self.assertTrue(payload["dryRun"])
        self.assertTrue(exists_after_prune)

    def test_prune_backups_requires_confirmation_for_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with self.assertRaises(admin_api.AdminError):
                service.prune_backups({"retentionDays": 14, "keepMin": 1, "dryRun": False})

    def test_prune_backups_rejects_invalid_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with self.assertRaises(admin_api.AdminError):
                service.prune_backups({"retentionDays": "bad", "keepMin": 1})
            with self.assertRaises(admin_api.AdminError):
                service.prune_backups({"retentionDays": 0, "keepMin": 1})

    def test_alert_status_hides_telegram_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "x-ui-20260101-000000.db"
            backup.write_bytes(b"backup")
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))
            with patch.dict(
                os.environ,
                {
                    "MIRAGE_ALERTS_ENABLED": "true",
                    "MIRAGE_ALERT_TELEGRAM_BOT_TOKEN": "test-bot-token",
                    "MIRAGE_ALERT_TELEGRAM_CHAT_ID": "test-chat-id",
                    "MIRAGE_ALERT_STATE_FILE": str(Path(tmp) / "state.json"),
                },
                clear=True,
            ):
                payload = service.alert_status()

        serialized = json.dumps(payload)
        self.assertTrue(payload["enabled"])
        self.assertTrue(payload["configured"])
        self.assertNotIn("test-bot-token", serialized)
        self.assertNotIn("test-chat-id", serialized)

    def test_send_test_alert_uses_configured_notifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            notifier = FakeNotifier()
            service = admin_api.AdminService(
                FakeApi(),
                backup_dir=Path(tmp),
                notifier_factory=lambda _token, _chat: notifier,
            )
            with patch.dict(
                os.environ,
                {
                    "MIRAGE_ALERTS_ENABLED": "true",
                    "MIRAGE_ALERT_TELEGRAM_BOT_TOKEN": "test-bot-token",
                    "MIRAGE_ALERT_TELEGRAM_CHAT_ID": "test-chat-id",
                },
                clear=True,
            ):
                payload = service.send_test_alert()

        self.assertEqual(payload, {"sent": True})
        self.assertEqual(notifier.messages, ["Mirage VPN: тестовое уведомление"])

    def test_http_handler_serves_static_and_requires_token_for_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(
                FakeApi(),
                {"public_host": "vpn.example.net"},
                backup_dir=Path(tmp),
                restore_request_dir=Path(tmp) / "restore-requests",
                restore_status_dir=Path(tmp) / "restore-status",
            )
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                admin_api.make_handler(service, "test-token"),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with request.urlopen(f"{base_url}/", timeout=5) as response:
                    self.assertIn("text/html", response.headers["Content-Type"])
                    self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                with request.urlopen(f"{base_url}/app.js", timeout=5) as response:
                    self.assertIn("application/javascript", response.headers["Content-Type"])
                with request.urlopen(f"{base_url}/styles.css", timeout=5) as response:
                    self.assertIn("text/css", response.headers["Content-Type"])

                with self.assertRaises(error.HTTPError) as ctx:
                    request.urlopen(f"{base_url}/api/v0/profiles", timeout=5)
                self.assertEqual(ctx.exception.code, 401)

                req = request.Request(
                    f"{base_url}/api/v0/profiles",
                    headers={"Authorization": "Bearer test-token"},
                )
                with request.urlopen(req, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["profiles"][0]["email"], "main")

                backup = Path(tmp) / "x-ui-20260101-000000.db"
                backup.write_bytes(b"backup")
                keep = Path(tmp) / "x-ui-20260102-000000.db"
                keep.write_bytes(b"backup")
                encoded = parse_quote(backup.name)
                delete_req = request.Request(
                    f"{base_url}/api/v0/backups/{encoded}?confirmName={encoded}",
                    headers={"Authorization": "Bearer test-token"},
                    method="DELETE",
                )
                with request.urlopen(delete_req, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["deleted"]["name"], backup.name)
                self.assertFalse(backup.exists())

                import_req = request.Request(
                    f"{base_url}/api/v0/backups/import",
                    data=sqlite_backup_bytes(),
                    headers={
                        "Authorization": "Bearer test-token",
                        "Content-Type": "application/octet-stream",
                    },
                    method="POST",
                )
                with request.urlopen(import_req, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue((Path(tmp) / payload["name"]).is_file())

                restore_body = json.dumps(
                    {"confirm": "restore", "confirmName": payload["name"], "ackDowntime": True}
                ).encode("utf-8")
                restore_req = request.Request(
                    f"{base_url}/api/v0/backups/{parse_quote(payload['name'])}/restore",
                    data=restore_body,
                    headers={
                        "Authorization": "Bearer test-token",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with request.urlopen(restore_req, timeout=5) as response:
                    self.assertEqual(response.status, 202)
                    restore_payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(restore_payload["status"], "queued")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_backup_freshness_check_uses_latest_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x-ui-20260101-000000.db"
            path.write_bytes(b"backup")
            now = time.time()
            os.utime(path, (now, now))

            payload = admin_api.backup_freshness_check(Path(tmp), 36)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["latest"], "x-ui-20260101-000000.db")

    def test_alert_tick_notifies_on_degradation_and_recovery_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = FakeAlertService(["degraded", "degraded", "ok"], Path(tmp))
            notifier = FakeNotifier()
            state_file = Path(tmp) / "state.json"

            first = admin_api.alert_tick(service, notifier, state_file, max_backup_age_hours=0)
            second = admin_api.alert_tick(service, notifier, state_file, max_backup_age_hours=0)
            third = admin_api.alert_tick(service, notifier, state_file, max_backup_age_hours=0)

        self.assertEqual(first, 2)
        self.assertEqual(second, 2)
        self.assertEqual(third, 0)
        self.assertEqual(len(notifier.messages), 2)
        self.assertIn("деградация", notifier.messages[0])
        self.assertIn("восстановлен", notifier.messages[1])

    def test_alert_tick_does_not_notify_on_initial_healthy_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = FakeAlertService(["ok"], Path(tmp))
            notifier = FakeNotifier()

            code = admin_api.alert_tick(
                service,
                notifier,
                Path(tmp) / "state.json",
                max_backup_age_hours=0,
            )

        self.assertEqual(code, 0)
        self.assertEqual(notifier.messages, [])

    def test_alert_monitor_handles_notifier_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = FakeAlertService(["degraded"], Path(tmp))

            code = admin_api.run_alert_monitor(
                service,
                FailingNotifier(),
                Path(tmp) / "state.json",
                interval_seconds=5,
                max_backup_age_hours=0,
                min_disk_free_percent=0,
                once=True,
            )

        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
