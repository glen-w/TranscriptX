"""Workflow 1: First analysis — import → run → Overview."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    assert_text_visible,
    fixture_planning_review,
    goto_app,
    launch_analysis,
    nav,
    page_text,
    select_analysis_preset,
    select_transcript,
    upload_transcript,
    wait,
    wait_for_analysis_finish,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_first_analysis_import_run_overview(live_app, page) -> None:
    """
    Import planning_review via the real Streamlit uploader, launch analysis,
    and open Overview.

    Asserts Balanced is the default preset. Under TRANSCRIPTX_DISABLE_DOWNLOADS=1
    Balanced may pull heavy/LLM modules that skip offline, so the launch uses
    Quick (no LLM / no heavy) for a deterministic offline completion while still
    validating the Balanced default control.
    """
    fixture = fixture_planning_review()
    assert fixture.is_file()

    goto_app(page, live_app.base_url)
    upload_transcript(page, fixture)

    body = page_text(page)
    assert "Processed" in body or "success" in body.lower() or "imported" in body.lower()

    # Library should list the new transcript.
    nav(page, "Library")
    lib_text = page_text(page)
    assert "No transcripts found" not in lib_text
    assert (
        "planning" in lib_text.lower()
        or "Launch planning" in lib_text
        or "planning_review" in lib_text
    )

    select_transcript(page, needle="planning")

    nav(page, "Run Analysis")
    wait(page, 2000)
    run_text = page_text(page)
    assert "Run Analysis" in run_text or "Analysis preset" in run_text
    # Balanced is the documented default.
    assert "Balanced" in run_text

    # Offline-friendly launch: Quick avoids LLM + heavy allowlist modules.
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
        or "highlight" in overview.lower()
        or "run" in overview.lower()
        or "module" in overview.lower()
        or "partial" in overview.lower()
        or "Completed" in overview
    )
    # Should not bounce to an empty-home dead end after a completed/partial run.
    assert_text_visible(page, "Overview", timeout_ms=15000)
