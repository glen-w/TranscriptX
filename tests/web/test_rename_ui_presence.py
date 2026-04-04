from __future__ import annotations

from pathlib import Path


def test_library_page_has_rename_action_text() -> None:
    import transcriptx.web.page_modules.library as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Rename transcript + linked audio" in source
    assert "Rename transcript and audio" in source


def test_audio_prep_page_has_rename_action_text() -> None:
    import transcriptx.web.page_modules.audio_prep as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Rename linked transcript + audio" in source
    assert "Rename linked files" in source


def test_audio_merge_page_has_rename_action_text() -> None:
    import transcriptx.web.page_modules.audio_merge as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Recording to rename" in source
    assert "Rename linked files" in source
