"""Unit tests for pipeline write-phase helpers and persistence ordering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline_write_phases import (
    build_preset_explanation,
    persist_canonical_results_and_artifacts,
    persist_canonical_run_outcomes,
)


@pytest.mark.unit
def test_build_preset_explanation_empty() -> None:
    assert build_preset_explanation([], []) == "Included: none. Excluded: none."


@pytest.mark.unit
def test_build_preset_explanation_dict_and_string_skips() -> None:
    text = build_preset_explanation(
        ["stats", "sentiment"],
        [
            {"module": "acts", "reason": "speaker gate"},
            "legacy_mod",
            {"module": "ner"},  # default reason
            {"not_a_module": True},  # ignored
        ],
    )
    assert text.startswith("Included: stats, sentiment.")
    assert "acts (speaker gate)" in text
    assert "legacy_mod (not in registry)" in text
    assert "ner (Skipped)" in text


@pytest.mark.unit
def test_persist_canonical_run_outcomes_writes_run_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written: dict = {}

    def _fake_write(**kwargs):
        written.update(kwargs)

    monkeypatch.setattr(
        "transcriptx.core.pipeline.pipeline_write_phases.write_run_results_summary",
        _fake_write,
    )
    persist_canonical_run_outcomes(
        run_dir=tmp_path,
        run_id="run-1",
        transcript_key="tk",
        modules_enabled=["stats"],
        modules_run=["stats"],
        skipped_modules=[{"module": "acts", "reason": "gate"}],
        errors=[],
        module_results={"stats": {"ok": True}},
    )
    assert written["run_id"] == "run-1"
    assert written["modules_run"] == ["stats"]
    assert "Included: stats" in written["preset_explanation"]
    assert "acts (gate)" in written["preset_explanation"]


@pytest.mark.unit
def test_persist_canonical_results_and_artifacts_orders_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []

    def _results(**_kwargs):
        order.append("results")

    def _manifest(**_kwargs):
        order.append("manifest")
        return tmp_path / "manifest.json"

    monkeypatch.setattr(
        "transcriptx.core.pipeline.pipeline_write_phases.persist_canonical_run_outcomes",
        _results,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.pipeline_write_phases.write_output_manifest",
        _manifest,
    )
    paths = persist_canonical_results_and_artifacts(
        run_dir=tmp_path,
        run_id="r1",
        transcript_key="tk",
        modules_enabled=["stats"],
        results={
            "modules_run": ["stats"],
            "skipped_modules": [],
            "errors": [],
            "module_results": {},
        },
    )
    assert order == ["results", "manifest"]
    assert paths["run_results_path"] == tmp_path / "run_results.json"
    assert paths["manifest_path"] == tmp_path / "manifest.json"


@pytest.mark.unit
def test_persist_canonical_results_and_artifacts_integration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end write of run_results.json + manifest.json without network."""
    monkeypatch.setattr(
        "transcriptx.core.pipeline.manifest_builder.compute_module_source_hash",
        lambda _module: "hash",
    )
    (tmp_path / "stats").mkdir()
    (tmp_path / "stats" / "note.txt").write_text("x", encoding="utf-8")

    paths = persist_canonical_results_and_artifacts(
        run_dir=tmp_path,
        run_id="run-int",
        transcript_key="tk",
        modules_enabled=["stats"],
        results={
            "modules_run": ["stats"],
            "skipped_modules": [{"module": "acts", "reason": "gate"}],
            "errors": [],
            "module_results": {"stats": {"n": 1}},
        },
    )
    run_results = json.loads(paths["run_results_path"].read_text(encoding="utf-8"))
    assert run_results["run_id"] == "run-int"
    assert run_results["modules_run"] == ["stats"]
    assert paths["manifest_path"] is not None
    assert paths["manifest_path"].exists()
