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
    monkeypatch.setattr(
        mod, "render_merge_profiles_editor", lambda: []
    )
    monkeypatch.setattr(
        mod,
        "_render_shared_merge_options",
        lambda: {
            "backup_wavs": True,
            "overwrite": False,
            "delete_originals": False,
            "apply_preprocessing": False,
        },
    )

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
    monkeypatch.setattr(mod, "render_merge_profiles_editor", lambda: [])
    monkeypatch.setattr(
        mod,
        "_render_shared_merge_options",
        lambda: {
            "backup_wavs": True,
            "overwrite": False,
            "delete_originals": False,
            "apply_preprocessing": False,
        },
    )

    mod.render_merge_panel(deps_ready=True)

    assert section_calls
    assert clip in section_calls[0]


@pytest.mark.unit
def test_merge_panel_has_delete_originals_option() -> None:
    import transcriptx.web.ui.tools.merge_panel as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Delete originals once merge is complete" in source
    assert "delete_originals=delete_originals" in source


@pytest.mark.unit
def test_merge_panel_exposes_profiles_and_auto_merge() -> None:
    import transcriptx.web.ui.tools.merge_panel as mod
    import transcriptx.web.ui.tools.merge_profiles_editor as editor

    merge_src = Path(mod.__file__).read_text(encoding="utf-8")
    editor_src = Path(editor.__file__).read_text(encoding="utf-8")
    assert "render_merge_profiles_editor" in merge_src
    assert "Auto-merge selected groups" in merge_src
    assert "_run_auto_merge" in merge_src
    assert "Merge source profiles" in editor_src
    assert "Day window" in editor_src
    assert "Within time period (minutes)" in editor_src
    assert "Merge options" in merge_src
    assert "_render_shared_merge_options" in merge_src


@pytest.mark.unit
def test_auto_merge_invokes_controller_per_group(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.ui.tools.merge_panel as mod
    from transcriptx.app.models.results import MergeResult
    from transcriptx.core.audio.serial_groups import SerialGroup

    DummyHomeStreamlit.session_state = {}
    calls: list = []

    class _Ctrl:
        def run_merge(self, request, progress=None):
            calls.append(
                {
                    "paths": list(request.file_paths),
                    "delete_originals": request.delete_originals,
                    "apply_preprocessing": request.apply_preprocessing,
                    "overwrite": request.overwrite,
                    "backup_wavs": request.backup_wavs,
                }
            )
            return MergeResult(
                success=True,
                output_path=tmp_path / f"out_{len(calls)}.mp3",
                files_merged=len(request.file_paths),
            )

    class _Status:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def update(self, **_k):
            return None

    class _St(DummyHomeStreamlit):
        @staticmethod
        def status(*_a, **_k):
            return _Status()

        @staticmethod
        def rerun(*_a, **_k):
            return None

    a1 = tmp_path / "a1.wav"
    a2 = tmp_path / "a2.wav"
    b1 = tmp_path / "b1.wav"
    b2 = tmp_path / "b2.wav"
    for path in (a1, a2, b1, b2):
        path.write_bytes(b"x")

    groups = [
        SerialGroup(
            base_key="A",
            ordered_paths=(a1, a2),
            confidence="high",
            matched_rule="timestamp_suffix",
            profile_id="serial_parts",
            profile_name="Serial parts",
        ),
        SerialGroup(
            base_key="B",
            ordered_paths=(b1, b2),
            confidence="medium",
            matched_rule="voice_note_run",
            profile_id="whatsapp",
            profile_name="WhatsApp",
        ),
    ]

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "MergeController", lambda: _Ctrl())
    monkeypatch.setattr(mod, "RECORDINGS_DIR", tmp_path)

    mod._run_auto_merge(
        groups,
        backup_wavs=False,
        overwrite=True,
        delete_originals=True,
        apply_preprocessing=True,
    )

    assert len(calls) == 2
    assert calls[0]["paths"] == [a1, a2]
    assert calls[1]["paths"] == [b1, b2]
    assert calls[0]["delete_originals"] is True
    assert calls[0]["apply_preprocessing"] is True
    assert calls[0]["overwrite"] is True
    assert calls[0]["backup_wavs"] is False
    assert DummyHomeStreamlit.session_state.get(mod._KEY_AUTO_RESULTS)


@pytest.mark.unit
def test_merge_panel_preprocessing_is_opt_in() -> None:
    import inspect

    import transcriptx.web.ui.tools.merge_panel as mod
    from transcriptx.app.models.requests import MergeRequest
    from transcriptx.core.audio.conversion import merge_audio_files, merge_wav_files

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "Preprocess files while merging" in source
    assert "apply_preprocessing=apply_preprocessing" in source
    assert MergeRequest.__dataclass_fields__["apply_preprocessing"].default is False
    assert (
        inspect.signature(merge_audio_files)
        .parameters["apply_preprocessing_steps"]
        .default
        is False
    )
    assert (
        inspect.signature(merge_wav_files)
        .parameters["apply_preprocessing_steps"]
        .default
        is False
    )


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
