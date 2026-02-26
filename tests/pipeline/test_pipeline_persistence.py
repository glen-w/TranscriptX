"""
Tests for persistence behavior in analysis pipeline.
"""

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import GroupRef
from transcriptx.database.models.transcript import TranscriptFile
from transcriptx.database.repositories.group import GroupRepository
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _mock_canonical():
    return CanonicalTranscript.from_segments(
        [{"speaker": "Alice", "text": "Test", "start": 0.0, "end": 1.0}]
    )


def test_run_analysis_pipeline_does_not_init_db_by_default(temp_transcript_file):
    with (
        patch(
            "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
        ) as mock_create_dag,
        patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
        patch(
            "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary",
            return_value={"summary": "ok"},
        ),
        patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
        patch("transcriptx.core.pipeline.pipeline.save_run_report"),
        patch("transcriptx.core.pipeline.pipeline.save_run_manifest"),
        patch("transcriptx.core.pipeline.pipeline.create_run_manifest"),
        patch(
            "transcriptx.io.transcript_loader.load_canonical_transcript"
        ) as mock_load_canonical,
        patch(
            "transcriptx.database.pipeline_run_service.PipelineRunCoordinator"
        ) as mock_coordinator,
    ):

        mock_pipeline = MagicMock()
        mock_pipeline.execute_pipeline.return_value = {
            "modules_run": [],
            "errors": [],
            "execution_order": [],
        }
        mock_create_dag.return_value = mock_pipeline
        mock_load_canonical.return_value = _mock_canonical()

        run_analysis_pipeline(
            transcript_path=str(temp_transcript_file),
            selected_modules=["sentiment"],
        )

        assert mock_coordinator.call_count == 0


def test_run_analysis_pipeline_inits_db_with_persist(temp_transcript_file):
    with (
        patch(
            "transcriptx.core.pipeline.pipeline.create_dag_pipeline"
        ) as mock_create_dag,
        patch("transcriptx.core.pipeline.pipeline.validate_transcript"),
        patch(
            "transcriptx.core.pipeline.pipeline.generate_comprehensive_output_summary",
            return_value={"summary": "ok"},
        ),
        patch("transcriptx.core.pipeline.pipeline.display_output_summary_to_user"),
        patch("transcriptx.core.pipeline.pipeline.save_run_report"),
        patch("transcriptx.core.pipeline.pipeline.save_run_manifest"),
        patch("transcriptx.core.pipeline.pipeline.create_run_manifest"),
        patch(
            "transcriptx.io.transcript_loader.load_canonical_transcript"
        ) as mock_load_canonical,
        patch(
            "transcriptx.database.pipeline_run_service.PipelineRunCoordinator"
        ) as mock_coordinator,
    ):

        mock_pipeline = MagicMock()
        mock_pipeline.execute_pipeline.return_value = {
            "modules_run": [],
            "errors": [],
            "execution_order": [],
        }
        mock_create_dag.return_value = mock_pipeline
        mock_load_canonical.return_value = _mock_canonical()
        mock_coordinator.return_value = MagicMock()

        run_analysis_pipeline(
            transcript_path=str(temp_transcript_file),
            selected_modules=["sentiment"],
            persist=True,
        )

        assert mock_coordinator.call_count == 1


def _mock_group_config():
    return SimpleNamespace(
        group_analysis=SimpleNamespace(
            enabled=True,
            output_dir="/tmp",
            enable_stats_aggregation=False,
            scaffold_by_session=False,
            scaffold_by_speaker=False,
            scaffold_comparisons=False,
        )
    )


def _mock_group_pipeline_result(idx: int) -> dict:
    return {
        "transcript_key": f"key-{idx}",
        "run_id": f"run-{idx}",
        "output_dir": "/tmp",
        "module_results": {},
        "errors": [],
    }


def _mock_canonical_map():
    return CanonicalSpeakerMap(
        transcript_to_speakers={},
        canonical_to_display={},
        transcript_to_display={},
    )


def test_group_run_writes_manifest(db_session):
    transcript_one = TranscriptFile(
        file_path="/tmp/first.json",
        file_name="first.json",
    )
    transcript_two = TranscriptFile(
        file_path="/tmp/second.json",
        file_name="second.json",
    )
    db_session.add_all([transcript_one, transcript_two])
    db_session.commit()

    group_repo = GroupRepository(db_session)
    group = group_repo.create_group(
        name="Test Group",
        group_type="merged_event",
        transcript_file_ids_ordered=[transcript_one.id, transcript_two.id],
    )

    with (
        patch(
            "transcriptx.core.pipeline.pipeline._run_single_analysis_pipeline"
        ) as mock_single,
        patch(
            "transcriptx.core.pipeline.pipeline.get_config",
            return_value=_mock_group_config(),
        ),
        patch(
            "transcriptx.core.pipeline.speaker_normalizer.normalize_speakers_across_transcripts",
            return_value=_mock_canonical_map(),
        ),
        patch(
            "transcriptx.core.analysis.stats.aggregation.aggregate_stats_group",
            return_value={},
        ),
        patch(
            "transcriptx.core.analysis.aggregation.sentiment.aggregate_sentiment_group",
            return_value=None,
        ),
        patch(
            "transcriptx.core.analysis.aggregation.emotion.aggregate_emotion_group",
            return_value=None,
        ),
        patch(
            "transcriptx.core.analysis.aggregation.interactions.aggregate_interactions_group",
            return_value=None,
        ),
        patch(
            "transcriptx.core.output.group_output_service.GroupOutputService"
        ) as mock_output_service,
        patch(
            "transcriptx.core.pipeline.target_resolver.get_session",
            return_value=db_session,
        ),
        patch(
            "transcriptx.core.services.group_service.get_session",
            return_value=db_session,
        ),
    ):

        mock_single.side_effect = [
            _mock_group_pipeline_result(1),
            _mock_group_pipeline_result(2),
        ]
        mock_output_service.return_value.base_dir = "/tmp"

        run_analysis_pipeline(
            target=GroupRef(group_uuid=group.uuid),
            selected_modules=["sentiment"],
        )

        assert mock_output_service.call_args.kwargs["group_uuid"] == group.uuid
        mock_output_service.return_value.write_group_manifest.assert_called_once()
