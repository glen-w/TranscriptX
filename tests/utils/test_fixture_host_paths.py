"""Committed JSON fixtures must not embed machine-specific home paths.

Goldens with paths like ``/Users/<name>/...`` only pass on the author's
machine. Use ``<REPO>/...`` (config goldens, see ``_normalize_pathish`` in
``tests/core/config/test_pydantic_bridge_drift.py``) or repo-relative paths.
"""

from __future__ import annotations

import re
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parents[1]
_HOST_PATH = re.compile(r'(/Users/[^/"\s]+/|/home/[^/"\s]+/|[A-Za-z]:\\\\Users\\\\)')
# Paths (relative to tests/) allowed to contain host-style paths on purpose.
_ALLOWLIST: frozenset[str] = frozenset()


def test_json_fixtures_have_no_host_home_paths() -> None:
    offenders: list[str] = []
    for path in sorted(_TESTS_DIR.rglob("*.json")):
        rel = path.relative_to(_TESTS_DIR).as_posix()
        if "node_modules" in path.parts or rel in _ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            match = _HOST_PATH.search(line)
            if match:
                offenders.append(f"tests/{rel}:{lineno}: {match.group(0)}")
                break
    assert not offenders, "Host-specific paths in JSON fixtures:\n" + "\n".join(
        offenders
    )
