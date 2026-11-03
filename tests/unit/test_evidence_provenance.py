"""Unit tests for shared P2 evidence / provenance helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.provenance import (
    PROVENANCE_SCHEMA_ID,
    attach_provenance,
    evidence_provenance,
)


@pytest.mark.unit
def test_evidence_provenance_filters_blank_quote_ids() -> None:
    env = evidence_provenance(
        source_module="insights",
        quote_ids=["q:1", "  ", "", "q:2"],
        confidence="MEDIUM",
        abstention={"reason": "low_evidence"},
        spans=[{"start": 0.0, "end": 1.0, "text": "hi"}, "skip-me"],  # type: ignore[list-item]
    )
    assert env["schema_id"] == PROVENANCE_SCHEMA_ID
    assert env["quote_ids"] == ["q:1", "q:2"]
    assert env["confidence"] == "medium"
    assert env["abstention"] == {"reason": "low_evidence"}
    assert env["spans"] == [{"start": 0.0, "end": 1.0, "text": "hi"}]


@pytest.mark.unit
def test_attach_provenance_is_shallow_copy() -> None:
    row = {"id": "r1", "text": "hello"}
    env = evidence_provenance(source_module="highlights", quote_ids=["q:9"])
    out = attach_provenance(row, env)
    assert out is not row
    assert out["id"] == "r1"
    assert out["provenance"] == env
    assert "provenance" not in row
    out["provenance"]["quote_ids"].append("mutated")
    assert env["quote_ids"] == ["q:9", "mutated"]
