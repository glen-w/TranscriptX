"""
Integration tests for pipeline + DB state recovery behavior.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.utils.canonicalization import (
    compute_transcript_content_hash,
    SCHEMA_VERSION,
    SENTENCE_SCHEMA_VERSION,
)
from transcriptx.core.utils.path_utils import get_transcript_dir
from transcriptx.database.models import TranscriptFile
from transcriptx.database.pipeline_run_service import PipelineRunCoordinator


@pytest.mark.integration
@pytest.mark.database
def test_pipeline_run_reuse_existing_state(
    db_session, temp_transcript_file, sample_transcript_data, tmp_path, monkeypatch
):
    """Ensure pipeline runs reuse existing state when inputs match."""
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()

    from transcriptx.core.utils import _path_core

    monkeypatch.setattr(_path_core, "OUTPUTS_DIR", str(outputs_root))

    content_hash = compute_transcript_content_hash(sample_transcript_data["segments"])
    transcript_file = TranscriptFile(
        file_path=str(temp_transcript_file.resolve()),
        file_name=temp_transcript_file.name,
        transcript_content_hash=content_hash,
        schema_version=SCHEMA_VERSION,
        sentence_schema_version=SENTENCE_SCHEMA_VERSION,
        source_hash="0" * 64,
        segment_count=len(sample_transcript_data["segments"]),
        speaker_count=1,
    )
    db_session.add(transcript_file)
    db_session.commit()

    pipeline_config = {
        "modules": ["sentiment"],
        "analysis_mode": "default",
        "quality_profile": "standard",
    }

    with (
        patch(
            "transcriptx.database.pipeline_run_service.get_session",
            return_value=db_session,
        ),
        patch(
            "transcriptx.database.artifact_registry.get_session",
            return_value=db_session,
        ),
        patch(
            "transcriptx.database.transcript_ingestion.get_session",
            return_value=db_session,
        ),
        patch(
            "transcriptx.database.sentence_storage.get_session", return_value=db_session
        ),
        patch("transcriptx.database.pipeline_run_service.require_up_to_date_schema"),
        patch("transcriptx.database.transcript_ingestion.require_up_to_date_schema"),
        patch(
            "transcriptx.database.pipeline_run_service.TranscriptIngestionService"
        ) as mock_ingestion,
    ):

        mock_ingestion.return_value = MagicMock(
            ingest_transcript=MagicMock(), close=MagicMock()
        )

        coordinator = PipelineRunCoordinator(
            transcript_path=str(temp_transcript_file),
            selected_modules=["sentiment"],
            pipeline_config=pipeline_config,
            cli_args={"rerun_mode": "reuse-existing-run"},
            rerun_mode="reuse-existing-run",
        )
        run = coordinator.start()
        assert coordinator.reused_pipeline_run is False

        module_run, cached = coordinator.begin_module_run(
            module_name="sentiment",
            module_config={},
            dependency_names=[],
        )
        assert cached is False
        assert module_run is not None

        module_dir = (
            Path(get_transcript_dir(str(temp_transcript_file)))
            / "sentiment"
            / "data"
            / "global"
        )
        module_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = module_dir / f"{temp_transcript_file.stem}_results.json"
        artifact_path.write_text('{"ok": true}')

        coordinator.complete_module_run(
            module_run=module_run,
            module_name="sentiment",
            duration_seconds=1.2,
            module_failed=False,
            module_result={"metrics": {"duration_seconds": 1.2}},
        )
        coordinator.finish(success=True)
        coordinator.close()

        coordinator_again = PipelineRunCoordinator(
            transcript_path=str(temp_transcript_file),
            selected_modules=["sentiment"],
            pipeline_config=pipeline_config,
            cli_args={"rerun_mode": "reuse-existing-run"},
            rerun_mode="reuse-existing-run",
        )
        run_again = coordinator_again.start()

        assert coordinator_again.reused_pipeline_run is True
        assert run_again.id == run.id
        assert coordinator_again.get_cached_module_names()

        coordinator_again.close()
