import argparse
import contextlib
import io
import json
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
        config = {"public_host": "https://vpn.example.net/panel"}
        self.assertEqual(xui_api.public_host_value(args, config), "vpn.example.net")

    def test_public_host_rejects_placeholders_and_localhost(self):
        self.assertIsNone(xui_api.normalize_public_host("SERVER_HOST_OR_DOMAIN"))
        self.assertIsNone(xui_api.normalize_public_host("http://127.0.0.1:2096/path"))
        self.assertEqual(xui_api.normalize_public_host("vpn.example.net:443"), "vpn.example.net")

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
                        {"id": 3, "protocol": "vless", "port": 2053, "remark": "old-vless-test"},
                    ],
                }

        args = argparse.Namespace(inbound_id=None, inbound_remark=None, protocol=None, port=None)
        self.assertEqual(xui_api.resolve_inbound_ids(args, {}, FakeApi()), [2])

    def test_build_vless_reality_payload_uses_safe_defaults(self):
        args = argparse.Namespace(
            vless_port=None,
            vless_remark=None,
            vless_listen=None,
            reality_target=None,
            reality_sni=None,
            reality_short_ids="ab,cd12",
        )
        payload = xui_api.build_vless_reality_payload(
            args,
            {},
            {"privateKey": "private", "publicKey": "public"},
        )
        self.assertEqual(payload["port"], 443)
        self.assertEqual(payload["protocol"], "vless")
        self.assertEqual(payload["settings"]["decryption"], "none")
        self.assertEqual(payload["streamSettings"]["network"], "tcp")
        self.assertEqual(payload["streamSettings"]["security"], "reality")
        reality = payload["streamSettings"]["realitySettings"]
        self.assertEqual(reality["target"], "www.amazon.com:443")
        self.assertEqual(reality["serverNames"], ["www.amazon.com"])
        self.assertEqual(reality["privateKey"], "private")
        self.assertEqual(reality["settings"]["publicKey"], "public")
        self.assertEqual(reality["shortIds"], ["ab", "cd12"])
        self.assertEqual(payload["shareAddrStrategy"], "listen")
        self.assertEqual(payload["shareAddr"], "")

    def test_build_vless_reality_payload_uses_public_host_for_share_addr(self):
        args = argparse.Namespace(
            public_host=None,
            vless_port=None,
            vless_remark=None,
            vless_listen=None,
            reality_target=None,
            reality_sni=None,
            reality_short_ids="ab",
        )
        payload = xui_api.build_vless_reality_payload(
            args,
            {"public_host": "vpn.example.net"},
            {"privateKey": "private", "publicKey": "public"},
        )
        self.assertEqual(payload["shareAddrStrategy"], "custom")
        self.assertEqual(payload["shareAddr"], "vpn.example.net")

    def test_scan_reality_target_returns_none_when_endpoint_is_missing(self):
        class FakeApi:
            def api(self, _method, _path, _data=None, expect_success=True):
                raise xui_api.ApiError("scan endpoint unavailable")

        self.assertIsNone(xui_api.scan_reality_target(FakeApi(), "www.amazon.com:443"))

    def test_reset_vless_inbound_deletes_and_recreates(self):
        class FakeApi:
            def __init__(self):
                self.deleted = []
                self.added = None

            def api(self, method, path, data=None, expect_success=True):
                if path == "/panel/api/inbounds/options":
                    if self.added:
                        return {
                            "success": True,
                            "obj": [
                                {
                                    "id": 4,
                                    "protocol": "vless",
                                    "port": 443,
                                    "remark": "vless-reality-vision",
                                }
                            ],
                        }
                    if self.deleted:
                        return {"success": True, "obj": []}
                    return {
                        "success": True,
                        "obj": [
                            {
                                "id": 2,
                                "protocol": "vless",
                                "port": 443,
                                "remark": "vless-reality-vision",
                            }
                        ],
                    }
                if method == "POST" and path == "/panel/api/inbounds/del/2":
                    self.deleted.append(2)
                    return {"success": True}
                if path == "/panel/api/server/getNewX25519Cert":
                    return {"success": True, "obj": {"privateKey": "private", "publicKey": "public"}}
                if method == "POST" and path == "/panel/api/inbounds/add":
                    self.added = data
                    return {"success": True, "obj": {"id": 4}}
                raise AssertionError(path)

        args = argparse.Namespace(
            public_host=None,
            vless_port=None,
            vless_remark=None,
            vless_listen=None,
            reality_target=None,
            reality_sni=None,
            reality_short_ids="ab",
            reset_inbound=True,
            skip_reality_scan=True,
            strict_reality_scan=False,
        )
        api = FakeApi()
        result = xui_api.ensure_vless_reality_inbound(args, {}, api)
        self.assertTrue(result["changed"])
        self.assertEqual(api.deleted, [2])
        self.assertEqual(result["deletedInbound"]["id"], 2)
        self.assertEqual(result["inbound"]["id"], 4)
        self.assertEqual(api.added["streamSettings"]["security"], "reality")

    def test_build_vpn_diagnostics_hides_sensitive_values(self):
        class FakeApi:
            def api(self, _method, path, data=None, expect_success=True):
                if path == "/panel/api/inbounds/options":
                    return {
                        "success": True,
                        "obj": [
                            {
                                "id": 4,
                                "protocol": "vless",
                                "port": 443,
                                "remark": "vless-reality-vision",
                            }
                        ],
                    }
                if path == "/panel/api/inbounds/get/4":
                    return {
                        "success": True,
                        "obj": {
                            "id": 4,
                            "protocol": "vless",
                            "port": 443,
                            "remark": "vless-reality-vision",
                            "enable": True,
                            "shareAddrStrategy": "custom",
                            "shareAddr": "vpn.example.net",
                            "settings": {
                                "clients": [
                                    {
                                        "email": "main",
                                        "id": "secret-uuid",
                                    }
                                ]
                            },
                            "streamSettings": {
                                "network": "tcp",
                                "security": "reality",
                                "realitySettings": {
                                    "target": "www.amazon.com:443",
                                    "serverNames": ["www.amazon.com"],
                                    "privateKey": "secret-private-key",
                                    "shortIds": ["secret-short-id"],
                                    "settings": {
                                        "publicKey": "secret-public-key",
                                        "fingerprint": "chrome",
                                        "spiderX": "/",
                                    },
                                },
                            },
                            "sniffing": {"enabled": True},
                        },
                    }
                raise AssertionError(path)

        args = argparse.Namespace(vless_port=None, vless_remark=None)
        diagnostics = xui_api.build_vpn_diagnostics(args, {"public_host": "vpn.example.net"}, FakeApi())
        inbound = diagnostics["inbound"]
        self.assertEqual(inbound["target"], "www.amazon.com:443")
        self.assertEqual(inbound["clients"], ["main"])
        self.assertTrue(inbound["privateKeyPresent"])
        self.assertTrue(inbound["publicKeyPresent"])
        self.assertNotIn("secret-private-key", str(diagnostics))
        self.assertNotIn("secret-public-key", str(diagnostics))
        self.assertNotIn("secret-short-id", str(diagnostics))
        self.assertNotIn("secret-uuid", str(diagnostics))
        self.assertEqual(diagnostics["warnings"], [])

    def test_ensure_client_attaches_existing_client(self):
        class FakeApi:
            def __init__(self):
                self.attached = None

            def api(self, method, path, data=None, expect_success=True):
                if path == "/panel/api/inbounds/options":
                    return {"success": True, "obj": [{"id": 2, "protocol": "vless", "port": 443}]}
                if path == "/panel/api/clients/get/main":
                    return {"success": True, "obj": {"client": {"email": "main"}, "inboundIds": []}}
                if method == "POST" and path == "/panel/api/clients/main/attach":
                    self.attached = data
                    return {"success": True}
                raise AssertionError(path)

        args = argparse.Namespace(email="main", inbound_id=None, inbound_remark=None, protocol=None, port=None)
        api = FakeApi()
        result = xui_api.ensure_client(args, {}, api)
        self.assertTrue(result["changed"])
        self.assertEqual(api.attached, {"inboundIds": [2]})

    def test_choose_users_path_falls_back_to_example(self):
        previous_local = xui_api.DEFAULT_USERS_FILE
        previous_example = xui_api.DEFAULT_USERS_EXAMPLE_FILE
        try:
            xui_api.DEFAULT_USERS_FILE = Path(".tmp") / "missing-users.local.json"
            xui_api.DEFAULT_USERS_EXAMPLE_FILE = Path(".tmp") / "users.example.json"
            self.assertEqual(xui_api.choose_users_path(None), xui_api.DEFAULT_USERS_EXAMPLE_FILE)
        finally:
            xui_api.DEFAULT_USERS_FILE = previous_local
            xui_api.DEFAULT_USERS_EXAMPLE_FILE = previous_example

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
                        {"id": 3, "protocol": "vless", "port": 2053, "remark": "old-vless-test"},
                    ],
                }

        args = argparse.Namespace(inbound_id=None, inbound_remark=None, protocol=None, port=None)
        self.assertEqual(xui_api.resolve_inbound_ids(args, {}, FakeApi()), [2])

    def test_build_vless_reality_payload_uses_safe_defaults(self):
        args = argparse.Namespace(
            vless_port=None,
            vless_remark=None,
            vless_listen=None,
            reality_target=None,
            reality_sni=None,
            reality_short_ids="ab,cd12",
        )
        payload = xui_api.build_vless_reality_payload(
            args,
            {},
            {"privateKey": "private", "publicKey": "public"},
        )
        self.assertEqual(payload["port"], 443)
        self.assertEqual(payload["protocol"], "vless")
        self.assertEqual(payload["settings"]["decryption"], "none")
        self.assertEqual(payload["streamSettings"]["network"], "tcp")
        self.assertEqual(payload["streamSettings"]["security"], "reality")
        reality = payload["streamSettings"]["realitySettings"]
        self.assertEqual(reality["target"], "www.amazon.com:443")
        self.assertEqual(reality["serverNames"], ["www.amazon.com"])
        self.assertEqual(reality["privateKey"], "private")
        self.assertEqual(reality["settings"]["publicKey"], "public")
        self.assertEqual(reality["shortIds"], ["ab", "cd12"])

    def test_ensure_client_attaches_existing_client(self):
        class FakeApi:
            def __init__(self):
                self.attached = None

            def api(self, method, path, data=None, expect_success=True):
                if path == "/panel/api/inbounds/options":
                    return {"success": True, "obj": [{"id": 2, "protocol": "vless", "port": 443}]}
                if path == "/panel/api/clients/get/main":
                    return {"success": True, "obj": {"client": {"email": "main"}, "inboundIds": []}}
                if method == "POST" and path == "/panel/api/clients/main/attach":
                    self.attached = data
                    return {"success": True}
                raise AssertionError(path)

        args = argparse.Namespace(email="main", inbound_id=None, inbound_remark=None, protocol=None, port=None)
        api = FakeApi()
        result = xui_api.ensure_client(args, {}, api)
        self.assertTrue(result["changed"])
        self.assertEqual(api.attached, {"inboundIds": [2]})

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

    def test_parse_vless_reality_link_extracts_manual_fields(self):
        link = (
            "vless://user-uuid@vpn.example.net:443?"
            "type=tcp&security=reality&flow=xtls-rprx-vision&sni=www.amazon.com"
            "&fp=chrome&pbk=public-key&sid=abcd&spx=%2F&encryption=none#main"
        )

        parsed = xui_api.parse_vless_reality_link(link)

        self.assertEqual(parsed["warnings"], [])
        self.assertEqual(parsed["manual"]["address"], "vpn.example.net")
        self.assertEqual(parsed["manual"]["port"], 443)
        self.assertEqual(parsed["manual"]["uuid"], "user-uuid")
        self.assertEqual(parsed["manual"]["network"], "tcp")
        self.assertEqual(parsed["manual"]["security"], "reality")
        self.assertEqual(parsed["manual"]["flow"], "xtls-rprx-vision")
        self.assertEqual(parsed["manual"]["sni"], "www.amazon.com")
        self.assertEqual(parsed["manual"]["fingerprint"], "chrome")
        self.assertEqual(parsed["manual"]["publicKey"], "public-key")
        self.assertEqual(parsed["manual"]["shortId"], "abcd")
        self.assertEqual(parsed["manual"]["spiderX"], "/")
        self.assertEqual(parsed["manual"]["remark"], "main")

    def test_parse_vless_reality_link_warns_on_missing_reality_fields(self):
        link = "vless://user-uuid@vpn.example.net:443?type=tcp&security=reality#main"

        parsed = xui_api.parse_vless_reality_link(link)

        self.assertIn("flow", parsed["warnings"][0])
        self.assertIn("pbk/publicKey", parsed["warnings"][0])
        self.assertIn("sid/shortId", parsed["warnings"][0])
        self.assertIn("fp/fingerprint", parsed["warnings"][0])

    def test_build_subscription_bundle_reads_links_without_mutating_api(self):
        link = (
            "vless://user-uuid@panel.local:443?"
            "type=tcp&security=reality&flow=xtls-rprx-vision&sni=www.amazon.com"
            "&fp=chrome&pbk=public-key&sid=abcd&spx=%2F#main"
        )

        class FakeApi:
            def __init__(self):
                self.calls = []

            def api(self, method, path, data=None, expect_success=True):
                self.calls.append((method, path, data))
                if method != "GET":
                    raise AssertionError("subscriptions must not mutate API state")
                if path == "/panel/api/clients/links/main":
                    return {"success": True, "obj": [link]}
                if path == "/panel/api/clients/get/main":
                    return {"success": True, "obj": {"client": {"subId": "sub123"}}}
                if path == "/panel/api/clients/subLinks/sub123":
                    return {"success": True, "obj": [link]}
                raise AssertionError(path)

        api = FakeApi()
        bundle = xui_api.build_subscription_bundle(api, "main", "vpn.example.net")

        self.assertEqual(bundle["email"], "main")
        self.assertEqual(bundle["raw"]["subId"], "sub123")
        self.assertIn("vpn.example.net", bundle["hiddify"]["directLinks"][0])
        self.assertEqual(bundle["v2raytun"]["manual"]["address"], "vpn.example.net")
        self.assertEqual(bundle["diagnostics"]["warnings"], [])
        self.assertTrue(all(method == "GET" for method, _path, _data in api.calls))

    def test_build_subscription_bundle_keeps_direct_link_when_sub_links_fail(self):
        link = (
            "vless://user-uuid@panel.local:443?"
            "type=tcp&security=reality&flow=xtls-rprx-vision&sni=www.amazon.com"
            "&fp=chrome&pbk=public-key&sid=abcd&spx=%2F#main"
        )

        class FakeApi:
            def api(self, method, path, data=None, expect_success=True):
                if path == "/panel/api/clients/links/main":
                    return {"success": True, "obj": [link]}
                if path == "/panel/api/clients/get/main":
                    return {"success": True, "obj": {"client": {"subId": "sub123"}}}
                if path == "/panel/api/clients/subLinks/sub123":
                    raise xui_api.ApiError(
                        "GET http://127.0.0.1:31453/secret-web-path failed "
                        "token=secret-value password=panel-password"
                    )
                raise AssertionError(path)

        bundle = xui_api.build_subscription_bundle(FakeApi(), "main", "vpn.example.net")

        self.assertEqual(bundle["hiddify"]["directLinks"][0].split("@", 1)[1].split(":", 1)[0], "vpn.example.net")
        self.assertEqual(bundle["hiddify"]["subscriptionDerivedLinks"], [])
        self.assertEqual(
            bundle["diagnostics"]["warnings"][0],
            "Subscription-derived links are not available from 3x-ui.",
        )
        self.assertNotIn("127.0.0.1:31453", json.dumps(bundle))
        self.assertNotIn("secret-web-path", json.dumps(bundle))
        self.assertNotIn("secret-value", json.dumps(bundle))
        self.assertNotIn("panel-password", json.dumps(bundle))

    def test_print_subscription_bundle_contains_app_sections(self):
        bundle = {
            "email": "main",
            "hiddify": {"directLinks": ["vless://example"], "subscriptionDerivedLinks": []},
            "v2raytun": {"manual": {"address": "vpn.example.net"}, "sourceLink": "vless://example"},
            "raw": {"subId": "sub123", "directLinks": ["vless://example"], "subscriptionDerivedLinks": []},
            "diagnostics": {"warnings": ["Subscription-derived links are not available from 3x-ui."]},
        }

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            xui_api.print_subscription_bundle(bundle, "all")

        text = output.getvalue()
        self.assertIn("Hiddify", text)
        self.assertIn("V2RayTun manual fields", text)
        self.assertIn("Raw links", text)
        self.assertIn("Diagnostics", text)


if __name__ == "__main__":
    unittest.main()
