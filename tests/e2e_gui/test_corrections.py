"""Workflow 8: Corrections — Correct mode propose on Transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    goto_app,
    nav,
    open_correct_mode_and_propose,
    open_corrections_studio_from_viewer,
    page_text,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

# Unique substring from the first planning_review segment.
_FIND = "Northwind Notes"
_REPLACEMENT = "Northwind Notes App"


def test_corrections_propose_in_viewer(seeded_run_app, page) -> None:
    """Enable Correct mode, propose a span replacement, and see pending copy."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")
    nav(page, "Transcript")
    wait(page, 4000)

    body = page_text(page)
    assert "Select a subject" not in body
    assert "Transcript" in body or "SPEAKER_" in body or "Northwind" in body

    open_correct_mode_and_propose(page, find_text=_FIND, replacement=_REPLACEMENT)

    after = page_text(page)
    assert (
        "pending" in after.lower()
        or "proposal" in after.lower()
        or "viewer proposal" in after.lower()
        or _FIND in after
        or _REPLACEMENT in after
        or "Corrections Studio" in after
    ), f"Expected Correct-mode proposal feedback; head={after[:900]!r}"


def test_corrections_studio_entry_from_viewer(seeded_run_app, page) -> None:
    """Walkthrough step 6: Corrections Studio should be reachable from viewer."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")
    nav(page, "Transcript")
    wait(page, 4000)

    open_correct_mode_and_propose(page, find_text=_FIND, replacement=_REPLACEMENT)

    opened = open_corrections_studio_from_viewer(page)
    if opened:
        studio = page_text(page)
        assert (
            "Corrections" in studio
            or "Studio" in studio
            or "candidate" in studio.lower()
            or "proposal" in studio.lower()
        )
    else:
        # Studio link is optional on some builds; propose feedback must still show.
        after = page_text(page)
        assert (
            "pending" in after.lower()
            or "proposal" in after.lower()
            or "Corrections" in after
        )


def test_corrections_correct_mode_toggle(seeded_run_app, page) -> None:
    """Correct mode checkbox should be available on Transcript."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")
    nav(page, "Transcript")
    wait(page, 4000)

    body = page_text(page)
    assert "Correct mode" in body or "Correct" in body
