"""Tests for transcript viewer segment filtering and artifact/nav helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.run_schema import MANIFEST_TYPE_RUN
from transcriptx.web.models.search import NavRequest, SegmentRef, TranscriptRef
from transcriptx.web.transcript_view_state import (
    consume_nav_request,
    filtered_display_segments,
    resolve_transcript_artifacts,
    segment_has_named_speaker,
    transcript_context_result,
)


def test_segment_has_named_speaker_rejects_placeholders() -> None:
    assert segment_has_named_speaker({"speaker": "SPEAKER_02"}) is False
    assert segment_has_named_speaker({"speaker_display": "Alice"}) is True
    assert segment_has_named_speaker({"speaker": "SPEAKER_00", "speaker_display": "Bob"})


def test_filtered_display_segments_excludes_unnamed_by_default() -> None:
    segments = [
        {"speaker": "Alice", "text": "hello"},
        {"speaker": "SPEAKER_02", "text": "subscribe"},
        {"speaker_display": "Bob", "speaker": "SPEAKER_01", "text": "bye"},
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="", jump_index=None
    )
    assert [idx for idx, _ in display] == [0, 2]
    assert caption == "Hiding 1 segment from unnamed speakers"


def test_filtered_display_segments_can_include_unnamed() -> None:
    segments = [
        {"speaker": "Alice", "text": "hello"},
        {"speaker": "SPEAKER_02", "text": "subscribe"},
    ]
    display, caption = filtered_display_segments(
        segments=segments,
        search_text="",
        jump_index=None,
        exclude_unnamed_speakers=False,
    )
    assert len(display) == 2
    assert caption is None


def test_filtered_display_segments_keeps_unnamed_jump_target() -> None:
    segments = [
        {"speaker": "Alice", "text": "hello"},
        {"speaker": "SPEAKER_02", "text": "subscribe"},
        {"speaker": "Bob", "text": "bye"},
        {"speaker": "SPEAKER_03", "text": "hidden neighbor"},
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="", jump_index=1
    )
    # Full transcript stays visible; unnamed jump target kept, other unnamed dropped.
    assert [idx for idx, _ in display] == [0, 1, 2]
    assert caption == "Hiding 1 segment from unnamed speakers"


def test_filtered_display_segments_jump_does_not_narrow_list() -> None:
    segments = [
        {"speaker": "Alice", "text": f"line {i}"} for i in range(8)
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="", jump_index=4
    )
    assert [idx for idx, _ in display] == list(range(8))
    assert caption is None


def test_filtered_display_segments_search_skips_unnamed() -> None:
    segments = [
        {"speaker": "Alice", "text": "please subscribe"},
        {"speaker": "SPEAKER_02", "text": "please subscribe"},
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="subscribe", jump_index=None
    )
    assert [idx for idx, _ in display] == [0]
    assert caption == "Showing 1 of 2 segments"


def test_transcript_context_result_requires_slug_and_run_id() -> None:
    both = transcript_context_result(ok=True, session_slug="meet", run_id="r1")
    assert both.selected_session == "meet/r1"

    slug_only = transcript_context_result(ok=False, session_slug="meet", reason="x")
    assert slug_only.selected_session is None

    run_only = transcript_context_result(ok=False, run_id="r1", reason="x")
    assert run_only.selected_session is None


def test_consume_nav_request_sets_jump_and_clear_flag() -> None:
    nav = NavRequest(
        segment_ref=SegmentRef(
            transcript_ref=TranscriptRef(session_slug="s", run_id="r"),
            primary_locator="index",
            segment_index=4,
        ),
        highlight_query="budget",
    )
    result = consume_nav_request({"nav_request": nav})
    assert result.jump_index == 4
    assert result.highlight_query == "budget"
    assert result.clear_nav_request is True
    assert result.guard_failed is False

    empty = consume_nav_request({})
    assert empty.jump_index is None
    assert empty.highlight_query is None
    assert empty.clear_nav_request is False


def test_resolve_transcript_artifacts_from_manifest_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "outputs" / "meet" / "run-1"
    transcripts = run_root / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "session-a-transcript.txt").write_text("hi", encoding="utf-8")
    (transcripts / "session-a-transcript.csv").write_text("c", encoding="utf-8")
    (transcripts / "session-a-transcript.srt").write_text("1", encoding="utf-8")
    (transcripts / "session-a-transcript.vtt").write_text("WEBVTT\n", encoding="utf-8")

    manifest_dir = run_root / ".transcriptx"
    manifest_dir.mkdir()
    managed = tmp_path / "managed" / "session-a.json"
    managed.parent.mkdir(parents=True)
    managed.write_text("{}", encoding="utf-8")
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_type": MANIFEST_TYPE_RUN,
                "run_id": "run-1",
                "transcript_path": str(managed),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "transcriptx.web.transcript_view_state.DIARISED_TRANSCRIPTS_DIR",
        tmp_path / "managed",
    )

    arts = resolve_transcript_artifacts(
        run_root=run_root, selected_session="meet", run_id="run-1"
    )
    assert arts.txt_file is not None and arts.txt_file.name.endswith(
        "session-a-transcript.txt"
    )
    assert arts.csv_file is not None
    assert arts.srt_file is not None
    assert arts.vtt_file is not None
    assert arts.json_file is not None
    assert arts.json_file.resolve() == managed.resolve()


def test_resolve_transcript_artifacts_falls_back_to_run_id_basename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "outputs" / "meet" / "run-xyz"
    transcripts = run_root / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "run-xyz-transcript.txt").write_text("hi", encoding="utf-8")
    # Corrupt / missing-type manifest must not raise; fall back to run_id stem.
    manifest_dir = run_root / ".transcriptx"
    manifest_dir.mkdir()
    (manifest_dir / "manifest.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.web.transcript_view_state.DIARISED_TRANSCRIPTS_DIR",
        tmp_path / "empty-managed",
    )

    arts = resolve_transcript_artifacts(
        run_root=run_root, selected_session="meet", run_id="run-xyz"
    )
    assert arts.txt_file is not None
    assert arts.txt_file.name == "run-xyz-transcript.txt"
    assert arts.json_file is None
