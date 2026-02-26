"""
Tests for OutputService interface and file generation.

This module tests the OutputService class including data saving,
chart generation, and output structure management.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.output.output_service import OutputService
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.core.utils.config import TranscriptXConfig, set_config
from transcriptx.core.utils._path_core import get_canonical_base_name


class TestOutputService:
    """Tests for OutputService class."""

    @pytest.fixture
    def output_service(self, temp_transcript_file):
        """Fixture for OutputService instance."""
        return OutputService(str(temp_transcript_file), "sentiment")

    def test_output_service_initialization(self, temp_transcript_file):
        """Test OutputService initialization."""
        service = OutputService(str(temp_transcript_file), "sentiment")

        assert service.transcript_path == str(temp_transcript_file)
        assert service.module_name == "sentiment"
        assert service.base_name == get_canonical_base_name(str(temp_transcript_file))
        assert service.output_structure is not None

    def test_save_data_json(self, output_service, tmp_path):
        """Test saving JSON data."""
        data = {"result": "test", "value": 42}

        with patch("transcriptx.core.output.output_service.save_json") as mock_save:
            file_path = output_service.save_data(
                data, "test_results", format_type="json"
            )

        assert file_path is not None
        mock_save.assert_called_once()

    def test_save_data_csv(self, output_service):
        """Test saving CSV data."""
        data = [{"col1": "val1", "col2": "val2"}]

        with patch("transcriptx.core.output.output_service.save_csv") as mock_save:
            file_path = output_service.save_data(
                data, "test_results", format_type="csv"
            )

        assert file_path is not None
        mock_save.assert_called_once()

    def test_save_data_txt(self, output_service, tmp_path):
        """Test saving text data."""
        data = "Simple text content"

        file_path = output_service.save_data(data, "test_results", format_type="txt")

        # Should create file
        assert Path(file_path).exists()
        assert Path(file_path).read_text() == data

    def test_save_data_with_subdirectory(self, output_service):
        """Test saving data to subdirectory."""
        data = {"result": "test"}

        with patch("transcriptx.core.output.output_service.save_json") as mock_save:
            file_path = output_service.save_data(
                data, "test_results", format_type="json", subdirectory="nested"
            )

        assert file_path is not None
        # Verify subdirectory was used
        call_args = mock_save.call_args[0][1]
        assert "nested" in call_args

    def test_skip_unidentified_override(self, temp_transcript_file):
        """Include-unidentified override should bypass exclusion."""
        config = TranscriptXConfig()
        config.analysis.exclude_unidentified_from_speaker_charts = True
        set_config(config)

        service = OutputService(
            str(temp_transcript_file),
            "sentiment",
            runtime_flags={
                "include_unidentified_speakers": False,
                "named_speaker_keys": {"1"},
            },
        )
        assert service._should_skip_speaker_artifact("1") is False
        assert service._should_skip_speaker_artifact("2") is True

        override_service = OutputService(
            str(temp_transcript_file),
            "sentiment",
            runtime_flags={
                "include_unidentified_speakers": True,
                "named_speaker_keys": {"1"},
            },
        )
        assert override_service._should_skip_speaker_artifact("2") is False

    def test_save_chart_global(self, output_service):
        """Test saving global chart."""
        with patch(
            "transcriptx.core.output.output_service.save_static_chart"
        ) as mock_save:
            mock_save.return_value = Path("static.png")
            spec = BarCategoricalSpec(
                viz_id="sentiment.test_chart.global",
                module="sentiment",
                name="test_chart",
                scope="global",
                chart_intent="bar_categorical",
                title="Test Chart",
                x_label="Category",
                y_label="Value",
                categories=["a"],
                values=[1],
            )
            with patch(
                "transcriptx.core.output.output_service.render_mpl",
                return_value=MagicMock(),
            ):
                result = output_service.save_chart(spec)

        assert result["static"] is not None
        mock_save.assert_called_once()

    def test_save_chart_speaker(self, output_service):
        """Test saving speaker chart."""
        with patch(
            "transcriptx.core.output.output_service.save_static_chart"
        ) as mock_save:
            mock_save.return_value = Path("speaker.png")
            spec = BarCategoricalSpec(
                viz_id="sentiment.test_chart.speaker",
                module="sentiment",
                name="test_chart",
                scope="speaker",
                speaker="Alice",
                chart_intent="bar_categorical",
                title="Test Chart",
                x_label="Category",
                y_label="Value",
                categories=["a"],
                values=[1],
            )
            with patch(
                "transcriptx.core.output.output_service.render_mpl",
                return_value=MagicMock(),
            ):
                result = output_service.save_chart(spec)

        assert result["static"] is not None
        mock_save.assert_called_once()

    def test_save_summary(self, output_service):
        """Test generating summary JSON."""
        results = {"status": "success", "data": "test"}

        with patch(
            "transcriptx.core.output.output_service.create_summary_json"
        ) as mock_create:
            summary_path = output_service.save_summary(
                results, {}, analysis_metadata={}
            )

        assert summary_path is not None
        mock_create.assert_called_once()

    def test_dynamic_charts_enabled_and_available(self, output_service):
        """Dynamic ON + Plotly available should save HTML."""
        config = TranscriptXConfig()
        config.output.dynamic_charts = "auto"
        set_config(config)

        with (
            patch(
                "transcriptx.core.output.output_service.is_plotly_available",
                return_value=True,
            ),
            patch(
                "transcriptx.core.output.output_service.save_dynamic_chart"
            ) as mock_dynamic,
            patch(
                "transcriptx.core.output.output_service.save_static_chart"
            ) as mock_static,
        ):
            mock_static.return_value = Path("static.png")
            mock_dynamic.return_value = Path("dynamic.html")
            spec = BarCategoricalSpec(
                viz_id="sentiment.test_chart.global",
                module="sentiment",
                name="test_chart",
                scope="global",
                chart_intent="bar_categorical",
                title="Test Chart",
                x_label="Category",
                y_label="Value",
                categories=["a"],
                values=[1],
            )
            with (
                patch(
                    "transcriptx.core.output.output_service.render_mpl",
                    return_value=MagicMock(),
                ),
                patch(
                    "transcriptx.core.output.output_service.render_plotly",
                    return_value=MagicMock(),
                ),
            ):
                result = output_service.save_chart(spec)

        assert result["dynamic"] is not None
        mock_dynamic.assert_called_once()

    def test_dynamic_charts_disabled(self, output_service):
        """Dynamic OFF should skip HTML output."""
        config = TranscriptXConfig()
        config.output.dynamic_charts = "off"
        set_config(config)

        with (
            patch(
                "transcriptx.core.output.output_service.save_dynamic_chart"
            ) as mock_dynamic,
            patch(
                "transcriptx.core.output.output_service.save_static_chart"
            ) as mock_static,
        ):
            mock_static.return_value = Path("static.png")
            spec = BarCategoricalSpec(
                viz_id="sentiment.test_chart.global",
                module="sentiment",
                name="test_chart",
                scope="global",
                chart_intent="bar_categorical",
                title="Test Chart",
                x_label="Category",
                y_label="Value",
                categories=["a"],
                values=[1],
            )
            with patch(
                "transcriptx.core.output.output_service.render_mpl",
                return_value=MagicMock(),
            ):
                result = output_service.save_chart(spec)

        assert result["dynamic"] is None
        mock_dynamic.assert_not_called()

    def test_dynamic_charts_missing_plotly_warns(self, output_service):
        """Dynamic ON + Plotly missing should warn and skip HTML."""
        config = TranscriptXConfig()
        config.output.dynamic_charts = "auto"
        set_config(config)

        with (
            patch(
                "transcriptx.core.output.output_service.is_plotly_available",
                return_value=False,
            ),
            patch(
                "transcriptx.core.output.output_service.warn_missing_plotly_once"
            ) as mock_warn,
            patch(
                "transcriptx.core.output.output_service.save_dynamic_chart"
            ) as mock_dynamic,
            patch(
                "transcriptx.core.output.output_service.save_static_chart"
            ) as mock_static,
        ):
            mock_static.return_value = Path("static.png")
            spec = BarCategoricalSpec(
                viz_id="sentiment.test_chart.global",
                module="sentiment",
                name="test_chart",
                scope="global",
                chart_intent="bar_categorical",
                title="Test Chart",
                x_label="Category",
                y_label="Value",
                categories=["a"],
                values=[1],
            )
            with patch(
                "transcriptx.core.output.output_service.render_mpl",
                return_value=MagicMock(),
            ):
                result = output_service.save_chart(spec)

        assert result["dynamic"] is None
        mock_warn.assert_called_once()
        mock_dynamic.assert_not_called()

    def test_output_structure_creation(self, temp_transcript_file):
        """Test that output structure is created correctly."""
        service = OutputService(str(temp_transcript_file), "sentiment")

        assert service.output_structure.data_dir is not None
        assert service.output_structure.global_data_dir is not None
        assert service.output_structure.charts_dir is not None
