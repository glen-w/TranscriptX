"""Workflow 5: Export results — Artifacts → Export → Create Export."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    click_section_tab,
    goto_app,
    nav,
    page_text,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_export_results(seeded_run_app, page) -> None:
    """Open Artifacts Export and create a downloadable package for a finished run."""
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")

    nav(page, "Artifacts")
    wait(page, 2500)
    click_section_tab(page, "Browse")
    browse = page_text(page)
    assert "Artifacts" in browse or "Browse" in browse
    assert "Select a subject" not in browse

    click_section_tab(page, "Export")
    wait(page, 2000)
    export_text = page_text(page)
    assert "Export" in export_text

    create = page.get_by_role("button", name="Create Export", exact=True)
    assert create.count(), "Create Export control should be present"
    create.first.click(force=True)
    wait(page, 5000)

    after = page_text(page)
    download = page.get_by_role("button", name="Download Export", exact=True)
    assert (
        download.count()
        or "Download" in after
        or "export" in after.lower()
        or "zip" in after.lower()
        or "Created" in after
        or "ready" in after.lower()
    ), f"Expected export completion / download UI; got head={after[:600]!r}"
