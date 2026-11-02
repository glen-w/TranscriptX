"""Speaker ID session keys and voice helpers stay importable from the page."""

from __future__ import annotations

import pytest

from transcriptx.web.page_modules import speaker_id as page
from transcriptx.web.workspaces import speaker_id_session_keys as keys
from transcriptx.web.workspaces import speaker_id_voice as voice


@pytest.mark.unit
def test_speaker_id_page_reexports_session_keys_and_voice() -> None:
    assert page.speaker_idx_key is keys.speaker_idx_key
    assert page.voice_pending_key is keys.voice_pending_key
    assert page.widget_key is keys.widget_key
    assert page._cb_voice_confirm is voice._cb_voice_confirm
    assert page._render_voice_suggestions is voice._render_voice_suggestions
    ns = keys._transcript_ns("/tmp/example.json")
    assert page.speaker_idx_key("/tmp/example.json") == f"sid:{ns}:speaker_idx"
