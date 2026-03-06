"""
Unit tests for manifest_loader.py: typed manifest loading with validation.

These tests are fast, deterministic, and require no external services.
"""

from __future__ import annotations

import json

import pytest

from transcriptx.core.pipeline.manifest_loader import (
    load_artifact_manifest,
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

    def test_backward_compat_no_manifest_type(self, tmp_path):
        manifest = {"run_id": "abc123", "artifacts": []}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        result = load_artifact_manifest(path)
        assert result["manifest_type"] == MANIFEST_TYPE_ARTIFACT

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

    def test_backward_compat_no_manifest_type(self, tmp_path):
        manifest = {"run_id": "run-001"}
        path = tmp_path / "manifest.json"
        _write_json(path, manifest)
        result = load_run_manifest(path)
        assert result["manifest_type"] == MANIFEST_TYPE_RUN

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
