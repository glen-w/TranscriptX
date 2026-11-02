"""Contract tests for the P2 evidence/provenance envelope."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.provenance import (
    PROVENANCE_SCHEMA_ID,
    evidence_provenance,
)

pytestmark = pytest.mark.contract


def test_envelope_shape() -> None:
    env = evidence_provenance(
        source_module="insights",
        quote_ids=["q:1"],
        confidence="high",
    )
    assert env["schema_id"] == PROVENANCE_SCHEMA_ID
    assert env["source_module"] == "insights"
    assert env["quote_ids"] == ["q:1"]
    assert env["confidence"] == "high"
    assert env["abstention"] is None
    assert env["spans"] == []


def test_invalid_confidence_becomes_null() -> None:
    env = evidence_provenance(source_module="highlights", confidence="nope")
    assert env["confidence"] is None
