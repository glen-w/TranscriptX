"""
Tests for core pipeline infrastructure: PipelineContext, run manifest, execution flow.

These tests exercise the architecture described in docs/ARCHITECTURE.md:
load transcript -> build plan -> execute modules -> write manifest.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.run_manifest import (
    RunManifest,
    create_run_manifest,
    get_transcriptx_version,
)


class TestRunManifest:
    """Run manifest creation and serialization (reproducibility contract)."""

    def test_run_manifest_from_dict_roundtrip(self):
        data = {
            "schema_version": "1",
            "transcript_hash": "sha256:abc",
            "canonical_schema_version": "1.0",
            "config_hash": None,
            "code_version": "0.5",
            "module_versions": {"stats": "abc123"},
            "artifact_index": [],
            "timestamp": "2026-03-13T12:00:00",
            "manifest_type": "run_manifest",
        }
        manifest = RunManifest.from_dict(data)
        assert manifest.schema_version == "1"
        assert manifest.transcript_hash == "sha256:abc"
        assert manifest.module_versions == {"stats": "abc123"}
        out = manifest.to_dict()
        assert out["manifest_type"] == "run_manifest"
        assert out["transcript_hash"] == "sha256:abc"

    def test_run_manifest_to_json(self):
        data = {
            "schema_version": "1",
            "transcript_hash": "sha256:def",
            "canonical_schema_version": "1.0",
            "config_hash": None,
            "code_version": "0.5",
            "module_versions": {},
            "artifact_index": [],
            "timestamp": "2026-03-13T12:00:00",
            "manifest_type": "run_manifest",
        }
        manifest = RunManifest.from_dict(data)
        js = manifest.to_json()
        assert "sha256:def" in js
        loaded = RunManifest.from_json(js)
        assert loaded.transcript_hash == manifest.transcript_hash

    def test_get_transcriptx_version_returns_string(self):
        v = get_transcriptx_version()
        assert isinstance(v, str)
        assert len(v) > 0
        # Should look like a version (digits and dots)
        assert any(c.isdigit() for c in v)

    def test_create_run_manifest_minimal(self):
        manifest = create_run_manifest(
            transcript_hash="sha256:minimal",
            selected_modules=["stats"],
            modules_run=["stats"],
        )
        assert manifest.transcript_hash == "sha256:minimal"
        assert "stats" in manifest.module_versions or manifest.module_versions == {}
        assert manifest.modules_run == ["stats"]


class TestPipelineContextLifecycle:
    """PipelineContext creation and basic access (requires fixture path)."""

    def test_pipeline_context_loads_fixture(self, tmp_path):
        """Context loads transcript from fixture path and exposes segments."""
        fixture_path = (
            Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "mini_transcriptx.json"
        )
        if not fixture_path.exists():
            pytest.skip("mini_transcriptx.json fixture not found")
        from transcriptx.core.pipeline.pipeline_context import PipelineContext

        with patch.dict("os.environ", {"TRANSCRIPTX_DB_ENABLED": "0"}):
            ctx = PipelineContext(
                str(fixture_path),
                output_dir=str(tmp_path),
            )
        try:
            assert ctx.segments is not None
            assert len(ctx.segments) > 0
            assert ctx.base_name is not None
            assert ctx.transcript_path == str(fixture_path)
        finally:
            ctx.close()

    def test_pipeline_context_store_and_retrieve_analysis_result(self, tmp_path):
        """Context can store and retrieve analysis result by module name."""
        fixture_path = (
            Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "mini_transcriptx.json"
        )
        if not fixture_path.exists():
            pytest.skip("mini_transcriptx.json fixture not found")
        from transcriptx.core.pipeline.pipeline_context import PipelineContext

        with patch.dict("os.environ", {"TRANSCRIPTX_DB_ENABLED": "0"}):
            ctx = PipelineContext(
                str(fixture_path),
                output_dir=str(tmp_path),
            )
        try:
            ctx.store_analysis_result("stats", {"word_count": 42, "segment_count": 3})
            result = ctx.get_analysis_result("stats")
            assert result is not None
            assert result.get("word_count") == 42
            assert ctx.get_analysis_result("nonexistent") is None
        finally:
            ctx.close()
