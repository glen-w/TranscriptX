"""Workflow 1: First analysis — import → run → Overview."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    assert_library_lists_transcript,
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
    assert "Processed" in body or "imported_and_registered" in body.lower()

    assert_library_lists_transcript(page, needle="planning")
    select_transcript(page, needle="planning")

    # Prefer Library action when present (passes subject context).
    run_btn = page.get_by_role("button", name="Run Analysis")
    if run_btn.count():
        run_btn.first.click(force=True)
        wait(page, 3500)
    else:
        nav(page, "Run Analysis")
        wait(page, 2000)

    run_text = page_text(page)
    assert "Run Analysis" in run_text or "Analysis preset" in run_text
    assert "Balanced" in run_text

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
    assert_text_visible(page, "Overview", timeout_ms=15000)
