"""
Unit tests for output_standards.py: output directory structure creation,
file-naming patterns, and directory cleanup.

These tests are fast, deterministic, and require no external services.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.utils.output_standards import (
    OutputStructure,
    create_standard_output_structure,
    get_standard_file_patterns,
    cleanup_empty_directories,
    cleanup_module_outputs,
)
from transcriptx.core.utils.paths import OUTPUTS_DIR


class TestCreateStandardOutputStructure:
    """create_standard_output_structure returns a well-formed OutputStructure."""

    def test_returns_output_structure(self, tmp_path, monkeypatch):
        transcript_dir = str(Path(OUTPUTS_DIR) / "my_transcript")
        structure = create_standard_output_structure(transcript_dir, "stats")
        assert isinstance(structure, OutputStructure)

    def test_module_dir_under_transcript_dir(self):
        transcript_dir = str(Path(OUTPUTS_DIR) / "my_transcript")
        structure = create_standard_output_structure(transcript_dir, "stats")
        assert str(structure.module_dir).startswith(str(Path(OUTPUTS_DIR).resolve()))
        assert structure.module_dir.name == "stats"

    def test_data_and_charts_dirs_set(self):
        transcript_dir = str(Path(OUTPUTS_DIR) / "my_transcript")
        structure = create_standard_output_structure(transcript_dir, "sentiment")
        assert structure.data_dir == structure.module_dir / "data"
        assert structure.charts_dir == structure.module_dir / "charts"

    def test_global_and_speaker_dirs(self):
        transcript_dir = str(Path(OUTPUTS_DIR) / "my_transcript")
        structure = create_standard_output_structure(transcript_dir, "emotion")
        assert structure.global_data_dir == structure.data_dir / "global"
        assert structure.speaker_data_dir == structure.data_dir / "speakers"

    def test_output_namespace_overrides_module_name(self):
        transcript_dir = str(Path(OUTPUTS_DIR) / "my_transcript")
        structure = create_standard_output_structure(
            transcript_dir, "stats", output_namespace="custom_ns"
        )
        assert "custom_ns" in str(structure.module_dir)
        assert "stats" not in str(structure.module_dir)

    def test_output_version_appends_to_namespace(self):
        transcript_dir = str(Path(OUTPUTS_DIR) / "my_transcript")
        structure = create_standard_output_structure(
            transcript_dir, "stats", output_version="v2"
        )
        assert structure.module_dir.name == "v2"
        assert structure.module_dir.parent.name == "stats"

    def test_redirects_non_outputs_dir_path(self):
        structure = create_standard_output_structure("/tmp/wrong_place", "stats")
        assert str(structure.transcript_dir).startswith(str(Path(OUTPUTS_DIR).resolve()))


class TestGetStandardFilePatterns:
    def test_returns_expected_keys(self):
        patterns = get_standard_file_patterns("my_transcript", "stats")
        expected_keys = {
            "global_summary",
            "global_data",
            "speaker_data",
            "speaker_chart",
            "global_chart",
        }
        assert set(patterns.keys()) == expected_keys

    def test_patterns_contain_base_name(self):
        patterns = get_standard_file_patterns("interview_001", "sentiment")
        for key, pattern in patterns.items():
            assert "interview_001" in pattern, f"{key} missing base_name"

    def test_patterns_contain_module_name(self):
        patterns = get_standard_file_patterns("interview_001", "sentiment")
        for key, pattern in patterns.items():
            assert "sentiment" in pattern, f"{key} missing module_name"


class TestCleanupEmptyDirectories:
    def test_removes_empty_dirs(self, tmp_path):
        empty_dir = tmp_path / "module" / "data" / "global"
        empty_dir.mkdir(parents=True)
        cleanup_empty_directories(tmp_path / "module")
        assert not empty_dir.exists()

    def test_keeps_dirs_with_files(self, tmp_path):
        data_dir = tmp_path / "module" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "results.json").write_text("{}")
        cleanup_empty_directories(tmp_path / "module")
        assert data_dir.exists()

    def test_nonexistent_dir_no_error(self, tmp_path):
        cleanup_empty_directories(tmp_path / "nonexistent")

    def test_mixed_empty_and_nonempty(self, tmp_path):
        module = tmp_path / "module"
        (module / "data" / "global").mkdir(parents=True)
        (module / "data" / "speakers").mkdir(parents=True)
        (module / "data" / "speakers" / "result.csv").write_text("a,b")
        cleanup_empty_directories(module)
        assert not (module / "data" / "global").exists()
        assert (module / "data" / "speakers").exists()


class TestCleanupModuleOutputs:
    def test_cleans_specific_module(self, tmp_path):
        module_dir = tmp_path / "stats" / "data" / "empty"
        module_dir.mkdir(parents=True)
        cleanup_module_outputs(tmp_path, "stats")
        assert not module_dir.exists()


class TestOutputStructureDataclass:
    """Verify OutputStructure fields and lazy init."""

    def test_all_fields_set(self):
        structure = OutputStructure(
            module_dir=Path("/tmp/m"),
            data_dir=Path("/tmp/m/data"),
            charts_dir=Path("/tmp/m/charts"),
            transcript_dir=Path("/tmp/t"),
            global_data_dir=Path("/tmp/m/data/global"),
            global_charts_dir=Path("/tmp/m/charts/global"),
            global_static_charts_dir=Path("/tmp/m/charts/global/static"),
            global_dynamic_charts_dir=Path("/tmp/m/charts/global/dynamic"),
            speaker_data_dir=Path("/tmp/m/data/speakers"),
            speaker_charts_dir=Path("/tmp/m/charts/speakers"),
            speaker_static_charts_dir=Path("/tmp/m/charts/speakers"),
            speaker_dynamic_charts_dir=Path("/tmp/m/charts/speakers"),
        )
        assert structure.module_dir == Path("/tmp/m")
        assert structure.global_data_dir == Path("/tmp/m/data/global")
