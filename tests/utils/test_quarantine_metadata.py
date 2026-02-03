from __future__ import annotations

import re
from pathlib import Path


_QUARANTINE_LINE = re.compile(
    r"pytest\.mark\.quarantined.*#\s*reason:.*owner:.*remove_by:",
    re.IGNORECASE,
)


def test_quarantined_markers_have_metadata() -> None:
    """Ensure quarantined tests include reason/owner/remove_by comment metadata."""
    tests_root = Path(__file__).resolve().parents[1]
    matches = []
    for path in tests_root.rglob("test_*.py"):
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "pytest.mark.quarantined" in line:
                matches.append((path, line))

    if not matches:
        return

    invalid = []
    for path, line in matches:
        if not _QUARANTINE_LINE.search(line):
            invalid.append((path, line))

    assert not invalid, (
        "Quarantined tests must include comment metadata "
        "(reason/owner/remove_by). Offending lines:\n"
        + "\n".join(f"{p}: {l}" for p, l in invalid)
    )
