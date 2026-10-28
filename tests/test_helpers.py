"""Local failure-path checks; no Docker daemon, VPS or real Telegram requests."""

import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infra"))
import backup
import host
import provision
import tls
import status


def fixture_token():
    return str(123456789) + ":" + "z" * 32


class PrivateFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mirage-helper-test-")
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.env = self.root / "compose.env"
        self.env.write_text((ROOT / ".env.example").read_text()
                            .replace("/var/lib/mirage-test/db", str(self.state / "db"))
                            .replace("/var/lib/mirage-test/tls", str(self.state / "tls")))
        self.env.chmod(0o600)
        self.config = {
            "project_dir": str(ROOT), "env_file": str(self.env), "state_dir": str(self.state),
            "acme_dir": str(self.root / "acme"), "age_recipient": "CHANGE_ME_AGE_RECIPIENT",
            "telegram_token": fixture_token(), "telegram_chat_id": "123456789",
            "public_host": "vpn.example.com", "ca_file": None,
        }
        self.config_path = self.root / "host.json"
        host.write_json(self.config_path, self.config)
        self.config = host.load_config(self.config_path)

    def tearDown(self):
        self.temporary.cleanup()


class ConfigurationTests(PrivateFixture):
    def test_document_receipt_preserves_download_id_without_bot_token(self):
        document = self.root / "fixture.age.part"
        document.write_bytes(b"encrypted fixture")
        response = mock.Mock(status=200)
        response.read.return_value = json.dumps({
            "ok": True, "result": {"message_id": 17, "chat": {"id": 123456789},
                                    "document": {"file_id": "fixture-file-id"}},
        }).encode()
        connection = mock.Mock()
        connection.getresponse.return_value = response
        with mock.patch.object(host.http.client, "HTTPSConnection", return_value=connection):
            self.assertEqual(host.send_document(self.config, document, "Fixture"), 17)
        receipt = self.state / "telegram-receipts" / "17.json"
        saved = json.loads(receipt.read_text())
        self.assertEqual(saved["file_id"], "fixture-file-id")
        self.assertEqual(saved["sha256"], host.sha256(document))
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(fixture_token(), receipt.read_text())

    def test_private_mode_and_environment_mismatch_are_rejected(self):
        self.config_path.chmod(0o644)
        with self.assertRaises(host.SafeError):
            host.load_config(self.config_path)
        self.config_path.chmod(0o600)
        self.env.write_text(self.env.read_text().replace(str(self.state / "db"), str(self.root / "other")))
        with self.assertRaises(host.SafeError):
            host.read_env(self.config)

    def test_staging_cannot_receive_dns_credential(self):
        payload = {"telegram_token": fixture_token(), "telegram_chat_id": "123456789",
                   "duckdns_token": "a" * 32, "apply_bot": False}
        with mock.patch.object(provision.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(host.SafeError, "Staging"):
                provision.receive("staging", payload)

    def test_recovery_reference_requires_a_complete_image_id(self):
        original = self.env.read_text()
        lines = original.splitlines()
        changed = ["XUI_IMAGE=mirage-recovery/x-ui:" + "a" * 64 if line.startswith("XUI_IMAGE=") else line for line in lines]
        self.env.write_text("\n".join(changed) + "\n")
        self.assertTrue(host.read_env(self.config)["XUI_IMAGE"].startswith("mirage-recovery/"))
        self.env.write_text(self.env.read_text().replace("a" * 64, "latest"))
        with self.assertRaises(host.SafeError):
            host.read_env(self.config)

    def test_sender_suppresses_ssh_output_and_cleans_ephemeral_key(self):
        environment = {"MIRAGE_TARGET": "staging", "MIRAGE_APPLY_BOT": "false",
                       "SSH_HOST": "server.example.com", "SSH_PORT": "22", "SSH_USER": "delivery",
                       "SSH_KNOWN_HOSTS": "fixture-host-key", "SSH_PRIVATE_KEY": "fixture-private-key",
                       "TELEGRAM_BOT_TOKEN": fixture_token(), "TELEGRAM_ADMIN_ID": "123456789"}
        paths = []

        def ssh(command, **kwargs):
            paths.append(Path(command[command.index("-i") + 1]))
            self.assertEqual(paths[-1].stat().st_mode & 0o777, 0o600)
            self.assertNotIn(fixture_token(), " ".join(command))
            self.assertEqual(json.loads(kwargs["input"])["duckdns_token"], "")
            return subprocess.CompletedProcess(command, 1, b"", fixture_token().encode())

        with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(provision.subprocess, "run", side_effect=ssh):
            with self.assertRaises(host.SafeError) as error:
                provision.send()
        self.assertNotIn(fixture_token(), str(error.exception))
        self.assertTrue(paths)
        self.assertFalse(paths[0].exists())


class SnapshotTests(PrivateFixture):
    def test_failure_log_keeps_stage_type_and_errno_without_private_values(self):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(backup.sys, "stdout", output), mock.patch.object(backup.sys, "stderr", errors):
            backup.progress("archive.runtime-state")
            try:
                try:
                    raise FileNotFoundError(2, fixture_token(), "/private/" + fixture_token())
                except OSError:
                    raise host.SafeError(fixture_token()) from None
            except host.SafeError as error:
                backup.log_failure(error)
        record = json.loads(errors.getvalue())
        self.assertEqual(record["stage"], "archive.runtime-state")
        self.assertEqual(record["error_type"], "SafeError")
        self.assertEqual(record["cause_type"], "FileNotFoundError")
        self.assertEqual(record["errno"], 2)
        self.assertNotIn(fixture_token(), output.getvalue() + errors.getvalue())
        self.assertNotIn("/private/", errors.getvalue())

    def test_forced_manual_snapshot_reuses_matching_images(self):
        root = self.state / "backups"
        root.mkdir(mode=0o700)
        host.write_json(root / "last-success.json", {
            "date": backup.dt.datetime.now(backup.ZoneInfo("Europe/Saratov")).date().isoformat()})
        host.write_json(root / "images.json", {"bundle": "existing-images", "image_ids": ["fixture-image"]})
        self.config["age_recipient"] = "age1" + "a" * 58
        with mock.patch.object(backup, "drain"), mock.patch.object(backup, "prune_delivered_recovery"), \
                mock.patch.object(backup, "image_inventory", return_value=([{"id": "fixture-image"}], "Xray fixture")) as inventory, \
                mock.patch.object(backup, "build_recovery", return_value=self.root / "snapshot") as build, \
                mock.patch.object(backup, "queue_archive", return_value="recovery"), \
                mock.patch.object(backup, "run") as external:
            backup.backup(self.config)
            inventory.assert_not_called()
            backup.backup(self.config, force=True)
        self.assertEqual(build.call_args.args[4], "existing-images")
        external.assert_not_called()

    def test_transient_paths_are_skipped_before_stat_and_symlink_resolution(self):
        source = self.root / "source"
        source.mkdir()
        (source / "kept").write_text("fixture")
        (source / "disappeared.tmp").symlink_to(self.root / "absent")
        transient = source / ".queue-fixture"
        transient.mkdir()
        (transient / "private").write_text(fixture_token())
        with tarfile.open(self.root / "transient.tar", "w") as archive:
            backup.add_tree(archive, source, "state")
        with tarfile.open(self.root / "transient.tar") as archive:
            self.assertEqual(archive.getnames(), ["state", "state/kept"])

    def test_image_identity_uses_actual_digest_not_normalized_reference_text(self):
        environment = host.read_env(self.config)
        digest = environment["XUI_IMAGE"].split("@", 1)[1]
        images = {
            "sha256:" + "a" * 64: {"Id": "sha256:" + "a" * 64, "Size": 1, "Architecture": "amd64",
                                      "RepoDigests": ["normalized-repository@" + digest]},
            "sha256:" + "b" * 64: {"Id": "sha256:" + "b" * 64, "Size": 1, "Architecture": "amd64",
                                      "RepoDigests": ["caddy@" + environment["CADDY_IMAGE"].split("@", 1)[1]]},
        }

        def compose(config, *arguments):
            if arguments[0] == "ps":
                return (("a" if arguments[-1] == "x-ui" else "b") * 64).encode()
            self.assertEqual(arguments[-2], environment.get("XUI_BIN_FOLDER", "/app/bin") + "/xray-linux-amd64")
            return b"Xray 26.10.10 (fixture build)\n"

        def run(command):
            if command[1] == "inspect":
                letter = command[-1][0]
                mounts = [{"Destination": "/certs", "Source": environment["TLS_DIR"], "RW": False}]
                if letter == "a":
                    mounts.append({"Destination": "/etc/x-ui", "Source": environment["DB_DIR"], "RW": True})
                return json.dumps([{"State": {"Running": True}, "Image": "sha256:" + letter * 64,
                                    "Config": {"Image": "normalized-reference", "Env":
                                               ["XUI_BIN_FOLDER=" + environment.get("XUI_BIN_FOLDER", "/app/bin")]},
                                    "Mounts": mounts}]).encode()
            return json.dumps([images[command[-1]]]).encode()

        with mock.patch.object(backup, "compose", side_effect=compose), mock.patch.object(backup, "run", side_effect=run):
            records, core = backup.image_inventory(self.config, environment)
            self.assertEqual(len(records), 2)
            self.assertEqual(core, "Xray 26.10.10")
            environment["XUI_BIN_FOLDER"] = "/etc/x-ui/bin"
            self.assertEqual(backup.image_inventory(self.config, environment)[1], "Xray 26.10.10")
            environment["XUI_BIN_FOLDER"] = "/unsupported"
            with self.assertRaises(host.SafeError):
                backup.image_inventory(self.config, environment)
            environment.pop("XUI_BIN_FOLDER")
            images["sha256:" + "a" * 64]["RepoDigests"] = []
            with self.assertRaises(host.SafeError):
                backup.image_inventory(self.config, environment)

    def test_wal_commits_survive_without_uncommitted_rows(self):
        source, destination = self.root / "live.db", self.root / "snapshot.db"
        connection = sqlite3.connect(source)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE users (name TEXT)")
            connection.execute("INSERT INTO users VALUES ('first')")
            connection.commit()
            connection.execute("INSERT INTO users VALUES ('second')")
            connection.commit()
            connection.execute("INSERT INTO users VALUES ('uncommitted')")
            backup.snapshot_database(source, destination)
            with sqlite3.connect(destination) as restored:
                self.assertEqual(restored.execute("SELECT name FROM users").fetchall(), [("first",), ("second",)])
                self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        finally:
            connection.close()

    def test_archive_rejects_escaping_link_and_special_file(self):
        source = self.root / "source"
        source.mkdir()
        (self.root / "outside").write_text("fixture")
        link = source / "link"
        link.symlink_to(self.root / "outside")
        with tarfile.open(self.root / "recovery.tar", "w") as archive:
            with self.assertRaises(host.SafeError):
                backup.add_tree(archive, source, "state")
        link.unlink()
        os.mkfifo(source / "pipe")
        with tarfile.open(self.root / "other.tar", "w") as archive:
            with self.assertRaises(host.SafeError):
                backup.add_tree(archive, source, "state")

    def test_full_bundle_contains_recoverable_database_and_only_acme_cron(self):
        database_dir = self.state / "db"
        database_dir.mkdir(mode=0o700)
        core_dir = database_dir / "bin"
        core_dir.mkdir(mode=0o700)
        core_file = core_dir / "xray-linux-amd64"
        core_file.write_text("fixture executable")
        core_file.chmod(0o755)
        with sqlite3.connect(database_dir / "x-ui.db") as database:
            database.execute("CREATE TABLE users (name TEXT)")
            database.execute("INSERT INTO users VALUES ('fixture')")
        metrics = database_dir / "system_metrics.gob"
        metrics.write_bytes(b"original published metric snapshot")
        (database_dir / "system_metrics.gob.tmp").symlink_to(self.root / "absent")
        certificate_root = self.state / "tls"
        certificate_root.mkdir(mode=0o700)
        (certificate_root / "fixture").write_text("fixture TLS state")
        tls_source = self.state / "tls-source"
        tls_source.mkdir(mode=0o700)
        (tls_source / "fixture").write_text("fixture ACME output")
        (self.config_path.parent / "panel-access.json").write_text('{"fixture": true}')
        acme = Path(self.config["acme_dir"])
        acme.mkdir(mode=0o700)
        (acme / "account.conf").write_text("fixture ACME account")
        (acme / "account.conf.tmp").symlink_to(self.root / "absent")
        work = self.root / "work"
        work.mkdir(mode=0o700)
        cron = ('0 0 * * * /unrelated/private-job\n0 1 * * * "' + str(acme)
                + '"/acme.sh --cron --home "' + str(acme) + '"\n').encode()
        original_copy = backup.shutil.copyfileobj
        original_open = backup.tarfile.open

        def publish_new_metrics(live, destination, **kwargs):
            replacement = database_dir / "replacement.tmp"
            replacement.write_bytes(b"newer smaller snapshot")
            os.replace(replacement, metrics)
            (acme / "changed.tmp").write_text("transient ACME state")
            return original_copy(live, destination, **kwargs)

        with mock.patch.object(backup, "run", return_value=cron), \
                mock.patch.object(backup.shutil, "copyfileobj", side_effect=publish_new_metrics), \
                mock.patch.object(backup.tarfile, "open", wraps=original_open) as opened:
            path = backup.build_recovery(self.config, host.read_env(self.config), [], "Xray fixture", "image-fixture", work)
        self.assertEqual(opened.call_args.kwargs["compresslevel"], 1)
        with tarfile.open(path, "r:gz") as archive:
            self.assertIn("deployment/infra/provision.py", archive.getnames())
            self.assertEqual(archive.getmember("state/db/bin/xray-linux-amd64").mode, 0o700)
            self.assertEqual(archive.getmember("state/db/x-ui.db").mode, 0o600)
            self.assertIn("RECOVERY.md", archive.getnames())
            self.assertIn("state/tls-source/fixture", archive.getnames())
            self.assertIn("deployment/panel-access.json", archive.getnames())
            self.assertEqual(archive.extractfile("state/db/system_metrics.gob").read(),
                             b"original published metric snapshot")
            self.assertFalse(any(name.endswith(".tmp") for name in archive.getnames()))
            metadata = json.load(archive.extractfile("manifest.json"))
            self.assertEqual(metadata["image_bundle"], "image-fixture")
            cron_snapshot = archive.extractfile("host/acme-cron.txt").read()
            self.assertNotIn(b"unrelated", cron_snapshot)
            restored = self.root / "restored.db"
            restored.write_bytes(archive.extractfile("state/db/x-ui.db").read())
        with sqlite3.connect(restored) as database:
            self.assertEqual(database.execute("SELECT name FROM users").fetchone(), ("fixture",))

        changed_work = self.root / "changed-work"
        changed_work.mkdir(mode=0o700)

        def change_account(live, destination, **kwargs):
            (acme / "account.conf").write_text("a genuinely changed ACME account")
            return original_copy(live, destination, **kwargs)

        with mock.patch.object(backup, "run", return_value=cron), \
                mock.patch.object(backup.shutil, "copyfileobj", side_effect=change_account):
            with self.assertRaisesRegex(host.SafeError, "ACME state changed"):
                backup.build_recovery(self.config, host.read_env(self.config), [],
                                      "Xray fixture", "image-fixture", changed_work)

    def test_retention_only_removes_old_delivered_recovery(self):
        sent = self.state / "sent"
        sent.mkdir(mode=0o700)
        old_date = (backup.dt.datetime.now(backup.ZoneInfo("Europe/Saratov")).date()
                    - backup.dt.timedelta(days=8)).isoformat()
        folders = []
        for index, (kind, delivered) in enumerate((("recovery", True), ("images", True), ("recovery", False))):
            name = f"20260101T000000Z-{index:08x}"
            folder = sent / name
            folder.mkdir(mode=0o700)
            host.write_json(folder / "delivery.json", {"id": name, "kind": kind,
                            "date": old_date, "parts": [{"sent": delivered}]})
            host.write_json(folder / "manifest.json", {})
            folders.append(folder)
        backup.prune_delivered_recovery(self.state)
        self.assertFalse(folders[0].exists())
        self.assertTrue(folders[1].exists())
        self.assertTrue(folders[2].exists())


@unittest.skipUnless(shutil.which("age") and shutil.which("age-keygen"), "age integration tools missing")
class EncryptionTests(PrivateFixture):
    def setUp(self):
        super().setUp()
        self.identity = self.root / "identity"
        host.run(["age-keygen", "-o", str(self.identity)])
        self.config["age_recipient"] = host.run(["age-keygen", "-y", str(self.identity)]).decode().strip()
        self.outbox = host.private_dir(self.state / "outbox")

    def test_encryption_chunk_reassembly_and_corruption(self):
        source = self.root / "source"
        source.write_bytes((fixture_token() * 200).encode())
        with mock.patch.object(backup, "PART_SIZE", 1024):
            identifier = backup.queue_archive(self.config, source, self.outbox, "recovery")
        folder = self.outbox / identifier
        metadata = json.loads((folder / "delivery.json").read_text())
        self.assertGreater(len(metadata["parts"]), 1)
        encrypted = self.root / "bundle.age"
        encrypted.write_bytes(b"".join((folder / part["name"]).read_bytes() for part in metadata["parts"]))
        self.assertNotIn(fixture_token().encode(), encrypted.read_bytes())
        restored = self.root / "restored"
        host.run(["age", "--decrypt", "-i", str(self.identity), "-o", str(restored), str(encrypted)])
        self.assertEqual(source.read_bytes(), restored.read_bytes())
        first = folder / metadata["parts"][0]["name"]
        first.write_bytes(first.read_bytes() + b"corrupted")
        with mock.patch.object(backup, "send_document") as send:
            with self.assertRaises(host.SafeError):
                backup.deliver(self.config, folder)
            send.assert_not_called()

    def test_failed_delivery_resumes_without_resending_acknowledged_parts(self):
        source = self.root / "source"
        source.write_bytes(b"fixture recovery" * 100)
        with mock.patch.object(backup, "PART_SIZE", 1024):
            identifier = backup.queue_archive(self.config, source, self.outbox, "recovery")
        folder = self.outbox / identifier
        with mock.patch.object(backup, "send_document", side_effect=[1, host.SafeError("Unavailable")]):
            with self.assertRaises(host.SafeError):
                backup.deliver(self.config, folder)
        metadata = json.loads((folder / "delivery.json").read_text())
        self.assertTrue(metadata["parts"][0]["sent"])
        with mock.patch.object(backup, "send_document", return_value=2) as send:
            backup.deliver(self.config, folder)
        self.assertEqual(send.call_count, len(metadata["parts"]))
        self.assertNotEqual(send.call_args_list[0].args[1].name, metadata["parts"][0]["name"])


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL missing")
class CertificateTests(PrivateFixture):
    def setUp(self):
        super().setUp()
        self.ca, self.ca_key = self.root / "ca.pem", self.root / "ca-key.pem"
        self.key, self.csr = self.root / "key.pem", self.root / "request.pem"
        host.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30",
                  "-subj", "/CN=Fixture CA", "-keyout", str(self.ca_key), "-out", str(self.ca)])
        host.run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=vpn.example.com",
                  "-keyout", str(self.key), "-out", str(self.csr)])
        extensions = self.root / "extensions"
        extensions.write_text("subjectAltName=DNS:vpn.example.com\nextendedKeyUsage=serverAuth\n")
        self.certificates = []
        for number in (1, 2):
            certificate = self.root / f"leaf-{number}.pem"
            host.run(["openssl", "x509", "-req", "-in", str(self.csr), "-CA", str(self.ca),
                      "-CAkey", str(self.ca_key), "-set_serial", str(number), "-days", "14",
                      "-extfile", str(extensions), "-out", str(certificate)])
            self.certificates.append(certificate)
        self.config["ca_file"] = str(self.ca)

    def test_bad_pair_and_wrong_hostname_never_publish(self):
        with self.assertRaises(host.SafeError):
            tls.publish(self.config, self.certificates[0], self.ca_key, publish_only=True)
        self.assertFalse((self.state / "tls" / "current").exists())
        self.config["public_host"] = "wrong.example.com"
        with self.assertRaises(host.SafeError):
            tls.validate_pair(self.certificates[0], self.key, self.config["public_host"], self.ca)

    def test_reload_failure_restores_pair_without_requesting_vpn_restart(self):
        tls.publish(self.config, self.certificates[0], self.key, publish_only=True)
        current = self.state / "tls" / "current"
        previous = os.readlink(current)
        with mock.patch.object(tls, "compose", side_effect=[b"valid", host.SafeError("failed"), b"restored"]) as compose:
            with self.assertRaisesRegex(host.SafeError, "previous pair"):
                tls.publish(self.config, self.certificates[1], self.key)
        self.assertEqual(os.readlink(current), previous)
        self.assertTrue(all("restart" not in call.args for call in compose.call_args_list))
        self.assertIn("--force", compose.call_args_list[1].args)
        self.assertEqual((current / "key.pem").stat().st_mode & 0o777, 0o600)


