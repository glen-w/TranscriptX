"""Settings config widgets, forms, and diff-view contracts."""

from __future__ import annotations

import pytest

from transcriptx.core.config.registry import FieldMetadata
from transcriptx.web.ui.settings.diff_view import render_config_diff
from transcriptx.web.ui.settings.forms import render_config_form
from transcriptx.web.ui.settings.widgets import render_field_widget


def _meta(**kwargs) -> FieldMetadata:
    defaults = dict(
        key="analysis.flag",
        path="analysis.flag",
        type=bool,
        default=False,
        category="analysis",
    )
    defaults.update(kwargs)
    return FieldMetadata(**defaults)


@pytest.mark.unit
def test_render_field_widget_bool_checkbox(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    calls: list = []

    class _St:
        @staticmethod
        def checkbox(label, value=False, key=None, help=None):
            calls.append((label, value, key, help))
            return True

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: True,
    )
    out = render_field_widget(
        _meta(type=bool, description="Toggle the flag"), False, "k1"
    )
    assert out is True
    assert calls[0][0] == "analysis.flag"
    assert calls[0][3] == "Toggle the flag"


@pytest.mark.unit
def test_render_field_widget_passes_description_as_help(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    captured: dict = {}

    class _St:
        @staticmethod
        def text_input(label, value="", key=None, help=None):
            captured.update(label=label, help=help, value=value, key=key)
            return value

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: True,
    )
    render_field_widget(
        _meta(type=str, key="analysis.model", path="analysis.model", description="  "),
        "m",
        "k",
    )
    assert captured["help"] is None
    render_field_widget(
        _meta(
            type=str,
            key="analysis.model",
            path="analysis.model",
            description="Model id for embeddings.",
        ),
        "m",
        "k2",
    )
    assert captured["help"] == "Model id for embeddings."


@pytest.mark.unit
def test_render_field_widget_suppresses_help_when_tips_disabled(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    captured: dict = {}

    class _St:
        @staticmethod
        def checkbox(label, value=False, key=None, help=None):
            captured["help"] = help
            return value

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.web.components.info_tooltip.info_tooltips_enabled",
        lambda: False,
    )
    render_field_widget(
        _meta(type=bool, description="Toggle the flag"),
        False,
        "k_off",
    )
    assert captured["help"] is None


@pytest.mark.unit
def test_render_field_widget_choices_selectbox(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    class _St:
        @staticmethod
        def selectbox(_label, options, index=0, key=None, help=None):
            return options[index]

    monkeypatch.setattr(mod, "st", _St)
    out = render_field_widget(
        _meta(type=str, choices=("a", "b"), key="analysis.mode", path="analysis.mode"),
        "b",
        "k2",
    )
    assert out == "b"


@pytest.mark.unit
def test_render_field_widget_multiselect_for_list_choices(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    class _St:
        @staticmethod
        def multiselect(_label, options, default=None, key=None, help=None):
            return list(default or [])

    monkeypatch.setattr(mod, "st", _St)
    out = render_field_widget(
        _meta(
            type=list,
            choices=("x", "y", "z"),
            key="analysis.mods",
            path="analysis.mods",
        ),
        ["x", "z"],
        "k3",
    )
    assert out == ["x", "z"]


@pytest.mark.unit
def test_render_field_widget_int_and_float(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    class _St:
        @staticmethod
        def number_input(_label, value=0, **_k):
            return value

    monkeypatch.setattr(mod, "st", _St)
    assert (
        render_field_widget(
            _meta(type=int, key="analysis.n", path="analysis.n", min=0, max=10),
            3,
            "ki",
        )
        == 3
    )
    assert (
        render_field_widget(
            _meta(type=float, key="analysis.f", path="analysis.f"),
            1.5,
            "kf",
        )
        == 1.5
    )


@pytest.mark.unit
def test_render_field_widget_json_list_and_invalid_keeps_current(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    class _St:
        raw = '["a"]'

        @classmethod
        def text_area(cls, *_a, **_k):
            return cls.raw

    monkeypatch.setattr(mod, "st", _St)
    assert render_field_widget(_meta(type=list, key="a.l", path="a.l"), [], "kj") == [
        "a"
    ]
    _St.raw = "not-json"
    assert render_field_widget(
        _meta(type=list, key="a.l", path="a.l"), ["keep"], "kj2"
    ) == ["keep"]


@pytest.mark.unit
def test_render_field_widget_hidden_returns_current(monkeypatch) -> None:
    import transcriptx.web.ui.settings.widgets as mod

    class _St:
        @staticmethod
        def checkbox(*_a, **_k):
            raise AssertionError("hidden fields must not render widgets")

    monkeypatch.setattr(mod, "st", _St)
    out = render_field_widget(
        _meta(sensitivity="hidden"),
        "secret",
        "kh",
    )
    assert out == "secret"


@pytest.mark.unit
def test_render_config_form_respects_allowed_keys_and_changed_filter(
    monkeypatch,
) -> None:
    import transcriptx.web.ui.settings.forms as forms_mod

    rendered: list[str] = []

    def _fake_widget(meta, value, key):
        rendered.append(meta.key)
        return value

    monkeypatch.setattr(forms_mod, "render_field_widget", _fake_widget)
    fields = [
        _meta(key="analysis.a", path="analysis.a", type=str),
        _meta(key="analysis.b", path="analysis.b", type=str),
        _meta(key="analysis.c", path="analysis.c", type=str),
    ]
    values = {"analysis.a": "1", "analysis.b": "2", "analysis.c": "3"}
    base = {"analysis.a": "1", "analysis.b": "old", "analysis.c": "3"}

    updated = render_config_form(
        category="analysis",
        fields=fields,
        values=values,
        show_only_changed=True,
        base_values=base,
        scope="project",
        allowed_keys={"analysis.a", "analysis.b"},
    )
    assert rendered == ["analysis.b"]  # a unchanged + filtered; c not allowed
    assert "analysis.b" in updated
    assert "analysis.c" not in updated


@pytest.mark.unit
def test_render_config_diff_no_changes(monkeypatch) -> None:
    import transcriptx.web.ui.settings.diff_view as mod

    captions: list[str] = []

    class _St:
        @staticmethod
        def caption(msg):
            captions.append(str(msg))

        @staticmethod
        def markdown(*_a, **_k):
            raise AssertionError("no markdown when unchanged")

    monkeypatch.setattr(mod, "st", _St)
    cfg = {"analysis": {"x": 1}}
    render_config_diff(cfg, cfg)
    assert captions == ["No changes."]


@pytest.mark.unit
def test_render_config_diff_lists_changes(monkeypatch) -> None:
    import transcriptx.web.ui.settings.diff_view as mod

    writes: list[str] = []

    class _St:
        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def markdown(*_a, **_k):
            return None

        @staticmethod
        def write(msg):
            writes.append(str(msg))

    monkeypatch.setattr(mod, "st", _St)
    render_config_diff({"analysis": {"x": 1}}, {"analysis": {"x": 2}})
    assert any("analysis.x" in w and "1" in w and "2" in w for w in writes)
