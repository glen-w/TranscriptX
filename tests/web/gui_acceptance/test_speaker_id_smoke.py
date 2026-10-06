"""AppTest smoke journeys for Speaker Identification (CCv2-only)."""

from __future__ import annotations

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    isolate_workspace,
    markdown_blob,
    run_page,
    seed_managed_transcript,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]


def test_speaker_id_ccv2_workspace(gui_ws, tmp_path, monkeypatch) -> None:
    """CCv2 workspace mounts without a missing-package error."""
    seed_managed_transcript(gui_ws)
    at = run_page(
        "transcriptx.web.page_modules.speaker_id",
        "render_speaker_id_page",
        session={
            "page": "Speaker Identification",
            "speaker_id_transcript": 1,
        },
        default_timeout=90.0,
        script_dir=tmp_path / "sid_ccv2",
    )
    assert_no_exception(at)
    blob = markdown_blob(at)
    assert "transcriptx-workspaces" not in blob.lower() or "requires" not in blob.lower()
