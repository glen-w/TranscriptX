"""
Artifact index contract tests for DB ↔ FS integrity.
"""

from unittest.mock import patch

import pytest

from transcriptx.core.utils.canonicalization import (
    SCHEMA_VERSION,
    SENTENCE_SCHEMA_VERSION,
)
from transcriptx.database.artifact_registry import ArtifactRegistry
from transcriptx.database.artifact_validation import ArtifactValidationService
from transcriptx.database.models import (
    ArtifactIndex,
    ModuleRun,
    PipelineRun,
    TranscriptFile,
)


@pytest.mark.database
def test_artifact_validation_detects_missing_and_orphan_files(
    db_session, temp_transcript_file, tmp_path, monkeypatch
):
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()

    from transcriptx.core.utils import _path_core

    monkeypatch.setattr(_path_core, "OUTPUTS_DIR", str(outputs_root))

    transcript = TranscriptFile(
        file_path=str(temp_transcript_file.resolve()),
        file_name=temp_transcript_file.name,
        transcript_content_hash="hash" * 16,
        schema_version=SCHEMA_VERSION,
        sentence_schema_version=SENTENCE_SCHEMA_VERSION,
        source_hash="source" * 10,
        segment_count=1,
        speaker_count=1,
    )
    db_session.add(transcript)
    db_session.commit()

    pipeline_run = PipelineRun(
        transcript_file_id=transcript.id,
        pipeline_version="1.0.0",
        pipeline_config_hash="cfg",
        pipeline_input_hash="input",
        status="completed",
    )
    db_session.add(pipeline_run)
    db_session.flush()

    module_run = ModuleRun(
        pipeline_run_id=pipeline_run.id,
        transcript_file_id=transcript.id,
        module_name="stats",
        module_version="v1",
        module_config_hash="cfg",
        module_input_hash="input",
        status="completed",
    )
    db_session.add(module_run)
    db_session.flush()

    artifact = ArtifactIndex(
        module_run_id=module_run.id,
        transcript_file_id=transcript.id,
        artifact_key="stats/data/global/test_stats.json",
        relative_path="stats/data/global/test_stats.json",
        artifact_root=str(outputs_root),
        artifact_type="json",
        artifact_role="primary",
        content_hash="abc123",
    )
    db_session.add(artifact)
    db_session.commit()

    # Orphan file on disk
    orphan_path = outputs_root / "stats" / "data" / "global" / "orphan.json"
    orphan_path.parent.mkdir(parents=True, exist_ok=True)
    orphan_path.write_text('{"orphan": true}')

    with patch(
        "transcriptx.database.artifact_validation.get_session", return_value=db_session
    ):
        service = ArtifactValidationService()
        report = service.validate(str(temp_transcript_file))
        service.close()

    assert any("Missing file" in msg for msg in report.p0_errors)
    assert any("Orphan file" in msg for msg in report.p1_errors)


@pytest.mark.database
def test_artifact_registry_registers_roles(
    db_session, temp_transcript_file, tmp_path, monkeypatch
):
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()

    from transcriptx.core.utils import _path_core

    monkeypatch.setattr(_path_core, "OUTPUTS_DIR", str(outputs_root))

    transcript = TranscriptFile(
        file_path=str(temp_transcript_file.resolve()),
        file_name=temp_transcript_file.name,
        transcript_content_hash="hash" * 16,
        schema_version=SCHEMA_VERSION,
        sentence_schema_version=SENTENCE_SCHEMA_VERSION,
        source_hash="source" * 10,
        segment_count=1,
        speaker_count=1,
    )
    db_session.add(transcript)
    db_session.commit()

    pipeline_run = PipelineRun(
        transcript_file_id=transcript.id,
        pipeline_version="1.0.0",
        pipeline_config_hash="cfg",
        pipeline_input_hash="input",
        status="completed",
    )
    db_session.add(pipeline_run)
    db_session.flush()

    module_run = ModuleRun(
        pipeline_run_id=pipeline_run.id,
        transcript_file_id=transcript.id,
        module_name="sentiment",
        module_version="v1",
        module_config_hash="cfg",
        module_input_hash="input",
        status="completed",
    )
    db_session.add(module_run)
    db_session.commit()

    from transcriptx.core.utils._path_core import get_canonical_base_name

    transcript_output_dir = outputs_root / get_canonical_base_name(
        str(temp_transcript_file)
    )

    global_file = (
        transcript_output_dir / "sentiment" / "data" / "global" / "sample.json"
    )
    global_file.parent.mkdir(parents=True, exist_ok=True)
    global_file.write_text('{"ok": true}')

    speaker_file = (
        transcript_output_dir / "sentiment" / "data" / "speakers" / "speaker.json"
    )
    speaker_file.parent.mkdir(parents=True, exist_ok=True)
    speaker_file.write_text('{"speaker": true}')

    with patch(
        "transcriptx.database.artifact_registry.get_session", return_value=db_session
    ):
        registry = ArtifactRegistry()
        artifacts = registry.register_module_artifacts(
            transcript_path=str(temp_transcript_file),
            module_name="sentiment",
            module_run_id=module_run.id,
            transcript_file_id=transcript.id,
        )

    roles = {artifact["artifact_role"] for artifact in artifacts}
    assert "primary" in roles
    assert "intermediate" in roles
    assert len({artifact["artifact_key"] for artifact in artifacts}) == len(artifacts)
