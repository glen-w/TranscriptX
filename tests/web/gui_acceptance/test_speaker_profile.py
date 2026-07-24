"""Journey 4: Speakers directory opens a seeded profile."""

from __future__ import annotations

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_page,
    seed_speaker_profile,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]


def test_open_speaker_profile(gui_ws, tmp_path) -> None:
    ws = seed_speaker_profile(gui_ws, name="Ada Lovelace")
    assert ws.profile_id

    at = run_page(
        "transcriptx.web.page_modules.speakers",
        "render_speakers_page",
        session={
            "page": "Speakers",
            "speakers_selected_profile": ws.profile_id,
        },
        default_timeout=60.0,
        script_dir=tmp_path / "apptest_scripts",
    )
    assert_no_exception(at)
    blob = markdown_blob(at)
    assert "Speakers" in blob
    assert "Ada" in blob or ws.profile_id in blob or at.selectbox
