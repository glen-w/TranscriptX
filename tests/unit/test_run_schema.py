"""
Unit tests for run_schema.py: RunManifestInput, RunResultsSummary, validate_manifest_shape.

These tests are fast, deterministic, and require no external services.
"""

from __future__ import annotations

import json

import pytest

from transcriptx.core.pipeline.run_schema import (
    MANIFEST_TYPE_ARTIFACT,
    RunManifestInput,
    RunResultsSummary,
    validate_manifest_shape,
)


class TestRunManifestInput:
    """RunManifestInput construction and from_file / from_cli_kwargs."""

    def test_minimal_from_cli_kwargs(self, tmp_path):
        f = tmp_path / "t.json"
        f.write_text("{}")
        m = RunManifestInput.from_cli_kwargs(str(f))
        assert m.transcript_path == str(f.resolve())
        assert m.modules == ["all"]
        assert m.mode == "quick"
        assert m.schema_version == 1

    def test_from_cli_kwargs_with_modules_and_options(self, tmp_path):
        f = tmp_path / "t.json"
        f.write_text("{}")
        m = RunManifestInput.from_cli_kwargs(
            str(f),
            modules=["stats", "sentiment"],
            output_dir="/out",
            persist=True,
            run_id="custom-run",
        )
        assert m.modules == ["stats", "sentiment"]
        assert m.output_dir == "/out"
        assert m.persist is True
        assert m.run_id == "custom-run"

    def test_from_file_valid(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "transcript_path": "/abs/transcript.json",
                    "modules": ["stats"],
                    "mode": "full",
                    "config_overrides": {},
                }
            )
        )
        m = RunManifestInput.from_file(path)
        assert m.transcript_path == "/abs/transcript.json"
        assert m.modules == ["stats"]
        assert m.mode == "full"

    def test_from_file_normalizes_config_overrides_none(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "transcript_path": "/abs/t.json",
                    "modules": ["stats"],
                    "config_overrides": None,
                }
            )
        )
        m = RunManifestInput.from_file(path)
        assert m.config_overrides == {}

    def test_from_file_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RunManifestInput.from_file(tmp_path / "missing.json")


class TestRunResultsSummary:
    """RunResultsSummary.validate_run_results normalization and validation."""

    def test_valid_minimal(self):
        data = {
            "schema_version": 1,
            "run_id": "r1",
            "transcript_key": "k1",
            "modules_enabled": ["stats"],
            "modules_run": ["stats"],
            "modules_skipped": [],
            "modules_failed": [],
            "errors": [],
        }
        s = RunResultsSummary.validate_run_results(data)
        assert s.run_id == "r1"
        assert s.transcript_key == "k1"
        assert s.modules_run == ["stats"]

    def test_normalizes_modules_skipped_dicts(self):
        data = {
            "schema_version": 1,
            "run_id": "r1",
            "transcript_key": "k1",
            "modules_enabled": ["stats", "sentiment"],
            "modules_run": ["stats"],
            "modules_skipped": [{"module": "sentiment", "reason": "Skipped"}],
            "modules_failed": [],
            "errors": [],
        }
        s = RunResultsSummary.validate_run_results(data)
        assert len(s.modules_skipped) == 1
        assert s.modules_skipped[0].module == "sentiment"
        assert s.modules_skipped[0].reason == "Skipped"

    def test_normalizes_modules_skipped_missing_reason(self):
        data = {
            "schema_version": 1,
            "run_id": "r1",
            "transcript_key": "k1",
            "modules_enabled": ["stats"],
            "modules_run": [],
            "modules_skipped": [{"module": "stats"}],
            "modules_failed": [],
            "errors": [],
        }
        s = RunResultsSummary.validate_run_results(data)
        assert s.modules_skipped[0].reason == "Skipped"


class TestValidateManifestShape:
    """validate_manifest_shape accepts valid artifact manifest and rejects wrong type."""

    def test_valid_artifact_manifest(self):
        manifest = {
            "manifest_type": MANIFEST_TYPE_ARTIFACT,
            "run_id": "r1",
            "run_metadata": {
                "timestamp": "2026-01-01T00:00:00",
                "transcript_key": "k1",
                "modules_enabled": ["stats"],
                "total_size_bytes": 0,
            },
            "artifacts": [],
        }
        validate_manifest_shape(manifest)

    def test_wrong_manifest_type_raises(self):
        manifest = {
            "manifest_type": "run_manifest",
            "run_id": "r1",
            "run_metadata": {
                "timestamp": "2026-01-01T00:00:00",
                "transcript_key": "k1",
                "modules_enabled": [],
                "total_size_bytes": 0,
            },
            "artifacts": [],
        }
        with pytest.raises(ValueError, match="Expected manifest_type"):
            validate_manifest_shape(manifest)

    def test_accepts_no_manifest_type_backward_compat(self):
        manifest = {
            "run_id": "r1",
            "run_metadata": {
                "timestamp": "2026-01-01T00:00:00",
                "transcript_key": "k1",
                "modules_enabled": [],
                "total_size_bytes": 0,
            },
            "artifacts": [],
        }
        validate_manifest_shape(manifest)
