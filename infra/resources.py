"""Bounded, local Linux resource history. No credentials or process arguments."""

import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

INTERVAL = 15
MAX_BYTES = 64 * 1024 * 1024
SEGMENT_BYTES = 4 * 1024 * 1024
MAX_AGE = 7 * 86400
TICKS = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")


def pairs(path):
    try:
        return {key.rstrip(":"): int(value.split()[0])
                for key, value in (line.split(None, 1) for line in path.read_text().splitlines())}
    except (OSError, ValueError):
        return {}


def pressure(path):
    result = {}
    try:
        for line in path.read_text().splitlines():
            fields = line.split()
            result[fields[0]] = {key: float(value) for key, value in
                                 (field.split("=") for field in fields[1:])}
    except (OSError, ValueError):
        pass
    return result


def container_id(cgroup):
    match = re.search(r"(?:docker-|/docker/)([0-9a-f]{64})(?:\.scope)?(?:/|$)", cgroup)
    return match[1] if match else None


def process(path):
    # /proc/PID/stat can contain spaces and parentheses in comm. Never read cmdline.
    raw = (path / "stat").read_text()
    left, right = raw.index("("), raw.rindex(")")
    fields = raw[right + 2:].split()
    cgroup = (path / "cgroup").read_text().strip().split("\n")[0].split(":", 2)[-1]
    io = pairs(path / "io")
    return {
        "pid": int(path.name), "start_ticks": int(fields[19]),
        "name": re.sub(r"[^a-zA-Z0-9_.:+-]", "_", raw[left + 1:right])[:32],
        "state": fields[0], "ticks": int(fields[11]) + int(fields[12]),
        "rss_bytes": max(0, int(fields[21])) * PAGE,
        "major_faults": int(fields[9]), "read_bytes": io.get("read_bytes", 0),
        "write_bytes": io.get("write_bytes", 0), "container": container_id(cgroup),
    }


