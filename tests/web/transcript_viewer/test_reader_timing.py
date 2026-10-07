"""Theme D reader absolute-time payload tests."""

from __future__ import annotations

import json

from transcriptx.web.transcript_viewer.karaoke_timing import build_reader_segment
from transcriptx.web.workspaces.reader_bridge import build_reader_workspace_data


def test_absolute_timing_past_60s_cap() -> None:
    segment = {
        "text": "late word",
        "start": 0.0,
        "end": 120.0,
        "speaker": "A",
        "words": [
            {"word": "late", "start": 85.0, "end": 90.0},
            {"word": "word", "start": 90.0, "end": 95.0},
        ],
    }
    payload = build_reader_segment(segment, 0)
    assert payload["mode"] == "karaoke"
    assert payload["words"][0]["t0"] == 85.0
    assert payload["words"][0]["t1"] == 90.0


def test_null_word_timing_segment_mode() -> None:
    segment = {
        "text": "hello",
        "start": 0.0,
        "end": 1.0,
        "speaker": "A",
        "words": [{"word": "hello", "start": None, "end": None}],
    }
    payload = build_reader_segment(segment, 0)
    assert payload["mode"] == "segment"
    assert "t0" not in payload["words"][0]


def test_low_coverage_segment_mode() -> None:
    segment = {
        "text": "a b c d",
        "start": 0.0,
        "end": 4.0,
        "speaker": "A",
        "words": [
            {"word": "a", "start": 0.0, "end": 1.0},
            {"word": "b", "start": None, "end": None},
            {"word": "c", "start": None, "end": None},
            {"word": "d", "start": None, "end": None},
        ],
    }
    payload = build_reader_segment(segment, 0)
    assert payload["mode"] == "segment"
    assert all("t0" not in w for w in payload["words"])


def test_empty_words_whitespace_fallback() -> None:
    segment = {"text": "hi there", "start": 0.0, "end": 1.0, "speaker": "A"}
    payload = build_reader_segment(segment, 0)
    assert len(payload["words"]) >= 2
    assert payload["mode"] == "segment"


def test_payload_cap_strips_word_timings(monkeypatch) -> None:
    from transcriptx.web.workspaces import reader_bridge as rb

    monkeypatch.setattr(rb, "_PAYLOAD_CHAR_CAP", 200)
    segments = [
        {
            "text": "word " * 20,
            "start": float(i),
            "end": float(i) + 1,
            "speaker": "S",
            "words": [
                {"word": "word", "start": float(i), "end": float(i) + 0.5},
            ]
            * 5,
        }
        for i in range(30)
    ]

    class _Ctl:
        def get_audio_path(self, _path: str):
            return None

        def ffmpeg_available(self) -> bool:
            return True

    data = build_reader_workspace_data(
        controller=_Ctl(),  # type: ignore[arg-type]
        transcript_path="/tmp/x.json",
        transcript_scope="scope",
        transcript_revision="1:1",
        segments=segments,
        session_state={},
        search_text="",
        show_unnamed=True,
        jump_epoch=0,
        jump_index=None,
        autoplay_jump=False,
    )
    assert data["word_timing_omitted"] is True
    blob = json.dumps(data)
    assert "t0" not in blob
