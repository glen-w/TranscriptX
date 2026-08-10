"""Theme D karaoke timing and player payload tests."""

from __future__ import annotations

import json

import pytest

from transcriptx.web.transcript_viewer.karaoke_player import (
    TranscriptKaraokeHost,
    build_karaoke_html,
    estimate_karaoke_frame_height,
)
from transcriptx.web.transcript_viewer.karaoke_timing import (
    build_karaoke_clip_model,
    karaoke_words_payload,
)
from transcriptx.web.workspaces.playback_host import word_timing_capability


def _timed_segment() -> dict:
    return {
        "speaker": "SPEAKER_00",
        "speaker_display": "Ada",
        "start": 10.0,
        "end": 14.0,
        "text": "Hello world today",
        "words": [
            {"word": "Hello", "start": 10.0, "end": 10.5},
            {"word": "world", "start": 10.6, "end": 11.2},
            {"word": "today", "start": 11.3, "end": 12.0},
        ],
    }


def test_karaoke_model_rebases_absolute_times_to_clip_relative() -> None:
    model = build_karaoke_clip_model(_timed_segment())
    assert model.mode == "karaoke"
    assert model.capabilities.word_timing_ready is True
    assert model.timed_word_count == 3
    assert model.words[0].t0 == 0.0
    assert model.words[0].t1 == 0.5
    assert model.words[1].t0 == pytest.approx(0.6)
    assert model.words[2].t1 == pytest.approx(2.0)


def test_karaoke_degrades_without_word_timings() -> None:
    segment = {
        "speaker": "A",
        "start": 0.0,
        "end": 2.0,
        "text": "No timings here",
    }
    model = build_karaoke_clip_model(segment)
    assert model.mode == "segment"
    assert model.capabilities.word_timing_ready is False
    assert model.timed_word_count == 0
    assert all(not w.timed for w in model.words)


def test_karaoke_degrades_when_edited_tokens_null_timings() -> None:
    segment = {
        "speaker": "A",
        "start": 1.0,
        "end": 4.0,
        "text": "alpha beta gamma",
        "words": [
            {"word": "alpha", "start": 1.0, "end": 1.4},
            {"word": "beta", "start": None, "end": None},
            {"word": "gamma", "start": None, "end": None},
        ],
    }
    model = build_karaoke_clip_model(segment)
    # 1/3 timed < 0.35 coverage floor → segment mode; never invent timings.
    assert model.mode == "segment"
    assert model.timed_word_count == 1
    assert model.words[0].timed is True
    assert model.words[1].timed is False
    assert model.words[2].timed is False


def test_karaoke_drops_words_outside_playable_clip_window() -> None:
    segment = {
        "speaker": "A",
        "start": 0.0,
        "end": 120.0,
        "text": "early late",
        "words": [
            {"word": "early", "start": 0.0, "end": 0.5},
            {"word": "late", "start": 90.0, "end": 91.0},  # beyond 60s clip cap
        ],
    }
    model = build_karaoke_clip_model(segment)
    assert model.playable_duration == 60.0
    assert model.words[0].timed is True
    assert model.words[1].timed is False
    # coverage 0.5 >= floor → karaoke with one timed word
    assert model.mode == "karaoke"


def test_karaoke_html_escapes_angle_brackets_in_payload() -> None:
    model = build_karaoke_clip_model(_timed_segment())
    html = build_karaoke_html(model, clip_b64="Zm9v", autoplay=True)
    assert "tx-karaoke-payload" in html
    assert "Zm9v" in html
    nasty = {
        "speaker": "A",
        "start": 0.0,
        "end": 2.0,
        "text": "say <b>hi</b> now",
        "words": [
            {"word": "say", "start": 0.0, "end": 0.3},
            {"word": "<b>hi</b>", "start": 0.4, "end": 0.8},
            {"word": "now", "start": 0.9, "end": 1.2},
        ],
    }
    model2 = build_karaoke_clip_model(nasty)
    html2 = build_karaoke_html(model2, clip_b64="YQ==", autoplay=False)
    raw_json = html2.split('id="tx-karaoke-payload">', 1)[1].split("</script>", 1)[0]
    assert "<b>" not in raw_json
    assert "\\u003c" in raw_json
    payload = json.loads(raw_json)
    assert payload["autoplay"] is False
    assert payload["mode"] in {"karaoke", "segment"}


def test_karaoke_words_payload_omits_untimed_keys() -> None:
    model = build_karaoke_clip_model(
        {
            "text": "a b",
            "start": 0,
            "end": 1,
            "words": [
                {"word": "a", "start": 0.0, "end": 0.2},
                {"word": "b"},
            ],
        }
    )
    payload = karaoke_words_payload(model)
    assert "t0" in payload[0] and "t1" in payload[0]
    assert "t0" not in payload[1]


def test_estimate_karaoke_frame_height_bounded() -> None:
    model = build_karaoke_clip_model(_timed_segment())
    h = estimate_karaoke_frame_height(model)
    assert 150 <= h <= 420
    long_model = build_karaoke_clip_model(
        {
            "text": ("word " * 400).strip(),
            "start": 0,
            "end": 1,
        }
    )
    assert estimate_karaoke_frame_height(long_model) == 420


def test_transcript_karaoke_host_binds_capabilities() -> None:
    host = TranscriptKaraokeHost()
    assert host.capabilities().word_timing_ready is False
    assert host.local_current_time_ms() == 0
    host.seek_ms(1500)
    assert host.local_current_time_ms() == 1500
    model = build_karaoke_clip_model(_timed_segment())
    host.bind_model(model)
    assert host.capabilities().word_timing_ready is True
    assert host.capabilities().local_clock_only is True
    host.bind_model(None)
    assert host.capabilities().word_timing_ready is False


def test_set_active_clip_requests_follow_along_scroll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.web.components import playback_panel as panel

    session: dict[str, object] = {}
    monkeypatch.setattr(panel.st, "session_state", session)
    panel.set_active_clip("transcript_viewer_play_seg", 3)
    assert session["transcript_viewer_play_seg"] == 3
    assert session["transcript_viewer_play_seg_scroll_playing"] is True
    assert panel.consume_scroll_playing("transcript_viewer_play_seg", session) is True
    assert panel.consume_scroll_playing("transcript_viewer_play_seg", session) is False


def test_word_timing_capability_helper() -> None:
    assert word_timing_capability(True).word_timing_ready is True
    assert word_timing_capability(False).word_timing_ready is False
