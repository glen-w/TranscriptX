"""Unit tests for group aggregation schema, common helpers, and warnings."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.aggregation.common import (
    build_rows_from_stats,
    extract_payload,
    warning_payload_shape,
)
from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    session_row_from_result,
)
from transcriptx.core.analysis.aggregation.schema import (
    get_transcript_id,
    serialize_value,
    validate_session_rows,
    validate_speaker_rows,
)
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _result(
    path: str = "/x/a.json",
    key: str = "akey",
    order: int = 0,
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=key,
        run_id="r1",
        order_index=order,
        output_dir="/out",
        module_results={},
    )


@pytest.mark.unit
class TestGetTranscriptId:
    def test_prefers_transcript_id_map(self) -> None:
        ts = TranscriptSet.create(
            ["/x/a.json"],
            metadata={"transcript_id_map": {"/x/a.json": 101}},
        )
        assert get_transcript_id(_result(), ts) == 101

    def test_prefers_transcript_key_map_over_raw_key(self) -> None:
        ts = TranscriptSet.create(
            ["/x/a.json"],
            metadata={"transcript_key_map": {"akey": "mapped-key"}},
        )
        assert get_transcript_id(_result(), ts) == "mapped-key"

    def test_falls_back_to_transcript_key(self) -> None:
        ts = TranscriptSet.create(["/x/a.json"], metadata={})
        assert get_transcript_id(_result(key="fallback-key"), ts) == "fallback-key"

    def test_falls_back_to_stable_hash_when_key_empty(self) -> None:
        ts = TranscriptSet.create(["/x/a.json"], metadata={})
        tid = get_transcript_id(_result(key=""), ts)
        assert isinstance(tid, str)
        assert tid.startswith("txid_v1_")
        assert get_transcript_id(_result(key=""), ts) == tid


@pytest.mark.unit
class TestValidateRows:
    def test_session_rows_missing_and_invalid(self) -> None:
        ok, errors = validate_session_rows(
            [
                {},
                {"transcript_id": "t", "order_index": "0"},
                {"transcript_id": None, "order_index": 1},
                {"transcript_id": "t", "order_index": 2},
            ]
        )
        assert ok is False
        assert any(err.get("missing_keys") for err in errors)
        assert any("order_index" in (err.get("invalid_keys") or {}) for err in errors)
        assert any("transcript_id" in (err.get("invalid_keys") or {}) for err in errors)

    def test_session_rows_ok(self) -> None:
        ok, errors = validate_session_rows([{"transcript_id": "t", "order_index": 0}])
        assert ok is True
        assert errors == []

    def test_speaker_rows_missing_and_invalid(self) -> None:
        ok, errors = validate_speaker_rows(
            [{}, {"canonical_speaker_id": None}, {"canonical_speaker_id": 7}]
        )
        assert ok is False
        assert any(err.get("missing_keys") for err in errors)
        assert any(
            "canonical_speaker_id" in (err.get("invalid_keys") or {}) for err in errors
        )

    def test_speaker_rows_ok(self) -> None:
        ok, errors = validate_speaker_rows([{"canonical_speaker_id": "s1"}])
        assert ok is True
        assert errors == []


@pytest.mark.unit
def test_serialize_value_normalizes_nested() -> None:
    assert serialize_value(None) is None
    assert serialize_value(True) is True
    assert serialize_value({"b": 1, "a": 2}) == '{"a": 2, "b": 1}'
    assert serialize_value([1, 2]) == "[1, 2]"
    assert serialize_value(object).__class__ is str


@pytest.mark.unit
class TestExtractPayloadAndRows:
    def test_extract_payload_variants(self) -> None:
        assert extract_payload({"m": {"payload": {"x": 1}}}, "m") == {"x": 1}
        assert extract_payload({"m": {"results": {"y": 2}}}, "m") == {"y": 2}
        assert extract_payload({"m": "bad"}, "m") == {}
        assert extract_payload({"m": {"payload": "bad"}}, "m") == {}
        assert extract_payload({}, "m") == {}

    def test_build_rows_from_stats_maps_speakers(self) -> None:
        cmap = CanonicalSpeakerMap(
            transcript_to_speakers={"/x/a.json": {"1": 7}},
            canonical_to_display={7: "Alice"},
            transcript_to_display={"/x/a.json": {"1": "Alice"}},
        )
        ts = TranscriptSet.create(["/x/a.json"], metadata={})
        out = build_rows_from_stats(
            _result(),
            ts,
            cmap,
            global_stats={"total": 3},
            speaker_stats={"Alice": {"count": 2}, "skip": "bad"},
        )
        assert out["session_rows"][0]["total"] == 3
        assert out["session_rows"][0]["transcript_id"] == "akey"
        assert len(out["speaker_rows"]) == 1
        assert out["speaker_rows"][0]["canonical_speaker_id"] == 7
        assert out["speaker_rows"][0]["count"] == 2

    def test_display_to_canonical_and_session_row_helper(self) -> None:
        cmap = CanonicalSpeakerMap(
            transcript_to_speakers={"/x/a.json": {"1": 9}},
            canonical_to_display={9: "Bob"},
            transcript_to_display={"/x/a.json": {"1": "Bob"}},
        )
        mapping = _build_display_to_canonical("/x/a.json", cmap)
        assert mapping == {"Bob": 9}
        assert isinstance(_fallback_canonical_id("Zed"), int)
        row = session_row_from_result(
            _result(), TranscriptSet.create(["/x/a.json"]), n=1
        )
        assert row["n"] == 1
        assert row["order_index"] == 0


@pytest.mark.unit
def test_build_warning_and_payload_shape() -> None:
    warning = build_warning(
        code="MISSING_DEP",
        message="need ner",
        aggregation_key="entity_sentiment",
        missing_deps=["ner"],
        transcripts_affected=["a"],
        details={"missing_keys": ["ner"]},
    )
    assert warning["code"] == "MISSING_DEP"
    assert warning["missing_deps"] == ["ner"]
    assert warning["transcripts_affected"] == ["a"]
    shaped = warning_payload_shape("acts", ["global_stats"])
    assert shaped["warning"]["code"] == "PAYLOAD_SHAPE_UNSUPPORTED"
    assert shaped["warning"]["details"]["missing_keys"] == ["global_stats"]
