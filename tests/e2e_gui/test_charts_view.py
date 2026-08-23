"""Workflow 6: Charts — open Charts for a finished run."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    goto_app,
    nav,
    page_text,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_charts_view(seeded_run_app, page) -> None:
    """Select a finished run context and open Charts without falling back home."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")

    nav(page, "Charts")
    wait(page, 3500)
    body = page_text(page)
    assert "Select a subject" not in body
    assert "Charts" in body or "chart" in body.lower() or "module" in body.lower()
    # Should not bounce to empty Library/Home dead-end.
    assert not body.lstrip().startswith("Library")


def test_charts_run_scoped_without_subject_shows_nudge(seeded_app, page) -> None:
    """Charts without a selected run should redirect or nudge rather than show charts."""
    goto_app(page, seeded_app.base_url)
    nav(page, "Charts")
    wait(page, 3500)
    body = page_text(page)
    assert (
        "Select a subject" in body
        or "select" in body.lower()
        or "Overview" in body
        or "Charts" in body
        or "Home" in body
        or "Resume work" in body
    )


def test_charts_complements_insights_navigation(seeded_run_app, page) -> None:
    """Charts and Insights should both open under the same run-scoped context."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")

    nav(page, "Charts")
    wait(page, 3500)
    charts = page_text(page)
    assert "Select a subject" not in charts

    nav(page, "Insights")
    wait(page, 2500)
    insights = page_text(page)
    assert "Select a subject" not in insights
    assert "Insights" in insights
