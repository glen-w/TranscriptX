"""Projection clearing and import-surface contracts for emotion extract."""

from __future__ import annotations

import copy

import pytest

from transcriptx.core.analysis import emotion as emotion_mod
from transcriptx.core.analysis import contextual_emotion as contextual_mod
from transcriptx.core.analysis import fine_grained_emotion as fine_mod
from transcriptx.core.analysis.contextual_emotion.projections import (
    CONTEXTUAL_PROJECTION_SEGMENT_FIELDS,
    clear_contextual_projection,
)
from transcriptx.core.analysis.emotion.projections import (
    LEXICAL_PROJECTION_SEGMENT_FIELDS,
)
from transcriptx.core.analysis.emotion_family import __all__ as emotion_family_all
from transcriptx.core.analysis.fine_grained_emotion import (
    format_fine_grained_failure_warning,
)
from transcriptx.core.analysis.fine_grained_emotion.projections import (
    FINE_GRAINED_PROJECTION_SEGMENT_FIELDS,
)
from transcriptx.core.analysis.emotion_family.run_status import RunStatus
from transcriptx.core.pipeline.module_registry_specs import MODULE_CLASS_MAP


def _seg_with_all_projections() -> dict:
    seg = {"id": "1", "text": "hi", "speaker": "A"}
    for f in LEXICAL_PROJECTION_SEGMENT_FIELDS:
        seg[f] = f"lex-{f}"
    for f in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
        seg[f] = f"ctx-{f}"
    seg["context_emotion_scores"] = {"joy": 1.0}
    for f in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        seg[f] = f"fg-{f}"
    return seg


@pytest.mark.unit
def test_format_fine_grained_failure_warning_exact_strings():
    assert (
        format_fine_grained_failure_warning("preflight_failed", {"message": "no model"})
        == "preflight_failed: no model"
    )
    assert (
        format_fine_grained_failure_warning(
            "inference_failed", {"message": "cuda boom"}
        )
        == "inference_failed: cuda boom"
    )
    assert (
        format_fine_grained_failure_warning(
            "scorer_cardinality_mismatch", {"expected": 2, "got": 0}
        )
        == "scorer_cardinality_mismatch: expected 2 got 0"
    )
    assert (
        format_fine_grained_failure_warning(
            "invalid_segment_ids", {"message": "duplicate segment_id: x"}
        )
        == "duplicate segment_id: x"
    )


@pytest.mark.unit
def test_contextual_failure_clears_only_owned_fields():
    seg = _seg_with_all_projections()
    before = copy.deepcopy(seg)
    out = contextual_mod.ContextualEmotionAnalysis()._failed(
        [seg],
        "a" * 32,
        RunStatus.FAILED,
        reason="preflight_failed",
        details={"message": "x"},
    )
    assert out["usable_output"] is False
    for f in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
        assert f not in seg
    assert "context_emotion_scores" not in seg
    for f in LEXICAL_PROJECTION_SEGMENT_FIELDS:
        assert seg[f] == before[f]
    for f in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        assert seg[f] == before[f]


@pytest.mark.unit
def test_fine_grained_failure_clears_only_owned_fields():
    seg = _seg_with_all_projections()
    before = copy.deepcopy(seg)
    out = fine_mod.FineGrainedEmotionAnalysis()._failed(
        [seg],
        "a" * 32,
        RunStatus.FAILED,
        reason="preflight_failed",
        details={"message": "x"},
    )
    assert out["warnings"] == ["preflight_failed: x"]
    for f in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        assert f not in seg
    for f in LEXICAL_PROJECTION_SEGMENT_FIELDS:
        assert seg[f] == before[f]
    for f in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
        assert seg[f] == before[f]
    assert seg["context_emotion_scores"] == before["context_emotion_scores"]


@pytest.mark.unit
def test_helper_failure_does_not_clear_projections():
    """ClassifierInferenceFailure is data-only; clearing is producer-local."""
    from transcriptx.core.analysis.emotion_family.classifier_inference import (
        ClassifierInferenceFailure,
    )

    seg = _seg_with_all_projections()
    before = copy.deepcopy(seg)
    _ = ClassifierInferenceFailure(
        kind="failure", reason="inference_failed", details={"message": "x"}
    )
    assert seg == before
    clear_contextual_projection(seg)  # still available and owned-only
    for f in LEXICAL_PROJECTION_SEGMENT_FIELDS:
        assert seg[f] == before[f]


@pytest.mark.unit
def test_emotion_family_all_unchanged_no_new_helpers():
    assert "build_segment_work_items" not in emotion_family_all
    assert "resolve_classifier_scores" not in emotion_family_all
    assert "SegmentWorkItem" not in emotion_family_all


@pytest.mark.unit
def test_producers_import_helpers_as_submodules():
    import transcriptx.core.analysis.emotion_family.work_items as wi
    import transcriptx.core.analysis.emotion_family.classifier_inference as ci

    assert contextual_mod.build_segment_work_items is wi.build_segment_work_items
    assert contextual_mod.resolve_classifier_scores is ci.resolve_classifier_scores
    assert fine_mod.build_segment_work_items is wi.build_segment_work_items
    assert fine_mod.resolve_classifier_scores is ci.resolve_classifier_scores
    assert emotion_mod.build_segment_work_items is wi.build_segment_work_items


