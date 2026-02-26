"""
Integration tests for output service.

This module tests: Analysis results → Output service → File generation.
"""

from pathlib import Path

import pytest

from transcriptx.core.output.output_service import OutputService


@pytest.mark.integration
class TestOutputServiceIntegration:
    """Tests for output service integration."""

    @pytest.fixture
    def temp_output_dir(self, tmp_path: Path) -> Path:
        """Fixture for temporary output directory."""
        output_dir = tmp_path / "outputs"
        output_dir.mkdir()
        return output_dir

    @pytest.fixture
    def transcript_path(self, tmp_path: Path) -> str:
        transcript_path = tmp_path / "test_transcript.json"
        transcript_path.write_text('{"segments": []}')
        return str(transcript_path)

    @pytest.fixture
    def sample_analysis_results(self):
        """Fixture for sample analysis results."""
        return {
            "segments": [{"speaker": "SPEAKER_00", "sentiment_score": 0.8}],
            "summary": {"average_sentiment": 0.8},
        }

    def test_output_service_file_generation(
        self, temp_output_dir: Path, transcript_path: str, sample_analysis_results
    ) -> None:
        """Test that output service generates files correctly."""
        output_service = OutputService(
            transcript_path=transcript_path,
            module_name="sentiment",
            output_dir=str(temp_output_dir),
        )

        # Save data
        output_service.save_data(
            sample_analysis_results, "sentiment", format_type="json"
        )

        # Verify file was created at standardized location
        output_path = (
            output_service.output_structure.global_data_dir
            / f"{output_service.base_name}_sentiment.json"
        )
        assert output_path.exists()

    def test_output_directory_structure(
        self, temp_output_dir: Path, transcript_path: str
    ) -> None:
        """Test output directory structure creation."""
        output_service = OutputService(
            transcript_path=transcript_path,
            module_name="sentiment",
            output_dir=str(temp_output_dir),
        )

        output_structure = output_service.get_output_structure()
        assert output_structure.module_dir.name == "sentiment"
        assert output_structure.global_data_dir.name == "global"
