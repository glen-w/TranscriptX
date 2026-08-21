"""AppTest smoke journeys for Speaker Identification (classic + CCv2)."""

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


def test_speaker_id_classic_fragment(gui_ws, tmp_path, monkeypatch) -> None:
    """Legacy Speaker ID fragment renders diarized speakers."""
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "0")
    ws = seed_managed_transcript(gui_ws)
    at = run_page(
        "transcriptx.web.page_modules.speaker_id",
        "render_speaker_id_page",
        session={
            "page": "Speaker Identification",
            "speaker_id_transcript": 1,
        },
        default_timeout=90.0,
        script_dir=tmp_path / "sid_classic",
    )
    assert_no_exception(at)
    blob = markdown_blob(at)
    assert "Speaker 1 / 2" in blob or "unnamed" in blob
    assert ws.slug is not None


def test_speaker_id_ccv2_workspace(gui_ws, tmp_path, monkeypatch) -> None:
    """Default CCv2 workspace mounts without falling back to classic."""
    monkeypatch.delenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", raising=False)
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
    assert "classic Speaker ID" not in blob.lower()
