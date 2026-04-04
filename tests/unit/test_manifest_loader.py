"""
Unit tests for manifest_loader.py: typed manifest loading with validation.

These tests are fast, deterministic, and require no external services.
"""

from __future__ import annotations

import json

import pytest

from transcriptx.core.pipeline.manifest_loader import (
    load_artifact_manifest,
    load_run_outcome_context,
    load_run_results,
    load_run_manifest,
)
from transcriptx.core.pipeline.run_schema import (
    MANIFEST_TYPE_ARTIFACT,
    MANIFEST_TYPE_RUN,
)


def _write_json(path, data):
    path.write_text(json.dumps(data))


class TestLoadArtifactManifest:
    def test_valid_artifact_manifest(self, tmp_path):
        manifest = {
            "manifest_type": MANIFEST_TYPE_ARTIFACT,
            "run_id": "abc123",
            "artifacts": [],
        }
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        result = load_artifact_manifest(path)
        assert result["manifest_type"] == MANIFEST_TYPE_ARTIFACT
        assert result["run_id"] == "abc123"

    def test_missing_manifest_type_raises(self, tmp_path):
        manifest = {"run_id": "abc123", "artifacts": []}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        with pytest.raises(ValueError, match="missing required manifest_type"):
            load_artifact_manifest(path)

    def test_wrong_manifest_type_raises(self, tmp_path):
        manifest = {"manifest_type": MANIFEST_TYPE_RUN, "run_id": "abc123"}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        with pytest.raises(ValueError, match="Expected manifest_type"):
            load_artifact_manifest(path)

    def test_not_json_object_raises(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps([1, 2, 3]))
        with pytest.raises(ValueError, match="not a JSON object"):
            load_artifact_manifest(path)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_artifact_manifest(tmp_path / "missing.json")

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text("{invalid json")
        with pytest.raises(json.JSONDecodeError):
            load_artifact_manifest(path)

    def test_accepts_string_path(self, tmp_path):
        manifest = {"manifest_type": MANIFEST_TYPE_ARTIFACT, "artifacts": []}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        result = load_artifact_manifest(str(path))
        assert result["manifest_type"] == MANIFEST_TYPE_ARTIFACT


class TestLoadRunManifest:
    def test_valid_run_manifest(self, tmp_path):
        manifest = {
            "manifest_type": MANIFEST_TYPE_RUN,
            "run_id": "run-001",
        }
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        result = load_run_manifest(path)
        assert result["manifest_type"] == MANIFEST_TYPE_RUN
        assert result["run_id"] == "run-001"

    def test_missing_manifest_type_raises(self, tmp_path):
        manifest = {"run_id": "run-001"}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        with pytest.raises(ValueError, match="missing required manifest_type"):
            load_run_manifest(path)

    def test_wrong_manifest_type_raises(self, tmp_path):
        manifest = {"manifest_type": MANIFEST_TYPE_ARTIFACT, "run_id": "run-001"}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        with pytest.raises(ValueError, match="Expected manifest_type"):
            load_run_manifest(path)

    def test_not_json_object_raises(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps("just a string"))
        with pytest.raises(ValueError, match="not a JSON object"):
            load_run_manifest(path)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_run_manifest(tmp_path / "missing.json")

    def test_accepts_string_path(self, tmp_path):
        manifest = {"manifest_type": MANIFEST_TYPE_RUN}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        result = load_run_manifest(str(path))
        assert result["manifest_type"] == MANIFEST_TYPE_RUN


class TestLoadRunResults:
    def test_valid_run_results(self, tmp_path):
        payload = {
            "schema_version": 2,
            "run_id": "r1",
            "transcript_key": "t1",
            "modules_enabled": ["stats"],
            "modules_run": ["stats"],
            "modules_skipped": [],
            "modules_failed": [],
            "errors": [],
        }
        path = tmp_path / "run_results.json"
        _write_json(path, payload)
        out = load_run_results(path)
        assert out["run_id"] == "r1"
        assert out["modules_run"] == ["stats"]

    def test_missing_run_id_raises(self, tmp_path):
        payload = {
            "schema_version": 2,
            "transcript_key": "t1",
            "modules_enabled": ["stats"],
            "modules_run": ["stats"],
            "modules_skipped": [],
            "modules_failed": [],
            "errors": [],
        }
        path = tmp_path / "run_results.json"
        _write_json(path, payload)
        with pytest.raises(ValueError, match="run_id"):
            load_run_results(path)

    def test_null_modules_enabled_raises(self, tmp_path):
        payload = {
            "schema_version": 2,
            "run_id": "r1",
            "transcript_key": "t1",
            "modules_enabled": None,
            "modules_run": [],
            "modules_skipped": [],
            "modules_failed": [],
            "errors": [],
        }
        path = tmp_path / "run_results.json"
        _write_json(path, payload)
        with pytest.raises(ValueError, match="null"):
            load_run_results(path)


class TestLoadRunOutcomeContext:
    def test_loads_run_results_and_optional_manifest(self, tmp_path):
        run_results = {
            "schema_version": 2,
            "run_id": "r1",
            "transcript_key": "t1",
            "modules_enabled": ["stats"],
            "modules_run": ["stats"],
            "modules_skipped": [],
            "modules_failed": [],
            "errors": [],
        }
        _write_json(tmp_path / "run_results.json", run_results)
        _write_json(
            tmp_path / "manifest.json",
            {"manifest_type": MANIFEST_TYPE_ARTIFACT, "run_id": "r1", "artifacts": []},
        )
        ctx = load_run_outcome_context(tmp_path)
        assert ctx.run_results["run_id"] == "r1"
        assert ctx.artifact_manifest is not None
