"""Tests for web cache helper invalidation."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import transcriptx.web.cache_helpers as mod


def _v1_doc(segments: list) -> dict:
    return {
        "schema_version": 1,
        "source": {
            "type": "manual",
            "original_path": "test.json",
            "imported_at": "2020-01-01T00:00:00+00:00",
        },
        "segments": segments,
    }


def test_segment_signature_excludes_sidecar_summary_includes_it(tmp_path: Path) -> None:
    from transcriptx.io.speaker_map_resolver import sidecar_path_for

    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps(_v1_doc([])), encoding="utf-8")
    seg_before = mod.transcript_segments_signature(transcript)
    sum_before = mod.transcript_summary_signature(transcript)

    sidecar = sidecar_path_for(transcript)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps({"speaker_map_schema_version": 1, "speaker_map": {"SPEAKER_00": "A"}}),
        encoding="utf-8",
    )
    # Ensure sidecar mtime can differ from the transcript write.
    time.sleep(0.01)
    sidecar.write_text(
        json.dumps({"speaker_map_schema_version": 1, "speaker_map": {"SPEAKER_00": "B"}}),
        encoding="utf-8",
    )

    assert mod.transcript_segments_signature(transcript) == seg_before
    assert mod.transcript_summary_signature(transcript) != sum_before
    assert len(mod.transcript_summary_signature(transcript)) == 3
    assert len(mod.transcript_segments_signature(transcript)) == 2


def test_cached_speaker_id_segments_misses_when_transcript_bytes_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        json.dumps(
            _v1_doc(
                [{"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}]
            )
        ),
        encoding="utf-8",
    )
    load_calls = {"n": 0}
    real_load = __import__(
        "transcriptx.io.transcript_loader", fromlist=["load_segments"]
    ).load_segments

    def _counting_load(path, *args, **kwargs):
        load_calls["n"] += 1
        return real_load(path, *args, **kwargs)

    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_segments", _counting_load
    )
    try:
        mod.cached_speaker_id_segments.clear()
    except Exception:
        pass

    path_str = str(transcript.resolve())
    first = mod.cached_speaker_id_segments(
        path_str, mod.transcript_segments_signature(path_str)
    )
    assert first[0].text == "Hello"
    assert load_calls["n"] == 1

    time.sleep(0.01)
    transcript.write_text(
        json.dumps(
            _v1_doc(
                [{"speaker": "SPEAKER_00", "text": "Changed", "start": 0.0, "end": 1.0}]
            )
        ),
        encoding="utf-8",
    )
    second = mod.cached_speaker_id_segments(
        path_str, mod.transcript_segments_signature(path_str)
    )
    assert load_calls["n"] == 2
    assert second[0].text == "Changed"


def test_transcript_segments_signature_fails_closed_on_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        mod.transcript_segments_signature(tmp_path / "nope.json")


def test_cached_get_transcript_summaries_aggregates_per_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Aggregator must call the per-path cache — not one all-paths entry."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")
    calls: list[str] = []

    def _per_path(path_str: str, signature: tuple[int, int, int]):
        calls.append(path_str)

        class _Sum:
            path = Path(path_str)

        return _Sum()

    monkeypatch.setattr(mod, "cached_transcript_summary_for_path", _per_path)
    monkeypatch.setattr(mod, "transcript_summary_signature", lambda _p: (1, 2, 3))
    out = mod.cached_get_transcript_summaries_for_paths((str(a), str(b)))
    assert len(out) == 2
    assert len(calls) == 2
    assert {Path(c).name for c in calls} == {"a.json", "b.json"}


def test_cached_speaker_id_segments_ignores_sidecar_and_hits_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Segments cache must not apply speaker-map remapping; same key hits once."""
    from transcriptx.io.speaker_map_resolver import sidecar_path_for

    transcript = tmp_path / "meeting.json"
    transcript.write_text(
        json.dumps(
            _v1_doc(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    sidecar = sidecar_path_for(transcript)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {
                "speaker_map_schema_version": 1,
                "speaker_map": {"SPEAKER_00": "Alice"},
            }
        ),
        encoding="utf-8",
    )

    load_calls = {"n": 0}
    real_load = __import__(
        "transcriptx.io.transcript_loader", fromlist=["load_segments"]
    ).load_segments

    def _counting_load(path, *args, **kwargs):
        load_calls["n"] += 1
        return real_load(path, *args, **kwargs)

    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_segments", _counting_load
    )
    # Clear any prior Streamlit cache entries for this helper.
    try:
        mod.cached_speaker_id_segments.clear()
    except Exception:
        pass

    path_str = str(transcript.resolve())
    sig = mod.transcript_segments_signature(path_str)
    first = mod.cached_speaker_id_segments(path_str, sig)
    second = mod.cached_speaker_id_segments(path_str, sig)

    assert len(first) == 1
    assert first[0].speaker == "SPEAKER_00"
    assert first[0].speaker_diarized_id == "SPEAKER_00"
    assert first[0].speaker != "Alice"
    assert load_calls["n"] == 1
    assert second[0].speaker == first[0].speaker

    # Sidecar-only change must not change segments signature.
    sidecar.write_text(
        json.dumps(
            {
                "speaker_map_schema_version": 1,
                "speaker_map": {"SPEAKER_00": "Bob"},
            }
        ),
        encoding="utf-8",
    )
    sig2 = mod.transcript_segments_signature(path_str)
    assert sig2 == sig
    third = mod.cached_speaker_id_segments(path_str, sig2)
    assert load_calls["n"] == 1
    assert third[0].speaker == "SPEAKER_00"


