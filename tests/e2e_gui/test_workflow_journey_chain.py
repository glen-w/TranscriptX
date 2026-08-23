"""Workflow journey chain — mirrors docs/workflows recommended order (1→3 subset)."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    assert_library_lists_transcript,
    assign_speaker_name,
    fixture_planning_review,
    goto_app,
    launch_analysis,
    nav,
    open_speaker_identification,
    page_text,
    select_analysis_preset,
    select_transcript,
    upload_transcript,
    wait,
    wait_for_analysis_finish,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_workflow_chain_import_name_analyze_overview(live_app, page) -> None:
    """
    Chain workflows 1–2 (partial) and 3 entry: import → name first speaker →
    Quick analysis → Overview landing.

    Uses Quick preset for deterministic offline completion (same rationale as
    test_first_analysis_import_run_overview).
    """
    fixture = fixture_planning_review()
    goto_app(page, live_app.base_url)

    upload_transcript(page, fixture)
    assert_library_lists_transcript(page, needle="planning")

    open_speaker_identification(page, needle="planning")
    assign_speaker_name(page, "Maya Facilitator", advance=False)

    select_transcript(page, needle="planning")
    nav(page, "Run Analysis")
    wait(page, 3000)
    select_analysis_preset(page, "Quick")
    launch_analysis(page)
    wait_for_analysis_finish(page, timeout_ms=300000)

    nav(page, "Overview")
    wait(page, 3000)
    overview = page_text(page)
    assert "Select a subject" not in overview
    assert (
        "Overview" in overview
        or "At a glance" in overview
        or "run" in overview.lower()
        or "module" in overview.lower()
    )

    nav(page, "Transcript")
    wait(page, 3000)
    transcript = page_text(page)
    assert "Maya Facilitator" in transcript or "SPEAKER_" in transcript
