import argparse
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xui_api


class XuiApiTests(unittest.TestCase):
    def test_build_endpoint_keeps_base_path(self):
        self.assertEqual(
            xui_api.build_endpoint("http://127.0.0.1:2096/secret", "/panel/api/inbounds/options"),
            "http://127.0.0.1:2096/secret/panel/api/inbounds/options",
        )

    def test_rewrite_vless_host_preserves_userinfo_port_and_query(self):
        link = "vless://uuid@example.local:443?security=reality&type=tcp#main"
        self.assertEqual(
            xui_api.rewrite_link_host(link, "vpn.example.com"),
            "vless://uuid@vpn.example.com:443?security=reality&type=tcp#main",
        )

    def test_rewrite_host_ignores_missing_public_host(self):
        link = "vless://uuid@example.local:443?security=reality&type=tcp#main"
        self.assertEqual(xui_api.rewrite_link_host(link, None), link)

    def test_public_host_accepts_url_or_hostport(self):
        args = argparse.Namespace(public_host=None)
        config = {"public_host": "https://vpn.example.com:8443/panel"}
        self.assertEqual(xui_api.public_host_value(args, config), "vpn.example.com")

    def test_panel_url_parts_keeps_base_path(self):
        parts = xui_api.panel_url_parts("http://127.0.0.1:31453/s-a0000000")
        self.assertEqual(parts["port"], 31453)
        self.assertEqual(parts["path"], "/s-a0000000/")

    def test_resolve_inbound_ids_defaults_to_vless_443(self):
        class FakeApi:
            def api(self, _method, _path):
                return {
                    "success": True,
                    "obj": [
                        {"id": 2, "protocol": "vless", "port": 443, "remark": "vless-reality-vision"},
                        {"id": 3, "protocol": "shadowsocks", "port": 8388, "remark": "reserve"},
                    ],
                }

        args = argparse.Namespace(inbound_id=None, inbound_remark=None, protocol=None, port=None)
        self.assertEqual(xui_api.resolve_inbound_ids(args, {}, FakeApi()), [2])

    def test_choose_users_path_falls_back_to_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_local = xui_api.DEFAULT_USERS_FILE
            previous_example = xui_api.DEFAULT_USERS_EXAMPLE_FILE
            try:
                xui_api.DEFAULT_USERS_FILE = Path(tmp) / "users.local.json"
                xui_api.DEFAULT_USERS_EXAMPLE_FILE = Path(tmp) / "users.example.json"
                self.assertEqual(xui_api.choose_users_path(None), xui_api.DEFAULT_USERS_EXAMPLE_FILE)
            finally:
                xui_api.DEFAULT_USERS_FILE = previous_local
                xui_api.DEFAULT_USERS_EXAMPLE_FILE = previous_example

    def test_build_client_payload_uses_vless_defaults(self):
        args = argparse.Namespace(
            email="main",
            sub_id="sub123",
            uuid="uuid123",
            password=None,
            auth=None,
            flow=None,
            security=None,
            total_gb=None,
            expiry_days=None,
            expiry_time_ms=None,
            reset_days=None,
            limit_ip=None,
            tg_id=None,
            group=None,
            comment=None,
        )
        payload = xui_api.build_client_payload(args, {"default_client": {"total_gb": 0}})
        self.assertEqual(payload["email"], "main")
        self.assertEqual(payload["subId"], "sub123")
        self.assertEqual(payload["id"], "uuid123")
        self.assertEqual(payload["flow"], "xtls-rprx-vision")
        self.assertEqual(payload["security"], "auto")
        self.assertEqual(payload["totalGB"], 0)
        self.assertTrue(payload["enable"])


if __name__ == "__main__":
    unittest.main()