@pytest.mark.unit
def test_registry_defining_modules_unchanged():
    assert MODULE_CLASS_MAP["emotion"] == (
        "transcriptx.core.analysis.emotion",
        "EmotionAnalysis",
    )
    assert MODULE_CLASS_MAP["contextual_emotion"] == (
        "transcriptx.core.analysis.contextual_emotion",
        "ContextualEmotionAnalysis",
    )
    assert MODULE_CLASS_MAP["fine_grained_emotion"] == (
        "transcriptx.core.analysis.fine_grained_emotion",
        "FineGrainedEmotionAnalysis",
    )
    assert emotion_mod.EmotionAnalysis.__module__ == (
        "transcriptx.core.analysis.emotion"
    )
    assert contextual_mod.ContextualEmotionAnalysis.__module__ == (
        "transcriptx.core.analysis.contextual_emotion"
    )
    assert fine_mod.FineGrainedEmotionAnalysis.__module__ == (
        "transcriptx.core.analysis.fine_grained_emotion"
    )


@pytest.mark.unit
def test_lexical_cache_lookup_before_work_items():
    """Call-order spy: inference cache load precedes build_segment_work_items."""
    from unittest.mock import patch

    from transcriptx.core.analysis.emotion import EmotionAnalysis
    from transcriptx.core.analysis.emotion.preflight import LexicalPreflightResult
    from transcriptx.core.analysis.emotion_family.work_items import (
        build_segment_work_items as real_build,
    )

    order: list[str] = []

    class _Store:
        def load(self, key):
            order.append("cache_load")
            return None

        def store(self, *a, **k):
            order.append("cache_store")

    def _build(segments):
        order.append("work_items")
        return real_build(segments)

    segs = [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "delighted",
            "language": "en",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    with (
        patch(
            "transcriptx.core.analysis.emotion.run_lexical_preflight",
            return_value=LexicalPreflightResult(True, "ok", nrclex_version="3.0.0"),
        ),
        patch(
            "transcriptx.core.analysis.emotion.build_lexicon_from_nrclex",
            return_value={"delighted": ["joy", "positive"]},
        ),
        patch(
            "transcriptx.core.analysis.emotion.InferenceCacheStore",
            side_effect=lambda root: _Store(),
        ),
        patch(
            "transcriptx.core.analysis.emotion.build_segment_work_items",
            side_effect=_build,
        ),
        patch.dict("sys.modules", {"nrclex": type("M", (), {"NRCLex": object})()}),
    ):
        EmotionAnalysis().analyze(segs)
    assert "cache_load" in order and "work_items" in order
    assert order.index("cache_load") < order.index("work_items")


@pytest.mark.unit
def test_assumed_en_warning_wording_all_producers(tmp_path):
    from tests.unit.emotion_family_char.harness import (
        run_contextual,
        run_fine_grained,
        run_lexical,
    )

    segs = [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "I am delighted",
            "start": 0.0,
            "end": 1.0,
            # no language → assumed_en_missing_metadata
        }
    ]
    expected = "1 segment(s) assumed English (missing language metadata)"
    ctx = run_contextual(segs, tmp_path=tmp_path / "c")
    assert expected in (ctx.get("warnings") or [])
    fg = run_fine_grained(
        [
            {
                "id": "1",
                "speaker": "Alice",
                "text": "I am grateful and joyful",
                "start": 0.0,
                "end": 1.0,
            }
        ],
        tmp_path=tmp_path / "f",
    )
    assert expected in (fg.get("warnings") or [])
    lex = run_lexical(
        [
            {
                "id": "1",
                "speaker": "Alice",
                "text": "delighted",
                "start": 0.0,
                "end": 1.0,
            }
        ],
        tmp_path=tmp_path / "l",
    )
    assert expected in (lex.get("warnings") or [])


@pytest.mark.unit
def test_pending_projection_segment_identity_and_ordered_ids(tmp_path):
    from tests.unit.emotion_family_char.harness import run_contextual, segs_success

    segs = segs_success()
    out = run_contextual(segs, tmp_path=tmp_path)
    assert out["ordered_segment_ids"] == ["1", "2"]
    pending = out.get("_pending_projections") or []
    assert pending
    for seg, proj in pending:
        assert any(seg is s for s in segs)
        assert proj.get("segment_id") in {"1", "2"}


