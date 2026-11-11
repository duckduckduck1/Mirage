"""Resource history: interval attribution, PID reuse and bounded private files."""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))
import resources


class ResourceTests(unittest.TestCase):
    def test_network_counters_exclude_duplicate_interfaces_and_handle_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / "net").mkdir()
            (proc / "net/dev").write_text("header\nheader\n" + "".join(
                name + ": " + " ".join(str(i) for i in range(16)) + "\n"
                for name in ("lo", "veth0123", "docker0", "br-abc", "ens1")))
            (proc / "net/softnet_stat").write_text("00000010 00000002 00000003\n00000020 00000000 00000001\n")
            net = resources.network(proc)
            self.assertEqual(set(net["interfaces"]), {"ens1"})
            self.assertEqual(net["interfaces"]["ens1"]["tx_packets"], 9)
            self.assertEqual(net["softnet"], {"processed": 48, "dropped": 2, "time_squeeze": 4})
        self.assertEqual(resources.counter_deltas({"a": 10, "b": 5, "c": 4}, {"a": 7, "b": 9}),
                         {"a": 3, "b": None, "c": None})

    def test_socket_history_keeps_only_transport_counts_without_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "net").mkdir()
            (root / "net/tcp").write_text("header\n0: 010200C0:01BB 02C63364:1234 01\n"
                                         "1: 010200C0:0805 02C63364:1234 08\n"
                                         "2: 010200C0:0050 02C63364:1234 01\n")
            (root / "net/tcp6").write_text("header\n0: 00000000000000000000000000000000:01BB 0:0 0A\n")
            result = resources.vpn_sockets(root)
            self.assertEqual(result["443"], {"established": 1, "listen": 1})
            self.assertEqual(result["2053"], {"close_wait": 1})
            self.assertNotIn("010200C0", json.dumps(result))
            self.assertNotIn("1234", json.dumps(result))

    def test_proc_stat_with_parentheses_does_not_read_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "42"
            path.mkdir()
            fields = ["S"] + ["0"] * 21
            for index, value in {9: "3", 11: "80", 12: "20", 19: "700", 21: "6"}.items():
                fields[index] = value
            (path / "stat").write_text("42 (name (worker)) " + " ".join(fields))
            (path / "cgroup").write_text("0::/system.slice/docker-" + "a" * 64 + ".scope\n")
            (path / "cmdline").write_text("PRIVATE_ARGUMENT_MUST_NOT_APPEAR")
            item = resources.process(path)
            self.assertEqual(item["ticks"], 100)
            self.assertEqual(item["start_ticks"], 700)
            self.assertEqual(item["rss_bytes"], 6 * resources.PAGE)
            self.assertEqual(item["container"], "a" * 64)
            self.assertNotIn("PRIVATE_ARGUMENT", json.dumps(item))

    def test_interval_cpu_oom_and_pid_reuse(self):
        item = {"pid": 42, "start_ticks": 1, "name": "xray", "state": "S",
                "rss_bytes": 4000, "ticks": 100, "major_faults": 0,
                "read_bytes": 1000, "write_bytes": 0, "container": "a" * 64}
        group = {"cpu": {"usage_usec": 100, "nr_throttled": 2},
                 "memory_events": {"oom_kill": 0}, "memory_bytes": 4000}
        before = {"monotonic": 10, "cpu": [100, 0, 50, 850, 0, 0, 0, 0],
                  "processes": {(42, 1): item}, "containers": {"a" * 64: group},
                  "vm": {"oom_kill": 0}}
        after = copy.deepcopy(before)
        after.update(monotonic=20, cpu=[120, 0, 60, 920, 0, 0, 0, 0],
                     memory_kib={}, psi={}, skipped_processes=0)
        after["processes"][(42, 1)]["ticks"] += resources.TICKS * 5
        after["containers"]["a" * 64]["memory_events"]["oom_kill"] = 1
        after["vm"]["oom_kill"] = 1
        result = resources.record(before, after, {"a" * 64: "mirage-x-ui-1"})
        self.assertEqual(result["processes"][0]["cpu_pct"], 50)
        self.assertEqual(result["cpu_pct"]["idle"], 70)
        self.assertEqual(result["vm_delta"]["oom_kill"], 1)
        self.assertEqual(result["containers"]["mirage-x-ui-1"]["memory_events_delta"]["oom_kill"], 1)
        after["processes"] = {(42, 2): dict(item, start_ticks=2)}
        result = resources.record(before, after, {})
        self.assertIsNone(result["processes"][0]["cpu_pct"])
        self.assertEqual(result["exited_processes"], 1)

    def test_history_rotates_with_private_modes_and_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = resources.History(root)
            with mock.patch.object(resources, "SEGMENT_BYTES", 128), \
                    mock.patch.object(resources, "MAX_BYTES", 512):
                for index in range(40):
                    history.append({"index": index, "data": "x" * 60})
                self.assertLessEqual(sum(path.stat().st_size for path in root.iterdir()), 512)
            for path in root.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertTrue(all(json.loads(line) for line in path.read_text().splitlines()))
            old = root / "resources-00000000000000000001.jsonl"
            old.write_text("{}\n")
            os.utime(old, (1, 1))
            history.maintain()
            self.assertFalse(old.exists())

    def test_history_rejects_public_directory_and_active_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o755)
            with self.assertRaises(ValueError):
                resources.History(root)
            root.chmod(0o700)
            history = resources.History(root)
            target = root / "untouched"
            target.write_text("original")
            history.active.symlink_to(target)
            with self.assertRaises(OSError):
                history.append({"test": True})
            self.assertEqual(target.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
