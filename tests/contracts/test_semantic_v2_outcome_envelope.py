"""Single-speaker motif-only envelope for semantic_similarity_v2 (B14)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from transcriptx.core.analysis.semantic_similarity_v2.analysis import (
    SemanticSimilarityV2Analysis,
)
from transcriptx.core.analysis.semantic_similarity_v2.output import SCHEMA_VERSION


def test_semantic_similarity_v2_single_speaker_skip_envelope_contract(
    monkeypatch,
) -> None:
    """B14: single speaker skips repetition path but still exports motif envelope."""
    stored: dict[str, dict] = {}
    context = SimpleNamespace(
        transcript_path="/tmp/input.json",
        get_segments=lambda: [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "one two three four"},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "four five six seven"},
        ],
        store_analysis_result=lambda name, payload: stored.setdefault(name, payload),
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        get_analysis_result=lambda _m: None,
    )
    fake_out = MagicMock()
    fake_out.get_artifacts.return_value = []
    fake_out.base_name = "input"
    monkeypatch.setattr(
        "transcriptx.core.output.output_service.create_output_service",
        lambda *a, **k: fake_out,
    )
    module = SemanticSimilarityV2Analysis()
    monkeypatch.setattr(module, "save_results", lambda *a, **k: None)
    result = module.run_from_context(context)
    assert result["module_name"] == "semantic_similarity_v2"
    assert result["status"] == "success"
    assert result["metrics"].get("repetition_path_skipped") is True
    assert result["metrics"].get("motif_export_status")
    payload = stored.get("semantic_similarity_v2") or result["payload"]
    assert payload.get("schema_version") == SCHEMA_VERSION
    assert payload.get("repetition_path") == "skipped"
    assert "motif_export_status" in payload
    assert "motifs" in payload
    assert payload.get("total_repetitions", 0) == 0
