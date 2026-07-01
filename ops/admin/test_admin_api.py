import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import admin_api


class FakeApi:
    def __init__(self):
        self.downloaded = b"sqlite-backup"
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


class AdminApiTests(unittest.TestCase):
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

    def test_http_handler_serves_static_and_requires_token_for_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(
                FakeApi(),
                {"public_host": "vpn.example.net"},
                backup_dir=Path(tmp),
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
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
