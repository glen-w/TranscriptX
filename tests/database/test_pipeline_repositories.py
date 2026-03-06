"""
Database repository tests for pipeline run and artifact operations.
"""

from datetime import datetime, timezone

import pytest

from transcriptx.database.models import TranscriptFile
from transcriptx.database.repositories import (
    PipelineRunRepository,
    ModuleRunRepository,
    ArtifactIndexRepository,
)


@pytest.mark.database
def test_pipeline_run_repository_roundtrip(db_session):
    """Create and update pipeline runs with input hash lookup."""
    transcript = TranscriptFile(
        file_path="/tmp/test_transcript.json",
        file_name="test_transcript.json",
        transcript_content_hash="a" * 64,
        schema_version="schema_v1",
        sentence_schema_version="sentence_v1",
        source_hash="b" * 64,
        segment_count=1,
        speaker_count=1,
    )
    db_session.add(transcript)
    db_session.commit()

    repo = PipelineRunRepository(db_session)
    run = repo.create_pipeline_run(
        transcript_file_id=transcript.id,
        pipeline_version="1.0.0",
        pipeline_config_hash="cfg",
        pipeline_input_hash="input",
        cli_args_json={"rerun_mode": "reuse-existing-run"},
    )

    assert run.status == "in_progress"
    repo.update_status(run.id, "completed")

    latest = repo.find_latest_by_input_hash(transcript.id, "input")
    assert latest is not None
    assert latest.id == run.id


@pytest.mark.database
def test_module_run_repository_lifecycle(db_session):
    """Create module runs, complete them, and mark superseded."""
    transcript = TranscriptFile(
        file_path="/tmp/test_module.json",
        file_name="test_module.json",
        transcript_content_hash="c" * 64,
        schema_version="schema_v1",
        sentence_schema_version="sentence_v1",
        source_hash="d" * 64,
        segment_count=1,
        speaker_count=1,
    )
    db_session.add(transcript)
    db_session.commit()

    pipeline_repo = PipelineRunRepository(db_session)
    pipeline_run = pipeline_repo.create_pipeline_run(
        transcript_file_id=transcript.id,
        pipeline_version="1.0.0",
        pipeline_config_hash="cfg",
        pipeline_input_hash="input",
    )

    module_repo = ModuleRunRepository(db_session)
    module_run = module_repo.create_module_run(
        pipeline_run_id=pipeline_run.id,
        transcript_file_id=transcript.id,
        module_name="sentiment",
        module_version="v1",
        module_config_hash="cfg",
        module_input_hash="input",
    )

    module_repo.update_completion(
        module_run_id=module_run.id,
        status="completed",
        duration_seconds=1.5,
        output_hash="hash123",
        is_cacheable=True,
    )

    cached = module_repo.find_cacheable_run(
        transcript_file_id=transcript.id,
        module_name="sentiment",
        module_version="v1",
        module_input_hash="input",
    )
    assert cached is not None

    module_repo.mark_superseded(module_run.id, datetime.now(timezone.utc))
    refreshed = db_session.query(type(module_run)).filter_by(id=module_run.id).first()
    assert refreshed.is_cacheable is False
    assert refreshed.superseded_at is not None


@pytest.mark.database
def test_artifact_index_repository(db_session):
    """Ensure artifact registrations can be created and queried."""
    transcript = TranscriptFile(
        file_path="/tmp/test_artifact.json",
        file_name="test_artifact.json",
        transcript_content_hash="e" * 64,
        schema_version="schema_v1",
        sentence_schema_version="sentence_v1",
        source_hash="f" * 64,
        segment_count=1,
        speaker_count=1,
    )
    db_session.add(transcript)
    db_session.commit()

    pipeline_repo = PipelineRunRepository(db_session)
    pipeline_run = pipeline_repo.create_pipeline_run(
        transcript_file_id=transcript.id,
        pipeline_version="1.0.0",
        pipeline_config_hash="cfg",
        pipeline_input_hash="input",
    )

    module_repo = ModuleRunRepository(db_session)
    module_run = module_repo.create_module_run(
        pipeline_run_id=pipeline_run.id,
        transcript_file_id=transcript.id,
        module_name="stats",
        module_version="v1",
        module_config_hash="cfg",
        module_input_hash="input",
    )

    repo = ArtifactIndexRepository(db_session)
    repo.create_artifact(
        module_run_id=module_run.id,
        transcript_file_id=transcript.id,
        artifact_key="stats/data/global/test_stats.json",
        relative_path="stats/data/global/test_stats.json",
        artifact_root="/tmp/outputs",
        artifact_type="json",
        artifact_role="primary",
        content_hash="abc123",
    )

    primary = repo.get_primary_artifacts(module_run.id)
    assert len(primary) == 1
    assert primary[0].artifact_key.endswith("test_stats.json")
