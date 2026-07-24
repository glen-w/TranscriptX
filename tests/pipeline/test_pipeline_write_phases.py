"""Unit tests for pipeline write-phase helpers and persistence ordering."""

from __future__ import annotations

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
        return tmp_path / "run_results.json"

    def _manifest(**_kwargs):
        order.append("manifest")
        return tmp_path / "manifest.json"

    class _Fin:
        module_results: dict = {}
        manifest_path = tmp_path / "manifest.json"

    def _finalize(**_kwargs):
        order.append("manifest")
        return _Fin()

    monkeypatch.setattr(
        "transcriptx.core.pipeline.pipeline_write_phases.persist_canonical_run_outcomes",
        _results,
    )
    monkeypatch.setattr(
        "transcriptx.core.pipeline.pipeline_write_phases.write_output_manifest",
        _manifest,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.chart_descriptions.coordinator.run_finalization_coordinator",
        _finalize,
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
    assert order[0] == "results"
    assert "manifest" in order
    assert paths["run_results_path"] == tmp_path / "run_results.json"
    assert paths["manifest_path"] == tmp_path / "manifest.json"


@pytest.mark.unit
def test_persist_marks_finalize_modules_pending_before_coordinator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chart_descriptions must not appear as modules_failed mid-finalize."""
    captured: list[dict] = []

    def _results(**kwargs):
        captured.append(kwargs)
        return tmp_path / f"run_results_{len(captured)}.json"

    class _Fin:
        module_results = {
            "chart_descriptions": {"status": "success", "duration_ms": 1.0}
        }
        manifest_path = tmp_path / "manifest.json"

    monkeypatch.setattr(
        "transcriptx.core.pipeline.pipeline_write_phases.persist_canonical_run_outcomes",
        _results,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.chart_descriptions.coordinator.run_finalization_coordinator",
        lambda **_k: _Fin(),
    )

    persist_canonical_results_and_artifacts(
        run_dir=tmp_path,
        run_id="r-fin",
        transcript_key="tk",
        modules_enabled=["stats", "chart_descriptions"],
        results={
            "modules_run": ["stats"],
            "skipped_modules": [],
            "errors": [],
            "module_results": {},
        },
    )

    assert len(captured) >= 2
    first_skipped = captured[0]["skipped_modules"]
    assert any(
        isinstance(s, dict)
        and s.get("module") == "chart_descriptions"
        and s.get("reason") == "pending_finalize"
        for s in first_skipped
    )
    # After finalize, pending placeholder is gone and module is in modules_run
    final = captured[-1]
    assert "chart_descriptions" in final["modules_run"]
    assert not any(
        isinstance(s, dict) and s.get("reason") == "pending_finalize"
        for s in final["skipped_modules"]
    )
