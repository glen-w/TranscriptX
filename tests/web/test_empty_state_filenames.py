"""Empty-state user copy must not leak artifact filenames."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from transcriptx.web.blocks import availability as availability_mod

_WEB = Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "web"
_FILENAME_MARKERS = (".json", "rows.json")


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


@pytest.mark.unit
def test_availability_missing_reason_has_no_filenames() -> None:
    text = availability_mod._missing_artifact_reason(
        deps="x",
        detail="insights/insight_rows.json",
        run_root=None,
        module_deps=("insights",),
        run_results=None,
    )
    assert ".json" not in text
    assert "rows.json" not in text
    assert "This run has no" in text


@pytest.mark.unit
def test_overview_insights_empty_copy_has_no_filenames() -> None:
    offenders: list[str] = []
    for rel in (
        "blocks/availability.py",
        "page_modules/overview.py",
        "page_modules/insights.py",
        "page_modules/charts.py",
    ):
        path = _WEB / rel
        for const in _string_constants(path):
            lowered = const.lower()
            if any(m in lowered for m in _FILENAME_MARKERS) and (
                "this run has no" in lowered
                or "no chart" in lowered
                or "not available" in lowered
            ):
                offenders.append(f"{rel}: {const!r}")
    assert not offenders, "empty-state copy leaked filenames:\n" + "\n".join(offenders)
