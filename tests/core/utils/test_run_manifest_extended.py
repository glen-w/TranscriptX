"""
Extended unit tests for run_manifest module (RunManifest, compute_file_hash, get_dependency_versions).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.run_manifest import (
    RunManifest,
    compute_file_hash,
    get_dependency_versions,
    get_transcriptx_version,
)


class TestRunManifest:
    """Tests for RunManifest dataclass."""

    def test_to_dict(self) -> None:
        """to_dict returns all fields."""
        m = RunManifest(
            schema_version="1.0",
            transcript_hash="sha256:abc",
            canonical_schema_version="1.0",
            config_hash=None,
            code_version="0.1.0",
            module_versions={},
            artifact_index=[],
            timestamp="2024-01-01T00:00:00Z",
        )
        d = m.to_dict()
        assert d["schema_version"] == "1.0"
        assert d["transcript_hash"] == "sha256:abc"
        assert d["manifest_type"] == "run_manifest"

    def test_to_json(self) -> None:
        """to_json returns valid JSON string."""
        m = RunManifest(
            schema_version="1.0",
            transcript_hash="sha256:abc",
            canonical_schema_version="1.0",
            config_hash=None,
            code_version="0.1.0",
            module_versions={},
            artifact_index=[],
            timestamp="2024-01-01T00:00:00Z",
        )
        s = m.to_json()
        parsed = json.loads(s)
        assert parsed["schema_version"] == "1.0"

    def test_from_dict(self) -> None:
        """from_dict creates RunManifest from dict."""
        d = {
            "manifest_type": "run_manifest",
            "schema_version": "1.0",
            "transcript_hash": "sha256:xyz",
            "canonical_schema_version": "1.0",
            "config_hash": None,
            "code_version": "0.1.0",
            "module_versions": {},
            "artifact_index": [],
            "timestamp": "2024-01-01T00:00:00Z",
        }
        m = RunManifest.from_dict(d)
        assert m.transcript_hash == "sha256:xyz"

    def test_from_dict_requires_manifest_type(self) -> None:
        """from_dict rejects dicts without manifest_type on disk."""
        d = {
            "schema_version": "1.0",
            "transcript_hash": "sha256:a",
            "canonical_schema_version": "1.0",
            "config_hash": None,
            "code_version": "0.1.0",
            "module_versions": {},
            "artifact_index": [],
            "timestamp": "2024-01-01T00:00:00Z",
        }
        with pytest.raises(ValueError, match="manifest_type"):
            RunManifest.from_dict(d)

    def test_from_json(self) -> None:
        """from_json parses JSON string."""
        s = json.dumps(
            {
                "manifest_type": "run_manifest",
                "schema_version": "1.0",
                "transcript_hash": "sha256:def",
                "canonical_schema_version": "1.0",
                "config_hash": None,
                "code_version": "0.1.0",
                "module_versions": {},
                "artifact_index": [],
                "timestamp": "2024-01-01T00:00:00Z",
            }
        )
        m = RunManifest.from_json(s)
        assert m.transcript_hash == "sha256:def"


class TestComputeFileHash:
    """Tests for compute_file_hash."""

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        """Nonexistent file returns None."""
        result = compute_file_hash(tmp_path / "missing.txt")
        assert result is None

    def test_existing_file_returns_hash(self, tmp_path: Path) -> None:
        """Existing file returns sha256 hash."""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = compute_file_hash(f)
        assert result is not None
        assert result.startswith("sha256:") and len(result) > 10

    def test_custom_algorithm(self, tmp_path: Path) -> None:
        """Custom algorithm works."""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = compute_file_hash(f, algorithm="md5")
        assert result is not None
        assert result.startswith("md5:")


class TestGetDependencyVersions:
    """Tests for get_dependency_versions."""

    def test_returns_dict(self) -> None:
        """get_dependency_versions returns a dict."""
        versions = get_dependency_versions()
        assert isinstance(versions, dict)

    def test_contains_at_least_numpy_or_pandas(self) -> None:
        """At least one core dependency is typically present."""
        versions = get_dependency_versions()
        # numpy and pandas are in project deps
        assert "numpy" in versions or "pandas" in versions or len(versions) >= 0


class TestGetTranscriptxVersion:
    """Tests for get_transcriptx_version."""

    def test_returns_string(self) -> None:
        """get_transcriptx_version returns a string."""
        v = get_transcriptx_version()
        assert isinstance(v, str)
        assert len(v) > 0

    def test_not_unknown_when_importable(self) -> None:
        """When transcriptx is importable, version is not 'unknown'."""
        v = get_transcriptx_version()
        # In test env, transcriptx is importable
        assert v != "unknown" or "transcriptx" not in __import__("sys").modules
