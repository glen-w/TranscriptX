"""Tests for activation key ownership contract."""

from __future__ import annotations

from pathlib import Path


def test_no_convention_based_activation_key_construction_outside_adapter() -> None:
    src_root = Path(__file__).resolve().parents[3] / "src" / "transcriptx"
    allowed = {
        src_root / "core" / "config" / "profile_target_adapter.py",
        src_root / "core" / "config" / "gui_support.py",
    }
    banned_tokens = (
        'startswith("active_")',
        'endswith("_profile")',
        'f"active_',
        'active_" +',
        '+ "_profile"',
        'removeprefix("analysis.")',
    )

    offenders: list[str] = []
    for path in src_root.rglob("*.py"):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in banned_tokens):
            offenders.append(str(path.relative_to(src_root)))

    assert offenders == []