@pytest.mark.unit
def test_generation_ids_on_hit_and_miss_distinct_concepts(tmp_path):
    from tests.unit.emotion_family_char.harness import (
        ARTIFACT_ID,
        run_contextual,
        segs_success,
    )

    miss = run_contextual(segs_success(), tmp_path=tmp_path, uuid_hex=ARTIFACT_ID)
    assert miss["inference_cache_hit"] is False
    assert (
        miss["artifact_generation_id"] == miss["inference_generation_id"] == ARTIFACT_ID
    )
    assert miss["aggregation_cache_key"]  # uses inference id binding

    second = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    hit = run_contextual(segs_success(), tmp_path=tmp_path, uuid_hex=second)
    assert hit["inference_cache_hit"] is True
    assert hit["artifact_generation_id"] == second
    assert hit["inference_generation_id"] == ARTIFACT_ID
    assert hit["artifact_generation_id"] != hit["inference_generation_id"]
    # Aggregation binds to inference id (shared with miss), not the new artifact id.
    assert hit["aggregation_cache_key"] == miss["aggregation_cache_key"]
    assert hit["inference_cache_key"] == miss["inference_cache_key"]


@pytest.mark.unit
def test_speaker_only_change_reuses_inference_busts_aggregation(tmp_path):
    from tests.unit.emotion_family_char.harness import run_contextual, segs_success

    base = segs_success()
    first = run_contextual(base, tmp_path=tmp_path, uuid_hex="a" * 32)
    assert first["inference_cache_hit"] is False
    renamed = [
        {**base[0], "speaker": "Carol"},
        {**base[1], "speaker": "Dave"},
    ]
    second = run_contextual(renamed, tmp_path=tmp_path, uuid_hex="b" * 32)
    assert second["inference_cache_hit"] is True
    assert second["aggregation_cache_hit"] is False
    assert first["inference_cache_key"] == second["inference_cache_key"]
    assert first["aggregation_cache_key"] != second["aggregation_cache_key"]


@pytest.mark.unit
def test_timeline_only_change_reuses_inference_busts_aggregation(tmp_path):
    from tests.unit.emotion_family_char.harness import run_contextual, segs_success

    base = segs_success()
    run_contextual(base, tmp_path=tmp_path, uuid_hex="a" * 32)
    retimed = [
        {**base[0], "start": 10.0, "end": 11.0},
        {**base[1], "start": 20.0, "end": 21.0},
    ]
    second = run_contextual(retimed, tmp_path=tmp_path, uuid_hex="b" * 32)
    assert second["inference_cache_hit"] is True
    assert second["aggregation_cache_hit"] is False


@pytest.mark.unit
def test_threshold_only_change_reuses_inference_busts_aggregation(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch

    from transcriptx.core.analysis.hf_text_classification.profiles import (
        CONTEXTUAL_HARTMANN_V1 as PROF,
    )
    from tests.unit.emotion_family_char import harness as H
    from tests.unit.emotion_family_char.harness import (
        run_contextual,
        segs_success,
        _loaded,
    )

    # First run at threshold 0.3
    first = run_contextual(segs_success(), tmp_path=tmp_path, uuid_hex="a" * 32)
    assert first["inference_cache_hit"] is False

    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            contextual_emotion=SimpleNamespace(
                profile_id=PROF.profile_id,
                confidence_threshold=0.9,
                batch_size=8,
            )
        )
    )
    segs = segs_success()
    inf_p, agg_p = H._cache_root_patches("contextual_emotion", tmp_path)
    with (
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
        patch(
            "transcriptx.core.analysis.contextual_emotion.load_classifier",
            return_value=_loaded(PROF),
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.score_texts",
            side_effect=AssertionError("must reuse inference cache"),
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.library_versions",
            return_value={"transformers_version": "0.0", "torch_version": "0.0"},
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.uuid.uuid4",
            side_effect=H._uuid_hex_factory("b" * 32),
        ),
        inf_p,
        agg_p,
    ):
        from transcriptx.core.analysis.contextual_emotion import (
            ContextualEmotionAnalysis,
        )

        out = ContextualEmotionAnalysis().analyze(segs)
    assert out["inference_cache_hit"] is True
    assert out["aggregation_cache_hit"] is False
    assert out["inference_cache_key"] == first["inference_cache_key"]
    assert out["aggregation_cache_key"] != first["aggregation_cache_key"]


@pytest.mark.unit
def test_empty_vs_non_english_only_producer_aggregation(tmp_path):
    from tests.unit.emotion_family_char.harness import run_contextual

    empty = run_contextual([], tmp_path=tmp_path / "e")
    fr_only = run_contextual(
        [
            {
                "id": "1",
                "speaker": "Alice",
                "text": "Bonjour",
                "language": "fr",
                "start": 0.0,
                "end": 1.0,
            }
        ],
        tmp_path=tmp_path / "f",
    )
    # Both have no English scores, but non-English still records skipped segments.
    assert empty.get("segments_skipped", 0) == 0
    assert fr_only.get("segments_skipped", 0) >= 1
    assert fr_only.get("ordered_segment_ids") == ["1"]
    assert empty.get("ordered_segment_ids") == []


@pytest.mark.unit
def test_work_items_whitespace_only_text_snapshot():
    from transcriptx.core.analysis.emotion_family.work_items import (
        build_segment_work_items,
    )

    work, _ = build_segment_work_items(
        [{"id": "1", "text": "   ", "language": "en", "speaker": "A"}]
    )
    assert work[0].text == ""
    assert work[0].text_hash  # hash of original unstripped whitespace
