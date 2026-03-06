"""
Tests for preprocessing service module.

This module tests transcript validation and data preparation.
"""

import json
from unittest.mock import patch

import pytest

from transcriptx.core.pipeline.preprocessing import (
    PreprocessingService,
    validate_transcript,
    prepare_transcript_data,
)


@pytest.mark.unit
class TestPreprocessingService:
    """Tests for PreprocessingService."""

    @pytest.fixture
    def preprocessing_service(self):
        """Fixture for PreprocessingService instance."""
        return PreprocessingService()

    @pytest.fixture
    def sample_transcript_data(self):
        """Fixture for sample transcript data."""
        return {
            "segments": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "Hello, welcome to our meeting.",
                    "start": 0.0,
                    "end": 3.5,
                },
                {
                    "speaker": "Bob",
                    "speaker_db_id": 2,
                    "text": "Thank you for having me.",
                    "start": 4.0,
                    "end": 6.0,
                },
            ]
        }

    @pytest.fixture
    def temp_transcript_file(self, tmp_path, sample_transcript_data):
        """Create a temporary transcript file for testing."""
        file_path = tmp_path / "test_transcript.json"
        file_path.write_text(json.dumps(sample_transcript_data, indent=2))
        return file_path

    def test_validate_transcript_success(
        self, preprocessing_service, temp_transcript_file
    ):
        """Test successful transcript validation."""
        with (
            patch(
                "transcriptx.core.pipeline.preprocessing.validate_transcript_file"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.preprocessing.validate_output_directory"
            ) as mock_validate_dir,
        ):
            mock_validate.return_value = None
            mock_validate_dir.return_value = None

            # Should not raise
            preprocessing_service.validate_transcript(str(temp_transcript_file))

            mock_validate.assert_called_once_with(str(temp_transcript_file))
            mock_validate_dir.assert_called_once()

    def test_validate_transcript_file_not_found(self, preprocessing_service, tmp_path):
        """Test validation with non-existent file."""
        non_existent_file = tmp_path / "nonexistent.json"

        with patch(
            "transcriptx.core.pipeline.preprocessing.validate_transcript_file"
        ) as mock_validate:
            mock_validate.side_effect = FileNotFoundError("File not found")

            with pytest.raises(FileNotFoundError):
                preprocessing_service.validate_transcript(str(non_existent_file))

    def test_validate_transcript_invalid_json(self, preprocessing_service, tmp_path):
        """Test validation with invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid json}")

        with patch(
            "transcriptx.core.pipeline.preprocessing.validate_transcript_file"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Invalid JSON structure")

            with pytest.raises(ValueError):
                preprocessing_service.validate_transcript(str(invalid_file))

    def test_prepare_transcript_data_success(
        self, preprocessing_service, temp_transcript_file, sample_transcript_data
    ):
        """Test successful transcript data preparation."""
        data, base_name = preprocessing_service.prepare_transcript_data(
            str(temp_transcript_file)
        )

        assert data == sample_transcript_data
        assert base_name == "test_transcript"

    def test_prepare_transcript_data_file_not_found(
        self, preprocessing_service, tmp_path
    ):
        """Test data preparation with non-existent file."""
        non_existent_file = tmp_path / "nonexistent.json"

        with pytest.raises((FileNotFoundError, OSError)):
            preprocessing_service.prepare_transcript_data(str(non_existent_file))

    def test_prepare_transcript_data_invalid_json(
        self, preprocessing_service, tmp_path
    ):
        """Test data preparation with invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid json}")

        with pytest.raises((json.JSONDecodeError, ValueError)):
            preprocessing_service.prepare_transcript_data(str(invalid_file))

    def test_prepare_transcript_data_empty_file(self, preprocessing_service, tmp_path):
        """Test data preparation with empty file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        with pytest.raises((json.JSONDecodeError, ValueError)):
            preprocessing_service.prepare_transcript_data(str(empty_file))


@pytest.mark.unit
class TestPreprocessingModuleFunctions:
    """Tests for module-level preprocessing functions."""

    @pytest.fixture
    def sample_transcript_data(self):
        """Fixture for sample transcript data."""
        return {
            "segments": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "Test segment",
                    "start": 0.0,
                    "end": 2.0,
                }
            ]
        }

    @pytest.fixture
    def temp_transcript_file(self, tmp_path, sample_transcript_data):
        """Create a temporary transcript file for testing."""
        file_path = tmp_path / "test_transcript.json"
        file_path.write_text(json.dumps(sample_transcript_data, indent=2))
        return file_path

    def test_validate_transcript_function(self, temp_transcript_file):
        """Test module-level validate_transcript function."""
        with (
            patch(
                "transcriptx.core.pipeline.preprocessing.validate_transcript_file"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.preprocessing.validate_output_directory"
            ) as mock_validate_dir,
        ):
            mock_validate.return_value = None
            mock_validate_dir.return_value = None

            # Should not raise
            validate_transcript(str(temp_transcript_file))

            mock_validate.assert_called_once()
            mock_validate_dir.assert_called_once()

    def test_prepare_transcript_data_function(
        self, temp_transcript_file, sample_transcript_data
    ):
        """Test module-level prepare_transcript_data function."""
        data, base_name = prepare_transcript_data(str(temp_transcript_file))

        assert data == sample_transcript_data
        assert base_name == "test_transcript"

    def test_prepare_transcript_data_with_nested_path(
        self, tmp_path, sample_transcript_data
    ):
        """Test data preparation with nested directory path."""
        nested_dir = tmp_path / "nested" / "subdir"
        nested_dir.mkdir(parents=True)
        file_path = nested_dir / "nested_transcript.json"
        file_path.write_text(json.dumps(sample_transcript_data, indent=2))

        data, base_name = prepare_transcript_data(str(file_path))

        assert data == sample_transcript_data
        assert base_name == "nested_transcript"
