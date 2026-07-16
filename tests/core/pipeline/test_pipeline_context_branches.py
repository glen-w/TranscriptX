"""Branch-coverage unit tests for PipelineContext and builder helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline.pipeline_context import (
    PipelineContext,
    PipelineContextBuilder,
    ReadOnlyPipelineContext,
    SpeakerResolution,
)


def _builder(**kwargs) -> PipelineContextBuilder:
    defaults = {
        "transcript_path": "/tmp/t.json",
        "include_unidentified_speakers": False,
        "anonymise_speakers": False,
        "batch_mode": False,
    }
    defaults.update(kwargs)
    return PipelineContextBuilder(**defaults)


@pytest.mark.unit
def test_builder_load_transcript_success_and_errors() -> None:
    builder = _builder()
    mock_service = MagicMock()
    mock_service.load_transcript_data.return_value = (
        [{"speaker": "A"}],
        "base",
        "/out",
    )
    with patch(
        "transcriptx.core.pipeline.pipeline_context.TranscriptService",
        return_value=mock_service,
    ):
        loaded = builder.load_transcript()
    assert loaded.base_name == "base"
    assert loaded.segments == [{"speaker": "A"}]

    mock_service.load_transcript_data.side_effect = FileNotFoundError("missing")
    with (
        patch(
            "transcriptx.core.pipeline.pipeline_context.TranscriptService",
            return_value=mock_service,
        ),
        pytest.raises(FileNotFoundError),
    ):
        builder.load_transcript()

    mock_service.load_transcript_data.side_effect = ValueError("bad")
    with (
        patch(
            "transcriptx.core.pipeline.pipeline_context.TranscriptService",
            return_value=mock_service,
        ),
        pytest.raises(ValueError),
    ):
        builder.load_transcript()

    mock_service.load_transcript_data.side_effect = OSError("io")
    with (
        patch(
            "transcriptx.core.pipeline.pipeline_context.TranscriptService",
            return_value=mock_service,
        ),
        pytest.raises(RuntimeError, match="Failed to initialize"),
    ):
        builder.load_transcript()


@pytest.mark.unit
def test_builder_speaker_key_helpers() -> None:
    assert (
        PipelineContextBuilder._get_speaker_key_from_segment(
            {"speaker_db_id": 7, "speaker": "A"}
        )
        == "7"
    )
    assert (
        PipelineContextBuilder._get_speaker_key_from_segment(
            {"speaker_key": "SK", "speaker": "A"}
        )
        == "SK"
    )
    assert (
        PipelineContextBuilder._get_speaker_key_from_segment(
            {"grouping_key": "GK", "speaker": "A"}
        )
        == "GK"
    )
    assert (
        PipelineContextBuilder._get_speaker_key_from_segment({"speaker": " SPEAKER "})
        == "SPEAKER"
    )
    assert PipelineContextBuilder._get_speaker_key_from_segment({}) is None
    assert (
        PipelineContextBuilder._get_speaker_key_from_segment({"speaker": "  "}) is None
    )

    named = PipelineContextBuilder._collect_named_speaker_keys(
        [
            {"speaker": "Alice", "speaker_db_id": "a1"},
            {"speaker": "SPEAKER_00", "speaker_db_id": "u1"},
            {"speaker": "Bob", "speaker_db_id": "b1"},
        ],
        ignored_speaker_ids=set(),
    )
    assert "a1" in named
    assert "b1" in named
    assert "u1" not in named

    anon = PipelineContextBuilder._build_speaker_anonymisation_map(
        [
            {"speaker_db_id": "a1", "speaker": "Alice"},
            {"speaker_db_id": "a1", "speaker": "Alice"},
            {"speaker_db_id": "b1", "speaker": "Bob"},
        ]
    )
    assert anon == {"a1": "Speaker 01", "b1": "Speaker 02"}

    aliases = PipelineContextBuilder._build_speaker_key_aliases(
        {"1": "Alice", "2": "Bob", "3": None, "4": "  ", "": "X"}
    )
    assert aliases["Alice"] == "1"
    assert aliases["Bob"] == "2"
    collisions = PipelineContextBuilder._build_speaker_key_aliases(
        {"1": "Alex", "2": "Alex"}
    )
    assert "Alex" not in collisions


@pytest.mark.unit
def test_builder_derive_speaker_map_from_original_cue() -> None:
    segments = [
        {
            "speaker": "SPEAKER_00",
            "original_cue": {"original_speaker": "Alice"},
        },
        {
            "speaker": "SPEAKER_00",
            "original_cue": {"original_speaker": "Alice"},
        },
        {
            "speaker": "SPEAKER_01",
            "original_cue": {"original_speaker": "Bob"},
        },
        {"speaker": "SPEAKER_02"},
        "not-a-dict",
        {"speaker": 123, "original_cue": {"original_speaker": "X"}},
    ]
    resolved = PipelineContextBuilder._derive_speaker_map_from_segments(segments)
    assert resolved == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


@pytest.mark.unit
def test_builder_compute_identity_and_runtime_flags_anonymise() -> None:
    builder = _builder(anonymise_speakers=True, transcript_key="fixed-key", run_id="r1")
    resolution = SpeakerResolution(
        segments=[
            {"speaker": "Alice", "speaker_db_id": 1},
            {"speaker": "Bob", "speaker_db_id": "b1"},
        ],
        speaker_map={"a1": "Alice", "b1": "Bob"},
        speaker_map_metadata={},
        ignored_speaker_ids=set(),
    )
    runtime = builder.compute_identity_and_runtime_flags(resolution)
    assert runtime.transcript_key == "fixed-key"
    assert runtime.run_id == "r1"
    assert runtime.runtime_flags["anonymise_speakers"] is True
    assert "speaker_anonymisation_map" in runtime.runtime_flags
    assert "named_speaker_keys" in runtime.runtime_flags
    assert runtime.runtime_flags["speaker_key_aliases"]["Alice"] == "a1"


@pytest.mark.unit
def test_builder_resolve_speakers_sets_display_map(tmp_path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    builder = _builder(transcript_path=str(transcript))
    loaded = MagicMock()
    loaded.segments = [{"speaker": "Alice", "speaker_db_id": 1, "text": "hi"}]
    loaded.transcript_service = MagicMock()

    state = MagicMock()
    state.ignored_speakers = ["ign"]
    state.speaker_map = {"a1": "Alice"}

    mock_resolver = MagicMock()
    mock_resolver.load_mapping.return_value = state
    mock_resolver.resolve_segments.return_value = loaded.segments

    with (
        patch(
            "transcriptx.io.speaker_map_resolver.SpeakerMapResolver",
            return_value=mock_resolver,
        ),
        patch(
            "transcriptx.core.utils.speaker_extraction.get_unique_speakers",
            return_value={"a1": "Alice"},
        ),
        patch(
            "transcriptx.core.utils.speaker_extraction.set_speaker_display_map"
        ) as set_map,
    ):
        result = builder.resolve_speakers(loaded)
    assert result.ignored_speaker_ids == {"ign"}
    set_map.assert_called()
    loaded.transcript_service.replace_cached_segments.assert_called_once()


@pytest.mark.unit
def test_pipeline_context_validate_and_context_manager(
    pipeline_context_factory,
) -> None:
    with pipeline_context_factory() as ctx:
        assert ctx.validate() is True
        ctx.set_segments([])
        assert ctx.validate() is False
        ctx.set_segments([{"speaker": "Alice", "text": "x"}])
        ctx.transcript_path = ""
        assert ctx.validate() is False
    assert ctx._closed is True
    assert ctx.validate() is False


@pytest.mark.unit
def test_pipeline_context_get_speaker_map_fallbacks(pipeline_context_factory) -> None:
    ctx = pipeline_context_factory()
    ctx._speaker_map_metadata = {}
    ctx.segments = [
        {"speaker": "Alice"},
        {"speaker": "Alice"},
        {"speaker": None},
        {"speaker": "Bob"},
    ]
    smap = ctx.get_speaker_map()
    assert smap["Alice"] == "Alice"
    assert smap["Bob"] == "Bob"

    ctx.segments = []
    ctx.speaker_map = {"fallback": "map"}
    assert ctx.get_speaker_map() == {"fallback": "map"}


@pytest.mark.unit
def test_pipeline_context_identity_and_speaker_helpers(
    pipeline_context_factory,
) -> None:
    ctx = pipeline_context_factory()
    assert ctx.get_transcript_dir()
    assert ctx.get_transcript_key()
    assert ctx.get_run_id() is None or isinstance(ctx.get_run_id(), str)
    assert isinstance(ctx.get_runtime_flags(), dict)

    assert ctx.get_speaker_key(None) is None
    assert ctx.get_speaker_key({"speaker_db_id": 9}) == "9"
    assert ctx.get_speaker_key("  X  ") == "X"
    assert ctx.get_speaker_key("   ") is None

    ordered = ctx.iter_speaker_keys_in_order(
        [
            {"speaker_db_id": "a"},
            {"speaker_db_id": "a"},
            {"speaker_db_id": "b"},
            {},
        ]
    )
    assert ordered == ["a", "b"]
    assert ctx.build_speaker_anonymisation_map(
        [{"speaker_db_id": "a"}, {"speaker_db_id": "b"}]
    ) == {"a": "Speaker 01", "b": "Speaker 02"}

    named = ctx._collect_named_speaker_keys(
        [
            {"speaker": "Alice", "speaker_db_id": "a"},
            {"speaker": "SPEAKER_00", "speaker_db_id": "u"},
        ]
    )
    assert "a" in named

    derived = ctx._derive_speaker_map_from_segments(
        [
            {
                "speaker": "SPEAKER_00",
                "original_cue": {"original_speaker": "Zed"},
            }
        ]
    )
    assert derived == {"SPEAKER_00": "Zed"}

    aliases = ctx._build_speaker_key_aliases({"1": "A", "2": "B", "3": "A"})
    assert "A" not in aliases
    assert aliases["B"] == "2"


@pytest.mark.unit
def test_close_clears_display_map_even_on_error(pipeline_context_factory) -> None:
    ctx = pipeline_context_factory()
    with patch(
        "transcriptx.core.utils.speaker_extraction.clear_speaker_display_map",
        side_effect=RuntimeError("boom"),
    ):
        ctx.close()
    assert ctx._closed is True


@pytest.mark.unit
def test_read_only_pipeline_context_properties_and_methods(
    pipeline_context_factory,
) -> None:
    ctx = pipeline_context_factory()
    ctx.store_analysis_result("m", {"ok": True})
    ctx.store_computed_value("k", 1)
    ro = ReadOnlyPipelineContext(ctx)

    assert ro.transcript_path == ctx.transcript_path
    assert ro.segments == ctx.segments
    assert ro.speaker_map == ctx.speaker_map
    assert ro.base_name == ctx.base_name
    assert ro.transcript_dir == ctx.transcript_dir
    assert ro.transcript_key == ctx.transcript_key
    assert ro.run_id == ctx.run_id
    assert ro.runtime_flags == ctx.runtime_flags

    assert ro.get_transcript_key() == ctx.get_transcript_key()
    assert ro.get_run_id() == ctx.get_run_id()
    assert ro.get_speaker_map() == ctx.get_speaker_map()
    assert ro.get_transcript_dir() == ctx.get_transcript_dir()
    assert ro.get_analysis_result("m") == {"ok": True}
    assert ro.get_computed_value("k") == 1
    assert ro.has_computed_value("k") is True
    assert ro.get_transcript_service() is ctx.get_transcript_service()
    assert ro.get_speaker_key_from_segment(
        {"speaker": "Alice"}
    ) == ctx.get_speaker_key_from_segment({"speaker": "Alice"})
    assert ro.get_speaker_key("Alice") == "Alice"
    assert ro.iter_speaker_keys_in_order([{"speaker": "A"}]) == ["A"]
    assert ro.get_speaker_display_name("missing") == "missing"


@pytest.mark.unit
def test_pipeline_context_init_with_anonymise_and_output_dir(
    tmp_path, mock_transcript_service
) -> None:
    transcript = tmp_path / "call.json"
    transcript.write_text("{}")
    segments = [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "hi",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    mock_transcript_service.load_transcript_data.return_value = (
        segments,
        "call",
        str(tmp_path / "outdir"),
    )
    with patch(
        "transcriptx.core.pipeline.pipeline_context.TranscriptService",
        return_value=mock_transcript_service,
    ):
        ctx = PipelineContext(
            transcript_path=str(transcript),
            anonymise_speakers=True,
            include_unidentified_speakers=True,
            output_dir=str(tmp_path / "outdir"),
            transcript_key="tk",
            run_id="run",
        )
    assert ctx.get_run_id() == "run"
    assert ctx.get_transcript_key() == "tk"
    assert ctx.get_runtime_flags()["include_unidentified_speakers"] is True
    assert ctx.get_speaker_display_name("1") == "Speaker 01"
