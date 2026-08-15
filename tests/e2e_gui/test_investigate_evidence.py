"""Workflow 3: Investigate with evidence — Overview → Insights → Transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    click_section_tab,
    goto_app,
    jump_to_transcript_if_present,
    nav,
    page_text,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_investigate_overview_insights_transcript(seeded_run_app, page) -> None:
    """Orient on Overview, open Insights, then land on Transcript evidence."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")

    nav(page, "Overview")
    wait(page, 3000)
    overview = page_text(page)
    assert "Select a subject" not in overview
    assert "Overview" in overview or "highlight" in overview.lower() or "run" in overview.lower()

    nav(page, "Insights")
    wait(page, 2500)
    click_section_tab(page, "Summary")
    insights = page_text(page)
    assert "Insights" in insights
    assert "Select a subject" not in insights

    # Prefer Highlights if Summary has no jump control.
    jumped = jump_to_transcript_if_present(page)
    if not jumped:
        click_section_tab(page, "Highlights")
        jumped = jump_to_transcript_if_present(page)

    if not jumped:
        nav(page, "Transcript")

    wait(page, 2500)
    transcript = page_text(page)
    assert "Select a subject" not in transcript
    # Evidence loop closed: transcript body or diarized turns visible.
    assert (
        "Transcript" in transcript
        or "SPEAKER_" in transcript
        or "Northwind" in transcript
        or "launch" in transcript.lower()
    )
