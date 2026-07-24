"""
Unit tests for manifest_loader.py: typed manifest loading with validation.

These tests are fast, deterministic, and require no external services.
"""

from __future__ import annotations

import json

import pytest

from transcriptx.core.pipeline.manifest_loader import (
    load_artifact_manifest,
    load_group_member_runs,
    load_group_phase_metadata,
    load_run_outcome_context,
    load_run_results,
    load_run_manifest,
)
from transcriptx.core.pipeline.run_schema import (
    MANIFEST_TYPE_ARTIFACT,
    MANIFEST_TYPE_RUN,
)


def _valid_run_results(**overrides):
    payload = {
        "schema_version": 1,
        "run_id": "r1",
        "transcript_key": "t1",
        "modules_enabled": ["stats"],
        "modules_run": ["stats"],
        "modules_skipped": [],
        "modules_failed": [],
        "errors": [],
    }
    payload.update(overrides)
    return payload


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
        path = tmp_path / "run_results.json"
        _write_json(path, _valid_run_results())
        out = load_run_results(path)
        assert out["run_id"] == "r1"
        assert out["modules_run"] == ["stats"]

    def test_missing_run_id_raises(self, tmp_path):
        path = tmp_path / "run_results.json"
        _write_json(path, _valid_run_results(run_id=None))
        with pytest.raises(ValueError, match="run_id"):
            load_run_results(path)

    def test_empty_run_id_raises(self, tmp_path):
        path = tmp_path / "run_results.json"
        _write_json(path, _valid_run_results(run_id="  "))
        with pytest.raises(ValueError, match="run_id"):
            load_run_results(path)

    def test_empty_transcript_key_raises(self, tmp_path):
        path = tmp_path / "run_results.json"
        _write_json(path, _valid_run_results(transcript_key=""))
        with pytest.raises(ValueError, match="transcript_key"):
            load_run_results(path)

    def test_null_modules_enabled_raises(self, tmp_path):
        path = tmp_path / "run_results.json"
        _write_json(path, _valid_run_results(modules_enabled=None))
        with pytest.raises(ValueError, match="null"):
            load_run_results(path)

    def test_not_json_object_raises(self, tmp_path):
        path = tmp_path / "run_results.json"
        path.write_text(json.dumps(["not", "an", "object"]))
        with pytest.raises(ValueError, match="not a JSON object"):
            load_run_results(path)

    def test_unsupported_schema_version_raises(self, tmp_path):
        path = tmp_path / "run_results.json"
        _write_json(path, _valid_run_results(schema_version=1))
        with pytest.raises(ValueError, match="schema_version"):
            load_run_results(path)


class TestLoadRunOutcomeContext:
    def test_loads_run_results_and_optional_manifest(self, tmp_path):
        _write_json(tmp_path / "run_results.json", _valid_run_results())
        _write_json(
            tmp_path / "manifest.json",
            {"manifest_type": MANIFEST_TYPE_ARTIFACT, "run_id": "r1", "artifacts": []},
        )
        ctx = load_run_outcome_context(tmp_path)
        assert ctx.run_results["run_id"] == "r1"
        assert ctx.artifact_manifest is not None

    def test_missing_manifest_is_none(self, tmp_path):
        _write_json(tmp_path / "run_results.json", _valid_run_results())
        ctx = load_run_outcome_context(tmp_path)
        assert ctx.run_results["run_id"] == "r1"
        assert ctx.artifact_manifest is None

    def test_invalid_manifest_is_best_effort_none(self, tmp_path):
        _write_json(tmp_path / "run_results.json", _valid_run_results())
        _write_json(
            tmp_path / "manifest.json",
            {"manifest_type": MANIFEST_TYPE_RUN, "run_id": "r1"},
        )
        ctx = load_run_outcome_context(tmp_path)
        assert ctx.artifact_manifest is None


class TestLoadGroupMemberRuns:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_group_member_runs(tmp_path / "group_member_runs.json") == []

    def test_invalid_root_returns_empty(self, tmp_path):
        path = tmp_path / "group_member_runs.json"
        _write_json(path, ["not", "a", "dict"])
        assert load_group_member_runs(path) == []

    def test_non_list_members_returns_empty(self, tmp_path):
        path = tmp_path / "group_member_runs.json"
        _write_json(path, {"members": {"a": 1}})
        assert load_group_member_runs(path) == []

    def test_filters_non_dict_members(self, tmp_path):
        path = tmp_path / "group_member_runs.json"
        _write_json(
            path,
            {"members": [{"run_id": "a"}, "skip-me", {"run_id": "b"}, 3]},
        )
        assert load_group_member_runs(path) == [{"run_id": "a"}, {"run_id": "b"}]


class TestLoadGroupPhaseMetadata:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_group_phase_metadata(tmp_path) == []

    def test_corrupt_json_returns_empty(self, tmp_path):
        (tmp_path / "aggregation_warnings.json").write_text("{not-json")
        assert load_group_phase_metadata(tmp_path) == []

    def test_non_list_returns_empty(self, tmp_path):
        _write_json(tmp_path / "aggregation_warnings.json", {"warning": "x"})
        assert load_group_phase_metadata(tmp_path) == []

    def test_filters_non_dict_rows(self, tmp_path):
        _write_json(
            tmp_path / "aggregation_warnings.json",
            [{"code": "a"}, "x", {"code": "b"}, None],
        )
        assert load_group_phase_metadata(tmp_path) == [
            {"code": "a"},
            {"code": "b"},
        ]