def snapshot(proc=Path("/proc"), cgroups=Path("/sys/fs/cgroup")):
    stat_lines = (proc / "stat").read_text().splitlines()
    stat = stat_lines[0].split()[1:9]
    scheduler = {line.split()[0]: int(line.split()[1]) for line in stat_lines
                 if line.startswith(("procs_running ", "procs_blocked "))}
    processes, skipped = {}, 0
    for path in proc.iterdir():
        if not path.name.isdecimal():
            continue
        try:
            item = process(path)
            processes[(item["pid"], item["start_ticks"])] = item
        except (OSError, ValueError, IndexError):
            skipped += 1  # Exited processes and kernel races must not stop collection.
    groups = {}
    # Docker's systemd and cgroupfs drivers, without traversing unrelated subtrees.
    paths = list((cgroups / "system.slice").glob("docker-*.scope"))
    paths += list((cgroups / "docker").glob("*"))
    for path in paths:
        identifier = container_id(str(path))
        if not identifier:
            continue
        try:
            groups[identifier] = {
                "memory_bytes": int((path / "memory.current").read_text()),
                "memory_max": (path / "memory.max").read_text().strip(),
                "swap_bytes": int((path / "memory.swap.current").read_text()),
                "memory_events": pairs(path / "memory.events"),
                "cpu": pairs(path / "cpu.stat"),
                "cpu_max": (path / "cpu.max").read_text().strip(),
                "memory_psi": pressure(path / "memory.pressure"),
            }
        except (OSError, ValueError):
            continue
    memory = pairs(proc / "meminfo")
    vm = pairs(proc / "vmstat")
    return {
        "monotonic": time.monotonic(), "cpu": list(map(int, stat)),
        "scheduler": scheduler,
        "memory_kib": {key: memory.get(key, 0) for key in
                       ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree", "Cached", "Slab")},
        "vm": {key: vm.get(key, 0) for key in ("oom_kill", "pgmajfault", "pswpin", "pswpout")},
        "psi": {key: pressure(proc / "pressure" / key) for key in ("cpu", "memory", "io")},
        "processes": processes, "skipped_processes": skipped, "containers": groups,
    }


def deltas(current, previous):
    return {key: max(0, value - previous.get(key, value)) for key, value in current.items()}


def record(before, after, names):
    elapsed = max(0.001, after["monotonic"] - before["monotonic"])
    ticks = [max(0, new - old) for old, new in zip(before["cpu"], after["cpu"])]
    total = max(1, sum(ticks))
    percentages = {key: round(value * 100 / total, 2) for key, value in zip(
        ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"), ticks)}
    rows = []
    for identity, item in after["processes"].items():
        previous = before["processes"].get(identity)
        # Newly observed processes have no complete interval; use null, not lifetime CPU.
        row = {key: item[key] for key in ("pid", "start_ticks", "name", "state", "rss_bytes")}
        row["container"] = names.get(item["container"], item["container"])
        row["cpu_pct"] = (round(max(0, item["ticks"] - previous["ticks"]) * 100 / TICKS / elapsed, 2)
                          if previous else None)
        for key in ("major_faults", "read_bytes", "write_bytes"):
            row[key + "_delta"] = max(0, item[key] - previous[key]) if previous else None
        rows.append(row)
    selected = {}
    for row in sorted(rows, key=lambda item: item["cpu_pct"] or 0, reverse=True)[:5]:
        selected[row["pid"]] = row
    for row in sorted(rows, key=lambda item: item["rss_bytes"], reverse=True)[:5]:
        selected[row["pid"]] = row
    containers = {}
    for identifier, item in after["containers"].items():
        old = before["containers"].get(identifier, {})
        cpu_delta = deltas(item["cpu"], old.get("cpu", {}))
        containers[names.get(identifier, identifier)] = {
            **item, "id": identifier[:12], "cpu_delta": cpu_delta,
            "cpu_pct": round(cpu_delta.get("usage_usec", 0) / elapsed / 10000, 2),
            "memory_events_delta": deltas(item["memory_events"], old.get("memory_events", {})),
        }
    return {
        "schema": 1, "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "interval_seconds": round(elapsed, 3), "cpu_pct": percentages,
        "scheduler": after.get("scheduler", {}),
        "memory_kib": after["memory_kib"], "vm": after["vm"],
        "vm_delta": deltas(after["vm"], before["vm"]), "psi": after["psi"],
        "process_count": len(rows), "skipped_processes": after["skipped_processes"],
        "exited_processes": len(before["processes"].keys() - after["processes"].keys()),
        "new_processes": len(after["processes"].keys() - before["processes"].keys()),
        "processes": list(selected.values()), "containers": containers,
    }


def container_names():
    try:
        output = subprocess.run(
            ["/usr/bin/docker", "ps", "--no-trunc", "--format", "{{.ID}} {{.Names}}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=3, check=True).stdout
        return {identifier: name for identifier, name in
                (line.split() for line in output.splitlines())
                if re.fullmatch(r"[0-9a-f]{64}", identifier)
                and re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", name)}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


class History:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if directory.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("History directory must be private and owned by the collector.")
        self.active = directory / "resources.jsonl"
        self.maintain()

    def maintain(self):
        now = time.time()
        archives = sorted(self.directory.glob("resources-*.jsonl"))
        for path in archives[:]:
            if now - path.stat().st_mtime > MAX_AGE:
                path.unlink()
                archives.remove(path)
        active_size = self.active.stat().st_size if self.active.exists() else 0
        size = active_size + sum(path.stat().st_size for path in archives)
        for path in archives:
            if size <= MAX_BYTES - SEGMENT_BYTES:
                break
            size -= path.stat().st_size
            path.unlink()

    def append(self, value):
        line = (json.dumps(value, separators=(",", ":")) + "\n").encode()
        if self.active.exists() and (self.active.stat().st_size + len(line) > SEGMENT_BYTES
                                     or time.time() - self.active.stat().st_mtime > MAX_AGE):
            self.active.rename(self.directory / f"resources-{time.time_ns():020d}.jsonl")
            self.maintain()
        fd = os.open(self.active, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "ab") as target:
            target.write(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("/var/log/mirage-resources"))
    args = parser.parse_args()
    os.umask(0o077)
    history = History(args.directory)
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    before, names, refresh = snapshot(), {}, 0
    while running:
        deadline = time.monotonic() + INTERVAL
        if time.monotonic() >= refresh:
            names = container_names()
            refresh = time.monotonic() + 300
            history.maintain()
        while running and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        if not running:
            break
        after = snapshot()
        history.append(record(before, after, names))
        before = after


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Exceptions must not copy /proc content into the journal.
        raise SystemExit("Resource collector stopped; inspect its private history and unit state.") from None
