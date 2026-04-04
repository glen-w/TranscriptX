"""Integration tests for pipeline storage + manifest contracts.

These tests exercise run_analysis_pipeline with a real mini transcript fixture while
patching storage roots to a tmp sandbox so processing_state and manifests are written
in an isolated tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from .test_pipeline_risk_integration import (
    _fixture_mini_transcript,
    _patch_output_roots,
)

pytestmark = pytest.mark.integration_core


def _run_minimal_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Run a small stats-only pipeline into tmp outputs root."""
    _patch_output_roots(tmp_path, monkeypatch)
    fixture_path = _fixture_mini_transcript()

    result = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats"],
        persist=False,
    )
    assert result.get("errors") == [], result.get("errors")
    return result


def test_pipeline_run_writes_run_results_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful pipeline run writes run_results.json and manifest.json."""
    result = _run_minimal_pipeline(tmp_path, monkeypatch)
    output_dir = Path(result["output_dir"])
    assert output_dir.is_dir()

    run_results = output_dir / "run_results.json"
    manifest_path = output_dir / "manifest.json"
    assert run_results.is_file()
    assert manifest_path.is_file()

    payload = json.loads(run_results.read_text(encoding="utf-8"))
    assert payload.get("modules_run") == ["stats"]


def test_manifest_artifact_paths_exist_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every artifact rel_path in manifest.json should exist under output_dir."""
    result = _run_minimal_pipeline(tmp_path, monkeypatch)
    output_dir = Path(result["output_dir"])
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts") or []
    assert artifacts, "manifest should contain at least one artifact entry"

    missing = []
    for art in artifacts:
        rel = art.get("rel_path")
        if not rel:
            continue
        candidate = output_dir / rel
        if not candidate.exists():
            missing.append(rel)

    assert not missing, f"Missing artifact paths on disk: {missing}"


def test_run_manifest_input_and_direct_call_share_output_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ManifestInput entrypoint and direct target call both write manifest.json with artifacts."""
    _patch_output_roots(tmp_path, monkeypatch)
    fixture_path = _fixture_mini_transcript()

    manifest = RunManifestInput(
        schema_version=1,
        transcript_path=str(fixture_path.resolve()),
        modules=["stats"],
        mode="quick",
        profile=None,
        skip_confirm=True,
        persist=False,
        run_id=None,
    )
    via_manifest = run_analysis_pipeline(manifest=manifest)
    direct = run_analysis_pipeline(
        target=TranscriptRef(path=str(fixture_path)),
        selected_modules=["stats"],
        persist=False,
    )

    for result in (via_manifest, direct):
        assert result.get("errors") == [], result.get("errors")
        odir = Path(result["output_dir"])
        mpath = odir / "manifest.json"
        assert mpath.is_file()
        payload = json.loads(mpath.read_text(encoding="utf-8"))
        assert isinstance(payload.get("artifacts"), list)
