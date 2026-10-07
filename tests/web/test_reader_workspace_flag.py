"""Theme D reader workspace flag + payload honesty."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.workspaces.flags import reader_workspace_component_enabled
from transcriptx.web.workspaces.reader_bridge import build_reader_workspace_data


def test_reader_flag_default_on(monkeypatch) -> None:
    monkeypatch.delenv("TX_READER_WORKSPACE_COMPONENT", raising=False)
    assert reader_workspace_component_enabled(None) is True


def test_reader_flag_env_rollback(monkeypatch) -> None:
    monkeypatch.setenv("TX_READER_WORKSPACE_COMPONENT", "0")
    assert reader_workspace_component_enabled(None) is False
    monkeypatch.setenv("TX_READER_WORKSPACE_COMPONENT", "false")
    assert reader_workspace_component_enabled(None) is False
    monkeypatch.setenv("TX_READER_WORKSPACE_COMPONENT", "on")
    assert reader_workspace_component_enabled(None) is True


def test_reader_flag_session_override(monkeypatch) -> None:
    monkeypatch.delenv("TX_READER_WORKSPACE_COMPONENT", raising=False)
    assert reader_workspace_component_enabled({"reader_workspace_component": False}) is False


def test_reader_payload_omits_filesystem_path(tmp_path: Path, monkeypatch) -> None:
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"1234")
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")

    class _Ctl:
        def get_audio_path(self, _path: str):
            return audio

        def ffmpeg_available(self) -> bool:
            return True

    monkeypatch.setenv("TRANSCRIPTX_HOST", "127.0.0.1")
    data = build_reader_workspace_data(
        controller=_Ctl(),  # type: ignore[arg-type]
        transcript_path=str(transcript),
        transcript_scope="scope",
        transcript_revision="1:1",
        segments=[
            {
                "text": "hi",
                "start": 0.0,
                "end": 1.0,
                "speaker": "A",
                "words": [{"word": "hi", "start": 0.0, "end": 0.5}],
            }
        ],
        session_state={},
        search_text="",
        show_unnamed=True,
        jump_epoch=0,
        jump_index=None,
        autoplay_jump=False,
    )
    blob = json.dumps(data)
    assert str(audio) not in blob
    assert "file://" not in blob
    assert data["audio_url"] is None or data["audio_url"].startswith(
        "http://127.0.0.1:"
    )
    if data["audio_fingerprint"]:
        assert "/" not in data["audio_fingerprint"]
