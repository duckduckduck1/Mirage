import argparse
import sys
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
