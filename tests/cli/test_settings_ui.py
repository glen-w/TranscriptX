from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Literal
from unittest.mock import MagicMock, patch

from transcriptx.cli.settings import (
    BACK_CHOICE_KEY,
    NONE_SENTINEL,
    SettingItem,
    create_choice_editor,
    create_int_editor,
    create_list_editor,
    default_formatter,
    settings_menu_loop,
)
from transcriptx.cli.settings.generate import build_setting_items_from_dataclass


def test_default_formatter_variants():
    assert default_formatter(True) == "ON"
    assert default_formatter(False) == "OFF"
    assert default_formatter(None) == "—"
    assert default_formatter(1.23456) == "1.23"
    assert default_formatter("x" * 50).endswith("…")


def test_settings_menu_loop_uses_keys_and_back():
    item = SettingItem(
        order=1,
        key="analysis.sentiment_window_size",
        label="Sentiment window size",
        getter=lambda: 10,
        setter=lambda value: None,
        editor=lambda _: None,
    )

    with patch("transcriptx.cli.settings.ui.questionary.select") as mock_select:
        mock_select.return_value.ask.side_effect = [item.key, BACK_CHOICE_KEY]

        settings_menu_loop(
            title="Test Menu",
            items=[item],
            on_back=lambda: None,
            dirty_tracker=lambda: False,
            mark_dirty=lambda: None,
        )

        _, kwargs = mock_select.call_args
        choices = kwargs["choices"]
        assert any(choice.value == item.key for choice in choices)


def test_settings_menu_loop_cancel_does_not_setter():
    setter = MagicMock()
    item = SettingItem(
        order=1,
        key="analysis.sentiment_window_size",
        label="Sentiment window size",
        getter=lambda: 10,
        setter=setter,
        editor=lambda _: None,
    )

    with patch("transcriptx.cli.settings.ui.questionary.select") as mock_select:
        mock_select.return_value.ask.side_effect = [item.key, BACK_CHOICE_KEY]

        settings_menu_loop(
            title="Test Menu",
            items=[item],
            on_back=lambda: None,
            dirty_tracker=lambda: False,
            mark_dirty=lambda: None,
        )

    setter.assert_not_called()


def test_settings_menu_loop_sets_dirty_on_change():
    setter = MagicMock()
    dirty = {"value": False}

    def mark_dirty():
        dirty["value"] = True

    item = SettingItem(
        order=1,
        key="analysis.sentiment_window_size",
        label="Sentiment window size",
        getter=lambda: 10,
        setter=setter,
        editor=lambda _: 20,
    )

    with patch("transcriptx.cli.settings.ui.questionary.select") as mock_select:
        mock_select.return_value.ask.side_effect = [item.key, BACK_CHOICE_KEY]

        settings_menu_loop(
            title="Test Menu",
            items=[item],
            on_back=lambda: None,
            dirty_tracker=lambda: dirty["value"],
            mark_dirty=mark_dirty,
        )

    setter.assert_called_once_with(20)
    assert dirty["value"] is True


def test_int_editor_handles_invalid_and_none():
    editor = create_int_editor(min_val=1, max_val=10)
    item = SettingItem(
        order=1,
        key="k",
        label="Value",
        getter=lambda: 5,
        setter=lambda value: None,
        editor=editor,
    )

    with patch("transcriptx.cli.settings.ui.questionary.text") as mock_text:
        mock_text.return_value.ask.return_value = "abc"
        assert editor(item) is None

    editor_optional = create_int_editor(allow_none=True)
    item_optional = SettingItem(
        order=1,
        key="k2",
        label="Value",
        getter=lambda: None,
        setter=lambda value: None,
        editor=editor_optional,
    )
    with patch("transcriptx.cli.settings.ui.questionary.text") as mock_text:
        mock_text.return_value.ask.return_value = ""
        assert editor_optional(item_optional) is NONE_SENTINEL


def test_choice_editor_optional_returns_none_sentinel():
    editor = create_choice_editor(["a", "b"], allow_none=True)
    item = SettingItem(
        order=1,
        key="k",
        label="Choice",
        getter=lambda: "a",
        setter=lambda value: None,
        editor=editor,
    )
    with patch("transcriptx.cli.settings.ui.questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = NONE_SENTINEL
        assert editor(item) is NONE_SENTINEL


def test_list_editor_parses_csv():
    editor = create_list_editor()
    item = SettingItem(
        order=1,
        key="k",
        label="Items",
        getter=lambda: ["a", "b"],
        setter=lambda value: None,
        editor=editor,
    )
    with patch("transcriptx.cli.settings.ui.questionary.text") as mock_text:
        mock_text.return_value.ask.return_value = "x, y, z"
        assert editor(item) == ["x", "y", "z"]


class Color(Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class NestedConfig:
    nested_value: int = 1


@dataclass
class DummyConfig:
    count: int = field(default=3, metadata={"min": 1, "max": 5})
    ratio: Optional[float] = None
    mode: Literal["fast", "slow"] = "fast"
    color: Color = Color.RED
    title: str = "demo"
    names: list[str] = field(default_factory=list)
    nested: NestedConfig = field(default_factory=NestedConfig)
    enabled: bool = True
    skipped: int = field(default=1, metadata={"exclude": True})


def test_build_setting_items_from_dataclass_handles_types():
    config = DummyConfig()
    items = build_setting_items_from_dataclass(config, prefix="analysis")
    keys = {item.key for item in items}

    assert "analysis.count" in keys
    assert "analysis.ratio" in keys
    assert "analysis.mode" in keys
    assert "analysis.color" in keys
    assert "analysis.title" in keys
    assert "analysis.enabled" in keys
    assert "analysis.names" not in keys
    assert "analysis.nested" not in keys
    assert "analysis.skipped" not in keys

    ratio_item = next(item for item in items if item.key == "analysis.ratio")
    with patch("transcriptx.cli.settings.ui.questionary.text") as mock_text:
        mock_text.return_value.ask.return_value = ""
        assert ratio_item.editor(ratio_item) is NONE_SENTINEL

    mode_item = next(item for item in items if item.key == "analysis.mode")
    with patch("transcriptx.cli.settings.ui.questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = "slow"
        assert mode_item.editor(mode_item) == "slow"
