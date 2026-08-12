"""Tools hub and preprocess/merge panel contracts (L3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_recordings_path_label_relative_and_fallback(monkeypatch, tmp_path) -> None:
    import transcriptx.web.ui.tools.shared as shared

    recordings = tmp_path / "recordings"
    nested = recordings / "imports" / "a.wav"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"x")
    monkeypatch.setattr(shared, "RECORDINGS_DIR", recordings)

    assert shared.recordings_path_label(nested) == "imports/a.wav"
    outside = tmp_path / "other" / "b.wav"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    assert shared.recordings_path_label(outside) == "b.wav"


@pytest.mark.unit
def test_resolve_output_dir_destinations(monkeypatch, tmp_path) -> None:
    import transcriptx.web.ui.tools.preprocess_panel as mod

    audio = tmp_path / "rec" / "clip.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"x")
    monkeypatch.setattr(mod, "RECORDINGS_DIR", tmp_path / "recordings")

    assert mod.resolve_output_dir(audio, "same") == audio.parent
    assert mod.resolve_output_dir(audio, "sub") == audio.parent / "preprocessed"
    assert mod.resolve_output_dir(audio, "app") == (
        tmp_path / "recordings" / "preprocessed"
    )


@pytest.mark.unit
def test_tools_page_renders_tabs_and_panels(monkeypatch) -> None:
    import transcriptx.web.page_modules.tools as mod

    DummyHomeStreamlit.session_state = {}
    rendered: list[str] = []
    captions: list[str] = []

    class _TabCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _St(DummyHomeStreamlit):
        @staticmethod
        def tabs(labels):
            return [_TabCtx() for _ in labels]

        @staticmethod
        def caption(msg, **_k):
            captions.append(str(msg))

        @staticmethod
        def markdown(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_dependency_banner", lambda: True)
    monkeypatch.setattr(
        mod,
        "render_preprocess_panel",
        lambda **_k: rendered.append("preprocess"),
    )
    monkeypatch.setattr(
        mod, "render_merge_panel", lambda **_k: rendered.append("merge")
    )

    mod.render_tools_page()

    assert rendered == ["preprocess", "merge"]
    assert any("Prepare recordings" in c for c in captions)


@pytest.mark.unit
def test_tools_page_force_tab_reorders(monkeypatch) -> None:
    import transcriptx.web.page_modules.tools as mod
    from transcriptx.web.navigation import TOOLS_HUB_FORCE_TAB_KEY

    DummyHomeStreamlit.session_state = {TOOLS_HUB_FORCE_TAB_KEY: "Merge"}
    seen_labels: list[list[str]] = []

    class _TabCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _St(DummyHomeStreamlit):
        @staticmethod
        def tabs(labels):
            seen_labels.append(list(labels))
            return [_TabCtx() for _ in labels]

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def markdown(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_dependency_banner", lambda: True)
    monkeypatch.setattr(mod, "render_preprocess_panel", lambda **_k: None)
    monkeypatch.setattr(mod, "render_merge_panel", lambda **_k: None)

    mod.render_tools_page()

    assert seen_labels
    assert seen_labels[0][0] == "Merge"
    assert TOOLS_HUB_FORCE_TAB_KEY not in DummyHomeStreamlit.session_state


@pytest.mark.unit
def test_preprocess_empty_list_shows_info(monkeypatch, tmp_path) -> None:
    import transcriptx.web.ui.tools.preprocess_panel as mod
    import transcriptx.web.ui.tools.shared as shared

    infos: list[str] = []
    DummyHomeStreamlit.session_state = {}
    recordings = tmp_path / "recordings"
    recordings.mkdir()

    class _St(DummyHomeStreamlit):
        @staticmethod
        def file_uploader(*_a, **_k):
            return []

        @staticmethod
        def info(msg, **_k):
            infos.append(str(msg))

        @staticmethod
        def fragment(fn=None, **_kwargs):
            if fn is None:

                def _decorator(f):
                    return f

                return _decorator
            return fn

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def subheader(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(shared, "st", _St)
    monkeypatch.setattr(shared.RecordingsService, "list_recordings", lambda *_a, **_k: [])
    monkeypatch.setattr(shared, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(shared, "RECORDINGS_IMPORTS_DIR", recordings / "imports")

    mod.render_preprocess_panel(deps_ready=True)

    assert infos
    assert "No audio files found" in infos[0]


@pytest.mark.unit
def test_merge_empty_recordings_shows_info(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.ui.tools.merge_panel as mod
    import transcriptx.web.ui.tools.shared as shared

    infos: list[str] = []
    DummyHomeStreamlit.session_state = {}
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    imports = recordings / "imports"
    imports.mkdir()

    class _St(DummyHomeStreamlit):
        @staticmethod
        def file_uploader(*_a, **_k):
            return []

        @staticmethod
        def info(msg, **_k):
            infos.append(str(msg))

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def markdown(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(shared, "st", _St)
    monkeypatch.setattr(shared, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(shared, "RECORDINGS_IMPORTS_DIR", imports)
    monkeypatch.setattr(shared.RecordingsService, "list_recordings", lambda *_a, **_k: [])
    section_calls: list = []
    monkeypatch.setattr(
        mod, "_render_section_select", lambda *_a, **_k: section_calls.append(True)
    )
    monkeypatch.setattr(mod, "_render_detected_serial_groups", lambda *_a, **_k: None)

    mod.render_merge_panel(deps_ready=True)

    assert infos
    assert "No audio files found" in infos[0]
    assert section_calls == []


@pytest.mark.unit
def test_merge_with_recordings_renders_section(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.ui.tools.merge_panel as mod
    import transcriptx.web.ui.tools.shared as shared

    DummyHomeStreamlit.session_state = {}
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    imports = recordings / "imports"
    imports.mkdir()
    clip = recordings / "a.wav"
    clip.write_bytes(b"x")

    class _St(DummyHomeStreamlit):
        @staticmethod
        def file_uploader(*_a, **_k):
            return []

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def markdown(*_a, **_k):
            return None

    section_calls: list = []
    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(shared, "st", _St)
    monkeypatch.setattr(shared, "RECORDINGS_DIR", recordings)
    monkeypatch.setattr(shared, "RECORDINGS_IMPORTS_DIR", imports)
    monkeypatch.setattr(
        shared.RecordingsService,
        "list_recordings",
        lambda root: [clip] if root == recordings else [],
    )
    monkeypatch.setattr(
        mod,
        "_render_section_select",
        lambda recs, **_k: section_calls.append(list(recs)),
    )
    monkeypatch.setattr(mod, "_render_detected_serial_groups", lambda *_a, **_k: None)

    mod.render_merge_panel(deps_ready=True)

    assert section_calls
    assert clip in section_calls[0]


@pytest.mark.unit
def test_dependency_banner_reports_missing(monkeypatch) -> None:
    import transcriptx.web.ui.tools.shared as shared

    errors: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def error(msg, **_k):
            errors.append(str(msg))

        @staticmethod
        def caption(*_a, **_k):
            return None

    monkeypatch.setattr(shared, "st", _St)
    monkeypatch.setattr(shared, "check_ffmpeg_available", lambda: (False, "no ffmpeg"))
    monkeypatch.setattr(shared, "PYDUB_AVAILABLE", False)

    assert shared.render_dependency_banner() is False
    assert errors
    assert "ffmpeg" in errors[0].lower() or "Audio tools" in errors[0]


@pytest.mark.unit
def test_navigate_to_tools_tab_sets_force_and_paths() -> None:
    from transcriptx.web.navigation import (
        PREPROCESS_SELECTED_FILES_KEY,
        TOOLS_HUB_FORCE_TAB_KEY,
        TOOLS_HUB_TAB_KEY,
        navigate_to_tools_tab,
    )

    session: dict = {}
    navigate_to_tools_tab(
        session, "Preprocessing", preprocess_paths=[Path("/tmp/out.mp3")]
    )
    assert session["page"] == "Tools"
    assert session[TOOLS_HUB_TAB_KEY] == "Preprocessing"
    assert session[TOOLS_HUB_FORCE_TAB_KEY] == "Preprocessing"
    assert session[PREPROCESS_SELECTED_FILES_KEY] == ["/tmp/out.mp3"]
