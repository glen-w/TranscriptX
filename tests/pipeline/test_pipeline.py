"""
Tests for the main analysis pipeline orchestrator.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.pipeline.pipeline import (
    run_analysis_pipeline,
    run_analysis_pipeline_from_file,
)


def _mock_canonical(segments=None):
    if segments is None:
        segments = [{"speaker": "Alice", "text": "Test", "start": 0.0, "end": 1.0}]
    return CanonicalTranscript.from_segments(segments)


class TestRunAnalysisPipeline:
    def test_run_analysis_pipeline_success(self, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch(
                "transcriptx.core.pipeline.pipeline.validate_transcript"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "transcript_path": str(temp_transcript_file),
                "modules_requested": ["sentiment", "stats"],
                "modules_run": ["sentiment", "stats"],
                "errors": [],
                "execution_order": ["sentiment", "stats"],
            }
            mock_create_dag.return_value = mock_dag
            mock_validate.return_value = None
            mock_summary.return_value = {"summary": "test"}
            mock_load_canonical.return_value = _mock_canonical()

            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment", "stats"],
            )

            assert result["transcript_path"] == str(temp_transcript_file)
            assert result["selected_modules"] == ["sentiment", "stats"]
            assert result["modules_run"] == ["sentiment", "stats"]
            assert result["errors"] == []
            assert "duration" in result
            assert "summary" in result
            assert "output_dir" in result
            assert "transcript_key" in result
            assert "run_id" in result
            assert result["run_id"] in result["output_dir"]

            mock_dag.execute_pipeline.assert_called_once()
            call_args = mock_dag.execute_pipeline.call_args
            assert call_args.kwargs["transcript_path"] == str(temp_transcript_file)
            assert call_args.kwargs["selected_modules"] == ["sentiment", "stats"]
            assert call_args.kwargs["output_dir"] == result["output_dir"]
            assert call_args.kwargs["transcript_key"] == result["transcript_key"]
            assert call_args.kwargs["run_id"] == result["run_id"]

    def test_run_analysis_pipeline_invalid_transcript(self, tmp_path):
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("invalid json")

        with patch(
            "transcriptx.core.pipeline.pipeline.validate_transcript"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Invalid transcript")
            with pytest.raises(ValueError, match="Invalid transcript"):
                run_analysis_pipeline(
                    transcript_path=str(invalid_file),
                    selected_modules=["sentiment"],
                )

    def test_run_analysis_pipeline_with_errors(self, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch(
                "transcriptx.core.pipeline.pipeline.validate_transcript"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["sentiment"],
                "errors": ["Error in stats module"],
                "execution_order": ["sentiment"],
            }
            mock_create_dag.return_value = mock_dag
            mock_validate.return_value = None
            mock_summary.return_value = {"summary": "test"}
            mock_load_canonical.return_value = _mock_canonical()

            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment", "stats"],
            )

            assert result["errors"] == ["Error in stats module"]
            assert len(result["modules_run"]) == 1

    def test_run_analysis_pipeline_parallel(self, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch(
                "transcriptx.core.pipeline.pipeline.validate_transcript"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["sentiment", "stats"],
                "errors": [],
                "execution_order": ["sentiment", "stats"],
            }
            mock_create_dag.return_value = mock_dag
            mock_validate.return_value = None
            mock_summary.return_value = {"summary": "test"}
            mock_load_canonical.return_value = _mock_canonical()

            run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment", "stats"],
                parallel=True,
                max_workers=2,
            )

            call_args = mock_dag.execute_pipeline.call_args
            assert call_args.kwargs["parallel"] is True
            assert call_args.kwargs["max_workers"] == 2

    def test_run_analysis_pipeline_large_transcript(self, temp_transcript_file):
        large_segments = [
            {
                "speaker": f"SPEAKER_{i % 5:02d}",
                "text": f"Segment {i}",
                "start": float(i),
                "end": float(i + 1),
            }
            for i in range(1000)
        ]
        temp_transcript_file.write_text(json.dumps({"segments": large_segments}))

        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch(
                "transcriptx.core.pipeline.pipeline.validate_transcript"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["sentiment"],
                "errors": [],
                "execution_order": ["sentiment"],
            }
            mock_create_dag.return_value = mock_dag
            mock_validate.return_value = None
            mock_summary.return_value = {"summary": "test"}
            mock_load_canonical.return_value = _mock_canonical(large_segments)

            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
            )

            assert result["modules_run"] == ["sentiment"]

    def test_run_analysis_pipeline_module_timeout(self, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch(
                "transcriptx.core.pipeline.pipeline.validate_transcript"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["sentiment"],
                "errors": ["Module stats timed out after 600 seconds"],
                "execution_order": ["sentiment"],
            }
            mock_create_dag.return_value = mock_dag
            mock_validate.return_value = None
            mock_summary.return_value = {"summary": "test"}
            mock_load_canonical.return_value = _mock_canonical()

            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment", "stats"],
            )

            assert len(result["errors"]) > 0
            assert "timed out" in result["errors"][0].lower()

    def test_run_analysis_pipeline_partial_failure(self, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch(
                "transcriptx.core.pipeline.pipeline.validate_transcript"
            ) as mock_validate,
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["sentiment"],
                "errors": ["Error in stats module"],
                "execution_order": ["sentiment", "stats"],
            }
            mock_create_dag.return_value = mock_dag
            mock_validate.return_value = None
            mock_summary.return_value = {"summary": "test"}
            mock_load_canonical.return_value = _mock_canonical()

            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment", "stats"],
            )

            assert len(result["modules_run"]) == 1
            assert len(result["errors"]) == 1

    def test_run_analysis_pipeline_includes_execution_metadata(
        self, temp_transcript_file
    ):
        mock_pipeline = MagicMock()
        mock_pipeline.execute_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": [],
            "execution_order": ["sentiment"],
            "cache_hits": ["sentiment"],
        }

        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline",
                return_value=mock_pipeline,
            ),
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary",
                return_value={"summary": "ok"},
            ),
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_load_canonical.return_value = _mock_canonical()
            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
            )

        assert result["execution_order"] == ["sentiment"]
        assert result["cache_hits"] == ["sentiment"]

    def test_run_analysis_pipeline_passes_rerun_mode_to_dag(self, temp_transcript_file):
        mock_pipeline = MagicMock()
        mock_pipeline.execute_pipeline.return_value = {
            "modules_run": ["sentiment"],
            "errors": [],
            "execution_order": ["sentiment"],
            "cache_hits": [],
        }

        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline",
                return_value=mock_pipeline,
            ),
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary",
                return_value={"summary": "ok"},
            ),
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_load_canonical.return_value = _mock_canonical()
            run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
                rerun_mode="recompute",
            )

        assert mock_pipeline.execute_pipeline.called


class TestRunAnalysisPipelineFromFile:
    def test_run_analysis_pipeline_from_file_with_modules(self, temp_transcript_file):
        with patch(
            "transcriptx.core.pipeline.pipeline.run_analysis_pipeline"
        ) as mock_run:
            mock_run.return_value = {
                "transcript_path": str(temp_transcript_file),
                "selected_modules": ["sentiment"],
                "modules_run": ["sentiment"],
                "errors": [],
            }

            result = run_analysis_pipeline_from_file(
                transcript_path=str(temp_transcript_file),
                modules=["sentiment"],
            )

            mock_run.assert_called_once()
            assert result["modules_run"] == ["sentiment"]

    def test_run_analysis_pipeline_from_file_all_modules(self, temp_transcript_file):
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.run_analysis_pipeline"
            ) as mock_run,
            patch(
                "transcriptx.core.pipeline.pipeline.get_default_modules"
            ) as mock_get_modules,
        ):
            mock_get_modules.return_value = ["sentiment", "stats", "ner"]
            mock_run.return_value = {
                "transcript_path": str(temp_transcript_file),
                "selected_modules": ["sentiment", "stats", "ner"],
                "modules_run": ["sentiment", "stats", "ner"],
                "errors": [],
            }

            run_analysis_pipeline_from_file(transcript_path=str(temp_transcript_file))

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args.kwargs["selected_modules"] == ["sentiment", "stats", "ner"]


class TestRunAnalysisPipelineWithManifest:
    """Tests for run_analysis_pipeline with RunManifestInput."""

    def test_run_with_manifest_normalizes_to_target_and_modules(
        self, temp_transcript_file
    ):
        """run_analysis_pipeline with manifest uses transcript_path and modules from manifest."""
        from transcriptx.core.pipeline.run_schema import RunManifestInput

        manifest = RunManifestInput(
            schema_version=1,
            transcript_path=str(temp_transcript_file),
            modules=["stats", "sentiment"],
        )

        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "transcript_path": str(temp_transcript_file),
                "modules_requested": ["stats", "sentiment"],
                "modules_run": ["stats", "sentiment"],
                "errors": [],
                "execution_order": ["stats", "sentiment"],
            }
            mock_create_dag.return_value = mock_dag
            mock_summary.return_value = {}
            mock_load_canonical.return_value = _mock_canonical()

            result = run_analysis_pipeline(manifest=manifest)

            assert result["selected_modules"] == ["stats", "sentiment"]
            assert result["modules_run"] == ["stats", "sentiment"]
            assert mock_dag.execute_pipeline.called

    def test_run_with_manifest_modules_all_resolves_defaults(
        self, temp_transcript_file
    ):
        """run_analysis_pipeline with manifest modules=['all'] calls get_default_modules."""
        from transcriptx.core.pipeline.run_schema import RunManifestInput

        manifest = RunManifestInput(
            schema_version=1,
            transcript_path=str(temp_transcript_file),
            modules=["all"],
        )

        with (
            patch(
                "transcriptx.core.pipeline.pipeline.get_default_modules_from_registry"
            ) as mock_get_default,
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_get_default.return_value = ["stats", "sentiment"]
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "modules_run": ["stats", "sentiment"],
                "errors": [],
            }
            mock_create_dag.return_value = mock_dag
            mock_summary.return_value = {}
            mock_load_canonical.return_value = _mock_canonical()

            run_analysis_pipeline(manifest=manifest)

            mock_get_default.assert_called_once()
            call_args = mock_get_default.call_args[0]
            assert str(temp_transcript_file) in call_args[0]


class TestRunAnalysisPipelineWithTarget:
    """Tests for run_analysis_pipeline with target=TranscriptRef."""

    def test_run_with_target_transcript_ref(self, temp_transcript_file):
        """run_analysis_pipeline with target=TranscriptRef resolves and runs single transcript."""
        from transcriptx.core.pipeline.target_resolver import TranscriptRef

        with (
            patch(
                "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
            ) as mock_create_dag,
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch(
                "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary"
            ) as mock_summary,
            patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
            patch(
                "transcriptx.io.transcript_loader.load_canonical_transcript"
            ) as mock_load_canonical,
        ):
            mock_dag = MagicMock()
            mock_dag.execute_pipeline.return_value = {
                "transcript_path": str(temp_transcript_file),
                "modules_run": ["stats"],
                "errors": [],
            }
            mock_create_dag.return_value = mock_dag
            mock_summary.return_value = {}
            mock_load_canonical.return_value = _mock_canonical()

            result = run_analysis_pipeline(
                target=TranscriptRef(path=str(temp_transcript_file)),
                selected_modules=["stats"],
            )

            assert result["modules_run"] == ["stats"]
            assert "output_dir" in result
