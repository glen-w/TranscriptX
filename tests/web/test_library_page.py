"""Tests for library page."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    AnalysisStatus,
    CorrectionsState,
    CorrectionsStatus,
    FieldIntegrity,
    FileStamp,
    InventoryFingerprint,
    InventoryRow,
    SpeakerIdState,
    SpeakerIdStatus,
)
from tests.web.streamlit_doubles import DummyStreamlitWithDataframe
from transcriptx.web.state import LIBRARY_SELECTED_TRANSCRIPT_PATH

_DummyStreamlit = DummyStreamlitWithDataframe


def _row(
    name: str, *, duration: float | None = 120.0, speakers: int | None = 2
) -> InventoryRow:
    return InventoryRow(
        transcript_path=Path(f"/tmp/{name}.json"),
        transcript_key=name,
        slug=name,
        title=name,
        imported_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        duration_seconds=duration,
        speaker_count=speakers,
        word_count=400,
        source_id="whisperx",
        listing_integrity=FieldIntegrity.OK,
        speaker=SpeakerIdState(
            status=SpeakerIdStatus.COMPLETE, integrity=FieldIntegrity.OK
        ),
        corrections=CorrectionsState(
            status=CorrectionsStatus.NEVER_STARTED, integrity=FieldIntegrity.MISSING
        ),
        analysis=AnalysisState(
            status=AnalysisStatus.UNANALYSED, integrity=FieldIntegrity.MISSING
        ),
        last_activity_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        fingerprint=InventoryFingerprint(
            stamps=(FileStamp(f"/tmp/{name}.json", 1, 1),)
        ),
    )


def _patch_library(monkeypatch, rows) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.captured_df = None
    _DummyStreamlit.captions = []
    _DummyStreamlit.audio_calls = []
    monkeypatch.setattr(mod, "st", _DummyStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "get_cached_corpus_inventory", lambda: rows)
    monkeypatch.setattr(mod, "render_configured_actions", lambda *_a, **_k: [])
    monkeypatch.setattr(
        mod.SubjectService,
        "set_transcript_context_from_path",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        mod,
        "_library_browser_fragment",
        mod._library_browser_fragment.__wrapped__,
    )


def test_format_duration_display() -> None:
    from transcriptx.utils.text_utils import format_duration_display

    assert format_duration_display(None) == "-"
    assert format_duration_display(125.0) == "2m"
    assert format_duration_display(3599.0) == "60m"
    assert format_duration_display(3720.0) == "1h 2m"


def test_inventory_table_row_includes_workflow_marks() -> None:
    from transcriptx.web.corpus_inventory_display import inventory_table_row

    data = inventory_table_row(_row("short", duration=125.0, speakers=2))
    assert data["Transcript"] == "short"
    assert data["Duration"] != "-"
    assert data["Speakers"] == "2"
    assert data["Speaker ID"] == "✓"
    assert data["Corrections"] == "—"
    assert data["Analysis"] == "—"
    assert data["Tags"] == "—"
    assert "Path" not in data


def test_render_library_table_uses_inventory_workflow_columns(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.session_state = {"library_filter_sort": "name"}
    _DummyStreamlit.selected_rows = []
    rows = [
        _row("short", duration=125.0, speakers=2),
        _row("long", duration=4920.0, speakers=3),
    ]
    _patch_library(monkeypatch, rows)
    summaries = {"count": 0}
    monkeypatch.setattr(
        "transcriptx.io.transcript_loader.load_segments",
        lambda *_a, **_k: summaries.__setitem__("count", summaries["count"] + 1),
    )

    mod.render_library()

    assert _DummyStreamlit.captured_df is not None
    assert "Path" not in _DummyStreamlit.captured_df.columns
    assert list(_DummyStreamlit.captured_df.columns) == [
        "Transcript",
        "Date",
        "Duration",
        "Speakers",
        "Speaker ID",
        "Corrections",
        "Analysis",
        "Tags",
        "Last activity",
    ]
    assert "-" not in list(_DummyStreamlit.captured_df["Duration"])
    assert set(_DummyStreamlit.captured_df["Speakers"]) == {"2", "3"}
    assert set(_DummyStreamlit.captured_df["Transcript"]) == {"short", "long"}
    assert summaries["count"] == 0
    assert "Select transcript" not in "".join(_DummyStreamlit.captions)


def test_library_row_selection_sets_path_identity(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.session_state = {}
    _DummyStreamlit.selected_rows = [0]
    _patch_library(monkeypatch, [_row("alice")])

    mod.render_library()

    selected = _DummyStreamlit.session_state.get(LIBRARY_SELECTED_TRANSCRIPT_PATH)
    assert selected is not None
    assert Path(str(selected)).name == "alice.json"
    assert any("Speaker identification:" in cap for cap in _DummyStreamlit.captions)
    assert any(cap.startswith("Tags:") for cap in _DummyStreamlit.captions)


def test_library_inspector_accepts_latest_run_id(monkeypatch) -> None:
    """Selecting an analysed row must pair run_id with run_dir (IdentityError otherwise)."""
    import transcriptx.web.page_modules.library as mod

    row = replace(
        _row("analysed"),
        analysis=AnalysisState(
            status=AnalysisStatus.COMPLETED,
            integrity=FieldIntegrity.OK,
            modules_succeeded=3,
            modules_eligible=3,
            latest_run_id="20260821_120000_abcdef12",
            run_status="completed",
            last_analysed_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        ),
    )
    captured: dict[str, object] = {}

    def _capture_actions(section, ctx):
        captured["identity"] = ctx.identity
        return []

    _DummyStreamlit.session_state = {
        LIBRARY_SELECTED_TRANSCRIPT_PATH: "/tmp/analysed.json",
    }
    _DummyStreamlit.selected_rows = []
    _patch_library(monkeypatch, [row])
    monkeypatch.setattr(mod, "render_configured_actions", _capture_actions)

    mod.render_library()

    identity = captured["identity"]
    assert identity.run_id == "20260821_120000_abcdef12"
    assert identity.run_dir is not None
    assert identity.run_dir.name == identity.run_id


def test_library_page_defers_rename_to_rename_transcript_page() -> None:
    """Library no longer embeds rename form; Rename lives on its own page."""
    import transcriptx.web.page_modules.library as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "library_rename_form" not in source
    assert "render_transcript_rename_form" not in source
    assert "library_transcript_select" not in source
    assert "st.dataframe" in source


def test_library_inspector_renders_linked_audio_player(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    audio = Path("/tmp/alice.mp3")
    _DummyStreamlit.session_state = {
        LIBRARY_SELECTED_TRANSCRIPT_PATH: "/tmp/alice.json",
    }
    _DummyStreamlit.selected_rows = []
    _patch_library(monkeypatch, [_row("alice")])
    monkeypatch.setattr(mod, "_resolve_audio_for_transcript", lambda _p: audio)

    mod.render_library()

    assert _DummyStreamlit.audio_calls == [audio]
    assert not any("No linked audio" in cap for cap in _DummyStreamlit.captions)


def test_library_inspector_shows_no_linked_audio(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.session_state = {
        LIBRARY_SELECTED_TRANSCRIPT_PATH: "/tmp/alice.json",
    }
    _DummyStreamlit.selected_rows = []
    _patch_library(monkeypatch, [_row("alice")])
    monkeypatch.setattr(mod, "_resolve_audio_for_transcript", lambda _p: None)

    mod.render_library()

    assert _DummyStreamlit.audio_calls == []
    assert any("No linked audio" in cap for cap in _DummyStreamlit.captions)


def test_library_delete_on_primary_strip_by_default() -> None:
    from transcriptx.web.action_menus.catalog import (
        SECTION_ALLOWLISTS,
        SECTION_DEFAULTS,
        section_default_actions,
    )
    from transcriptx.web.action_menus.ids import ActionId, SectionId

    assert ActionId.DELETE in SECTION_ALLOWLISTS[SectionId.LIBRARY_SELECTED]
    defaults = section_default_actions(
        SectionId.LIBRARY_SELECTED, subject_type="transcript", has_run=False
    )
    assert ActionId.DELETE in defaults
    assert defaults[-1] is ActionId.DELETE
    for key, section_defaults in SECTION_DEFAULTS.items():
        if key.section is SectionId.LIBRARY_SELECTED:
            assert ActionId.DELETE in section_defaults
        else:
            assert ActionId.DELETE not in section_defaults
