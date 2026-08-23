"""README / docs/workflows API walkthrough — managed import then analysis."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLANNING_FIXTURE = (
    _REPO_ROOT / "docs" / "workflows" / "fixtures" / "planning_review.json"
)

pytestmark = [pytest.mark.integration_core, pytest.mark.heavy]


def _patch_workflow_roots(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    from dataclasses import replace

    import transcriptx.core.utils.paths as paths_mod

    data_dir = root / "data"
    transcripts = data_dir / "transcripts"
    outputs = data_dir / "outputs"
    config = root / "config"
    for path in (
        transcripts,
        transcripts / "imports",
        transcripts / "originals",
        transcripts / "metadata",
        transcripts / "metadata" / "speaker_maps",
        outputs,
        config / "profiles",
        data_dir / "state",
        data_dir / "speaker_profiles",
        data_dir / "groups",
    ):
        path.mkdir(parents=True, exist_ok=True)

    built = replace(
        paths_mod.PATHS,
        project_root=root,
        data_dir=data_dir,
        transcripts_dir=transcripts,
        transcripts_imports_dir=transcripts / "imports",
        transcripts_originals_dir=transcripts / "originals",
        transcripts_metadata_dir=transcripts / "metadata",
        transcripts_speaker_maps_dir=transcripts / "metadata" / "speaker_maps",
        outputs_dir=outputs,
        group_outputs_dir=outputs / "groups",
        config_dir=config,
        profiles_dir=config / "profiles",
        speaker_profiles_dir=data_dir / "speaker_profiles",
        state_dir=data_dir / "state",
        processing_state_file=data_dir / "state" / "processing_state.json",
    )
    monkeypatch.setattr(paths_mod, "PATHS", built)
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(outputs))
    monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(transcripts))
    monkeypatch.setenv("TRANSCRIPTX_CONFIG_DIR", str(config))
    monkeypatch.setenv("TRANSCRIPTX_DISABLE_DOWNLOADS", "1")

    for mod_path, attr, value in (
        ("transcriptx.io.managed_import_workflow", "DIARISED_TRANSCRIPTS_DIR", transcripts),
        (
            "transcriptx.io.managed_import_workflow",
            "TRANSCRIPTS_ORIGINALS_DIR",
            transcripts / "originals",
        ),
        ("transcriptx.io.import_admission", "DIARISED_TRANSCRIPTS_DIR", transcripts),
        (
            "transcriptx.io.import_admission",
            "TRANSCRIPTS_IMPORTS_DIR",
            transcripts / "imports",
        ),
        ("transcriptx.io.import_metadata.paths", "DIARISED_TRANSCRIPTS_DIR", transcripts),
        (
            "transcriptx.io.import_metadata.paths",
            "TRANSCRIPTS_METADATA_DIR",
            transcripts / "metadata",
        ),
        ("transcriptx.core.utils.slug_manager", "OUTPUTS_DIR", outputs),
        (
            "transcriptx.core.utils.slug_manager",
            "INDEX_FILE",
            outputs / ".transcriptx_index.json",
        ),
    ):
        module = __import__(mod_path, fromlist=[attr])
        monkeypatch.setattr(module, attr, value)

    return transcripts


def test_readme_managed_import_then_stats_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """README Python snippet: managed import + run_analysis on planning_review."""
    if not _PLANNING_FIXTURE.is_file():
        pytest.skip(f"workflow fixture missing: {_PLANNING_FIXTURE}")

    transcripts = _patch_workflow_roots(monkeypatch, tmp_path)
    staging = transcripts / "imports" / "planning_review.json"
    shutil.copy(_PLANNING_FIXTURE, staging)

    imported = run_managed_import_workflow(staging, overwrite=False)
    assert imported.json_path.exists()

    doc = json.loads(imported.json_path.read_text(encoding="utf-8"))
    assert doc.get("schema_version") == 1
    assert isinstance(doc.get("segments"), list) and doc["segments"]
    meta = doc.get("metadata") or {}
    assert meta.get("title") or "planning" in imported.json_path.stem

    result = run_analysis(
        AnalysisRequest(
            transcript_path=imported.json_path,
            modules=["stats"],
            mode="quick",
            run_label="_readme_workflow_walkthrough",
        )
    )
    assert result.success is True, result.errors
    assert result.status
    run_dir = getattr(result, "run_dir", None)
    assert run_dir is not None and Path(run_dir).is_dir()
    assert (Path(run_dir) / "run_results.json").is_file()


def test_workflow_fixture_has_three_speaker_disagreement_shape() -> None:
    """Planning-review fixture should match walkthrough speaker/disagreement story."""
    if not _PLANNING_FIXTURE.is_file():
        pytest.skip(f"workflow fixture missing: {_PLANNING_FIXTURE}")

    doc = json.loads(_PLANNING_FIXTURE.read_text(encoding="utf-8"))
    speakers = {seg.get("speaker") for seg in doc.get("segments", [])}
    assert len(speakers) >= 3
    text_blob = " ".join(seg.get("text", "") for seg in doc.get("segments", [])).lower()
    assert "northwind" in text_blob
    assert "offline" in text_blob or "shared folders" in text_blob
