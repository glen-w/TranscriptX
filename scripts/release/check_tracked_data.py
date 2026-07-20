#!/usr/bin/env python3
"""Assert git ls-files 'data/**' equals scripts/release/tracked_data_allowlist.toml."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = Path(__file__).resolve().parent / "tracked_data_allowlist.toml"


def _load_allowlist() -> set[str]:
    data = tomllib.loads(ALLOWLIST.read_text(encoding="utf-8"))
    paths = data.get("paths") or []
    out: set[str] = set()
    for entry in paths:
        path = str(entry.get("path") or "").strip()
        if not path:
            raise SystemExit(f"allowlist entry missing path: {entry!r}")
        if not entry.get("owner") or not entry.get("purpose"):
            raise SystemExit(f"allowlist entry missing owner/purpose: {path}")
        out.add(path)
    return out


def _tracked_data() -> set[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--", "data/**"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    raw = proc.stdout.decode("utf-8")
    if not raw:
        return set()
    return {p for p in raw.split("\0") if p}


def main() -> int:
    allowed = _load_allowlist()
    tracked = _tracked_data()
    extra = sorted(tracked - allowed)
    missing = sorted(allowed - tracked)
    if extra or missing:
        if extra:
            print("ERROR: tracked data paths not on allowlist:")
            for p in extra:
                print(f"  + {p}")
        if missing:
            print("ERROR: allowlist paths not tracked:")
            for p in missing:
                print(f"  - {p}")
        return 1
    print(f"OK: tracked data allowlist matches ({len(tracked)} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
