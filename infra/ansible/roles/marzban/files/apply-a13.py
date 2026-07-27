#!/usr/bin/env python3
"""Apply the reviewed one-line fix from upstream Marzban PR #2036."""

from pathlib import Path
import sys


OLD_ASSIGNMENT = """\
                if sids := inbound.get("sids"):
                    inbound["sid"] = random.choice(sids)
"""
NEW_ASSIGNMENT = """\
                if sids := inbound.get("sids"):
                    host_inbound["sid"] = random.choice(sids)
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply-a13.py PATH", file=sys.stderr)
        return 2

    target = Path(sys.argv[1])
    source = target.read_text(encoding="utf-8")
    matches = source.count(OLD_ASSIGNMENT)
    if matches != 1:
        print(
            f"refusing to patch {target}: expected one vulnerable assignment, "
            f"found {matches}",
            file=sys.stderr,
        )
        return 1

    target.write_text(
        source.replace(OLD_ASSIGNMENT, NEW_ASSIGNMENT, 1),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
