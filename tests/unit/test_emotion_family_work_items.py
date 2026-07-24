"""Unit tests for emotion_family.work_items."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash
from transcriptx.core.analysis.emotion_family.source_identity import ensure_segment_ids
from transcriptx.core.analysis.emotion_family.work_items import (
    build_segment_work_items,
)


@pytest.mark.unit
def test_work_items_order_and_identity():
    segs = [
        {"id": "a", "speaker": "Alice", "text": " hello ", "language": "en"},
        {"id": "b", "speaker": "Bob", "text": "world", "language": "en"},
    ]
    work, assumed = build_segment_work_items(segs)
    assert assumed == 0
    assert len(work) == 2
    assert work[0].seg is segs[0]
    assert work[1].seg is segs[1]
    assert work[0].text == "hello"
    assert work[0].text_hash == segment_text_hash(" hello ")
    segs[0]["extra"] = 1
    assert work[0].seg["extra"] == 1
    assert work[0].text == "hello"  # scalar snapshot unchanged


@pytest.mark.unit
def test_work_items_missing_id_raises():
    with pytest.raises(ValueError, match="canonical id"):
        build_segment_work_items([{"speaker": "A", "text": "x"}])


@pytest.mark.unit
def test_work_items_none_id_not_str_none():
    # str(None).strip() == "None" must not pass
    with pytest.raises(ValueError):
        build_segment_work_items([{"id": None, "text": "x"}])


@pytest.mark.unit
def test_work_items_id_zero_uses_segment_id():
    seg = {"id": 0, "segment_id": "real", "text": "hi", "language": "en"}
    work, _ = build_segment_work_items([seg])
    # 0 is falsy → segment_id wins
    assert work[0].sid == "real"


@pytest.mark.unit
def test_work_items_whitespace_id_rejected_after_check():
    with pytest.raises(ValueError):
        build_segment_work_items([{"id": "   ", "text": "x"}])


@pytest.mark.unit
def test_work_items_preserves_unnormalized_sid():
    seg = {"id": "  abc  ", "text": "x", "language": "en"}
    # non-empty after strip check, but returned sid is str(raw) without strip
    work, _ = build_segment_work_items([seg])
    assert work[0].sid == "  abc  "


@pytest.mark.unit
def test_ensure_segment_ids_rejects_duplicates_before_helper():
    segs = [
        {"id": "dup", "text": "a", "language": "en"},
        {"id": "dup", "text": "b", "language": "en"},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        ensure_segment_ids(segs)


@pytest.mark.unit
def test_work_items_preserves_duplicate_ids_if_forced():
    segs = [
        {"id": "dup", "text": "a", "language": "en"},
        {"id": "dup", "text": "b", "language": "en"},
    ]
    work, _ = build_segment_work_items(segs)
    assert [w.sid for w in work] == ["dup", "dup"]


@pytest.mark.unit
def test_work_items_assumed_en_and_metadata_once():
    segs = (
        {"id": "1", "speaker": "Alice", "text": "hi"},
        {"id": "2", "speaker": "Bob", "text": "yo", "language": "fr"},
    )
    with patch(
        "transcriptx.core.analysis.emotion_family.work_items.extract_transcript_metadata",
        return_value={},
    ) as meta_spy:
        work, assumed = build_segment_work_items(segs)
    assert meta_spy.call_count == 1
    assert meta_spy.call_args.args[0] is segs
    assert assumed == 1
    assert work[0].lang_res == "assumed_en_missing_metadata"
    assert work[1].lang == "fr"


@pytest.mark.unit
def test_work_items_passes_original_sequence_to_speaker_display():
    segs = ({"id": "1", "speaker": "Alice", "text": "hi", "language": "en"},)
    with patch(
        "transcriptx.core.analysis.emotion_family.work_items.get_speaker_display_name",
        return_value="Alice",
    ) as disp:
        build_segment_work_items(segs)
    assert disp.call_count == 1
    assert disp.call_args.args[2] is segs


@pytest.mark.unit
def test_work_items_non_string_text_raises():
    with pytest.raises(AttributeError):
        build_segment_work_items([{"id": "1", "text": 12345, "language": "en"}])


@pytest.mark.unit
def test_work_items_empty_transcript():
    work, assumed = build_segment_work_items([])
    assert work == ()
    assert assumed == 0
