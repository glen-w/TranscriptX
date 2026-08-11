"""Contract: today's archived GUI perf docs carry the hygiene archive banner."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TODAYS_ARCHIVE_DOCS = (
    "docs/archive/assessments/gui_performance_assessment_2026-08-11.md",
    "docs/archive/assessments/gui_performance_upgrades_2026-08-11.md",
)


@pytest.mark.contract
@pytest.mark.parametrize("rel", TODAYS_ARCHIVE_DOCS)
def test_todays_gui_perf_archive_docs_have_banner(rel: str) -> None:
    text = (ROOT / rel).read_text(encoding="utf-8")[:800]
    assert "Archived / superseded" in text or "[ARCHIVED]" in text
