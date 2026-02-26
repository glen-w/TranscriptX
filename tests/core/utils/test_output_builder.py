"""
Tests for output builder utilities.

This module tests output structure creation, metadata files, and data saving.
"""

import json
from pathlib import Path

import pytest

from transcriptx.core.utils.output_builder import (
    OutputStructureBuilder,
    create_standard_output_structure,
    save_global_data,
    save_speaker_data,
    create_summary_json,
)


class TestOutputStructureBuilder:
    """Tests for OutputStructureBuilder class."""

    def test_initialization(self):
        """Test OutputStructureBuilder initialization."""
        builder = OutputStructureBuilder("sentiment")

        assert builder.module_name == "sentiment"
        assert builder.logger is not None

    def test_create_standard_output_structure(self, tmp_path):
        """Test that standard output structure is created."""
        builder = OutputStructureBuilder("sentiment")
        transcript_path = str(tmp_path / "test.json")

        structure = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )

        assert "module_dir" in structure
        assert "data_dir" in structure
        assert "charts_dir" in structure
        assert "global_data_dir" in structure
        assert "speaker_data_dir" in structure

        # Check that directories were created
        assert Path(structure["module_dir"]).exists()
        assert Path(structure["data_dir"]).exists()
        assert Path(structure["charts_dir"]).exists()

    def test_create_metadata_file(self, tmp_path):
        """Test that metadata file is created."""
        builder = OutputStructureBuilder("sentiment")
        transcript_path = str(tmp_path / "test.json")
        structure = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )

        config = {"window_size": 10}
        metadata_path = builder.create_metadata_file(structure, config)

        assert Path(metadata_path).exists()
        with open(metadata_path) as f:
            metadata = json.load(f)
            assert metadata["module"] == "sentiment"
            assert metadata["analysis_config"] == config


class TestCreateStandardOutputStructure:
    """Tests for create_standard_output_structure function."""

    def test_creates_output_structure(self, tmp_path):
        """Test that output structure is created."""
        transcript_path = str(tmp_path / "test.json")

        structure = create_standard_output_structure(
            transcript_path, "sentiment", base_output_dir=str(tmp_path)
        )

        assert "module_dir" in structure
        assert Path(structure["module_dir"]).exists()

    def test_uses_custom_base_output_dir(self, tmp_path):
        """Test that custom base output directory is used."""
        custom_dir = tmp_path / "custom"
        transcript_path = str(tmp_path / "test.json")

        structure = create_standard_output_structure(
            transcript_path, "sentiment", base_output_dir=str(custom_dir)
        )

        assert str(custom_dir) in structure["module_dir"]


class TestSaveGlobalData:
    """Tests for save_global_data function."""

    def test_saves_global_data(self, tmp_path):
        """Test that global data is saved."""
        structure = {"global_data_dir": str(tmp_path / "data" / "global")}
        Path(structure["global_data_dir"]).mkdir(parents=True)

        data = {"total_sentiment": 0.5, "count": 10}
        file_path = save_global_data(data, structure, "sentiment_summary.json")

        assert Path(file_path).exists()
        with open(file_path) as f:
            loaded = json.load(f)
            assert loaded == data


class TestSaveSpeakerData:
    """Tests for save_speaker_data function."""

    def test_saves_speaker_data(self, tmp_path):
        """Test that speaker data is saved."""
        structure = {"speaker_data_dir": str(tmp_path / "data" / "speakers")}
        Path(structure["speaker_data_dir"]).mkdir(parents=True)

        speaker_data = {
            "Alice": {"sentiment": 0.7, "count": 5},
            "Bob": {"sentiment": 0.3, "count": 3},
        }

        file_paths = save_speaker_data(speaker_data, structure)

        assert isinstance(file_paths, list)
        assert len(file_paths) == 2
        for file_path in file_paths:
            assert Path(file_path).exists()
            with open(file_path) as f:
                loaded = json.load(f)
                assert "sentiment" in loaded or "count" in loaded


