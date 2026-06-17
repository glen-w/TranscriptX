from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.metadata import TranscriptMetadata


class _DummyForm:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyStreamlit:
    captured_df = None
    session_state = {}

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def info(*_args, **_kwargs):
        return None

    @classmethod
    def dataframe(cls, df, **_kwargs):
        cls.captured_df = df.copy()
        return None

    @staticmethod
    def divider():
        return None

    @staticmethod
    def subheader(*_args, **_kwargs):
        return None

    @staticmethod
    def selectbox(*_args, **_kwargs):
        return 0

    @staticmethod
    def columns(_n):
        return (_DummyColumn(), _DummyColumn())

    @staticmethod
    def button(*_args, **_kwargs):
        return False

    @staticmethod
    def rerun():
        return None

    @staticmethod
    def caption(*_args, **_kwargs):
        return None

    @staticmethod
    def form(*_args, **_kwargs):
        return _DummyForm()

    @staticmethod
    def text_input(*_args, **_kwargs):
        return ""

    @staticmethod
    def form_submit_button(*_args, **_kwargs):
        return False

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def success(*_args, **_kwargs):
        return None

    @staticmethod
    def toggle(*_args, **_kwargs):
        return False


def test_format_duration_display() -> None:
    import transcriptx.web.page_modules.library as mod

    assert mod._format_duration_display(None) == "-"
    assert mod._format_duration_display(125.0) == "2m"
    assert mod._format_duration_display(3599.0) == "60m"
    assert mod._format_duration_display(3720.0) == "1h 2m"


def test_render_library_summary_shows_has_audio_and_duration(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.captured_df = None

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
    monkeypatch.setattr(mod, "get_cached_list_transcripts", lambda: transcripts)
    monkeypatch.setattr(
        mod,
        "cached_get_transcript_summaries_for_paths",
        lambda _paths: [
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
            )(),
            type(
                "_Summary",
                (),
                {
                    "path": str(Path("/tmp/long.json").resolve()),
                    "speaker_map_status": "partial",
                    "unidentified_speaker_count": 2,
                    "ignored_speaker_count": 1,
                    "unique_speaker_count": 3,
                },
            )(),
        ],
    )
    monkeypatch.setattr(
        mod,
        "has_resolvable_audio",
        lambda p: Path(p).stem == "short",
    )
    monkeypatch.setattr(mod, "_format_path_created_at", lambda _p: "2026-03-25 10:00")
    monkeypatch.setattr(
        mod,
        "_resolve_audio_for_transcript",
        lambda p: Path("/tmp/short.mp3") if p.stem == "short" else None,
    )
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
    assert list(_DummyStreamlit.captured_df["Date Recorded"]) == [
        "2026-03-25 10:00",
        "—",
    ]
    assert list(_DummyStreamlit.captured_df["Duration"]) == ["2m", "1h 2m"]
    assert list(_DummyStreamlit.captured_df["Has Audio"]) == ["✓", "—"]
    assert list(_DummyStreamlit.captured_df["Fully Mapped"]) == ["✓", "—"]
    assert list(_DummyStreamlit.captured_df["Identified"]) == ["2", "0"]
    assert list(_DummyStreamlit.captured_df["Ignored"]) == ["0", "1"]


def test_library_page_wires_rename_service_for_transcript_rename_form() -> None:
    """Library uses RenameService + refresh for the post-rename Streamlit form."""
    import transcriptx.web.page_modules.library as mod

    assert getattr(mod, "RenameService", None) is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "library_rename_form" in source
    assert "RenameService.rename_transcript_and_audio" in source
    assert "RenameService.refresh_after_rename" in source
