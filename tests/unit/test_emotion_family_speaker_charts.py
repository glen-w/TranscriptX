"""Unit tests for contextual / fine-grained per-speaker label-count charts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.viz_ids import (
    VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL,
    VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER,
    VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL,
    VIZ_FINE_GRAINED_EMOTION_LABELS_SPEAKER,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


def _canonical_row(segment_id: str = "s1") -> dict:
    return {
        "segment_id": segment_id,
        "evaluation_state": "scored",
        "scores": {"joy": 0.9, "anger": 0.05, "neutral": 0.05},
        "scored_text_hash": "abc123",
        "truncated": False,
        "omitted_token_count_lower_bound": 0,
    }


@pytest.mark.unit
def test_contextual_emotion_save_results_emits_global_and_speaker_charts(
    tmp_path,
) -> None:
    from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis

    module = ContextualEmotionAnalysis.__new__(ContextualEmotionAnalysis)
    module.module_name = "contextual_emotion"
    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "_canonical_rows": [_canonical_row()],
        "segments_with_contextual_emotion": [{"id": "s1", "text": "hi"}],
        "global_stats": {},
        "label_counts": {"joy": 3, "anger": 1},
        "speaker_stats": {
            "Alice": {"label_counts": {"joy": 2, "anger": 1}},
            "Bob": {"label_counts": {"joy": 1}},
            "Empty": {"label_counts": {}},
        },
        "warnings": [],
        "release_channel": "experimental",
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    with patch(
        "transcriptx.core.analysis.contextual_emotion.write_enriched_transcript"
    ):
        module._save_results(results, output_service)

    specs = [c.args[0] for c in output_service.save_chart.call_args_list]
    assert all(isinstance(s, BarCategoricalSpec) for s in specs)
    by_viz = {}
    for spec in specs:
        by_viz.setdefault(spec.viz_id, []).append(spec)

    assert len(by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL]) == 1
    global_spec = by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL][0]
    assert global_spec.scope == "global"
    assert global_spec.categories == ["anger", "joy"]

    speaker_specs = by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER]
    assert {s.speaker for s in speaker_specs} == {"Alice", "Bob"}
    assert all(s.scope == "speaker" for s in speaker_specs)
    alice = next(s for s in speaker_specs if s.speaker == "Alice")
    assert alice.categories == ["anger", "joy"]
    assert alice.values == [1.0, 2.0]


@pytest.mark.unit
def test_fine_grained_emotion_save_results_emits_global_and_speaker_charts(
    tmp_path,
) -> None:
    from transcriptx.core.analysis.fine_grained_emotion import (
        FineGrainedEmotionAnalysis,
    )

    module = FineGrainedEmotionAnalysis.__new__(FineGrainedEmotionAnalysis)
    module.module_name = "fine_grained_emotion"
    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "b1c2d3e4f5a60718293a4b5c6d7e8f91",
        "_canonical_rows": [_canonical_row()],
        "segments_with_fine_grained_emotion": [{"id": "s1", "text": "hi"}],
        "global_stats": {},
        "native_label_prevalence": {"approval": 5, "curiosity": 2, "neutral": 10},
        "speaker_stats": {
            "Alice": {"label_counts": {"approval": 3, "curiosity": 1}},
            "Bob": {"label_counts": {"neutral": 4}},
            "Empty": {"label_counts": {}},
        },
        "warnings": [],
        "release_channel": "experimental",
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    with patch(
        "transcriptx.core.analysis.fine_grained_emotion.write_enriched_transcript"
    ):
        module._save_results(results, output_service)

    specs = [c.args[0] for c in output_service.save_chart.call_args_list]
    assert all(isinstance(s, BarCategoricalSpec) for s in specs)
    by_viz = {}
    for spec in specs:
        by_viz.setdefault(spec.viz_id, []).append(spec)

    assert len(by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL]) == 1
    global_spec = by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL][0]
    assert global_spec.scope == "global"
    assert global_spec.categories == ["neutral", "approval", "curiosity"]

    speaker_specs = by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_SPEAKER]
    assert {s.speaker for s in speaker_specs} == {"Alice", "Bob"}
    assert all(s.scope == "speaker" for s in speaker_specs)
    alice = next(s for s in speaker_specs if s.speaker == "Alice")
    assert alice.categories == ["approval", "curiosity"]
    assert alice.values == [3.0, 1.0]
