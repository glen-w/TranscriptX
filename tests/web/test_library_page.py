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
from transcriptx.web.state import (
    LIBRARY_FILTER_QUERY_KEY,
    LIBRARY_LIST_PAGE_KEY,
    LIBRARY_SELECTED_TRANSCRIPT_PATH,
)

_DummyStreamlit = DummyStreamlitWithDataframe


def _row(name: str, *, duration: float | None = 120.0, speakers: int | None = 2) -> InventoryRow:
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
        fingerprint=InventoryFingerprint(stamps=(FileStamp(f"/tmp/{name}.json", 1, 1),)),
    )


def _patch_library(monkeypatch, rows, *, click_key: str | None = None) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.captured_df = None
    _DummyStreamlit.captions = []
    _DummyStreamlit.button_labels = []
    _DummyStreamlit.button_presses = {click_key} if click_key else set()
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


def test_inventory_list_caption_includes_workflow_marks() -> None:
    from transcriptx.web.corpus_inventory_display import inventory_list_caption

    caption = inventory_list_caption(_row("short", duration=125.0, speakers=2))
    assert "2m" in caption or "2 speakers" in caption
    assert "2 speakers" in caption
    assert "SID ✓" in caption
    assert "Corr —" in caption
    assert "Anal —" in caption


def test_render_library_list_shows_title_buttons(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    _DummyStreamlit.session_state = {"library_filter_sort": "name"}
    rows = [_row("short", duration=125.0, speakers=2), _row("long", duration=4920.0, speakers=3)]
    _patch_library(monkeypatch, rows)

    mod.render_library()

    assert "short" in _DummyStreamlit.button_labels
    assert "long" in _DummyStreamlit.button_labels
    assert any("2 of 2 transcripts" in cap for cap in _DummyStreamlit.captions)
    assert any("Showing 1–2 of 2" in cap for cap in _DummyStreamlit.captions)
    assert _DummyStreamlit.captured_df is None
    assert "Select transcript" not in "".join(_DummyStreamlit.captions)
    assert "Show path column" not in "".join(_DummyStreamlit.captions)


def test_library_row_button_sets_path_identity(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    row = _row("alice")
    click_key = mod._row_widget_key(row)
    _DummyStreamlit.session_state = {}
    _patch_library(monkeypatch, [row], click_key=click_key)

    mod.render_library()

    selected = _DummyStreamlit.session_state.get(LIBRARY_SELECTED_TRANSCRIPT_PATH)
    assert selected is not None
    assert Path(str(selected)).name == "alice.json"
    assert any("Speaker identification:" in cap for cap in _DummyStreamlit.captions)


def test_library_pagination_page_two_and_filter_reset(monkeypatch) -> None:
    import transcriptx.web.page_modules.library as mod

    rows = [_row(f"item_{i:02d}") for i in range(30)]
    _DummyStreamlit.session_state = {
        "library_filter_sort": "name",
        LIBRARY_LIST_PAGE_KEY: 2,
    }
    _patch_library(monkeypatch, rows)

    mod.render_library()

    assert "item_25" in _DummyStreamlit.button_labels
    assert "item_29" in _DummyStreamlit.button_labels
    assert "item_00" not in _DummyStreamlit.button_labels
    assert any("Showing 26–30 of 30" in cap for cap in _DummyStreamlit.captions)

    _DummyStreamlit.captions = []
    _DummyStreamlit.button_labels = []
    _DummyStreamlit.session_state[LIBRARY_FILTER_QUERY_KEY] = "item_01"
    mod.render_library()

    assert _DummyStreamlit.session_state[LIBRARY_LIST_PAGE_KEY] == 1
    assert "item_01" in _DummyStreamlit.button_labels
    assert any("Showing 1–1 of 1" in cap for cap in _DummyStreamlit.captions)


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
    assert "st.dataframe" not in source
