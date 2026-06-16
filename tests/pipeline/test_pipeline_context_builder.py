from __future__ import annotations

from unittest.mock import MagicMock, patch

from transcriptx.core.pipeline.pipeline_context import (
    PipelineContext,
    PipelineContextBuilder,
)


def test_pipeline_context_required_public_attributes_stable(
    temp_transcript_file, mock_transcript_service
) -> None:
    with patch(
        "transcriptx.core.pipeline.pipeline_context.TranscriptService",
        return_value=mock_transcript_service,
    ):
        context = PipelineContext(
            transcript_path=str(temp_transcript_file),
            transcript_key="key",
            run_id="run",
        )

    required = {
        "segments",
        "base_name",
        "transcript_dir",
        "speaker_map",
        "transcript_key",
        "run_id",
        "runtime_flags",
        "ignored_speaker_ids",
    }
    public_attrs = {name for name in vars(context) if not name.startswith("_")}

    assert required.issubset(public_attrs)
    assert context.transcript_key == "key"
    assert context.run_id == "run"
    assert isinstance(context.segments, list)
    assert isinstance(context.speaker_map, dict)
    assert isinstance(context.runtime_flags, dict)


def test_builder_steps_are_independently_testable(
    temp_transcript_file, mock_transcript_service
) -> None:
    builder = PipelineContextBuilder(transcript_path=str(temp_transcript_file))

    with patch(
        "transcriptx.core.pipeline.pipeline_context.TranscriptService",
        return_value=mock_transcript_service,
    ):
        loaded = builder.load_transcript()

    assert (
        loaded.segments == mock_transcript_service.load_transcript_data.return_value[0]
    )
    mock_transcript_service.replace_cached_segments.assert_not_called()

    speaker_resolution = builder.resolve_speakers(loaded)
    runtime = builder.compute_identity_and_runtime_flags(speaker_resolution)

    assert speaker_resolution.segments
    assert isinstance(speaker_resolution.speaker_map, dict)
    assert runtime.transcript_key
    assert "named_speaker_keys" in runtime.runtime_flags


def test_speaker_display_map_lifecycle(
    temp_transcript_file, mock_transcript_service
) -> None:
    with (
        patch(
            "transcriptx.core.pipeline.pipeline_context.TranscriptService",
            return_value=mock_transcript_service,
        ),
        patch(
            "transcriptx.core.utils.speaker_extraction.set_speaker_display_map"
        ) as set_display,
        patch(
            "transcriptx.core.utils.speaker_extraction.clear_speaker_display_map"
        ) as clear_display,
    ):
        context = PipelineContext(transcript_path=str(temp_transcript_file))
        context._speaker_map_metadata = {"SPEAKER_00": "Alice"}
        context.close()
        context.close()

    assert set_display.call_count <= 1
    assert clear_display.call_count == 1


def test_builder_repeated_invocation_does_not_reuse_prior_state(
    temp_transcript_file, mock_transcript_service
) -> None:
    first_service = mock_transcript_service
    second_service = MagicMock()
    second_service.load_transcript_data.return_value = (
        [{"speaker": "Bob", "text": "Hi"}],
        "second",
        "/tmp",
    )

    first = PipelineContextBuilder(transcript_path=str(temp_transcript_file))
    second = PipelineContextBuilder(transcript_path=str(temp_transcript_file))

    with patch(
        "transcriptx.core.pipeline.pipeline_context.TranscriptService",
        side_effect=[first_service, second_service],
    ):
        first_loaded = first.load_transcript()
        second_loaded = second.load_transcript()

    assert first_loaded.segments != second_loaded.segments


def test_pipeline_context_close_idempotent(pipeline_context_factory) -> None:
    context = pipeline_context_factory()

    context.close()
    after_first = {
        "_analysis_results": dict(context._analysis_results),
        "_computed_values": dict(context._computed_values),
        "_closed": context._closed,
    }
    context.close()
    after_second = {
        "_analysis_results": dict(context._analysis_results),
        "_computed_values": dict(context._computed_values),
        "_closed": context._closed,
    }

    assert after_first == after_second
