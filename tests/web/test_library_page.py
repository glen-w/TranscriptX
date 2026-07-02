from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata
from tests.web.streamlit_doubles import DummyStreamlitWithDataframe


_DummyStreamlit = DummyStreamlitWithDataframe


def test_format_duration_display() -> None:
    from transcriptx.utils.text_utils import format_duration_display

    assert format_duration_display(None) == "-"
    assert format_duration_display(125.0) == "2m"
    assert format_duration_display(3599.0) == "60m"
    assert format_duration_display(3720.0) == "1h 2m"


def test_render_library_default_render_skips_batch_summary_enrichment(
    monkeypatch,
) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.captured_df = None
    _DummyStreamlit.captions = []
    _DummyStreamlit.session_state = {}

    transcripts = [
        TranscriptMetadata(
            path=Path("/tmp/short.json"),
            base_name="short",
            duration_seconds=125.0,
            speaker_count=2,
            has_analysis_outputs=False,
            has_speaker_map=True,
        ),
        TranscriptMetadata(
            path=Path("/tmp/long.json"),
            base_name="long",
            duration_seconds=3720.0,
            speaker_count=3,
            has_analysis_outputs=True,
            has_speaker_map=False,
        ),
    ]

    monkeypatch.setattr(mod, "st", _DummyStreamlit)
    called = {"transcripts": 0, "summaries": 0}
    monkeypatch.setattr(
        mod,
        "get_cached_list_transcripts",
        lambda: called.__setitem__("transcripts", called["transcripts"] + 1)
        or transcripts,
    )
    monkeypatch.setattr(
        mod,
        "cached_get_transcript_summaries_for_paths",
        lambda _paths: called.__setitem__("summaries", called["summaries"] + 1),
    )
    monkeypatch.setattr(mod, "_format_path_created_at", lambda _p: "2026-03-25 10:00")
    monkeypatch.setattr(
        mod,
        "_library_browser_fragment",
        mod._library_browser_fragment.__wrapped__,
    )

    mod.render_library()

    assert _DummyStreamlit.captured_df is not None
    assert "Path" not in _DummyStreamlit.captured_df.columns
    assert list(_DummyStreamlit.captured_df["Date Created"]) == [
        "2026-03-25 10:00",
        "2026-03-25 10:00",
    ]
    assert list(_DummyStreamlit.captured_df["Duration"]) == ["2m", "1h 2m"]
    assert called["transcripts"] == 1
    assert called["summaries"] == 0


def test_library_default_render_calls_transcript_index_only(monkeypatch) -> None:
    test_render_library_default_render_skips_batch_summary_enrichment(monkeypatch)


def test_library_detail_toggle_enriches_selected_transcript_only(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.captions = []
    _DummyStreamlit.session_state = {}

    transcripts = [
        TranscriptMetadata(
            path=Path("/tmp/short.json"),
            base_name="short",
            duration_seconds=125.0,
            speaker_count=2,
            has_analysis_outputs=False,
            has_speaker_map=True,
        )
    ]

    monkeypatch.setattr(mod, "st", _DummyStreamlit)
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: transcripts)
    monkeypatch.setattr(mod, "_format_path_created_at", lambda _p: "2026-03-25 10:00")
    audio_calls = {"resolve": 0, "has_resolvable": 0}
    monkeypatch.setattr(
        mod,
        "_resolve_audio_for_transcript",
        lambda _p: audio_calls.__setitem__("resolve", audio_calls["resolve"] + 1)
        or Path("/tmp/short.mp3"),
    )
    if hasattr(mod, "has_resolvable_audio"):
        monkeypatch.setattr(
            mod,
            "has_resolvable_audio",
            lambda _p: audio_calls.__setitem__(
                "has_resolvable", audio_calls["has_resolvable"] + 1
            ),
        )
    monkeypatch.setattr(mod, "apply_transcript_selection_context", lambda *_args: None)
    monkeypatch.setattr(
        mod,
        "_library_browser_fragment",
        mod._library_browser_fragment.__wrapped__,
    )

    toggle_values = iter([False, True])
    monkeypatch.setattr(
        _DummyStreamlit, "toggle", lambda *_args, **_kwargs: next(toggle_values)
    )
    monkeypatch.setattr(_DummyStreamlit, "selectbox", lambda *_args, **_kwargs: 1)
    calls = {"paths": None}
    monkeypatch.setattr(
        mod,
        "cached_get_transcript_summaries_for_paths",
        lambda paths: calls.__setitem__("paths", paths)
        or [
            type(
                "_Summary",
                (),
                {
                    "path": str(Path("/tmp/short.json").resolve()),
                    "speaker_map_status": "complete",
                    "unidentified_speaker_count": 0,
                    "ignored_speaker_count": 0,
                    "unique_speaker_count": 2,
                },
            )()
        ],
    )

    mod.render_library()

    assert calls["paths"] == (str(Path("/tmp/short.json").resolve()),)
    assert audio_calls["resolve"] == 1
    assert audio_calls["has_resolvable"] == 0


def test_library_detailed_metadata_reuses_audio_resolution(monkeypatch) -> None:
    test_library_detail_toggle_enriches_selected_transcript_only(monkeypatch)


def test_library_page_wires_shared_rename_form() -> None:
    """Library uses shared rename form component."""
    import transcriptx.web.page_modules.library as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "library_rename_form" in source
    assert "render_transcript_rename_form" in source
