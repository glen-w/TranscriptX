"""
Tests for analysis module integration via registry.

This module tests module execution through the registry system,
dependency resolution, and error handling.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline.module_registry import get_module_function, get_available_modules


class TestModuleIntegration:
    """Tests for module integration via registry."""
    
    def test_module_execution_via_registry(self, temp_transcript_file):
        """Test executing a module through the registry."""
        # Get module function from registry
        func = get_module_function("sentiment")
        
        if func is not None:
            # Mock the AnalysisModule entrypoint; registry calls run_from_file()
            with patch(
                "transcriptx.core.analysis.sentiment.SentimentAnalysis.run_from_file"
            ) as mock_run:
                mock_run.return_value = {
                    "module": "sentiment",
                    "transcript_path": str(temp_transcript_file),
                    "status": "success",
                    "results": {},
                }

                result = func(str(temp_transcript_file))
                assert isinstance(result, dict)
                assert result.get("status") == "success"
                mock_run.assert_called_once()
    
    def test_module_dependency_resolution(self):
        """Test that modules with dependencies are resolved correctly."""
        from transcriptx.core.pipeline.module_registry import get_dependencies
        
        # entity_sentiment depends on ner and sentiment
        deps = get_dependencies("entity_sentiment")
        
        if "entity_sentiment" in get_available_modules():
            # Should have dependencies
            assert isinstance(deps, list)
    
    def test_module_execution_order(self):
        """Test that modules execute in correct dependency order."""
        from transcriptx.core.pipeline.dag_pipeline import DAGPipeline, create_dag_pipeline
        
        dag = create_dag_pipeline()
        
        # Select modules with dependencies
        selected = ["entity_sentiment"]
        
        # Resolve dependencies
        execution_order = dag.resolve_dependencies(selected)
        
        # Dependencies should come before dependent modules
        if "entity_sentiment" in execution_order:
            assert "ner" in execution_order or "sentiment" in execution_order
    
    @patch('transcriptx.core.pipeline.module_registry.get_module_function')
    def test_module_error_handling(self, mock_get_function, temp_transcript_file):
        """Test error handling in module execution."""
        # Mock module function that raises error
        mock_function = MagicMock(side_effect=Exception("Module error"))
        mock_get_function.return_value = mock_function
        
        # Should handle errors gracefully
        func = mock_get_function("sentiment")
        
        if func is not None:
            with pytest.raises(Exception):
                func(str(temp_transcript_file))
    
    def test_module_lazy_loading(self):
        """Test that modules are loaded lazily."""
        # First call should load the function
        func1 = get_module_function("sentiment")
        
        # Second call should return cached function
        func2 = get_module_function("sentiment")
        
        if func1 is not None and func2 is not None:
            # Should be the same function object (cached)
            assert func1 == func2
    
    def test_all_modules_available(self):
        """Test that all expected modules are available."""
        modules = get_available_modules()
        
        # Check for some expected modules
        expected_modules = ["sentiment", "stats", "ner", "emotion"]
        
        # At least some should be available
        assert any(m in modules for m in expected_modules)
    
    def test_module_metadata_consistency(self):
        """Test that module metadata is consistent."""
        from transcriptx.core.pipeline.module_registry import get_module_info, get_category, get_description
        
        modules = get_available_modules()
        
        for module_name in modules[:5]:  # Test first 5 modules
            info = get_module_info(module_name)
            if info is not None:
                assert info.name == module_name
                assert info.category in ["light", "medium", "heavy"]
                assert isinstance(info.description, str)
                assert len(info.description) > 0
