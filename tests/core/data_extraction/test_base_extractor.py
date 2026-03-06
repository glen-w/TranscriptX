"""
Tests for base data extractor.

This module tests the BaseDataExtractor abstract base class, including
validation, transformation, aggregation, and quality metrics calculation.
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
import numpy as np

from transcriptx.core.data_extraction.base_extractor import BaseDataExtractor


# Concrete implementation for testing abstract base class
class ConcreteDataExtractor(BaseDataExtractor):
    """Concrete implementation of BaseDataExtractor for testing."""

    def __init__(self, module_name: str = "test_module", required_fields: list = None):
        """Initialize concrete extractor."""
        super().__init__(module_name)
        self._required_fields = required_fields or []

    def extract_data(self, analysis_results: dict, speaker_id: str) -> dict:
        """Extract data for testing."""
        return {
            "test_field": "test_value",
            "numeric_field": 42,
            "list_field": [1, 2, 3],
        }

    def get_required_fields(self) -> list:
        """Get required fields."""
        return self._required_fields


class TestBaseDataExtractor:
    """Tests for BaseDataExtractor base class."""

    @pytest.fixture
    def extractor(self):
        """Fixture for BaseDataExtractor instance."""
        return ConcreteDataExtractor("test_module")

    @pytest.fixture
    def extractor_with_required_fields(self):
        """Fixture for extractor with required fields."""
        return ConcreteDataExtractor(
            "test_module", required_fields=["test_field", "numeric_field"]
        )

    def test_abstract_interface_enforcement(self):
        """Test that abstract methods must be implemented."""
        # Should raise TypeError if trying to instantiate abstract class
        with pytest.raises(TypeError):
            BaseDataExtractor("test")

    def test_initialization(self, extractor):
        """Test extractor initialization."""
        assert extractor.module_name == "test_module"
        assert extractor.logger is not None

    def test_extract_data_abstract(self):
        """Test that extract_data is abstract and must be implemented."""
        # Concrete implementation should work
        extractor = ConcreteDataExtractor()
        result = extractor.extract_data({}, "SPEAKER_00")
        assert isinstance(result, dict)

    def test_validate_data_valid_input(self, extractor):
        """Test data validation with valid input."""
        valid_data = {"test_field": "value", "numeric_field": 42}

        result = extractor.validate_data(valid_data, "SPEAKER_00")

        assert result is True

    def test_validate_data_invalid_types(self, extractor):
        """Test data validation with invalid types."""
        # Test with non-dict input
        result = extractor.validate_data("not a dict", "SPEAKER_00")
        assert result is False

        # Test with list input
        result = extractor.validate_data([1, 2, 3], "SPEAKER_00")
        assert result is False

        # Test with None
        result = extractor.validate_data(None, "SPEAKER_00")
        assert result is False

    def test_validate_data_empty_data(self, extractor):
        """Test data validation with empty data."""
        result = extractor.validate_data({}, "SPEAKER_00")
        assert result is False

    def test_validate_data_missing_required_fields(
        self, extractor_with_required_fields
    ):
        """Test data validation with missing required fields."""
        # Missing one required field
        incomplete_data = {
            "test_field": "value"
            # Missing numeric_field
        }

        result = extractor_with_required_fields.validate_data(
            incomplete_data, "SPEAKER_00"
        )
        assert result is False

        # Missing all required fields
        empty_data = {}
        result = extractor_with_required_fields.validate_data(empty_data, "SPEAKER_00")
        assert result is False

        # All required fields present
        complete_data = {"test_field": "value", "numeric_field": 42}
        result = extractor_with_required_fields.validate_data(
            complete_data, "SPEAKER_00"
        )
        assert result is True

    def test_validate_data_exception_handling(self, extractor):
        """Test that validation handles exceptions gracefully."""
        # Create data that causes exception during validation
        with patch.object(
            extractor, "get_required_fields", side_effect=Exception("Test error")
        ):
            result = extractor.validate_data({"test": "value"}, "SPEAKER_00")
            assert result is False

    def test_get_required_fields_default(self, extractor):
        """Test default required fields."""
        fields = extractor.get_required_fields()
        assert isinstance(fields, list)
        assert len(fields) == 0

    def test_get_required_fields_custom(self, extractor_with_required_fields):
        """Test custom required fields."""
        fields = extractor_with_required_fields.get_required_fields()
        assert len(fields) == 2
        assert "test_field" in fields
        assert "numeric_field" in fields

    def test_transform_data_standardization(self, extractor):
        """Test data transformation into standardized format."""
        raw_data = {"test_field": "value", "numeric_field": 42}

        result = extractor.transform_data(raw_data, "SPEAKER_00")

        assert "speaker_id" in result
        assert result["speaker_id"] == "SPEAKER_00"
        assert "module" in result
        assert result["module"] == "test_module"
        assert "extracted_at" in result
        assert "data" in result
        assert result["data"] == raw_data
        assert "metadata" in result
        assert "quality_metrics" in result

    def test_transform_data_metadata(self, extractor):
        """Test metadata extraction in transformation."""
        raw_data = {
            "text_field": "Hello world",
            "numeric_field": 42,
            "list_field": [1, 2, 3],
        }

        result = extractor.transform_data(raw_data, "SPEAKER_00")
        metadata = result["metadata"]

        assert "data_type" in metadata
        assert "data_size" in metadata
        assert "has_numeric_data" in metadata
        assert metadata["has_numeric_data"] is True
        assert "has_text_data" in metadata
        assert metadata["has_text_data"] is True
        assert "has_list_data" in metadata
        assert metadata["has_list_data"] is True
        assert "field_count" in metadata
        assert metadata["field_count"] == 3
        assert "field_types" in metadata

    def test_transform_data_error_handling(self, extractor):
        """Test transformation error handling."""
        # Create data that causes exception
        with patch.object(
            extractor, "_get_timestamp", side_effect=Exception("Test error")
        ):
            raw_data = {"test": "value"}
            result = extractor.transform_data(raw_data, "SPEAKER_00")

            assert "error" in result
            assert result["speaker_id"] == "SPEAKER_00"
            assert result["module"] == "test_module"

    def test_get_timestamp(self, extractor):
        """Test timestamp generation."""
        timestamp = extractor._get_timestamp()
        assert isinstance(timestamp, str)
        assert "T" in timestamp or "-" in timestamp  # ISO format

    def test_extract_metadata(self, extractor):
        """Test metadata extraction."""
        data = {"text": "Hello", "number": 42, "items": [1, 2, 3]}

        metadata = extractor._extract_metadata(data)

        assert metadata["data_type"] == "dict"
        assert metadata["has_numeric_data"] is True
        assert metadata["has_text_data"] is True
        assert metadata["has_list_data"] is True
        assert metadata["field_count"] == 3

    def test_has_numeric_data(self, extractor):
        """Test numeric data detection."""
        assert extractor._has_numeric_data(42) is True
        assert extractor._has_numeric_data(3.14) is True
        assert extractor._has_numeric_data("text") is False
        assert extractor._has_numeric_data({"num": 42}) is True
        assert extractor._has_numeric_data([1, 2, 3]) is True
        assert extractor._has_numeric_data({"text": "hello"}) is False

    def test_has_text_data(self, extractor):
        """Test text data detection."""
        assert extractor._has_text_data("text") is True
        assert extractor._has_text_data(42) is False
        assert extractor._has_text_data({"text": "hello"}) is True
        assert extractor._has_text_data([1, 2, 3]) is False
        assert extractor._has_text_data(["text", 1]) is True

    def test_has_list_data(self, extractor):
        """Test list data detection."""
        assert extractor._has_list_data([1, 2, 3]) is True
        assert extractor._has_list_data({"items": [1, 2]}) is True
        assert extractor._has_list_data("text") is False
        assert extractor._has_list_data(42) is False

    def test_calculate_quality_metrics(self, extractor):
        """Test quality metrics calculation."""
        data = {"text": "Hello world", "number": 42, "items": [1, 2, 3]}

        metrics = extractor._calculate_quality_metrics(data)

        assert "completeness" in metrics
        assert "consistency" in metrics
        assert "validity" in metrics
        assert "numeric_quality" in metrics
        assert "text_quality" in metrics

    def test_calculate_completeness(self, extractor):
        """Test completeness calculation."""
        # No required fields - should be 1.0
        data = {"field": "value"}
        completeness = extractor._calculate_completeness(data)
        assert completeness == 1.0

        # With required fields
        extractor_with_req = ConcreteDataExtractor(required_fields=["field1", "field2"])
        data_missing = {"field1": "value"}
        completeness = extractor_with_req._calculate_completeness(data_missing)
        assert completeness == 0.5

        data_complete = {"field1": "value", "field2": "value"}
        completeness = extractor_with_req._calculate_completeness(data_complete)
        assert completeness == 1.0

    def test_calculate_consistency(self, extractor):
        """Test consistency calculation."""
        # Consistent list
        data_consistent = {"items": [1, 2, 3]}
        consistency = extractor._calculate_consistency(data_consistent)
        assert 0.0 <= consistency <= 1.0

        # Inconsistent list
        data_inconsistent = {"items": [1, "text", 3]}
        consistency = extractor._calculate_consistency(data_inconsistent)
        assert consistency < 1.0

        # Non-dict input
        consistency = extractor._calculate_consistency("not a dict")
        assert consistency == 0.0

    def test_calculate_validity(self, extractor):
        """Test validity calculation."""
        # Valid data
        data_valid = {"field1": "value", "field2": 42}
        validity = extractor._calculate_validity(data_valid)
        assert validity == 1.0

        # Invalid data (None values)
        data_invalid = {"field1": None, "field2": "value"}
        validity = extractor._calculate_validity(data_invalid)
        assert validity < 1.0

        # Empty strings
        data_empty = {"field1": "", "field2": "value"}
        validity = extractor._calculate_validity(data_empty)
        assert validity < 1.0

        # Empty collections
        data_empty_col = {"field1": [], "field2": "value"}
        validity = extractor._calculate_validity(data_empty_col)
        assert validity < 1.0

    def test_calculate_numeric_quality(self, extractor):
        """Test numeric quality calculation."""
        # With numeric data
        data = {"numbers": [1, 2, 3, 4, 5], "value": 10}
        quality = extractor._calculate_numeric_quality(data)

        assert "mean" in quality
        assert "std" in quality
        assert "range" in quality
        assert quality["mean"] > 0
        assert quality["range"] >= 0

        # Without numeric data
        data_no_numeric = {"text": "hello"}
        quality = extractor._calculate_numeric_quality(data_no_numeric)
        assert quality["mean"] == 0.0
        assert quality["std"] == 0.0
        assert quality["range"] == 0.0

    def test_calculate_text_quality(self, extractor):
        """Test text quality calculation."""
        # With text data
        data = {"text1": "Hello world", "text2": "Python programming"}
        quality = extractor._calculate_text_quality(data)

        assert "avg_length" in quality
        assert "total_words" in quality
        assert "unique_words" in quality
        assert quality["avg_length"] > 0
        assert quality["total_words"] > 0
        assert quality["unique_words"] > 0

        # Without text data
        data_no_text = {"number": 42}
        quality = extractor._calculate_text_quality(data_no_text)
        assert quality["avg_length"] == 0.0
        assert quality["total_words"] == 0
        assert quality["unique_words"] == 0


class TestBaseExtractorAggregation:
    """Tests for data aggregation across speakers."""

    @pytest.fixture
    def extractor(self):
        """Fixture for extractor."""
        return ConcreteDataExtractor("test_module")

    @pytest.fixture
    def sample_speaker_data(self):
        """Fixture for sample speaker data."""
        return {
            "SPEAKER_00": {
                "data": {"field1": "value1", "field2": 10},
                "quality_metrics": {
                    "completeness": 1.0,
                    "consistency": 0.9,
                    "validity": 1.0,
                },
                "metadata": {"data_size": 100},
            },
            "SPEAKER_01": {
                "data": {"field1": "value2", "field2": 20},
                "quality_metrics": {
                    "completeness": 0.8,
                    "consistency": 0.85,
                    "validity": 0.9,
                },
                "metadata": {"data_size": 150},
            },
        }

    def test_aggregate_speaker_data_basic(self, extractor, sample_speaker_data):
        """Test basic speaker data aggregation."""
        result = extractor.aggregate_speaker_data(sample_speaker_data)

        assert "module" in result
        assert result["module"] == "test_module"
        assert "speaker_count" in result
        assert result["speaker_count"] == 2
        assert "aggregated_at" in result
        assert "speakers" in result
        assert len(result["speakers"]) == 2
        assert "summary" in result
        assert "patterns" in result
        assert "statistics" in result

    def test_aggregate_speaker_data_summary(self, extractor, sample_speaker_data):
        """Test summary creation in aggregation."""
        result = extractor.aggregate_speaker_data(sample_speaker_data)
        summary = result["summary"]

        assert "total_speakers" in summary
        assert summary["total_speakers"] == 2
        assert "successful_extractions" in summary
        assert "failed_extractions" in summary
        assert "average_quality" in summary
        assert 0.0 <= summary["average_quality"] <= 1.0

    def test_aggregate_speaker_data_patterns(self, extractor, sample_speaker_data):
        """Test pattern extraction in aggregation."""
        result = extractor.aggregate_speaker_data(sample_speaker_data)
        patterns = result["patterns"]

        assert "common_fields" in patterns
        assert isinstance(patterns["common_fields"], list)
        assert "field_frequency" in patterns
        assert isinstance(patterns["field_frequency"], dict)
        assert "data_types" in patterns
        assert isinstance(patterns["data_types"], dict)

    def test_aggregate_speaker_data_statistics(self, extractor, sample_speaker_data):
        """Test statistics calculation in aggregation."""
        result = extractor.aggregate_speaker_data(sample_speaker_data)
        stats = result["statistics"]

        assert "data_sizes" in stats
        assert "quality_scores" in stats
        # Each should have mean, std, min, max, count
        for stat_key in ["data_sizes", "quality_scores"]:
            if stat_key in stats:
                stat_data = stats[stat_key]
                assert "mean" in stat_data
                assert "std" in stat_data
                assert "min" in stat_data
                assert "max" in stat_data
                assert "count" in stat_data

    def test_aggregate_speaker_data_with_errors(self, extractor):
        """Test aggregation with some failed extractions."""
        speaker_data = {
            "SPEAKER_00": {
                "data": {"field": "value"},
                "quality_metrics": {
                    "completeness": 1.0,
                    "consistency": 1.0,
                    "validity": 1.0,
                },
            },
            "SPEAKER_01": {"error": "Extraction failed"},
        }

        result = extractor.aggregate_speaker_data(speaker_data)
        summary = result["summary"]

        assert summary["successful_extractions"] == 1
        assert summary["failed_extractions"] == 1

    def test_aggregate_speaker_data_error_handling(self, extractor):
        """Test aggregation error handling."""
        # Create data that causes exception
        with patch.object(
            extractor, "_get_timestamp", side_effect=Exception("Test error")
        ):
            speaker_data = {"SPEAKER_00": {"data": {"field": "value"}}}
            result = extractor.aggregate_speaker_data(speaker_data)

            assert "error" in result
            assert result["module"] == "test_module"

    def test_create_summary(self, extractor, sample_speaker_data):
        """Test summary creation."""
        summary = extractor._create_summary(sample_speaker_data)

        assert summary["total_speakers"] == 2
        assert summary["successful_extractions"] == 2
        assert summary["failed_extractions"] == 0
        assert "average_quality" in summary

    def test_extract_patterns(self, extractor, sample_speaker_data):
        """Test pattern extraction."""
        patterns = extractor._extract_patterns(sample_speaker_data)

        assert "common_fields" in patterns
        assert "field_frequency" in patterns
        assert "data_types" in patterns
        assert isinstance(patterns["common_fields"], list)
        assert isinstance(patterns["field_frequency"], dict)
        assert isinstance(patterns["data_types"], dict)

    def test_calculate_statistics(self, extractor, sample_speaker_data):
        """Test statistics calculation."""
        stats = extractor._calculate_statistics(sample_speaker_data)

        assert "data_sizes" in stats
        assert "quality_scores" in stats
        assert "extraction_times" in stats


class TestBaseExtractorFileOperations:
    """Tests for file save/load operations."""

    @pytest.fixture
    def extractor(self):
        """Fixture for extractor."""
        return ConcreteDataExtractor("test_module")

    def test_save_extracted_data_success(self, extractor, tmp_path):
        """Test successful data saving."""
        data = {"test": "data", "number": 42}
        output_path = str(tmp_path / "test_output.json")

        result = extractor.save_extracted_data(data, output_path)

        assert result is True
        assert Path(output_path).exists()

        # Verify content
        with open(output_path, "r") as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_save_extracted_data_creates_directory(self, extractor, tmp_path):
        """Test that save creates directory if needed."""
        data = {"test": "data"}
        output_path = str(tmp_path / "subdir" / "test_output.json")

        result = extractor.save_extracted_data(data, output_path)

        assert result is True
        assert Path(output_path).exists()
        assert Path(output_path).parent.exists()

    def test_save_extracted_data_error_handling(self, extractor):
        """Test save error handling."""
        # Invalid path (read-only directory or permission error)
        invalid_path = "/invalid/path/that/does/not/exist/test.json"

        result = extractor.save_extracted_data({"test": "data"}, invalid_path)

        assert result is False

    def test_save_extracted_data_with_numpy_types(self, extractor, tmp_path):
        """Test saving data with numpy types."""
        data = {
            "numpy_int": np.int64(42),
            "numpy_float": np.float64(3.14),
            "numpy_array": np.array([1, 2, 3]),
        }
        output_path = str(tmp_path / "test_numpy.json")

        result = extractor.save_extracted_data(data, output_path)

        assert result is True
        # Should handle numpy types via default=str in json.dump

    def test_load_extracted_data_success(self, extractor, tmp_path):
        """Test successful data loading."""
        data = {"test": "data", "number": 42}
        input_path = tmp_path / "test_input.json"
        input_path.write_text(json.dumps(data))

        result = extractor.load_extracted_data(str(input_path))

        assert result == data

    def test_load_extracted_data_not_found(self, extractor):
        """Test loading non-existent file."""
        result = extractor.load_extracted_data("/nonexistent/path.json")

        assert result is None

    def test_load_extracted_data_invalid_json(self, extractor, tmp_path):
        """Test loading invalid JSON."""
        input_path = tmp_path / "invalid.json"
        input_path.write_text("not valid json {")

        result = extractor.load_extracted_data(str(input_path))

        assert result is None


class TestBaseExtractorIntegration:
    """Integration tests for base extractor with concrete implementations."""

    def test_inheritance_patterns(self):
        """Test that concrete extractors properly inherit from base."""
        extractor = ConcreteDataExtractor("test")

        # Should have all base class methods
        assert hasattr(extractor, "validate_data")
        assert hasattr(extractor, "transform_data")
        assert hasattr(extractor, "aggregate_speaker_data")
        assert hasattr(extractor, "extract_data")

    def test_concrete_implementations_use_base(self):
        """Test that concrete implementations use base class methods."""
        extractor = ConcreteDataExtractor("test")
        data = {"field": "value"}

        # Should use base class validation
        result = extractor.validate_data(data, "SPEAKER_00")
        assert result is True

        # Should use base class transformation
        transformed = extractor.transform_data(data, "SPEAKER_00")
        assert "speaker_id" in transformed
        assert "module" in transformed
        assert "data" in transformed

    def test_shared_utilities_integration(self):
        """Test integration with shared utilities (similarity_calculator)."""
        # The base extractor imports similarity_calculator
        # This test verifies the import works
        from transcriptx.core.utils.similarity_utils import similarity_calculator

        assert similarity_calculator is not None
        # Verify it can be used
        similarity = similarity_calculator.calculate_text_similarity("hello", "world")
        assert 0.0 <= similarity <= 1.0

    def test_full_extraction_workflow(self, tmp_path):
        """Test complete extraction workflow."""
        extractor = ConcreteDataExtractor("test_module")

        # Extract data
        analysis_results = {"segments": []}
        extracted = extractor.extract_data(analysis_results, "SPEAKER_00")

        # Validate
        is_valid = extractor.validate_data(extracted, "SPEAKER_00")
        assert is_valid is True

        # Transform
        transformed = extractor.transform_data(extracted, "SPEAKER_00")
        assert "quality_metrics" in transformed

        # Save
        output_path = str(tmp_path / "extracted.json")
        saved = extractor.save_extracted_data(transformed, output_path)
        assert saved is True

        # Load
        loaded = extractor.load_extracted_data(output_path)
        assert loaded is not None
        assert "speaker_id" in loaded
