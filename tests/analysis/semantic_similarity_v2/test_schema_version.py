"""Schema version helpers for v2 JSON."""

from __future__ import annotations

from transcriptx.core.analysis.semantic_similarity_v2.output import (
    SCHEMA_VERSION,
    reader_accepts_schema,
    with_schema,
)


def test_schema_constant() -> None:
    assert SCHEMA_VERSION == "semantic_similarity_v2.1"


def test_with_schema_injects_version() -> None:
    d = with_schema({"a": 1})
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["a"] == 1


def test_reader_accepts_current_and_minor_future() -> None:
    assert reader_accepts_schema("semantic_similarity_v2.1")
    assert reader_accepts_schema("semantic_similarity_v2.1.99")
    assert not reader_accepts_schema("semantic_similarity_v2.2.0")
