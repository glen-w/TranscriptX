"""Workflow 2: Speaker-aware trust — name speakers and confirm on Transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    fill_assign_name,
    goto_app,
    nav,
    page_text,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_DISPLAY_NAME = "Alex Facilitator"


def test_speaker_trust_name_and_confirm(seeded_app, page) -> None:
    """Name a diarized speaker and confirm the label appears on Transcript."""
    goto_app(page, seeded_app.base_url)
    select_transcript(page, needle="planning")

    nav(page, "Speaker Identification")
    wait(page, 2500)
    sid_text = page_text(page)
    assert "Speaker" in sid_text
    assert "SPEAKER_" in sid_text or "Assign name" in sid_text

    fill_assign_name(page, _DISPLAY_NAME)

    # Advance if Next is available (multi-speaker walkthrough).
    next_btn = page.get_by_role("button", name="Next →", exact=True)
    if next_btn.count():
        try:
            next_btn.first.click(force=True)
            wait(page, 1500)
        except Exception:
            pass

    nav(page, "Transcript")
    wait(page, 3000)
    transcript_text = page_text(page)
    assert "Transcript" in transcript_text or "SPEAKER_" in transcript_text
    assert _DISPLAY_NAME in transcript_text, (
        f"Expected display name {_DISPLAY_NAME!r} on Transcript; "
        f"got head={transcript_text[:600]!r}"
    )
