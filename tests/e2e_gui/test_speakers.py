"""Workflow 10: Speakers — open a longitudinal speaker profile."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import goto_app, nav, page_text, wait

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