class NativeProvisionTests(PrivateFixture):
    def test_native_api_preserves_settings_and_revokes_temporary_token(self):
        settings = {"webPort": 12080, "twoFactorEnable": True, "panelOutbound": "existing",
                    "subPort": 12081, "unrelated": "preserved"}
        sent = []

        class Response:
            def __init__(self, obj):
                self.obj = obj

            def __enter__(self):
                return io.BytesIO(json.dumps({"success": True, "obj": self.obj}).encode())

            def __exit__(self, *args):
                pass

        class Opener:
            def open(_, request, **kwargs):
                endpoint = request.full_url.split("/setting/")[1]
                payload = json.loads(request.data) if request.data else None
                sent.append((endpoint, payload))
                if endpoint == "apiTokens":
                    return Response([{"id": 7, "name": "mirage-secret-delivery"}])
                if endpoint == "all":
                    return Response(settings.copy())
                if endpoint == "update":
                    settings.update(payload)
                    settings["hasTgBotToken"] = True
                return Response(None)

        with mock.patch.object(provision, "compose", return_value=b"apiToken: fixture-value\n"), mock.patch.object(provision.urllib.request, "build_opener", return_value=Opener()):
            provision.apply_bot(self.config, host.read_env(self.config))
        self.assertEqual(settings["unrelated"], "preserved")
        self.assertTrue(settings["twoFactorEnable"])
        self.assertFalse(settings["tgBotBackup"])
        self.assertEqual(sent[-1], ("apiTokens/setEnabled/7", {"enabled": False, "expectedScope": "admin"}))


class StatusTests(PrivateFixture):
    def test_failed_server_check_sends_warning_without_private_error_text(self):
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["status.py", "--config", str(self.config_path)]), \
                mock.patch.object(status, "check", side_effect=OSError(fixture_token())), \
                mock.patch.object(status, "notify") as send, \
                mock.patch.object(sys, "stdout", output):
            self.assertEqual(status.main(), 0)
        self.assertFalse(json.loads(output.getvalue())["healthy"])
        self.assertIn("не завершилась", send.call_args.args[1])
        self.assertNotIn(fixture_token(), output.getvalue() + send.call_args.args[1])

    def test_failed_telegram_send_is_not_reported_as_delivered(self):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["status.py", "--config", str(self.config_path)]), \
                mock.patch.object(status, "check", return_value=({"healthy": True}, "fixture status")), \
                mock.patch.object(status, "notify", side_effect=host.SafeError(fixture_token())), \
                mock.patch.object(sys, "stdout", output), mock.patch.object(sys, "stderr", errors):
            self.assertEqual(status.main(), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(errors.getvalue())["event"], "nightly_status_failed")
        self.assertNotIn(fixture_token(), errors.getvalue())


if __name__ == "__main__":
    unittest.main()
