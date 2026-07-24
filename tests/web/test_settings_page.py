"""Settings hub page orchestration contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.web.streamlit_doubles import DummyHomeStreamlit


class _Tabs:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


_SETTINGS_TABS = (
    "Configuration",
    "Analysis",
    "Storage",
    "Speakers",
    "Interface",
    "Models",
    "Questions",
)


def _seven_tabs():
    return (_Tabs(), _Tabs(), _Tabs(), _Tabs(), _Tabs(), _Tabs(), _Tabs())


def _patch_settings_presentation(monkeypatch, mod) -> None:
    """Force Full controls so all Settings tabs remain visible in unit doubles."""
    from transcriptx.web.presentation.prefs import MODE_FULL

    monkeypatch.setattr(mod, "resolve_presentation_mode", lambda: MODE_FULL)
    monkeypatch.setattr(mod, "render_presentation_mode_switch", lambda **_k: None)
    monkeypatch.setattr(
        "transcriptx.web.demo_ui.render_settings_demo_controls",
        lambda: None,
    )


@pytest.mark.unit
def test_settings_page_invokes_all_panels(monkeypatch) -> None:
    import transcriptx.web.page_modules.settings as mod

    DummyHomeStreamlit.session_state = {}
    panel_calls: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def tabs(_labels):
            assert list(_labels) == list(_SETTINGS_TABS)
            return _seven_tabs()

        @staticmethod
        def error(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    _patch_settings_presentation(monkeypatch, mod)
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    monkeypatch.setattr(
        mod,
        "render_configuration_panel",
        lambda **kwargs: panel_calls.append(("configuration", kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "render_analysis_presets_panel",
        lambda: panel_calls.append(("analysis", {})),
    )
    monkeypatch.setattr(
        mod, "render_storage_panel", lambda: panel_calls.append(("storage", {}))
    )
    monkeypatch.setattr(
        mod, "render_speakers_panel", lambda: panel_calls.append(("speakers", {}))
    )
    monkeypatch.setattr(
        mod, "render_interface_panel", lambda: panel_calls.append(("interface", {}))
    )
    monkeypatch.setattr(
        mod, "render_models_panel", lambda: panel_calls.append(("models", {}))
    )
    monkeypatch.setattr(
        mod, "render_questions_panel", lambda: panel_calls.append(("questions", {}))
    )

    mod.render_settings_page()

    names = [c[0] for c in panel_calls]
    assert names == [
        "configuration",
        "analysis",
        "storage",
        "speakers",
        "interface",
        "models",
        "questions",
    ]
    assert panel_calls[0][1]["run_dir"] is None
    assert panel_calls[0][1]["subject_display"] is None


@pytest.mark.unit
def test_settings_page_passes_resolved_run_dir(monkeypatch, tmp_path) -> None:
    import transcriptx.web.page_modules.settings as mod

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    DummyHomeStreamlit.session_state = {"run_id": "r1"}
    cfg_kwargs: list[dict] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def tabs(_labels):
            return _seven_tabs()

    subject = SimpleNamespace(
        scope="transcript",
        subject_id="slug-a",
        display=SimpleNamespace(name="Meeting"),
    )
    monkeypatch.setattr(mod, "st", _St)
    _patch_settings_presentation(monkeypatch, mod)
    monkeypatch.setattr(
        mod.SubjectService, "resolve_current_subject", lambda _ss: subject
    )
    monkeypatch.setattr(mod.RunIndex, "get_run_root", lambda *_a, **_k: run_dir)
    monkeypatch.setattr(
        mod,
        "render_configuration_panel",
        lambda **kwargs: cfg_kwargs.append(kwargs),
    )
    monkeypatch.setattr(mod, "render_analysis_presets_panel", lambda: None)
    monkeypatch.setattr(mod, "render_storage_panel", lambda: None)
    monkeypatch.setattr(mod, "render_speakers_panel", lambda: None)
    monkeypatch.setattr(mod, "render_interface_panel", lambda: None)
    monkeypatch.setattr(mod, "render_models_panel", lambda: None)
    monkeypatch.setattr(mod, "render_questions_panel", lambda: None)

    mod.render_settings_page()

    assert cfg_kwargs
    assert cfg_kwargs[0]["run_dir"] == run_dir
    assert cfg_kwargs[0]["subject_display"] == "Meeting"
    assert cfg_kwargs[0]["run_display"] == "r1"


@pytest.mark.unit
def test_settings_page_surfaces_panel_errors(monkeypatch) -> None:
    import transcriptx.web.page_modules.settings as mod

    DummyHomeStreamlit.session_state = {}
    errors: list[str] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def tabs(_labels):
            return _seven_tabs()

        @classmethod
        def error(cls, msg, **_k):
            errors.append(str(msg))

    monkeypatch.setattr(mod, "st", _St)
    _patch_settings_presentation(monkeypatch, mod)
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)

    def _boom(**_k):
        raise RuntimeError("cfg boom")

    monkeypatch.setattr(mod, "render_configuration_panel", _boom)
    monkeypatch.setattr(mod, "render_analysis_presets_panel", lambda: None)
    monkeypatch.setattr(mod, "render_storage_panel", lambda: None)
    monkeypatch.setattr(mod, "render_speakers_panel", lambda: None)
    monkeypatch.setattr(mod, "render_interface_panel", lambda: None)
    monkeypatch.setattr(mod, "render_models_panel", lambda: None)
    monkeypatch.setattr(mod, "render_questions_panel", lambda: None)

    mod.render_settings_page()

    assert errors
    assert "Could not load Configuration" in errors[0]
    assert "cfg boom" in errors[0]


@pytest.mark.unit
def test_settings_page_guided_hides_advanced_tabs(monkeypatch) -> None:
    import transcriptx.web.page_modules.settings as mod
    from transcriptx.web.presentation.prefs import MODE_GUIDED

    DummyHomeStreamlit.session_state = {"settings_hub_selected_tab": "Interface"}
    seen_labels: list[list[str]] = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def tabs(labels):
            seen_labels.append(list(labels))
            return tuple(_Tabs() for _ in labels)

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "resolve_presentation_mode", lambda: MODE_GUIDED)
    monkeypatch.setattr(mod, "render_presentation_mode_switch", lambda **_k: None)
    monkeypatch.setattr(
        "transcriptx.web.demo_ui.render_settings_demo_controls",
        lambda: None,
    )
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    for name in (
        "render_configuration_panel",
        "render_analysis_presets_panel",
        "render_storage_panel",
        "render_speakers_panel",
        "render_interface_panel",
        "render_models_panel",
        "render_questions_panel",
    ):
        monkeypatch.setattr(mod, name, lambda **_k: None)

    mod.render_settings_page()
    assert seen_labels
    assert seen_labels[0] == [
        "Configuration",
        "Analysis",
        "Storage",
        "Speakers",
    ]
    assert "Interface" not in seen_labels[0]
    assert "Models" not in seen_labels[0]
    assert "Questions" not in seen_labels[0]