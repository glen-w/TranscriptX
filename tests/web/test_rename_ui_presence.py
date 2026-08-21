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


def test_library_page_does_not_embed_rename_form() -> None:
    import transcriptx.web.page_modules.library as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "library_rename_form" not in source
    assert "render_transcript_rename_form" not in source


def test_rename_transcript_page_uses_shared_rename_form() -> None:
    import transcriptx.web.page_modules.rename_transcript as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "render_transcript_rename_form" in source
    assert "rename_transcript_page_form" in source
    assert "date_prefix_prefill=True" in source
    assert "autoplay=True" in source
    assert "@st.fragment" in source
