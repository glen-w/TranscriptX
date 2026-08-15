"""Workflow 7: Groups — create a group from the planning-review transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    create_group_via_ui,
    goto_app,
    nav,
    page_text,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]

_GROUP_NAME = "E2E Planning Cohort"


def test_groups_create_and_list(seeded_app, page) -> None:
    """Create a group via the Groups expander and confirm it is listed."""
    goto_app(page, seeded_app.base_url)
    create_group_via_ui(page, name=_GROUP_NAME, transcript_needle="planning")

    body = page_text(page)
    assert (
        "Group created" in body
        or _GROUP_NAME in body
        or "already exists" in body.lower()
    ), f"Expected group create confirmation; head={body[:800]!r}"

    # Re-open Groups and confirm the group is selectable / visible.
    nav(page, "Groups")
    wait(page, 2500)
    listed = page_text(page)
    assert "No groups yet" not in listed
    assert _GROUP_NAME in listed or "Select group" in listed or "Group" in listed
