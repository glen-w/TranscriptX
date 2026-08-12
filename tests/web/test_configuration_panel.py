"""Configuration panel helpers and orchestration contracts (L3)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.web.streamlit_doubles import DummyColumn, DummyExpander, DummyHomeStreamlit


class _ConfigSt(DummyHomeStreamlit):
    session_state: dict = {}
    select_ix: int = 1
    edit_mode: bool = False
    show_changed: bool = False
    show_advanced: bool = False
    button_returns: dict[str, bool] = {}
    infos: list[str] = []
    successes: list[str] = []
    captions: list[str] = []
    subheaders: list[str] = []
    rerun_calls: int = 0

    @classmethod
    def reset(cls) -> None:
        cls.session_state = {}
        cls.select_ix = 1
        cls.edit_mode = False
        cls.show_changed = False
        cls.show_advanced = False
        cls.button_returns = {}
        cls.infos = []
        cls.successes = []
        cls.captions = []
        cls.subheaders = []
        cls.rerun_calls = 0

    @classmethod
    def selectbox(cls, *_a, **_k):
        options = _k.get("options")
        if options is None and len(_a) >= 2:
            options = _a[1]
        if options is not None:
            opts = list(options)
            if cls.select_ix in opts:
                return cls.select_ix
            if opts:
                index = int(_k.get("index", 0) or 0)
                if 0 <= index < len(opts):
                    return opts[index]
                return opts[0]
        return cls.select_ix

    @classmethod
    def toggle(cls, label, value=False, key=None, **_kwargs):
        if key == "settings_config_edit_mode":
            return cls.edit_mode
        if key == "settings_config_changed_only":
            return cls.show_changed
        if key == "settings_config_show_advanced_editor":
            return cls.show_advanced
        return value

    @classmethod
    def button(cls, label, key=None, disabled=False, **_kwargs):
        if disabled:
            return False
        if key and key in cls.button_returns:
            return cls.button_returns[key]
        return bool(cls.button_returns.get(label, False))

    @classmethod
    def checkbox(cls, _label, value=False, key=None, **_kwargs):
        if key is not None and key in cls.session_state:
            return bool(cls.session_state[key])
        return value

    @classmethod
    def number_input(cls, _label, min_value=0, value=0, **_kwargs):
        return value

    @classmethod
    def info(cls, msg, **_k):
        cls.infos.append(str(msg))

    @classmethod
    def success(cls, msg, **_k):
        cls.successes.append(str(msg))

    @classmethod
    def caption(cls, text, **_k):
        cls.captions.append(str(text))

    @classmethod
    def subheader(cls, text, **_k):
        cls.subheaders.append(str(text))

    @classmethod
    def markdown(cls, text, **_k):
        cls.captions.append(str(text))

    @staticmethod
    def expander(*_a, **_k):
        return DummyExpander()

    @staticmethod
    def columns(_n):
        return tuple(DummyColumn() for _ in range(_n))

    @staticmethod
    def download_button(*_a, **_k):
        return False

    @staticmethod
    def code(*_a, **_k):
        return None

    @staticmethod
    def write(*_a, **_k):
        return None

    @staticmethod
    def divider():
        return None

    @staticmethod
    def error(*_a, **_k):
        return None

    @staticmethod
    def warning(*_a, **_k):
        return None

    @staticmethod
    def json(*_a, **_k):
        return None

    @classmethod
    def rerun(cls):
        cls.rerun_calls += 1


def _resolved(*, nested: dict | None = None) -> SimpleNamespace:
    nested = nested or {"analysis": {"semantic_model_name": "x"}}
    return SimpleNamespace(
        effective_dict_nested=nested,
        sources_by_key={"analysis.semantic_model_name": "default"},
    )


def _patch_config_loads(monkeypatch, mod, *, defaults=None, project=None, draft=None):
    defaults = defaults or {"analysis": {"semantic_model_name": "default-model"}}
    monkeypatch.setattr(mod, "resolve_effective_config", lambda **_k: _resolved())
    monkeypatch.setattr(mod, "get_default_config_dict", lambda: defaults)
    monkeypatch.setattr(mod, "load_project_config", lambda: project or {})
    monkeypatch.setattr(mod, "load_draft_override", lambda: draft or {})
    monkeypatch.setattr(mod, "load_run_override", lambda _rd: {})
    monkeypatch.setattr(
        mod,
        "build_registry",
        lambda: {
            "analysis.semantic_model_name": SimpleNamespace(
                category="analysis",
                key="analysis.semantic_model_name",
            )
        },
    )
    monkeypatch.setattr(mod, "COMMON_SETTINGS_SCHEMA", ())
    monkeypatch.setattr(mod, "iter_all_profile_target_adapters", lambda: [])
    monkeypatch.setattr(mod, "validate_config", lambda _c: {})
    monkeypatch.setattr(mod, "render_config_diff", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "render_config_form", lambda **_k: {})
    monkeypatch.setattr(mod, "_render_active_profile_selectors", lambda **_k: None)
    import transcriptx.web.ui.settings.charts_overview_selector as ov_mod

    monkeypatch.setattr(ov_mod, "st", _ConfigSt)


@pytest.mark.unit
def test_coerce_scope_index_snaps_run_override_without_run(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.session_state[mod._SCOPE_WIDGET_KEY] = 3
    monkeypatch.setattr(mod, "st", _ConfigSt)
    mod._coerce_scope_index_if_needed(None)
    assert _ConfigSt.session_state[mod._SCOPE_WIDGET_KEY] == 1


@pytest.mark.unit
def test_coerce_scope_index_keeps_run_override_when_run_present(
    monkeypatch, tmp_path
) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.session_state[mod._SCOPE_WIDGET_KEY] = 3
    monkeypatch.setattr(mod, "st", _ConfigSt)
    mod._coerce_scope_index_if_needed(tmp_path)
    assert _ConfigSt.session_state[mod._SCOPE_WIDGET_KEY] == 3


@pytest.mark.unit
def test_save_target_paths(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    project = tmp_path / "project.json"
    draft = tmp_path / "draft.json"
    run_ov = tmp_path / "run_override.json"
    monkeypatch.setattr(mod, "get_project_config_path", lambda: project)
    monkeypatch.setattr(mod, "get_draft_override_path", lambda: draft)
    monkeypatch.setattr(mod, "get_run_override_path", lambda _rd: run_ov)

    assert mod._save_target("Project", None)[0] == "Project config"
    assert str(project.resolve()) in mod._save_target("Project", None)[1]
    assert mod._save_target("Draft override", None)[0] == "Draft override"
    assert mod._save_target("Run override", tmp_path)[0] == "Run override"
    assert mod._save_target("Default", None) == ("Default", "")


@pytest.mark.unit
def test_configuration_panel_workspace_title_without_run(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 1
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod)
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert any("workspace" in s.lower() for s in _ConfigSt.subheaders)
    assert any("Enable **edit mode**" in i for i in _ConfigSt.infos)


@pytest.mark.unit
def test_configuration_panel_default_scope_is_readonly_info(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 0  # Default
    _ConfigSt.edit_mode = True
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod)
    mod.render_configuration_panel(run_dir=None, subject_display="S", run_display=None)
    assert any("read-only" in i.lower() for i in _ConfigSt.infos)


@pytest.mark.unit
def test_configuration_panel_save_project(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 1
    _ConfigSt.edit_mode = True
    _ConfigSt.button_returns = {"settings_config_save": True}
    save_calls: list = []
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(
        monkeypatch,
        mod,
        project={"analysis": {"semantic_model_name": "proj"}},
    )
    monkeypatch.setattr(
        mod, "get_project_config_path", lambda: Path("/tmp/project.json")
    )
    monkeypatch.setattr(mod, "save_project_config", lambda cfg: save_calls.append(cfg))
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert save_calls
    assert _ConfigSt.successes
    assert _ConfigSt.rerun_calls == 1


@pytest.mark.unit
def test_configuration_panel_save_draft_strips_activation(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 2  # Draft override
    _ConfigSt.edit_mode = True
    _ConfigSt.button_returns = {"settings_config_save": True}
    save_calls: list = []
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(
        monkeypatch,
        mod,
        draft={"analysis": {"semantic_model_name": "d"}},
    )
    monkeypatch.setattr(mod, "get_draft_override_path", lambda: Path("/tmp/draft.json"))
    monkeypatch.setattr(
        mod,
        "save_draft_override",
        lambda cfg: save_calls.append(cfg),
    )
    monkeypatch.setattr(mod, "_strip_activation_keys", lambda cfg: cfg)
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert save_calls
    assert _ConfigSt.rerun_calls == 1


@pytest.mark.unit
def test_configuration_panel_save_run_override(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 3
    _ConfigSt.edit_mode = True
    _ConfigSt.button_returns = {"settings_config_save": True}
    save_calls: list = []
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "load_run_override", lambda _rd: {"analysis": {"semantic_model_name": "r"}}
    )
    monkeypatch.setattr(mod, "get_run_override_path", lambda _rd: tmp_path / "run.json")
    monkeypatch.setattr(
        mod,
        "save_run_override",
        lambda rd, cfg: save_calls.append((rd, cfg)),
    )
    mod.render_configuration_panel(
        run_dir=tmp_path, subject_display="S", run_display="r1"
    )
    assert save_calls
    assert save_calls[0][0] == tmp_path
    assert any("selected run" in s.lower() for s in _ConfigSt.subheaders)
    assert _ConfigSt.rerun_calls == 1


@pytest.mark.unit
def test_configuration_panel_reset_restores_base(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 1
    _ConfigSt.edit_mode = True
    _ConfigSt.button_returns = {"settings_config_reset": True}
    project = {"analysis": {"semantic_model_name": "proj-base"}}
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod, project=project)
    monkeypatch.setattr(
        mod, "get_project_config_path", lambda: Path("/tmp/project.json")
    )
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert _ConfigSt.session_state[mod._DRAFT_STATE_KEY] == project
    assert _ConfigSt.rerun_calls == 1


@pytest.mark.unit
def test_configuration_panel_revert_to_defaults(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 1
    _ConfigSt.edit_mode = True
    _ConfigSt.button_returns = {"settings_config_revert": True}
    defaults = {"analysis": {"semantic_model_name": "factory"}}
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod, defaults=defaults, project={"analysis": {}})
    monkeypatch.setattr(
        mod, "get_project_config_path", lambda: Path("/tmp/project.json")
    )
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert _ConfigSt.session_state[mod._DRAFT_STATE_KEY] == defaults
    assert _ConfigSt.rerun_calls == 1


@pytest.mark.unit
def test_configuration_panel_blocks_save_on_validation_errors(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 1
    _ConfigSt.edit_mode = True
    _ConfigSt.button_returns = {"settings_config_save": True}
    save_calls: list = []
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod, project={"analysis": {}})
    monkeypatch.setattr(
        mod,
        "validate_config",
        lambda _c: {
            "analysis.x": [SimpleNamespace(message="bad")],
        },
    )
    monkeypatch.setattr(
        mod, "get_project_config_path", lambda: Path("/tmp/project.json")
    )
    monkeypatch.setattr(mod, "save_project_config", lambda cfg: save_calls.append(cfg))
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert save_calls == []


@pytest.mark.unit
def test_profile_selector_writes_activation_in_project_scope(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as panel

    class _StubSt:
        @staticmethod
        def caption(_msg: str) -> None:
            return None

        @staticmethod
        def markdown(_msg: str) -> None:
            return None

        @staticmethod
        def warning(_msg: str) -> None:
            return None

        @staticmethod
        def selectbox(_label, options, index=0, **_k):
            return options[index]

    class _Adapter:
        target_id = "workflow"
        activation_key = "active_workflow_profile"
        activation_label = "Workflow profile"

        def matches_type(self, t: str) -> bool:
            return t == "workflow"

        def write_activation_value(self, *, value, flat_map):
            flat_map[self.activation_key] = value

    class _Ctrl:
        def can_edit_activation_for_scope(self, _tid, scope):
            return scope in ("Project", "Run override")

        def list_profiles(self, _tid):
            return ["default", "nightly"]

    monkeypatch.setattr(panel, "st", _StubSt())
    monkeypatch.setattr(panel, "iter_all_profile_target_adapters", lambda: [_Adapter()])
    monkeypatch.setattr(
        "transcriptx.app.controllers.profile_controller.ProfileController",
        lambda: _Ctrl(),
    )
    draft_dot: dict = {"active_workflow_profile": "default"}
    panel._render_active_profile_selectors(
        draft_dot=draft_dot,
        scope="Project",
        form_scope_key="project",
    )
    assert draft_dot["active_workflow_profile"] == "default"


@pytest.mark.unit
def test_configuration_panel_edit_mode_shows_charts_overview(monkeypatch) -> None:
    import transcriptx.web.ui.settings.configuration_panel as mod

    _ConfigSt.reset()
    _ConfigSt.select_ix = 1
    _ConfigSt.edit_mode = True
    monkeypatch.setattr(mod, "st", _ConfigSt)
    _patch_config_loads(monkeypatch, mod)
    mod.render_configuration_panel(run_dir=None, subject_display=None, run_display=None)
    assert any("Charts overview" in c for c in _ConfigSt.captions)