class TestOutputBuilderAdvanced:
    """Advanced tests for OutputStructureBuilder covering edge cases."""

    @pytest.fixture
    def builder(self):
        """Fixture for OutputStructureBuilder instance."""
        return OutputStructureBuilder("test_module")

    @pytest.fixture
    def output_structure(self, builder, tmp_path):
        """Fixture for output structure."""
        transcript_path = str(tmp_path / "test.json")
        return builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )

    def test_metadata_generation_edge_cases(self, builder, output_structure):
        """Test metadata generation with various configs."""
        # Empty config
        metadata_path = builder.create_metadata_file(output_structure, {})
        assert Path(metadata_path).exists()

        # Complex config
        complex_config = {
            "window_size": 10,
            "threshold": 0.5,
            "nested": {"key": "value"},
        }
        metadata_path = builder.create_metadata_file(output_structure, complex_config)
        with open(metadata_path) as f:
            metadata = json.load(f)
            assert metadata["analysis_config"] == complex_config

    def test_chart_organization(self, builder, output_structure, tmp_path):
        """Test chart organization and saving."""
        # Create a dummy chart file
        chart_file = tmp_path / "test_chart.png"
        chart_file.write_bytes(b"fake png data")

        # Save global chart
        saved_path = builder.save_chart(
            str(chart_file), output_structure, chart_type="global"
        )
        assert Path(saved_path).exists()
        assert "global" in saved_path

        # Save speaker chart
        saved_path = builder.save_chart(
            str(chart_file),
            output_structure,
            chart_type="speaker",
            speaker_id="SPEAKER_00",
        )
        assert Path(saved_path).exists()
        assert "speaker" in saved_path
        assert "SPEAKER_00" in saved_path

    def test_chart_organization_invalid_type(self, builder, output_structure, tmp_path):
        """Test chart saving with invalid type."""
        chart_file = tmp_path / "test_chart.png"
        chart_file.write_bytes(b"fake png data")

        with pytest.raises(ValueError, match="Invalid chart type"):
            builder.save_chart(str(chart_file), output_structure, chart_type="invalid")

    def test_concurrent_access(self, builder, tmp_path):
        """Test concurrent access handling (basic test)."""
        transcript_path = str(tmp_path / "test.json")

        # Create multiple structures (simulating concurrent access)
        structure1 = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path / "output1")
        )
        structure2 = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path / "output2")
        )

        # Both should be created successfully
        assert Path(structure1["module_dir"]).exists()
        assert Path(structure2["module_dir"]).exists()

    def test_large_directory_structures(self, builder, tmp_path):
        """Test creating large directory structures."""
        transcript_path = str(tmp_path / "test.json")
        structure = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )

        # Create many files
        for i in range(100):
            data = {"index": i, "data": "x" * 1000}
            builder.save_global_data(data, structure, f"file_{i}.json")

        # All files should exist
        assert len(list(Path(structure["global_data_dir"]).glob("*.json"))) == 100

    def test_error_handling_invalid_paths(self, builder):
        """Test error handling for invalid paths."""
        # Invalid output structure
        invalid_structure = {"global_data_dir": "/invalid/path/that/does/not/exist"}

        with pytest.raises((OSError, IOError)):
            builder.save_global_data({"test": "data"}, invalid_structure, "test.json")

    def test_sanitize_filename(self, builder):
        """Test filename sanitization."""
        # Invalid characters
        sanitized = builder._sanitize_filename("test<>file:name|?*.json")
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert ":" not in sanitized
        assert "|" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized

        # Long filename
        long_name = "a" * 200
        sanitized = builder._sanitize_filename(long_name)
        assert len(sanitized) <= 100

    def test_create_summary_file(self, builder, output_structure):
        """Test summary file creation."""
        summary_data = {
            "total_items": 100,
            "average_score": 0.75,
            "summary": "Test summary",
        }

        summary_path = builder.create_summary_file(output_structure, summary_data)

        assert Path(summary_path).exists()
        with open(summary_path) as f:
            loaded = json.load(f)
            assert loaded == summary_data

    def test_cleanup_empty_directories(self, builder, tmp_path):
        """Test cleanup of empty directories."""
        # Create a fresh output structure
        transcript_path = str(tmp_path / "test.json")
        structure = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )

        # Verify structure directories exist
        assert Path(structure["global_data_dir"]).exists()
        assert Path(structure["speaker_data_dir"]).exists()

        # Cleanup should remove empty directories from the structure
        # (Note: cleanup only removes directories that are in the structure values,
        # not subdirectories. So we test that it doesn't fail and processes the structure)
        builder.cleanup_empty_directories(structure)

        # The cleanup function processes directories in the structure
        # If they're empty, they'll be removed. If not, they remain.
        # We just verify the function runs without error
        # (The actual cleanup depends on whether directories are empty)

    def test_save_speaker_data_multiple_speakers(self, builder, output_structure):
        """Test saving data for multiple speakers."""
        speaker_data = {
            "SPEAKER_00": {"score": 0.8, "count": 10},
            "SPEAKER_01": {"score": 0.6, "count": 5},
            "SPEAKER_02": {"score": 0.9, "count": 15},
        }

        saved_files = builder.save_speaker_data(speaker_data, output_structure)

        assert len(saved_files) == 3
        for file_path in saved_files:
            assert Path(file_path).exists()
            with open(file_path) as f:
                data = json.load(f)
                assert "score" in data
                assert "count" in data


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_summary_json_function(self, tmp_path):
        """Test create_summary_json convenience function."""
        output_structure = {"module_dir": str(tmp_path / "module")}
        Path(output_structure["module_dir"]).mkdir(parents=True)

        summary_data = {"test": "data"}
        summary_path = create_summary_json(summary_data, output_structure)

        assert Path(summary_path).exists()
        with open(summary_path) as f:
            assert json.load(f) == summary_data
