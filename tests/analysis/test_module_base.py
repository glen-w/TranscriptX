"""
Tests for AnalysisModule base class.

This module tests the AnalysisModule interface and its methods
including run_from_context and run_from_file.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.base import AnalysisModule


class MockAnalysisModule(AnalysisModule):
    """Mock analysis module for testing."""
    
    def __init__(self):
        super().__init__()
        self.module_name = "test_module"
    
    def analyze(self, segments, speaker_map=None):
        """Mock analyze method."""
        return {"result": "test", "segments_processed": len(segments)}
    
    def validate_input(self, segments):
        """Mock validate_input method."""
        return len(segments) > 0
    
    def save_results(self, results, output_service=None, output_structure=None, base_name=None):
        """Mock save_results method."""
        return super().save_results(
            results,
            output_service=output_service,
            output_structure=output_structure,
            base_name=base_name,
        )


class TestAnalysisModule:
    """Tests for AnalysisModule base class."""
    
    def test_module_initialization(self):
        """Test AnalysisModule initialization."""
        module = MockAnalysisModule()
        
        assert module.module_name == "test_module"
        assert hasattr(module, "analyze")
        assert hasattr(module, "validate_input")
        assert hasattr(module, "save_results")
    
    def test_analyze_method(self):
        """Test analyze method."""
        module = MockAnalysisModule()
        segments = [
            {"speaker": "SPEAKER_00", "text": "Test", "start": 0.0, "end": 1.0}
        ]
        
        result = module.analyze(segments)
        
        assert result["result"] == "test"
        assert result["segments_processed"] == 1
    
    def test_validate_input(self):
        """Test validate_input method."""
        module = MockAnalysisModule()
        
        valid_segments = [{"speaker": "SPEAKER_00", "text": "Test"}]
        assert module.validate_input(valid_segments) is True
        
        invalid_segments = []
        assert module.validate_input(invalid_segments) is False
    
    def test_get_dependencies(self):
        """Test get_dependencies method."""
        module = MockAnalysisModule()
        
        deps = module.get_dependencies()
        
        assert isinstance(deps, list)
    
    @patch('transcriptx.core.analysis.base.create_output_service')
    @patch('transcriptx.core.analysis.base.log_analysis_start')
    @patch('transcriptx.core.analysis.base.log_analysis_complete')
    def test_run_from_context(
        self, mock_log_complete, mock_log_start, mock_output_service, pipeline_context_factory
    ):
        """Test run_from_context method."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()
        
        mock_output_service.return_value = MagicMock(
            get_output_structure=MagicMock(return_value={"module_dir": "/tmp/test"})
        )
        
        result = module.run_from_context(context)
        
        assert result["module"] == "test_module"
        assert result["status"] == "success"
        assert "results" in result
        assert "output_directory" in result
    
    @patch('transcriptx.core.analysis.base.create_output_service')
    @patch('transcriptx.core.analysis.base.log_analysis_start')
    @patch('transcriptx.core.analysis.base.log_analysis_complete')
    def test_run_from_context_invalid_input(
        self, mock_log_complete, mock_log_start, mock_output_service, pipeline_context_factory
    ):
        """Test run_from_context with invalid input."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()
        
        # Set empty segments to trigger validation failure
        context.set_segments([])
        
        with pytest.raises(ValueError, match="Invalid input"):
            module.run_from_context(context)
    
    @patch('transcriptx.core.analysis.base.load_transcript_data')
    @patch('transcriptx.core.analysis.base.create_module_output_structure')
    @patch('transcriptx.core.analysis.base.log_analysis_start')
    @patch('transcriptx.core.analysis.base.log_analysis_complete')
    def test_run_from_file(
        self, mock_log_complete, mock_log_start, mock_output_structure, mock_load_data, temp_transcript_file
    ):
        """Test run_from_file method (legacy)."""
        module = MockAnalysisModule()
        
        mock_load_data.return_value = (
            [{"speaker": "SPEAKER_00", "text": "Test", "start": 0.0, "end": 1.0}],
            "test",
            "/tmp",
            {"SPEAKER_00": "Speaker 1"}
        )
        mock_output_structure.return_value = {"module_dir": "/tmp/test"}
        
        result = module.run_from_file(str(temp_transcript_file))
        
        assert result["module"] == "test_module"
        assert result["status"] == "success"
        assert "results" in result
    
    def test_store_analysis_result_in_context(self, pipeline_context_factory):
        """Test that run_from_context stores results in context."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()
        
        with patch('transcriptx.core.analysis.base.create_output_service') as mock_output, \
             patch('transcriptx.core.analysis.base.log_analysis_start'), \
             patch('transcriptx.core.analysis.base.log_analysis_complete'):
            
            mock_output.return_value = MagicMock(
                get_output_structure=MagicMock(return_value={"module_dir": "/tmp/test"})
            )
            
            module.run_from_context(context)
            
            # Verify result was stored
            stored_result = context.get_analysis_result("test_module")
            assert stored_result is not None

    def test_run_from_context_analyze_error(self, pipeline_context_factory):
        """Test run_from_context returns error result when analyze raises."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        with patch.object(module, "analyze", side_effect=RuntimeError("boom")), \
             patch('transcriptx.core.analysis.base.create_output_service') as mock_output, \
             patch('transcriptx.core.analysis.base.log_analysis_start'), \
             patch('transcriptx.core.analysis.base.log_analysis_complete'), \
             patch('transcriptx.core.analysis.base.log_analysis_error'):
            mock_output.return_value = MagicMock(
                get_output_structure=MagicMock(return_value={"module_dir": "/tmp/test"})
            )
            result = module.run_from_context(context)

        assert result["status"] == "error"
        assert "boom" in str(result.get("error", {}))

    def test_run_from_context_save_results_error(self, pipeline_context_factory):
        """Test run_from_context returns error result when save_results fails."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        with patch.object(module, "save_results", side_effect=RuntimeError("save failed")), \
             patch('transcriptx.core.analysis.base.create_output_service') as mock_output, \
             patch('transcriptx.core.analysis.base.log_analysis_start'), \
             patch('transcriptx.core.analysis.base.log_analysis_complete'), \
             patch('transcriptx.core.analysis.base.log_analysis_error'):
            mock_output.return_value = MagicMock(
                get_output_structure=MagicMock(return_value={"module_dir": "/tmp/test"})
            )
            result = module.run_from_context(context)

        assert result["status"] == "error"
        assert "save failed" in str(result.get("error", {}))

    def test_save_results_requires_output_target(self):
        """Test save_results enforces output_service or legacy output structure."""
        module = MockAnalysisModule()
        with pytest.raises(ValueError, match="Either output_service"):
            module.save_results({"result": "test"})

    def test_run_from_file_fallback_error(self, temp_transcript_file):
        """Test legacy run_from_file returns error on invalid input."""
        module = MockAnalysisModule()

        with patch('transcriptx.core.analysis.base.PipelineContext', None), \
             patch('transcriptx.core.analysis.base.load_transcript_data') as mock_load, \
             patch('transcriptx.core.analysis.base.create_module_output_structure') as mock_output, \
             patch('transcriptx.core.analysis.base.log_analysis_start'), \
             patch('transcriptx.core.analysis.base.log_analysis_complete'), \
             patch('transcriptx.core.analysis.base.log_analysis_error'):
            mock_load.return_value = ([], "test", "/tmp", {})
            mock_output.return_value = {"module_dir": "/tmp/test"}

            result = module.run_from_file(str(temp_transcript_file))

        assert result["status"] == "error"
