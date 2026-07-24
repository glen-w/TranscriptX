"""Tests for pipeline public API shim and orchestration entrypoints."""

import logging
from unittest.mock import patch

from transcriptx.core.pipeline.contracts import PersistenceOutcome, RunResult
from transcriptx.core.pipeline.pipeline import (
    run_analysis_pipeline,
    run_analysis_pipeline_from_file,
)


class TestRunAnalysisPipeline:
    def _fake_result(self, transcript_path: str) -> RunResult:
        return RunResult(
            status="partial",
            execution_status="succeeded",
            final_status="partial",
            transcript_path=transcript_path,
            transcript_key="thash",
            run_id="rid",
            output_dir="/tmp/out",
            selected_modules=["sentiment"],
            modules_run=["sentiment"],
            skipped_modules=[
                {"module": "stats", "reason": "blocked", "execution_status": "blocked"}
            ],
            errors=[],
            module_results={"sentiment": {"status": "success"}},
            execution_order=["sentiment", "stats"],
            cache_hits=[],
            duration=1.2,
            summary={"ok": True},
            persistence_outcomes=[
                PersistenceOutcome(name="manifest", success=False, severity="optional")
            ],
            termination_reason=None,
        )

    def test_run_analysis_pipeline_shim_includes_status_fields(
        self, temp_transcript_file
    ):
        with (
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch.object(
                run_analysis_pipeline.__globals__["_orchestrator"],
                "run",
                return_value=self._fake_result(str(temp_transcript_file)),
            ),
        ):
            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
            )
        assert result["status"] == "partial"
        assert result["execution_status"] == "succeeded"
        assert result["final_status"] == "partial"
        assert result["schema_version"] == 1
        assert result["skipped_modules"] == [
            {"module": "stats", "reason": "blocked", "execution_status": "blocked"}
        ]
        assert isinstance(result["persistence_outcomes"], list)

    def test_deprecated_parallel_args_warn_once(self, caplog, temp_transcript_file):
        with (
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch.object(
                run_analysis_pipeline.__globals__["_orchestrator"],
                "run",
                return_value=self._fake_result(str(temp_transcript_file)),
            ),
        ):
            caplog.set_level(logging.WARNING, logger="transcriptx")
            result = run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
                parallel=True,
                max_workers=8,
            )
        assert result["modules_run"] == ["sentiment"]
        deprecated = [
            record
            for record in caplog.records
            if "parallel/max_workers are deprecated" in record.getMessage()
        ]
        assert len(deprecated) == 1

    def test_deprecated_max_workers_without_parallel_warns_once(
        self, caplog, temp_transcript_file
    ):
        with (
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch.object(
                run_analysis_pipeline.__globals__["_orchestrator"],
                "run",
                return_value=self._fake_result(str(temp_transcript_file)),
            ),
        ):
            caplog.set_level(logging.WARNING, logger="transcriptx")
            run_analysis_pipeline(
                transcript_path=str(temp_transcript_file),
                selected_modules=["sentiment"],
                max_workers=8,
            )
        deprecated = [
            record
            for record in caplog.records
            if "parallel/max_workers are deprecated" in record.getMessage()
        ]
        assert len(deprecated) == 1


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


class TestGetDefaultModules:
    def test_get_default_modules_forwards_include_legacy(self):
        from transcriptx.core.pipeline.pipeline import get_default_modules

        with patch(
            "transcriptx.core.pipeline.pipeline.get_default_modules_from_registry",
            return_value=["semantic_similarity"],
        ) as mock_get:
            result = get_default_modules(["/tmp/t.json"], include_legacy=True)

        assert result == ["semantic_similarity"]
        assert mock_get.call_args.kwargs["include_legacy"] is True


class TestRunAnalysisPipelineManifestAndTarget:
    def test_manifest_modules_all_calls_default_registry(self, temp_transcript_file):
        from transcriptx.core.pipeline.run_schema import RunManifestInput

        manifest = RunManifestInput(
            schema_version=1,
            transcript_path=str(temp_transcript_file),
            modules=["all"],
        )
        fake = TestRunAnalysisPipeline()._fake_result(str(temp_transcript_file))
        with (
            patch(
                "transcriptx.core.pipeline.pipeline.get_default_modules_from_registry",
                return_value=["sentiment"],
            ),
            patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
            patch.object(
                run_analysis_pipeline.__globals__["_orchestrator"],
                "run",
                return_value=fake,
            ),
        ):
            out = run_analysis_pipeline(manifest=manifest)
        assert out["selected_modules"] == ["sentiment"]
