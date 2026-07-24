"""Tests for import orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.io.import_adapters.registry_builtins import build_default_registry
from transcriptx.io.import_core.contracts import ImportOutcome
from transcriptx.io.import_core.orchestrator import run_import_orchestration
from transcriptx.io.transcript_importer import ensure_json_artifact


def test_orchestrator_returns_structured_import_result() -> None:
    fixture = Path("tests/fixtures/vtt/simple.vtt")
    registry = build_default_registry()
    result = run_import_orchestration(source_path=fixture, registry=registry)

    assert result.selected_adapter_id in {"zoom", "vtt"}
    assert result.normalized_segments
    assert result.canonical_document["schema_version"] == 1
    assert result.outcome == ImportOutcome.SUPPORTED_IMPORTABLE
    assert result.normalization_summary.output_segment_count == len(
        result.normalized_segments
    )


def test_orchestrator_recognizes_transcriptx_canonical_artifact(tmp_path: Path) -> None:
    source = Path("tests/fixtures/vtt/simple.vtt")
    canonical = ensure_json_artifact(source)
    copied = tmp_path / "copy.json"
    copied.write_text(Path(canonical).read_text(encoding="utf-8"), encoding="utf-8")

    registry = build_default_registry()
    result = run_import_orchestration(source_path=copied, registry=registry)

    assert result.outcome == ImportOutcome.RECOGNIZED_TRANSCRIPTX_CANONICAL
    assert result.canonical_document["schema_version"] == 1
    assert isinstance(json.dumps(result.canonical_document), str)
