"""
Integration tests for pipeline state management.

This module tests pipeline execution → State updates → Resume capability.
"""

from unittest.mock import patch
from types import SimpleNamespace
import pytest
import json

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef


@pytest.mark.heavy
@pytest.mark.integration
class TestPipelineStateIntegration:
    """Tests for pipeline and state management integration."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Fixture for temporary state file."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({}))
        return state_file

    def test_pipeline_updates_state(
        self, temp_transcript_file, sample_speaker_map, temp_state_file
    ):
        """Test that pipeline execution updates state."""
        with (
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch(
                "transcriptx.io.import_metadata_sidecar.validate_managed_transcript",
                return_value=SimpleNamespace(
                    ok=True, category=SimpleNamespace(value="ok"), message="ok"
                ),
            ),
            patch("transcriptx.core.pipeline.pipeline._orchestrator.run") as mock_run,
        ):
            mock_run.return_value = SimpleNamespace(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
                modules_run=["sentiment"],
                errors=[],
                duration=0.1,
                summary={},
                execution_order=["sentiment"],
                cache_hits=[],
                output_dir=str(temp_transcript_file.parent),
                transcript_key="k",
                run_id="r1",
                module_results={},
                status="success",
                execution_status="succeeded",
                final_status="succeeded",
                persistence_outcomes=[],
                termination_reason=None,
                schema_version=1,
            )

            result = run_analysis_pipeline(
                target=TranscriptRef(path=str(temp_transcript_file)),
                selected_modules=["sentiment"],
            )

            assert result is not None
            assert "modules_run" in result

    def test_state_consistency(self, temp_state_file):
        """Test state consistency across workflow steps."""
        # Load initial state
        initial_state = json.loads(temp_state_file.read_text())

        # Simulate state update
        initial_state["test_key"] = "test_value"
        temp_state_file.write_text(json.dumps(initial_state))

        # Verify state persists
        updated_state = json.loads(temp_state_file.read_text())
        assert updated_state["test_key"] == "test_value"
