"""
Integration tests for shared utilities across modules.

This module verifies that shared utilities (similarity_utils, base_extractor,
output_builder) work correctly when used by multiple analysis modules.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.similarity_utils import similarity_calculator
from transcriptx.core.data_extraction.base_extractor import BaseDataExtractor
from transcriptx.core.utils.output_builder import OutputStructureBuilder


# Concrete extractor implementations for testing
class MockExtractor1(BaseDataExtractor):
    """Mock extractor 1 for testing."""
    def extract_data(self, analysis_results, speaker_id):
        return {"field1": "value1", "score": 0.8}
    def get_required_fields(self):
        return ["field1"]


class MockExtractor2(BaseDataExtractor):
    """Mock extractor 2 for testing."""
    def extract_data(self, analysis_results, speaker_id):
        return {"field2": "value2", "count": 10}
    def get_required_fields(self):
        return ["field2"]


class TestSharedUtilitiesIntegration:
    """Integration tests for shared utilities."""
    
    def test_similarity_utils_used_across_modules(self):
        """Test that similarity_utils works consistently across modules."""
        # Module 1 uses similarity calculator
        text1 = "Python programming"
        text2 = "Python coding"
        similarity1 = similarity_calculator.calculate_text_similarity(text1, text2)
        
        # Module 2 uses same calculator
        text3 = "Python programming"
        text4 = "Python coding"
        similarity2 = similarity_calculator.calculate_text_similarity(text3, text4)
        
        # Should get same results (consistency)
        assert similarity1 == similarity2
        assert 0.0 <= similarity1 <= 1.0
    
    def test_base_extractor_used_by_all_extractors(self):
        """Test that all extractors use base extractor functionality."""
        extractor1 = MockExtractor1("module1")
        extractor2 = MockExtractor2("module2")
        
        # Both should have base class methods
        assert hasattr(extractor1, 'validate_data')
        assert hasattr(extractor1, 'transform_data')
        assert hasattr(extractor1, 'aggregate_speaker_data')
        
        assert hasattr(extractor2, 'validate_data')
        assert hasattr(extractor2, 'transform_data')
        assert hasattr(extractor2, 'aggregate_speaker_data')
        
        # Both should validate data correctly
        data1 = {"field1": "value1"}
        assert extractor1.validate_data(data1, "SPEAKER_00") is True
        
        data2 = {"field2": "value2"}
        assert extractor2.validate_data(data2, "SPEAKER_00") is True
    
    def test_output_builder_used_by_all_modules(self, tmp_path):
        """Test that output_builder works consistently across modules."""
        builder1 = OutputStructureBuilder("module1")
        builder2 = OutputStructureBuilder("module2")
        
        transcript_path = str(tmp_path / "test.json")
        
        # Both should create consistent structures
        structure1 = builder1.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )
        structure2 = builder2.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )
        
        # Both should have same keys
        assert set(structure1.keys()) == set(structure2.keys())
        # Both should create directories
        assert Path(structure1["module_dir"]).exists()
        assert Path(structure2["module_dir"]).exists()
    
    def test_consistency_across_modules_using_shared_utilities(self):
        """Test consistency when multiple modules use shared utilities."""
        # Multiple extractors using base class
        extractors = [
            MockExtractor1("module1"),
            MockExtractor2("module2")
        ]
        
        # All should transform data consistently
        for extractor in extractors:
            data = extractor.extract_data({}, "SPEAKER_00")
            transformed = extractor.transform_data(data, "SPEAKER_00")
            
            # Should have consistent structure
            assert "speaker_id" in transformed
            assert "module" in transformed
            assert "data" in transformed
            assert "metadata" in transformed
            assert "quality_metrics" in transformed
    
    def test_shared_utilities_performance(self):
        """Test that shared utilities perform well under load."""
        # Use similarity calculator many times
        similarities = []
        for i in range(100):
            similarity = similarity_calculator.calculate_text_similarity(
                f"text {i}", f"text {i+1}"
            )
            similarities.append(similarity)
        
        # Should complete without error
        assert len(similarities) == 100
        assert all(0.0 <= s <= 1.0 for s in similarities)
    
    def test_shared_utilities_error_handling(self):
        """Test that shared utilities handle errors gracefully."""
        # Similarity calculator with invalid input
        similarity = similarity_calculator.calculate_text_similarity("", "")
        assert similarity == 0.0
        
        # Base extractor with invalid data
        extractor = MockExtractor1("test")
        result = extractor.validate_data("not a dict", "SPEAKER_00")
        assert result is False
    
    def test_output_builder_concurrent_usage(self, tmp_path):
        """Test output_builder with concurrent-like usage."""
        builders = [
            OutputStructureBuilder(f"module{i}")
            for i in range(5)
        ]
        
        transcript_path = str(tmp_path / "test.json")
        
        # All should create structures without conflicts
        structures = []
        for builder in builders:
            structure = builder.create_standard_output_structure(
                transcript_path, base_output_dir=str(tmp_path)
            )
            structures.append(structure)
        
        # All should be created
        assert len(structures) == 5
        for structure in structures:
            assert Path(structure["module_dir"]).exists()
    
    def test_integration_similarity_with_extractors(self):
        """Test integration of similarity_utils with extractors."""
        extractor = MockExtractor1("test")
        
        # Extract data
        data1 = extractor.extract_data({}, "SPEAKER_00")
        data2 = extractor.extract_data({}, "SPEAKER_01")
        
        # Use similarity calculator to compare
        similarity = similarity_calculator.calculate_dict_similarity(
            data1, data2
        )
        
        assert 0.0 <= similarity <= 1.0
    
    def test_integration_extractors_with_output_builder(self, tmp_path):
        """Test integration of extractors with output_builder."""
        extractor = MockExtractor1("test")
        builder = OutputStructureBuilder("test")
        
        transcript_path = str(tmp_path / "test.json")
        structure = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )
        
        # Extract and save data
        data = extractor.extract_data({}, "SPEAKER_00")
        transformed = extractor.transform_data(data, "SPEAKER_00")
        
        # Save using output builder
        saved_path = builder.save_global_data(transformed, structure, "extracted.json")
        
        assert Path(saved_path).exists()
        with open(saved_path) as f:
            loaded = json.load(f)
            assert "speaker_id" in loaded
    
    def test_full_workflow_with_shared_utilities(self, tmp_path):
        """Test complete workflow using all shared utilities."""
        # Setup
        extractor = MockExtractor1("test")
        builder = OutputStructureBuilder("test")
        
        transcript_path = str(tmp_path / "test.json")
        structure = builder.create_standard_output_structure(
            transcript_path, base_output_dir=str(tmp_path)
        )
        
        # Extract data for multiple speakers
        speaker_data = {}
        for speaker_id in ["SPEAKER_00", "SPEAKER_01"]:
            data = extractor.extract_data({}, speaker_id)
            transformed = extractor.transform_data(data, speaker_id)
            speaker_data[speaker_id] = transformed
        
        # Aggregate using base extractor
        aggregated = extractor.aggregate_speaker_data(speaker_data)
        
        # Use similarity to compare speakers
        similarity = similarity_calculator.calculate_dict_similarity(
            speaker_data["SPEAKER_00"]["data"],
            speaker_data["SPEAKER_01"]["data"]
        )
        
        # Save results using output builder
        builder.save_global_data(aggregated, structure, "aggregated.json")
        builder.save_global_data({"similarity": similarity}, structure, "similarity.json")
        
        # Verify files exist
        assert Path(structure["global_data_dir"]) / "aggregated.json"
        assert Path(structure["global_data_dir"]) / "similarity.json"
        # Check that files were actually created
        assert (Path(structure["global_data_dir"]) / "aggregated.json").exists()
        assert (Path(structure["global_data_dir"]) / "similarity.json").exists()
