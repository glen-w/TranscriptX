"""Single-speaker skip envelope for semantic_similarity_v2."""

from __future__ import annotations

from types import SimpleNamespace

from transcriptx.core.analysis.semantic_similarity_v2.analysis import (
    SemanticSimilarityV2Analysis,
)


def test_semantic_similarity_v2_single_speaker_skip_envelope_contract() -> None:
    stored: dict[str, dict] = {}
    context = SimpleNamespace(
        transcript_path="/tmp/input.json",
        get_segments=lambda: [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "one two three"},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "four five six"},
        ],
        store_analysis_result=lambda name, payload: stored.setdefault(name, payload),
    )
    module = SemanticSimilarityV2Analysis()
    result = module.run_from_context(context)
    assert result["module_name"] == "semantic_similarity_v2"
    assert result["status"] == "success"
    assert result["metrics"]["skipped"] is True
    assert result["metrics"]["reason"] == "single_identified_speaker"
    assert stored.get("semantic_similarity_v2") == {}
