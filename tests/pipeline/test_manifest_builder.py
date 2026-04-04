"""Tests for output manifest builder and run results summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.manifest_builder import (
    _infer_kind,
    build_output_manifest,
    build_run_results_summary,
    write_run_results_summary,
)


def test_build_output_manifest_basic(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    module_dir = run_dir / "sentiment" / "data" / "global"
    module_dir.mkdir(parents=True)
    data_path = module_dir / "sample_sentiment_summary.json"
    data_path.write_text("{}")

    meta_dir = run_dir / ".transcriptx"
    meta_dir.mkdir()
    (meta_dir / "run_config_effective.json").write_text(
        json.dumps({"schema_version": 1, "config": {"analysis": {"mode": "quick"}}})
    )

    monkeypatch.setattr(
        "transcriptx.core.pipeline.manifest_builder.compute_module_source_hash",
        lambda module: "hash123",
    )

    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["sentiment"],
    )

    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == "run-1"
    assert manifest["run_metadata"]["transcript_key"] == "tkey"
    assert any(
        a["rel_path"].endswith("sample_sentiment_summary.json")
        for a in manifest["artifacts"]
    )


def test_manifest_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "stats").mkdir()
    (run_dir / "stats" / "report.md").write_text("content")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.manifest_builder.compute_module_source_hash",
        lambda module: "hash123",
    )

    first = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["stats"],
    )
    second = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["stats"],
    )
    assert first["artifacts"] == second["artifacts"]


def test_manifest_tags_eligibility_artifacts(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    g = run_dir / "insight_eligibility" / "data" / "global"
    g.mkdir(parents=True)
    (g / "sample_insight_eligibility.json").write_text("{}")
    (g / "sample_insight_eligibility_tic_mask.json").write_text("{}")
    (g / "sample_insight_eligibility_phrase_scores.json").write_text("{}")
    monkeypatch.setattr(
        "transcriptx.core.pipeline.manifest_builder.compute_module_source_hash",
        lambda module: "hash123",
    )
    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["insight_eligibility"],
    )
    artifacts = {
        Path(a["rel_path"]).name: set(a.get("tags", [])) for a in manifest["artifacts"]
    }
    assert "eligibility" in artifacts["sample_insight_eligibility.json"]
    assert "tic_mask" in artifacts["sample_insight_eligibility_tic_mask.json"]
    assert "phrase_scores" in artifacts["sample_insight_eligibility_phrase_scores.json"]


def test_infer_kind_map_artifacts_use_metadata_and_fallbacks() -> None:
    html_rel = "ner/maps/html/sample-locations-Alice.html"
    png_rel = "ner/maps/images/sample-locations-Alice.png"
    html_parts = html_rel.split("/")
    png_parts = png_rel.split("/")

    assert (
        _infer_kind(html_rel, html_parts, artifact_meta={"render_hint": "dynamic"})
        == "chart_dynamic"
    )
    assert (
        _infer_kind(png_rel, png_parts, artifact_meta={"render_hint": "static"})
        == "chart_static"
    )

    # Partial/absent metadata should still classify correctly via extension/path.
    assert _infer_kind(html_rel, html_parts, artifact_meta={}) == "chart_dynamic"
    assert _infer_kind(png_rel, png_parts, artifact_meta=None) == "chart_static"


# --- build_run_results_summary / write_run_results_summary (high-leverage) ---


@pytest.mark.unit
class TestBuildRunResultsSummary:
    """Unit tests for build_run_results_summary (run_results.json payload)."""

    def test_minimal_payload_has_required_keys(self) -> None:
        payload = build_run_results_summary(
            run_id="run-1",
            transcript_key="tkey",
            modules_enabled=["stats"],
            modules_run=["stats"],
            skipped_modules=[],
            errors=[],
        )
        assert payload["schema_version"] == 2
        assert "module_outcomes" in payload
        assert isinstance(payload["module_outcomes"], list)
        assert payload["run_id"] == "run-1"
        assert payload["transcript_key"] == "tkey"
        assert payload["modules_enabled"] == ["stats"]
        assert payload["modules_run"] == ["stats"]
        assert payload["modules_skipped"] == []
        assert payload["modules_failed"] == []
        assert payload["errors"] == []

    def test_skipped_normalized_and_failed_computed(self) -> None:
        payload = build_run_results_summary(
            run_id="r",
            transcript_key="k",
            modules_enabled=["stats", "sentiment", "emotion"],
            modules_run=["stats"],
            skipped_modules=[{"module": "emotion", "reason": "No model"}],
            errors=[],
        )
        assert payload["modules_run"] == ["stats"]
        assert any(
            s["module"] == "emotion"
            and s["reason"] == "No model"
            and s.get("execution_status") == "skipped"
            for s in payload["modules_skipped"]
        )
        # sentiment not run, not skipped -> failed
        assert "sentiment" in payload["modules_failed"]
        assert "emotion" not in payload["modules_failed"]

    def test_preset_explanation_included_when_provided(self) -> None:
        payload = build_run_results_summary(
            run_id="r",
            transcript_key="k",
            modules_enabled=[],
            modules_run=[],
            skipped_modules=[],
            errors=[],
            preset_explanation="Quick preset",
        )
        assert payload["preset_explanation"] == "Quick preset"

    def test_preset_explanation_absent_when_not_provided(self) -> None:
        payload = build_run_results_summary(
            run_id="r",
            transcript_key="k",
            modules_enabled=[],
            modules_run=[],
            skipped_modules=[],
            errors=[],
        )
        assert "preset_explanation" not in payload

    def test_errors_passed_through(self) -> None:
        payload = build_run_results_summary(
            run_id="r",
            transcript_key="k",
            modules_enabled=["stats"],
            modules_run=[],
            skipped_modules=[],
            errors=["Module stats failed"],
        )
        assert payload["errors"] == ["Module stats failed"]


@pytest.mark.unit
def test_write_run_results_summary_creates_file(tmp_path: Path) -> None:
    """write_run_results_summary writes run_results.json under run_dir."""
    run_dir = tmp_path / "out"
    run_dir.mkdir()
    path = write_run_results_summary(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["stats"],
        modules_run=["stats"],
        skipped_modules=[],
        errors=[],
    )
    assert path is not None
    assert path == run_dir.resolve() / "run_results.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == "run-1"
    assert data["schema_version"] == 2

    # Contract: written payload validates with RunResultsSummary
    from transcriptx.core.pipeline.run_schema import RunResultsSummary

    RunResultsSummary.validate_run_results(data)
