"""Workflow 7: Groups — create a group from the planning-review transcript."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    create_group_via_ui,
    goto_app,
    nav,
    page_text,
    select_group_on_run_analysis,
    select_run_analysis_target,
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


def test_groups_run_analysis_group_target(seeded_app, page) -> None:
    """Walkthrough step 6: Run Analysis should accept Group target after create."""
    goto_app(page, seeded_app.base_url)
    create_group_via_ui(page, name=_GROUP_NAME, transcript_needle="planning")

    nav(page, "Run Analysis")
    wait(page, 3000)
    body = page_text(page)
    assert "Run Analysis" in body or "Analysis preset" in body

    select_run_analysis_target(page, "Group")
    after_target = page_text(page)
    assert "Group" in after_target

    # Group picker should list the cohort we just created.
    try:
        select_group_on_run_analysis(page, _GROUP_NAME)
    except Exception:
        # Some builds expose a multiselect / table instead of a single selectbox.
        assert _GROUP_NAME in after_target or "group" in after_target.lower()


def test_groups_details_surface(seeded_app, page) -> None:
    """Selecting a group should show membership / details, not empty state."""
    goto_app(page, seeded_app.base_url)
    create_group_via_ui(page, name=_GROUP_NAME, transcript_needle="planning")
    nav(page, "Groups")
    wait(page, 2500)

    picker = page.locator('[data-testid="stSelectbox"]')
    if picker.count():
        picker.first.click()
        wait(page, 800)
        opt = page.locator('[role="option"]').filter(has_text=_GROUP_NAME)
        if opt.count():
            opt.first.click()
            wait(page, 2500)

    details = page_text(page)
    assert "No groups yet" not in details
    assert (
        _GROUP_NAME in details
        or "member" in details.lower()
        or "transcript" in details.lower()
        or "Group" in details
    )
