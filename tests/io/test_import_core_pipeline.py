from __future__ import annotations

from transcriptx.io.import_core.normalization_policy import NormalizationPolicy
from transcriptx.io.import_core import pipeline as mod
from transcriptx.io.intermediate_transcript import (
    IntermediateTranscript,
    IntermediateTurn,
)


def _intermediate(turns):
    return IntermediateTranscript(
        source_tool="stub",
        source_format="json",
        turns=turns,
        source_metadata={},
        warnings=["warn"],
    )


def test_run_normalization_pipeline_applies_sort_drop_and_dedupe(monkeypatch):
    turns = [
        IntermediateTurn(text="a", speaker=" ", start=3.0, end=3.0, turn_index=0),
        IntermediateTurn(
            text="b", speaker="SPEAKER_01", start=2.0, end=3.0, turn_index=1
        ),
    ]
    intermediate = _intermediate(turns)

    monkeypatch.setattr(
        mod.TranscriptNormalizer,
        "normalize",
        lambda self, _i: turns,
    )

    monkeypatch.setattr(
        mod,
        "normalize_speakers",
        lambda _turns: [
            {"start": 3.0, "end": 3.0, "speaker": "S1", "text": "z"},
            {"start": 2.0, "end": 3.0, "speaker": "S2", "text": "x"},
            {"start": 2.0, "end": 3.0, "speaker": "S2", "text": "x"},
        ],
    )

    policy = NormalizationPolicy(
        sort_segments=True,
        drop_zero_length_segments=True,
        dedupe_exact_duplicates=True,
        preserve_empty_speaker_labels=False,
    )

    segments, actions = mod.run_normalization_pipeline(intermediate, policy)
    assert segments == [{"start": 2.0, "end": 3.0, "speaker": "S2", "text": "x"}]
    assert actions["turns_in"] == 2
    assert actions["segments_out"] == 1
    assert actions["warnings_total"] == 1


def test_apply_turn_policies_preserves_empty_when_enabled():
    turns = [IntermediateTurn(text="a", speaker=" ", start=0.0, end=1.0, turn_index=0)]
    policy = NormalizationPolicy(preserve_empty_speaker_labels=True)
    out = mod._apply_turn_policies(turns, policy)
    assert out[0].speaker == " "


def test_dedupe_segments_uses_start_end_speaker_text_keys():
    segs = [
        {"start": 1.0, "end": 2.0, "speaker": "A", "text": "hi"},
        {"start": 1.0, "end": 2.0, "speaker": "A", "text": "hi"},
        {"start": 1.0, "end": 2.0, "speaker": "A", "text": "bye"},
    ]
    out = mod._dedupe_segments(segs)
    assert len(out) == 2
