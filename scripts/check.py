#!/usr/bin/env python3
"""Check tracked documentation and common secret patterns without network access."""

import ipaddress
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


SENSITIVE_DIRS = {"secrets", "credentials", "backups", "exports"}
SENSITIVE_NAMES = {"access", "bot_telegram_key", "duckdns_token"}
SENSITIVE_SUFFIXES = {
    ".key", ".pem", ".crt", ".p12", ".vault", ".db", ".sqlite", ".sqlite3",
    ".backup", ".dump", ".tar", ".gz", ".tgz", ".zip", ".qcow2",
}
CONTENT_RULES = {
    "private key marker": re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----"),
    "Telegram credential": re.compile(r"\b[0-9]{6,20}:[A-Za-z0-9_-]{20,}\b"),
    "GitHub credential": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "proxy URL": re.compile(r"\b(?:vless|trojan|ss)://[^\s]+@[^\s]+"),
    "user identifier": re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b"),
}
ASSIGNMENT = re.compile(
    r"^\s*[\"']?([A-Za-z0-9_]*(?:TOKEN|PASSWORD|PRIVATE_KEY|SECRET)[A-Za-z0-9_]*)"
    r"[\"']?\s*[:=]\s*(.*?)\s*$", re.IGNORECASE
)
IPV4 = re.compile(r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])")
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)")
REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|[^\s]+)")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def placeholder(value: str) -> bool:
    value = value.strip().rstrip(",").strip("\"'")
    return (
        not value
        or value == "..."
        or value.startswith(("CHANGE_", "PASTE_", "EXAMPLE_", "${", "{{"))
        or (value.startswith("<") and value.endswith(">"))
    )


def inspect_file(root: Path, relative: Path, tracked: set[str]) -> list[str]:
    problems = []
    path = root / relative

    def report(reason: str, line: int | None = None) -> None:
        location = relative.as_posix() + (f":{line}" if line else "")
        problems.append(f"{location}: {reason}")

    name = relative.name.lower()
    if (
        any(part.lower() in SENSITIVE_DIRS for part in relative.parts)
        or name in SENSITIVE_NAMES
        or (name.startswith(".env") and not name.endswith(".example"))
        or relative.suffix.lower() in SENSITIVE_SUFFIXES
        or re.search(r"\.(?:db|sqlite3?)-(?:wal|shm|journal)$", name)
        or name.startswith(("vault-password", ".vault_pass"))
        or ".tfstate" in name
    ):
        report("sensitive filename")
        return problems
    if path.is_symlink():
        report("tracked symlink requires review")
        return problems
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return problems
    except OSError:
        report("tracked file cannot be read")
        return problems

    fence = None
    for number, line in enumerate(source.splitlines(), 1):
        for reason, pattern in CONTENT_RULES.items():
            if pattern.search(line):
                report(reason, number)
        assignment = ASSIGNMENT.match(line)
        if assignment and not placeholder(assignment[2]):
            report("credential-like assignment", number)
        for match in IPV4.finditer(line):
            try:
                if ipaddress.IPv4Address(match[0]).is_global:
                    report("public infrastructure address", number)
            except ipaddress.AddressValueError:
                pass

        if relative.suffix.lower() != ".md":
            continue
        marker = FENCE.match(line)
        if marker:
            value = marker[1]
            if fence is None:
                fence = value
            elif value.startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue
        links = [match[1] for match in INLINE_LINK.finditer(line)]
        reference = REFERENCE_LINK.match(line)
        if reference:
            links.append(reference[1])
        for destination in links:
            try:
                parsed = urlsplit(destination.strip("<>"))
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                local = unquote(parsed.path)
                target = (root / local.lstrip("/") if local.startswith("/")
                          else path.parent / local).resolve()
                target_name = target.relative_to(root).as_posix()
                indexed = target_name in tracked or (
                    target.is_dir() and any(p.startswith(target_name + "/") for p in tracked)
                )
                if not target.exists() or not indexed:
                    report("relative Markdown target is missing or untracked", number)
            except ValueError:
                report("invalid or escaping Markdown target", number)
    return problems


def main() -> int:
    try:
        root = Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.PIPE, text=True
        ).strip()).resolve()
        raw = subprocess.check_output(
            ["git", "ls-files", "--cached", "-z"], cwd=root, stderr=subprocess.PIPE
        )
        tracked = {p.decode("utf-8") for p in raw.split(b"\0") if p}
    except (subprocess.CalledProcessError, UnicodeError):
        print("Run the checker inside a Git checkout.", file=sys.stderr)
        return 1
    problems = [problem for p in sorted(tracked)
                for problem in inspect_file(root, Path(p), tracked)]
    if problems:
        print("Repository checks failed (values suppressed):", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"Repository checks passed: {len(tracked)} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
