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

        @staticmethod
        def error(msg, **_k):
            errors.append(str(msg))

    monkeypatch.setattr(mod, "st", _St)
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
