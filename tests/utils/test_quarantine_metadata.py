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
    lines_by_path = {}
    for path in tests_root.rglob("test_*.py"):
        if path.name in {
            "test_quarantine_enforcement.py",
            "test_quarantine_metadata.py",
        }:
            continue
        content = path.read_text(encoding="utf-8")
        line_list = content.splitlines()
        lines_by_path[path] = line_list
        for i, line in enumerate(line_list):
            if "pytest.mark.quarantined" in line:
                # Allow metadata on same line or within next few lines (e.g. ]  # reason: ...)
                following = " ".join(
                    line_list[i + 1 : i + 4]
                )  # next 3 lines cover ]  # reason: ... owner: ... remove_by:
                combined = line + " " + following
                matches.append((path, line, combined))

    if not matches:
        return

    invalid = []
    for path, line, combined in matches:
        if not _QUARANTINE_LINE.search(combined):
            invalid.append((path, line))

    assert not invalid, (
        "Quarantined tests must include comment metadata "
        "(reason/owner/remove_by). Offending lines:\n"
        + "\n".join(f"{p}: {line}" for p, line in invalid)
    )
