"""PR0 characterization suite for emotion-family producers.

Update goldens (deterministic doubles only)::

    UPDATE_EMOTION_FAMILY_CHARACTERIZATION=1 pytest tests/unit/test_emotion_family_characterization.py -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.emotion.preflight import LexicalPreflightResult
from transcriptx.core.analysis.emotion_family.source_identity import ensure_segment_ids

from tests.unit.emotion_family_char.harness import (
    ARTIFACT_ID,
    assert_generation_id_relationships,
    assert_matches_golden,
    run_contextual,
    run_fine_grained,
    run_lexical,
    segs_empty,
    segs_missing_text,
    segs_mixed_language,
    segs_success,
    segs_whitespace_en,
    segs_whitespace_fr,
    serialize_analyze_result,
)

SECOND_ARTIFACT_ID = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _freeze(name: str, raw: dict, *, cache_hit: bool, cached_id: str | None = None):
    assert_generation_id_relationships(
        raw, expect_cache_hit=cache_hit, cached_inference_id=cached_id
    )
    assert_matches_golden(name, serialize_analyze_result(raw))


# ----- contextual ------------------------------------------------------------


@pytest.mark.unit
def test_char_contextual_success(tmp_path: Path):
    raw = run_contextual(segs_success(), tmp_path=tmp_path)
    assert raw["run_status"] == "complete"
    _freeze("contextual_success", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_empty(tmp_path: Path):
    raw = run_contextual(segs_empty(), tmp_path=tmp_path)
    _freeze("contextual_empty", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_mixed_language(tmp_path: Path):
    raw = run_contextual(segs_mixed_language(), tmp_path=tmp_path)
    assert raw["segments_skipped"] >= 1
    _freeze("contextual_mixed_language", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_cache_miss_then_hit(tmp_path: Path):
    segs = segs_success()
    miss = run_contextual(segs, tmp_path=tmp_path, uuid_hex=ARTIFACT_ID)
    assert miss["inference_cache_hit"] is False
    _freeze("contextual_cache_miss", miss, cache_hit=False)

    hit = run_contextual(
        segs_success(), tmp_path=tmp_path, uuid_hex=SECOND_ARTIFACT_ID
    )
    assert hit["inference_cache_hit"] is True
    _freeze(
        "contextual_cache_hit",
        hit,
        cache_hit=True,
        cached_id=ARTIFACT_ID,
    )


@pytest.mark.unit
def test_char_contextual_preflight_failed(tmp_path: Path):
    raw = run_contextual(
        segs_success(),
        tmp_path=tmp_path,
        load_side_effect=RuntimeError("no model"),
    )
    assert raw["run_status"] == "skipped"
    assert raw.get("preflight_reason") == "preflight_failed"
    _freeze("contextual_preflight_failed", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_invalid_segment_ids(tmp_path: Path):
    segs = [
        {"id": "dup", "speaker": "A", "text": "hi", "language": "en"},
        {"id": "dup", "speaker": "B", "text": "yo", "language": "en"},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        ensure_segment_ids(segs)
    raw = run_contextual(segs, tmp_path=tmp_path)
    assert raw.get("preflight_reason") == "invalid_segment_ids"
    _freeze("contextual_invalid_segment_ids", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_inference_failed(tmp_path: Path):
    raw = run_contextual(
        segs_success(),
        tmp_path=tmp_path,
        score_side_effect=RuntimeError("cuda boom"),
    )
    assert raw.get("preflight_reason") == "inference_failed"
    _freeze("contextual_inference_failed", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_scorer_cardinality_mismatch(tmp_path: Path):
    def _bad(_loaded, texts, max_length=None):
        return []  # wrong length

    raw = run_contextual(segs_success(), tmp_path=tmp_path, score_fn=_bad)
    assert raw.get("preflight_reason") == "scorer_cardinality_mismatch"
    _freeze("contextual_scorer_cardinality_mismatch", raw, cache_hit=False)


@pytest.mark.unit
def test_char_contextual_whitespace_and_missing(tmp_path: Path):
    _freeze(
        "contextual_whitespace_en",
        run_contextual(segs_whitespace_en(), tmp_path=tmp_path),
        cache_hit=False,
    )
    _freeze(
        "contextual_whitespace_fr",
        run_contextual(segs_whitespace_fr(), tmp_path=tmp_path),
        cache_hit=False,
    )
    _freeze(
        "contextual_missing_text",
        run_contextual(segs_missing_text(), tmp_path=tmp_path),
        cache_hit=False,
    )


# ----- fine-grained ----------------------------------------------------------


@pytest.mark.unit
def test_char_fine_grained_success(tmp_path: Path):
    raw = run_fine_grained(segs_success(), tmp_path=tmp_path)
    assert raw["run_status"] == "complete"
    _freeze("fine_grained_success", raw, cache_hit=False)


@pytest.mark.unit
def test_char_fine_grained_empty(tmp_path: Path):
    _freeze(
        "fine_grained_empty",
        run_fine_grained(segs_empty(), tmp_path=tmp_path),
        cache_hit=False,
    )


@pytest.mark.unit
def test_char_fine_grained_mixed_language(tmp_path: Path):
    _freeze(
        "fine_grained_mixed_language",
        run_fine_grained(segs_mixed_language(), tmp_path=tmp_path),
        cache_hit=False,
    )


@pytest.mark.unit
def test_char_fine_grained_cache_miss_then_hit(tmp_path: Path):
    miss = run_fine_grained(segs_success(), tmp_path=tmp_path, uuid_hex=ARTIFACT_ID)
    assert miss["inference_cache_hit"] is False
    _freeze("fine_grained_cache_miss", miss, cache_hit=False)
    hit = run_fine_grained(
        segs_success(), tmp_path=tmp_path, uuid_hex=SECOND_ARTIFACT_ID
    )
    assert hit["inference_cache_hit"] is True
    _freeze(
        "fine_grained_cache_hit",
        hit,
        cache_hit=True,
        cached_id=ARTIFACT_ID,
    )


@pytest.mark.unit
def test_char_fine_grained_preflight_failed(tmp_path: Path):
    raw = run_fine_grained(
        segs_success(),
        tmp_path=tmp_path,
        load_side_effect=RuntimeError("no model"),
    )
    assert raw["run_status"] == "skipped"
    assert "preflight_failed" in (raw.get("warnings") or [""])[0]
    _freeze("fine_grained_preflight_failed", raw, cache_hit=False)


@pytest.mark.unit
def test_char_fine_grained_invalid_segment_ids(tmp_path: Path):
    segs = [
        {"id": "dup", "speaker": "A", "text": "hi", "language": "en"},
        {"id": "dup", "speaker": "B", "text": "yo", "language": "en"},
    ]
    raw = run_fine_grained(segs, tmp_path=tmp_path)
    assert raw["run_status"] == "failed"
    _freeze("fine_grained_invalid_segment_ids", raw, cache_hit=False)


@pytest.mark.unit
def test_char_fine_grained_inference_failed(tmp_path: Path):
    raw = run_fine_grained(
        segs_success(),
        tmp_path=tmp_path,
        score_side_effect=RuntimeError("cuda boom"),
    )
    assert any("inference_failed" in w for w in (raw.get("warnings") or []))
    _freeze("fine_grained_inference_failed", raw, cache_hit=False)


@pytest.mark.unit
def test_char_fine_grained_scorer_cardinality_mismatch(tmp_path: Path):
    def _bad(_loaded, texts, max_length=None):
        return []

    raw = run_fine_grained(segs_success(), tmp_path=tmp_path, score_fn=_bad)
    assert any(
        "scorer_cardinality_mismatch" in w for w in (raw.get("warnings") or [])
    )
    _freeze("fine_grained_scorer_cardinality_mismatch", raw, cache_hit=False)


@pytest.mark.unit
def test_char_fine_grained_whitespace_and_missing(tmp_path: Path):
    _freeze(
        "fine_grained_whitespace_en",
        run_fine_grained(segs_whitespace_en(), tmp_path=tmp_path),
        cache_hit=False,
    )
    _freeze(
        "fine_grained_whitespace_fr",
        run_fine_grained(segs_whitespace_fr(), tmp_path=tmp_path),
        cache_hit=False,
    )
    _freeze(
        "fine_grained_missing_text",
        run_fine_grained(segs_missing_text(), tmp_path=tmp_path),
        cache_hit=False,
    )


# ----- lexical ---------------------------------------------------------------


@pytest.mark.unit
def test_char_lexical_success(tmp_path: Path):
    raw = run_lexical(segs_success(), tmp_path=tmp_path)
    assert raw["run_status"] == "complete"
    _freeze("lexical_success", raw, cache_hit=False)


@pytest.mark.unit
def test_char_lexical_empty(tmp_path: Path):
    _freeze(
        "lexical_empty",
        run_lexical(segs_empty(), tmp_path=tmp_path),
        cache_hit=False,
    )


@pytest.mark.unit
def test_char_lexical_mixed_language(tmp_path: Path):
    raw = run_lexical(segs_mixed_language(), tmp_path=tmp_path)
    assert raw["segments_skipped"] >= 1
    _freeze("lexical_mixed_language", raw, cache_hit=False)


@pytest.mark.unit
def test_char_lexical_cache_miss_then_hit(tmp_path: Path):
    miss = run_lexical(segs_success(), tmp_path=tmp_path, uuid_hex=ARTIFACT_ID)
    assert miss["inference_cache_hit"] is False
    _freeze("lexical_cache_miss", miss, cache_hit=False)
    hit = run_lexical(
        segs_success(), tmp_path=tmp_path, uuid_hex=SECOND_ARTIFACT_ID
    )
    assert hit["inference_cache_hit"] is True
    _freeze("lexical_cache_hit", hit, cache_hit=True, cached_id=ARTIFACT_ID)


@pytest.mark.unit
def test_char_lexical_preflight_failed(tmp_path: Path):
    raw = run_lexical(
        segs_success(),
        tmp_path=tmp_path,
        preflight=LexicalPreflightResult(
            False,
            "lexical_preflight_failed",
            details={"error": "nrclex_not_installed"},
        ),
    )
    assert raw["run_status"] == "skipped"
    assert raw.get("preflight_reason") == "lexical_preflight_failed"
    _freeze("lexical_preflight_failed", raw, cache_hit=False)


@pytest.mark.unit
def test_char_lexical_invalid_segment_ids(tmp_path: Path):
    segs = [
        {"id": "dup", "speaker": "A", "text": "delighted", "language": "en"},
        {"id": "dup", "speaker": "B", "text": "furious", "language": "en"},
    ]
    raw = run_lexical(segs, tmp_path=tmp_path)
    assert raw.get("preflight_reason") == "invalid_segment_ids"
    _freeze("lexical_invalid_segment_ids", raw, cache_hit=False)


@pytest.mark.unit
def test_char_lexical_whitespace_and_missing(tmp_path: Path):
    _freeze(
        "lexical_whitespace_en",
        run_lexical(segs_whitespace_en(), tmp_path=tmp_path),
        cache_hit=False,
    )
    _freeze(
        "lexical_whitespace_fr",
        run_lexical(segs_whitespace_fr(), tmp_path=tmp_path),
        cache_hit=False,
    )
    _freeze(
        "lexical_missing_text",
        run_lexical(segs_missing_text(), tmp_path=tmp_path),
        cache_hit=False,
    )
