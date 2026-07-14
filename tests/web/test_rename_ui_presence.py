"""Tests that rename UI controls are present where expected."""

from __future__ import annotations

from pathlib import Path


def test_rename_ui_component_has_shared_form_text() -> None:
    import transcriptx.web.components.rename_form as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "working-copy audio" in source
    assert "render_transcript_rename_form" in source
    assert "render_audio_linked_rename_form" in source
    assert "Rename linked files" in source


def test_library_page_uses_shared_rename_form() -> None:
    import transcriptx.web.page_modules.library as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "render_transcript_rename_form" in source
    assert "library_rename_form" in source


def test_audio_prep_page_uses_shared_rename_form() -> None:
    import transcriptx.web.page_modules.audio_prep as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "render_audio_linked_rename_form" in source
    assert "audio_prep_rename_form" in source


def test_audio_merge_page_uses_shared_rename_form() -> None:
    import transcriptx.web.page_modules.audio_merge as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "render_audio_linked_rename_form" in source
    assert "audio_merge_rename_form" in source
