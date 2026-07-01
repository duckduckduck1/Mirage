import json
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_list_profiles_hides_client_uuid(self):
        service = admin_api.AdminService(FakeApi(), {"public_host": "vpn.example.net"})

        payload = service.list_profiles()

        self.assertEqual(payload["profiles"][0]["email"], "main")
        self.assertNotIn("secret-uuid", json.dumps(payload))

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

    def test_create_and_list_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = admin_api.AdminService(FakeApi(), backup_dir=Path(tmp))

            created = service.create_backup()
            listed = service.list_backups()

            self.assertTrue(created["name"].startswith("x-ui-"))
            self.assertEqual(listed["backups"][0]["name"], created["name"])


if __name__ == "__main__":
    unittest.main()
