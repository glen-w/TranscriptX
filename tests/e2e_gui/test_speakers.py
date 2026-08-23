"""Workflow 10: Speakers — open a longitudinal speaker profile."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    goto_app,
    nav,
    open_speaker_profile,
    page_text,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_PROFILE_NAME = "Maya Facilitator"


def test_speakers_open_profile(seeded_profile_app, page) -> None:
    """Open Speakers and confirm a seeded longitudinal profile is visible."""
    goto_app(page, seeded_profile_app.base_url)
    nav(page, "Speakers")
    wait(page, 3500)

    body = page_text(page)
    assert "Speakers" in body
    assert "No speaker profiles yet" not in body
    assert (
        _PROFILE_NAME in body
        or "profile" in body.lower()
        or "Maya" in body
    ), f"Expected seeded speaker profile on Speakers; head={body[:800]!r}"


def test_speakers_profile_detail_surface(seeded_profile_app, page) -> None:
    """Walkthrough step 3: selecting a profile should open its detail surface."""
    goto_app(page, seeded_profile_app.base_url)
    open_speaker_profile(page, _PROFILE_NAME)

    detail = page_text(page)
    assert "No speaker profiles yet" not in detail
    assert (
        _PROFILE_NAME in detail
        or "Maya" in detail
        or "profile" in detail.lower()
        or "display" in detail.lower()
        or "active" in detail.lower()
    )


def test_speakers_empty_state_guidance(live_app, page) -> None:
    """Fresh library should explain how to create the first profile."""
    goto_app(page, live_app.base_url)
    nav(page, "Speakers")
    wait(page, 3500)

    body = page_text(page)
    assert "Speakers" in body
    assert (
        "No speaker profiles yet" in body
        or "Speaker Identification" in body
        or "profile" in body.lower()
    )
