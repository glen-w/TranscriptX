"""Stage 1: frozen voice_quality.v1 excerpt selection + identity helpers."""

from __future__ import annotations

from transcriptx.core.speaker_profiles.voice.excerpts import select_excerpts_v1
from transcriptx.core.speaker_profiles.voice.ids import (
    compute_embedding_id,
    compute_sample_id,
)
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


def _segs(*pairs: tuple[str, float, float]) -> list[dict]:
    return [
        {"speaker": spk, "start": start, "end": end, "text": "x"}
        for spk, start, end in pairs
    ]


def test_insufficient_speech() -> None:
    result = select_excerpts_v1(
        _segs(("SPEAKER_00", 0.0, 2.0)),
        local_speaker_key="SPEAKER_00",
        normalize_speaker=normalize_diarized_id,
    )
    assert result.outcome == "insufficient_speech"
    assert result.excerpts == ()


def test_display_name_speaker_uses_diarized_id_field() -> None:
    """Remapped UI display names must not starve excerpt selection."""
    segments = [
        {
            "speaker": "Speaker 1",
            "speaker_diarized_id": "SPEAKER_00",
            "start": 0.0,
            "end": 4.0,
            "text": "a",
        },
        {
            "speaker": "Speaker 1",
            "speaker_diarized_id": "SPEAKER_00",
            "start": 5.0,
            "end": 10.0,
            "text": "b",
        },
    ]
    result = select_excerpts_v1(
        segments,
        local_speaker_key="SPEAKER_00",
        normalize_speaker=normalize_diarized_id,
    )
    assert result.outcome == "ok"
    assert len(result.excerpts) >= 1


def test_display_name_only_without_diarized_id_is_insufficient() -> None:
    """Without diarized id, a remapped display name does not match SPEAKER_00."""
    segments = [
        {"speaker": "Speaker 1", "start": 0.0, "end": 10.0, "text": "a"},
    ]
    result = select_excerpts_v1(
        segments,
        local_speaker_key="SPEAKER_00",
        normalize_speaker=normalize_diarized_id,
    )
    assert result.outcome == "insufficient_speech"


def test_stable_excerpt_selection_golden() -> None:
    segments = _segs(
        ("SPEAKER_00", 0.0, 3.0),
        ("SPEAKER_00", 3.1, 6.0),
        ("SPEAKER_00", 10.0, 14.0),
        ("SPEAKER_00", 20.0, 28.0),
        ("SPEAKER_01", 5.5, 5.8),  # small overlap with second block — may drop
    )
    a = select_excerpts_v1(
        segments,
        local_speaker_key="SPEAKER_00",
        normalize_speaker=normalize_diarized_id,
    )
    b = select_excerpts_v1(
        segments,
        local_speaker_key="SPEAKER_00",
        normalize_speaker=normalize_diarized_id,
    )
    assert a.outcome == "ok"
    assert a.excerpts == b.excerpts
    assert a.quality_policy_id == "voice_quality.v1"
    assert len(a.excerpts) >= 1
    assert len(a.excerpts) <= 5


def test_does_not_bridge_other_speakers() -> None:
    # Two target blocks separated by another speaker — must not merge across.
    segments = _segs(
        ("SPEAKER_00", 0.0, 5.0),
        ("SPEAKER_01", 5.05, 5.2),
        ("SPEAKER_00", 5.25, 10.5),
    )
    result = select_excerpts_v1(
        segments,
        local_speaker_key="SPEAKER_00",
        normalize_speaker=normalize_diarized_id,
    )
    assert result.outcome == "ok"
    # No single excerpt may span the other-speaker gap.
    for ex in result.excerpts:
        spans_gap = ex.start < 5.1 and ex.end > 5.15
        assert not spans_gap


def test_sample_id_deterministic_and_stable() -> None:
    kwargs = dict(
        occurrence_fingerprint="occurrence_fingerprint.v1:abc",
        audio_content_sha256="sha256:deadbeef",
        clip_start_us=1_500_000,
        clip_end_us=3_000_000,
        model_generation_id="gen1",
    )
    a = compute_sample_id(**kwargs)
    b = compute_sample_id(**kwargs)
    assert a == b
    assert a != compute_sample_id(**{**kwargs, "clip_end_us": 3_000_001})
    emb = compute_embedding_id(sample_id=a, model_generation_id="gen1")
    assert emb == compute_embedding_id(sample_id=a, model_generation_id="gen1")
    assert emb != compute_embedding_id(sample_id=a, model_generation_id="gen2")
