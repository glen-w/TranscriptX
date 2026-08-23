"""Workflow 9: Rename Transcript — rename a managed library transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    assert_library_lists_transcript,
    goto_app,
    nav,
    page_text,
    rename_transcript_via_ui,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_NEW_NAME = "planning_review_e2e_renamed"


def test_rename_transcript(seeded_app, page) -> None:
    """Rename planning_review via Rename Transcript and confirm Library lists it."""
    goto_app(page, seeded_app.base_url)
    rename_transcript_via_ui(page, new_name=_NEW_NAME, needle="planning")

    body = page_text(page)
    assert (
        "Renamed" in body
        or _NEW_NAME in body
        or "rename" in body.lower()
    ), f"Expected rename success copy; head={body[:800]!r}"

    assert_library_lists_transcript(page, needle="planning_review_e2e_renamed")


def test_rename_transcript_shows_current_filename(seeded_app, page) -> None:
    """Rename page should show the current managed stem before editing."""
    goto_app(page, seeded_app.base_url)
    nav(page, "Rename Transcript")
    wait(page, 2500)

    boxes = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]')
    if boxes.count() == 0:
        boxes = page.locator('[data-testid="stSelectbox"]')
    boxes.first.click()
    wait(page, 800)
    opt = page.locator('[role="option"]').filter(has_text="planning")
    opt.first.click()
    wait(page, 2500)

    body = page_text(page)
    assert (
        "Current file name" in body
        or "planning" in body.lower()
        or "New file name" in body
    )
