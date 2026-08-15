"""Charts view journey — run-scoped Charts page after a completed run."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import goto_app, nav, page_text, select_transcript, wait

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
