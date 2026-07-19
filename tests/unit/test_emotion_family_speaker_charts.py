"""Unit tests for contextual / fine-grained label-count and non-neutral charts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.output_standards import (
    get_global_static_chart_path,
    get_speaker_static_chart_path,
)
from transcriptx.core.utils.viz_ids import (
    VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL,
    VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER,
    VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL,
    VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER,
    VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL,
    VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER,
    VIZ_FINE_GRAINED_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL,
    VIZ_FINE_GRAINED_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER,
    VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL,
    VIZ_FINE_GRAINED_EMOTION_LABELS_SPEAKER,
    VIZ_FINE_GRAINED_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL,
    VIZ_FINE_GRAINED_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER,
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


def _specs_by_viz(output_service: MagicMock) -> dict[str, list[BarCategoricalSpec]]:
    specs = [c.args[0] for c in output_service.save_chart.call_args_list]
    assert all(isinstance(s, BarCategoricalSpec) for s in specs)
    by_viz: dict[str, list[BarCategoricalSpec]] = {}
    for spec in specs:
        by_viz.setdefault(spec.viz_id, []).append(spec)
    return by_viz


def _fine_grained_top15_prevalence() -> dict[str, int]:
    counts = {"neutral": 999}
    high = [
        "admiration",
        "amusement",
        "anger",
        "annoyance",
        "approval",
        "caring",
        "confusion",
        "curiosity",
        "desire",
        "disappointment",
        "disapproval",
        "disgust",
        "embarrassment",
        "excitement",
    ]
    for i, name in enumerate(high):
        counts[name] = 30 - i
    counts["fear"] = 5
    counts["grief"] = 5
    counts["gratitude"] = 4
    return counts


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
        "label_counts": {"joy": 3, "anger": 1, "neutral": 50},
        "speaker_stats": {
            "Alice": {"label_counts": {"joy": 2, "anger": 1, "neutral": 9}},
            "Bob": {"label_counts": {"joy": 1}},
            "Empty": {"label_counts": {}},
            "SPEAKER_00": {"label_counts": {"joy": 4}},
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

    by_viz = _specs_by_viz(output_service)

    inclusive_global = by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL][0]
    assert inclusive_global.categories == ["anger", "joy", "neutral"]

    excl_global = by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL][0]
    assert excl_global.categories == ["anger", "joy"]
    assert excl_global.values == [1.0, 3.0]
    assert excl_global.name == "contextual_emotion_label_counts_excluding_neutral"

    share_global = by_viz[VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL][0]
    assert share_global.categories == excl_global.categories
    assert share_global.values == pytest.approx([0.25, 0.75])
    assert share_global.name == "contextual_emotion_label_share_non_neutral"
    assert share_global.y_label == "Share of non-neutral"

    speaker_inclusive = by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER]
    assert {s.speaker for s in speaker_inclusive} == {"Alice", "Bob"}
    alice_excl = next(
        s
        for s in by_viz[VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER]
        if s.speaker == "Alice"
    )
    assert alice_excl.categories == ["anger", "joy"]
    alice_share = next(
        s
        for s in by_viz[VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER]
        if s.speaker == "Alice"
    )
    assert alice_share.categories == alice_excl.categories
    assert alice_share.values == pytest.approx([1 / 3, 2 / 3])


@pytest.mark.unit
def test_contextual_all_neutral_and_empty_scopes_skip_non_neutral(
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
        "label_counts": {"neutral": 12},
        "speaker_stats": {
            "Alice": {"label_counts": {"neutral": 4}},
            "Bob": {"label_counts": {}},
        },
        "timeline": [{"segment_id": "s1"}],
        "representative_examples": {"neutral": []},
        "warnings": [],
        "release_channel": "experimental",
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    with patch(
        "transcriptx.core.analysis.contextual_emotion.write_enriched_transcript"
    ):
        module._save_results(results, output_service)

    by_viz = _specs_by_viz(output_service)
    assert VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL in by_viz
    assert VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL not in by_viz
    assert VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL not in by_viz
    assert VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER not in by_viz
    assert VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER not in by_viz
    assert output_service.save_data.call_count >= 3  # results + timeline + examples
    output_service.save_summary.assert_called_once()


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

    by_viz = _specs_by_viz(output_service)

    assert by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL][0].categories == [
        "neutral",
        "approval",
        "curiosity",
    ]
    excl = by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL][0]
    assert excl.categories == ["approval", "curiosity"]
    share = by_viz[VIZ_FINE_GRAINED_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL][0]
    assert share.categories == excl.categories
    assert share.values == pytest.approx([5 / 7, 2 / 7])

    speaker_inclusive = by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_SPEAKER]
    assert {s.speaker for s in speaker_inclusive} == {"Alice", "Bob"}
    assert {
        s.speaker
        for s in by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER]
    } == {"Alice"}
    assert VIZ_FINE_GRAINED_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER in by_viz


@pytest.mark.unit
def test_fine_grained_top15_fixture_honours_denominator_and_ties(tmp_path) -> None:
    from transcriptx.core.analysis.fine_grained_emotion import (
        FineGrainedEmotionAnalysis,
    )

    prevalence = _fine_grained_top15_prevalence()
    module = FineGrainedEmotionAnalysis.__new__(FineGrainedEmotionAnalysis)
    module.module_name = "fine_grained_emotion"
    results = {
        "run_status": "complete",
        "usable_output": True,
        "artifact_generation_id": "b1c2d3e4f5a60718293a4b5c6d7e8f91",
        "_canonical_rows": [_canonical_row()],
        "segments_with_fine_grained_emotion": [{"id": "s1", "text": "hi"}],
        "global_stats": {},
        "native_label_prevalence": prevalence,
        "speaker_stats": {
            "Alice": {"label_counts": dict(prevalence)},
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

    by_viz = _specs_by_viz(output_service)
    excl = by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL][0]
    share = by_viz[VIZ_FINE_GRAINED_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL][0]
    assert excl.categories == share.categories
    assert "neutral" not in excl.categories
    assert "grief" not in excl.categories
    assert "gratitude" not in excl.categories
    assert excl.categories[-1] == "fear"
    total = sum(v for k, v in prevalence.items() if k != "neutral")
    assert sum(share.values) < 1.0 - 1e-9
    assert share.values[-1] == pytest.approx(5.0 / total)

    alice_excl = by_viz[VIZ_FINE_GRAINED_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER][0]
    alice_share = by_viz[VIZ_FINE_GRAINED_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER][0]
    assert alice_excl.categories == excl.categories
    assert alice_share.categories == share.categories


@pytest.mark.unit
def test_chart_failure_isolation_does_not_block_remaining_artifacts(tmp_path) -> None:
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
        "label_counts": {"joy": 3, "anger": 1, "neutral": 8},
        "speaker_stats": {
            "Alice": {"label_counts": {"joy": 2, "anger": 1}},
        },
        "timeline": [{"segment_id": "s1"}],
        "representative_examples": {"joy": [{"segment_id": "s1"}]},
        "warnings": [],
        "release_channel": "experimental",
    }
    output_service = MagicMock()
    output_service.get_output_structure.return_value = MagicMock(module_dir=tmp_path)

    fail_once = {"hit": False}

    def flaky_save(spec, chart_type="bar"):
        if (
            not fail_once["hit"]
            and spec.viz_id == VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL
        ):
            fail_once["hit"] = True
            raise RuntimeError("injected chart failure")
        return {"static": None, "dynamic": None}

    output_service.save_chart.side_effect = flaky_save

    with patch(
        "transcriptx.core.analysis.contextual_emotion.write_enriched_transcript"
    ):
        module._save_results(results, output_service)

    by_viz = _specs_by_viz(output_service)
    # Inclusive global still attempted before the failing new chart.
    assert VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL in by_viz
    # Share chart still attempted after the failed exclude-neutral save.
    assert VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL in by_viz
    assert VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER in by_viz
    assert VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER in by_viz
    output_service.save_summary.assert_called_once()
    saved_names = [c.args[1] for c in output_service.save_data.call_args_list]
    assert "contextual_emotion_timeline" in saved_names
    assert "contextual_emotion_examples" in saved_names


@pytest.mark.unit
def test_non_neutral_global_and_speaker_paths_do_not_collide(tmp_path) -> None:
    structure = MagicMock()
    structure.global_static_charts_dir = tmp_path / "global" / "static"
    structure.speaker_static_charts_dir = tmp_path / "speakers"
    slug = "contextual_emotion_label_counts_excluding_neutral"
    global_path = get_global_static_chart_path(structure, None, slug, "bar")
    speaker_path = get_speaker_static_chart_path(structure, None, "Alice", slug, "bar")
    assert global_path is not None and speaker_path is not None
    assert global_path != speaker_path
    assert global_path.name == speaker_path.name
    share_slug = "contextual_emotion_label_share_non_neutral"
    assert slug != share_slug
