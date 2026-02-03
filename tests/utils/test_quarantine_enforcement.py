from __future__ import annotations

from pathlib import Path


def _has_strict_xfail_nearby(lines: list[str], start_index: int, window: int = 4) -> bool:
    end = min(len(lines), start_index + window)
    for line in lines[start_index:end]:
        if "xfail" in line and "strict=True" in line:
            return True
    return False


def test_quarantined_requires_strict_xfail_or_quarantine_folder() -> None:
    """Quarantined tests must be strict xfail or live under tests/quarantine/."""
    tests_root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in tests_root.rglob("test_*.py"):
        rel = path.as_posix()
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for idx, line in enumerate(lines):
            if "pytest.mark.quarantined" not in line:
                continue
            if "/tests/quarantine/" in rel:
                continue
            if not _has_strict_xfail_nearby(lines, idx):
                offenders.append(f"{rel}:{idx + 1} -> {line.strip()}")

    assert not offenders, (
        "Quarantined tests must be marked with xfail(strict=True) or live under "
        "tests/quarantine/. Offenders:\n" + "\n".join(offenders)
    )
