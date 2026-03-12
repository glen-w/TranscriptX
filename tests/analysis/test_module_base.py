"""
Tests for AnalysisModule base class.

This module tests the AnalysisModule interface and its methods
including run_from_context and run_from_file.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.base import (
    AnalysisModule,
    AnalysisResult,
    create_analysis_module,
    validate_module_interface,
)


class MockAnalysisModule(AnalysisModule):
    """Mock analysis module for testing."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config=config)
        self.module_name = "test_module"

    def analyze(
        self, segments: list[dict[str, Any]], speaker_map: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Mock analyze method."""
        return {"result": "test", "segments_processed": len(segments)}

    def validate_input(self, segments: list[dict[str, Any]]) -> bool:
        """Mock validate_input method."""
        return len(segments) > 0


class TestAnalysisModule:
    """Tests for AnalysisModule base class."""

    def test_module_initialization(self) -> None:
        """Test AnalysisModule initialization."""
        module = MockAnalysisModule()

        assert module.module_name == "test_module"
        assert hasattr(module, "analyze")
        assert hasattr(module, "validate_input")
        assert hasattr(module, "save_results")

    def test_analyze_method(self) -> None:
        """Test analyze method."""
        module = MockAnalysisModule()
        segments = [{"speaker": "SPEAKER_00", "text": "Test", "start": 0.0, "end": 1.0}]

        result = module.analyze(segments)

        assert result["result"] == "test"
        assert result["segments_processed"] == 1

    def test_validate_input(self) -> None:
        """Test validate_input method."""
        module = MockAnalysisModule()

        valid_segments = [{"speaker": "SPEAKER_00", "text": "Test"}]
        assert module.validate_input(valid_segments) is True

        invalid_segments = []
        assert module.validate_input(invalid_segments) is False

    def test_get_dependencies(self) -> None:
        """Test get_dependencies method."""
        module = MockAnalysisModule()

        deps = module.get_dependencies()

        assert isinstance(deps, list)

    @patch("transcriptx.core.analysis.base.create_output_service")
    @patch("transcriptx.core.analysis.base.log_analysis_start")
    @patch("transcriptx.core.analysis.base.log_analysis_complete")
    def test_run_from_context(
        self,
        mock_log_complete,
        mock_log_start,
        mock_output_service,
        pipeline_context_factory,
    ) -> None:
        """Test run_from_context method."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        mock_output_service.return_value = MagicMock(
            save_data=MagicMock(),
            get_artifacts=MagicMock(return_value=[]),
            get_output_structure=MagicMock(return_value={"module_dir": "/tmp/test"}),
        )

        result = module.run_from_context(context)

        assert result["module"] == "test_module"
        assert result["status"] == "success"
        assert "results" in result
        assert "output_directory" in result

    @patch("transcriptx.core.analysis.base.create_output_service")
    @patch("transcriptx.core.analysis.base.log_analysis_start")
    @patch("transcriptx.core.analysis.base.log_analysis_complete")
    def test_run_from_context_invalid_input(
        self,
        mock_log_complete,
        mock_log_start,
        mock_output_service,
        pipeline_context_factory,
    ) -> None:
        """Test run_from_context with invalid input."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        # Set empty segments to trigger validation failure
        context.set_segments([])

        with pytest.raises(ValueError, match="Invalid input"):
            module.run_from_context(context)

    @patch("transcriptx.core.analysis.base.log_analysis_start")
    @patch("transcriptx.core.analysis.base.log_analysis_complete")
    def test_run_from_file(
        self,
        mock_log_complete,
        mock_log_start,
        pipeline_context_factory,
        temp_transcript_file,
    ) -> None:
        """Test run_from_file delegates to PipelineContext + run_from_context."""
        module = MockAnalysisModule()

        context = pipeline_context_factory(transcript_path=str(temp_transcript_file))
        with (
            patch(
                "transcriptx.core.analysis.base.PipelineContext", return_value=context
            ),
            patch(
                "transcriptx.core.analysis.base.create_output_service"
            ) as mock_output_service,
        ):
            mock_output_service.return_value = MagicMock(
                save_data=MagicMock(),
                get_artifacts=MagicMock(return_value=[]),
                get_output_structure=MagicMock(
                    return_value={"module_dir": "/tmp/test"}
                ),
            )
            result = module.run_from_file(str(temp_transcript_file))

        assert result["module"] == "test_module"
        assert result["status"] == "success"
        assert "results" in result

    def test_store_analysis_result_in_context(self, pipeline_context_factory) -> None:
        """Test that run_from_context stores results in context."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        with (
            patch(
                "transcriptx.core.analysis.base.create_output_service"
            ) as mock_output,
            patch("transcriptx.core.analysis.base.log_analysis_start"),
            patch("transcriptx.core.analysis.base.log_analysis_complete"),
        ):
            mock_output.return_value = MagicMock(
                save_data=MagicMock(),
                get_artifacts=MagicMock(return_value=[]),
                get_output_structure=MagicMock(
                    return_value={"module_dir": "/tmp/test"}
                ),
            )

            module.run_from_context(context)

            # Verify result was stored
            stored_result = context.get_analysis_result("test_module")
            assert stored_result is not None

    def test_run_from_context_analyze_error(self, pipeline_context_factory) -> None:
        """Test run_from_context returns error result when analyze raises."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        with (
            patch.object(module, "analyze", side_effect=RuntimeError("boom")),
            patch(
                "transcriptx.core.analysis.base.create_output_service"
            ) as mock_output,
            patch("transcriptx.core.analysis.base.log_analysis_start"),
            patch("transcriptx.core.analysis.base.log_analysis_complete"),
            patch("transcriptx.core.analysis.base.log_analysis_error"),
        ):
            mock_output.return_value = MagicMock(
                save_data=MagicMock(),
                get_artifacts=MagicMock(return_value=[]),
                get_output_structure=MagicMock(
                    return_value={"module_dir": "/tmp/test"}
                ),
            )
            result = module.run_from_context(context)

        assert result["status"] == "error"
        assert "boom" in str(result.get("error", {}))

    def test_run_from_context_save_results_error(
        self, pipeline_context_factory
    ) -> None:
        """Test run_from_context returns error result when save_results fails."""
        module = MockAnalysisModule()
        context = pipeline_context_factory()

        with (
            patch.object(
                module, "save_results", side_effect=RuntimeError("save failed")
            ),
            patch(
                "transcriptx.core.analysis.base.create_output_service"
            ) as mock_output,
            patch("transcriptx.core.analysis.base.log_analysis_start"),
            patch("transcriptx.core.analysis.base.log_analysis_complete"),
            patch("transcriptx.core.analysis.base.log_analysis_error"),
        ):
            mock_output.return_value = MagicMock(
                save_data=MagicMock(),
                get_artifacts=MagicMock(return_value=[]),
                get_output_structure=MagicMock(
                    return_value={"module_dir": "/tmp/test"}
                ),
            )
            result = module.run_from_context(context)

        assert result["status"] == "error"
        assert "save failed" in str(result.get("error", {}))

    def test_save_results_requires_output_target(self) -> None:
        """save_results requires an OutputService in the new API."""
        module = MockAnalysisModule()
        with pytest.raises(TypeError):
            module.save_results({"result": "test"})

    def test_config_must_be_dict_or_none(self) -> None:
        """AnalysisModule raises TypeError if config is not None or dict."""
        with pytest.raises(TypeError, match="config must be None or a dict"):
            MockAnalysisModule(config="invalid")

    def test_aggregate_raises_not_implemented(self) -> None:
        """aggregate() raises NotImplementedError for non-aggregation modules."""
        module = MockAnalysisModule()
        with pytest.raises(NotImplementedError, match="does not support aggregation"):
            module.aggregate()

    def test_run_from_file_requires_pipeline_context(self) -> None:
        """run_from_file raises ImportError when PipelineContext is not available."""
        module = MockAnalysisModule()
        with patch(
            "transcriptx.core.analysis.base.PipelineContext",
            None,
        ):
            with pytest.raises(ImportError, match="PipelineContext is required"):
                module.run_from_file("/path/to/transcript.json")

    def test_get_module_info_returns_dict(self) -> None:
        """get_module_info returns name, description, version, dependencies."""
        module = MockAnalysisModule()
        info = module.get_module_info()
        assert "name" in info
        assert "description" in info
        assert "version" in info
        assert "dependencies" in info
        assert info["name"] == "test_module"


class TestAnalysisResult:
    """Tests for AnalysisResult container."""

    def test_to_dict(self) -> None:
        """to_dict returns module, transcript_path, status, results, errors, metadata."""
        r = AnalysisResult(
            module_name="m",
            transcript_path="/p",
            status="success",
            results={"k": "v"},
            errors=[],
            metadata={"x": 1},
        )
        d = r.to_dict()
        assert d["module"] == "m"
        assert d["transcript_path"] == "/p"
        assert d["status"] == "success"
        assert d["results"] == {"k": "v"}
        assert d["errors"] == []
        assert d["metadata"] == {"x": 1}

    def test_is_successful(self) -> None:
        """is_successful is True when status is success and no errors."""
        assert AnalysisResult("m", "/p", "success", {}, []).is_successful() is True
        assert (
            AnalysisResult("m", "/p", "success", {}, ["e"]).is_successful() is False
        )
        assert AnalysisResult("m", "/p", "error", {}, []).is_successful() is False

    def test_has_errors(self) -> None:
        """has_errors is True when errors list non-empty or status is error."""
        assert AnalysisResult("m", "/p", "success", {}, []).has_errors() is False
        assert AnalysisResult("m", "/p", "success", {}, ["e"]).has_errors() is True
        assert AnalysisResult("m", "/p", "error", {}, []).has_errors() is True


class TestCreateAnalysisModule:
    """Tests for create_analysis_module factory."""

    def test_create_analysis_module_with_config(self) -> None:
        """create_analysis_module passes config to module class."""
        module = create_analysis_module(MockAnalysisModule, config={"key": "value"})
        assert isinstance(module, MockAnalysisModule)
        assert module.config == {"key": "value"}

    def test_create_analysis_module_no_config(self) -> None:
        """create_analysis_module with None config uses empty dict."""
        module = create_analysis_module(MockAnalysisModule)
        assert module.config == {}


class TestValidateModuleInterface:
    """Tests for validate_module_interface."""

    def test_validate_module_interface_valid(self) -> None:
        """validate_module_interface returns True for valid module."""
        module = MockAnalysisModule()
        assert validate_module_interface(module) is True

    def test_validate_module_interface_missing_method(self) -> None:
        """validate_module_interface returns False when required method is not callable."""
        class IncompleteModule(AnalysisModule):
            def analyze(self, segments, speaker_map=None):
                return {}
        # Make run_from_file non-callable so interface validation fails
        IncompleteModule.run_from_file = None  # type: ignore[assignment]
        module = IncompleteModule()
        assert validate_module_interface(module) is False
