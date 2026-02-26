from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.database import get_session
from transcriptx.database.migrations import run_migrations
from transcriptx.database.models import (
    ArtifactIndex,
    ModuleRun,
    TranscriptFile,
    TranscriptSegment,
    TranscriptSentence,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "vtt" / "golden" / "simple.json"
)


def _configure_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TRANSCRIPTX_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TRANSCRIPTX_DB_ENABLED", "1")
    monkeypatch.setenv("TRANSCRIPTX_DB_FIRST", "1")
    monkeypatch.setenv("TRANSCRIPTX_DB_AUTO_IMPORT", "1")
    monkeypatch.setenv("TRANSCRIPTX_DB_STRICT", "0")
    monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "outputs"))

    import transcriptx.database.database as db_module

    db_module._db_manager = None

    import transcriptx.core.utils.config as config_module

    config_module._config = None


def test_pipeline_idempotent_cache_and_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_env(monkeypatch, tmp_path)
    run_migrations()

    result_first = run_analysis_pipeline(
        transcript_path=str(FIXTURE_PATH),
        selected_modules=["transcript_output"],
    )
    assert not result_first.get("errors")

    session = get_session()
    try:
        transcript_count = session.query(TranscriptFile).count()
        segment_count = session.query(TranscriptSegment).count()
        sentence_count = session.query(TranscriptSentence).count()
    finally:
        session.close()

    result_second = run_analysis_pipeline(
        transcript_path=str(FIXTURE_PATH),
        selected_modules=["transcript_output"],
    )

    assert "transcript_output" in result_second.get("cache_hits", [])

    session = get_session()
    try:
        assert session.query(TranscriptFile).count() == transcript_count
        assert session.query(TranscriptSegment).count() == segment_count
        assert session.query(TranscriptSentence).count() == sentence_count

        artifact = session.query(ArtifactIndex).first()
        assert artifact is not None
        assert artifact.module_run is not None
        assert artifact.module_run.pipeline_run is not None
        assert (
            artifact.module_run.pipeline_run.transcript_file_id
            == artifact.transcript_file_id
        )

        artifact_path = Path(artifact.artifact_root) / artifact.relative_path
        assert artifact_path.exists()
    finally:
        session.close()


def test_failed_module_creates_failed_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_env(monkeypatch, tmp_path)
    run_migrations()

    import transcriptx.core.pipeline.module_registry as registry

    original_get_module_function = registry.get_module_function

    def _fail_module(name: str) -> object:
        if name == "transcript_output":

            def _raise(*args, **kwargs) -> None:
                raise RuntimeError("forced failure")

            return _raise
        return original_get_module_function(name)

    monkeypatch.setattr(registry, "get_module_function", _fail_module)

    result = run_analysis_pipeline(
        transcript_path=str(FIXTURE_PATH),
        selected_modules=["transcript_output"],
    )
    assert result.get("errors")

    session = get_session()
    try:
        failed_run = (
            session.query(ModuleRun)
            .filter(
                ModuleRun.module_name == "transcript_output",
                ModuleRun.status == "failed",
            )
            .order_by(ModuleRun.created_at.desc())
            .first()
        )
        assert failed_run is not None
        artifacts = (
            session.query(ArtifactIndex)
            .filter(ArtifactIndex.module_run_id == failed_run.id)
            .all()
        )
        assert artifacts == []
    finally:
        session.close()
