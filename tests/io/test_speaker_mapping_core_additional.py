"""Tests for speaker mapping core additional."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.io.speaker_mapping import core as mod
from transcriptx.io.speaker_mapping._types import SpeakerChoice


@pytest.mark.unit
def test_apply_speaker_map_to_data_rewrites_segments_and_db_ids() -> None:
    data = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "a"},
            {"speaker": "SPEAKER_01", "text": "b"},
        ]
    }
    mod._apply_speaker_map_to_data(
        data,
        {"SPEAKER_00": "Alice"},
        speaker_id_to_db_id={"SPEAKER_00": 11},
    )
    assert data["segments"][0]["speaker"] == "Alice"
    assert data["segments"][0]["speaker_db_id"] == 11
    assert data["segments"][1]["speaker"] == "SPEAKER_01"


@pytest.mark.unit
def test_build_speaker_map_returns_empty_for_missing_speakers() -> None:
    segments = [{"text": "x"}, {"speaker": None, "text": "y"}]
    assert mod.build_speaker_map(segments, batch_mode=False) == {}


@pytest.mark.unit
def test_build_speaker_map_batch_mode_persists_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured = {}

    class _Svc:
        def bulk_update(self, transcript_path, speaker_map, ignored, method="batch"):
            captured["transcript_path"] = transcript_path
            captured["speaker_map"] = dict(speaker_map)
            captured["ignored"] = list(ignored)
            captured["method"] = method

    monkeypatch.setattr(
        "transcriptx.services.speaker_studio.SpeakerMappingService",
        _Svc,
    )

    out = mod.build_speaker_map(
        [
            {"speaker": "SPEAKER_00", "text": "a"},
            {"speaker": "SPEAKER_01", "text": "b"},
        ],
        batch_mode=True,
        transcript_path=str(tmp_path / "t.json"),
    )

    assert out == {"SPEAKER_00": "Speaker 1", "SPEAKER_01": "Speaker 2"}
    assert captured["method"] == "batch"
    assert captured["speaker_map"] == out


@pytest.mark.unit
def test_build_speaker_map_interactive_name_and_ignore(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    choices = iter([SpeakerChoice("name", "Alice"), SpeakerChoice("ignore", None)])

    monkeypatch.setattr(mod, "_is_test_environment", lambda: False)
    monkeypatch.setattr(mod, "_select_name_with_playback", lambda **_k: next(choices))
    monkeypatch.setattr(
        mod,
        "resolve_file_path",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no audio")),
    )
    monkeypatch.setattr(
        mod,
        "compute_speaker_stats_from_segments",
        lambda _segs: {
            "SPEAKER_00": {"segment_count": 1, "total_duration": 1.0, "percent": 50.0},
            "SPEAKER_01": {"segment_count": 1, "total_duration": 1.0, "percent": 50.0},
        },
    )

    class _Resolver:
        def load_mapping(self, _path):
            return SimpleNamespace(speaker_map={}, ignored_speakers=[])

    monkeypatch.setattr(mod, "SpeakerMapResolver", _Resolver)

    captured = {}

    class _Svc:
        def bulk_update(
            self, transcript_path, speaker_map, ignored, method="interactive"
        ):
            captured["transcript_path"] = transcript_path
            captured["speaker_map"] = dict(speaker_map)
            captured["ignored"] = list(ignored)
            captured["method"] = method

    monkeypatch.setattr(
        "transcriptx.services.speaker_studio.SpeakerMappingService",
        _Svc,
    )

    result = mod.build_speaker_map(
        [
            {"speaker": "SPEAKER_00", "text": "a", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "b", "start": 1.0, "end": 2.0},
        ],
        batch_mode=False,
        transcript_path=str(tmp_path / "t.json"),
    )

    assert result == {"SPEAKER_00": "Alice"}
    assert captured["method"] == "interactive"
    assert captured["ignored"] == ["SPEAKER_01"]