def test_clear_transcript_listing_caches_clears_session_list(monkeypatch) -> None:
    cleared: list[str] = []

    def _track_clear(name: str):
        def _clear(*_a, **_k) -> None:
            cleared.append(name)

        return _clear

    monkeypatch.setattr(
        mod,
        "cached_list_available_sessions",
        MagicMock(clear=_track_clear("sessions")),
    )
    monkeypatch.setattr(
        mod,
        "cached_list_transcripts",
        MagicMock(clear=_track_clear("transcripts")),
    )
    monkeypatch.setattr(
        mod,
        "cached_count_managed_transcripts",
        MagicMock(clear=_track_clear("transcript_count")),
    )
    monkeypatch.setattr(
        mod,
        "cached_transcript_summary_for_path",
        MagicMock(clear=_track_clear("per_path_summaries")),
    )
    monkeypatch.setattr(
        mod,
        "cached_speaker_id_segments",
        MagicMock(clear=_track_clear("speaker_id_segments")),
    )
    monkeypatch.setattr(
        mod,
        "cached_list_all_transcript_summaries",
        MagicMock(clear=_track_clear("all_summaries")),
    )
    monkeypatch.setattr(
        mod,
        "_cached_resolve_transcript_path",
        MagicMock(clear=_track_clear("resolve")),
    )
    monkeypatch.setattr(
        mod,
        "_cached_transcript_metadata",
        MagicMock(clear=_track_clear("metadata")),
    )
    monkeypatch.setattr(
        mod,
        "cached_transcript_paths_for_speaker_views",
        MagicMock(clear=_track_clear("speaker_paths")),
    )

    mod.clear_transcript_listing_caches()

    assert cleared == [
        "sessions",
        "transcripts",
        "transcript_count",
        "per_path_summaries",
        "speaker_id_segments",
        "all_summaries",
        "resolve",
        "metadata",
        "speaker_paths",
    ]


def test_cached_speaker_id_segments_prefers_start_ms_end_ms(tmp_path: Path) -> None:
    """Millisecond fields override second-based start/end when both are present."""
    transcript = tmp_path / "ms.json"
    transcript.write_text(
        json.dumps(
            _v1_doc(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 99.0,
                        "end": 100.0,
                        "start_ms": 1500,
                        "end_ms": 2750,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    try:
        mod.cached_speaker_id_segments.clear()
    except Exception:
        pass
    path_str = str(transcript.resolve())
    segs = mod.cached_speaker_id_segments(
        path_str, mod.transcript_segments_signature(path_str)
    )
    assert len(segs) == 1
    assert segs[0].start == pytest.approx(1.5)
    assert segs[0].end == pytest.approx(2.75)


def test_transcript_paths_for_speaker_views_scans_run_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run-dir scan finds transcript JSON and skips manifest/state/report names."""
    outputs = tmp_path / "outputs"
    run_dir = outputs / "meeting-slug" / "run-001"
    run_dir.mkdir(parents=True)
    transcript = run_dir / "meeting-slug-transcript.json"
    transcript.write_text(json.dumps(_v1_doc([])), encoding="utf-8")
    for skip_name in (
        "manifest.json",
        "run_results.json",
        "processing_state.json",
        "report.json",
    ):
        (run_dir / skip_name).write_text("{}", encoding="utf-8")
    nested = run_dir / ".transcriptx"
    nested.mkdir()
    (nested / "should-skip.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "transcriptx.core.utils.paths.OUTPUTS_DIR",
        outputs,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.discover_managed_transcript_paths",
        lambda _cfg: [],
    )
    monkeypatch.setattr(mod, "cached_list_available_sessions", lambda: [])

    found = mod.transcript_paths_for_speaker_views_impl()
    names = {p.name for p in found}
    assert "meeting-slug-transcript.json" in names
    assert names.isdisjoint(
        {
            "manifest.json",
            "run_results.json",
            "processing_state.json",
            "report.json",
            "should-skip.json",
        }
    )


def test_transcript_paths_for_speaker_views_dedupes_managed_and_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same resolved path from managed discovery and run-dir scan is listed once."""
    outputs = tmp_path / "outputs"
    run_dir = outputs / "slug" / "run-a"
    run_dir.mkdir(parents=True)
    transcript = run_dir / "session.json"
    transcript.write_text(json.dumps(_v1_doc([])), encoding="utf-8")

    monkeypatch.setattr("transcriptx.core.utils.paths.OUTPUTS_DIR", outputs)
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.discover_managed_transcript_paths",
        lambda _cfg: [transcript],
    )
    monkeypatch.setattr(mod, "cached_list_available_sessions", lambda: [])

    found = mod.transcript_paths_for_speaker_views_impl()
    assert len(found) == 1
    assert found[0].resolve() == transcript.resolve()
