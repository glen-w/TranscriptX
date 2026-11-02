"""Launcher flag contracts for ``python -m transcriptx.web``."""

from __future__ import annotations

import pytest

from transcriptx.web.__main__ import BRAND_PRIMARY_COLOR, file_watcher_args, theme_args


@pytest.mark.unit
def test_brand_primary_colour_by_default() -> None:
    assert theme_args({}) == ["--theme.primaryColor", BRAND_PRIMARY_COLOR]


@pytest.mark.unit
def test_operator_theme_env_wins() -> None:
    assert theme_args({"STREAMLIT_THEME_PRIMARY_COLOR": "#123456"}) == []


@pytest.mark.unit
def test_file_watcher_off_by_default() -> None:
    assert file_watcher_args({}) == ["--server.fileWatcherType", "none"]


@pytest.mark.unit
@pytest.mark.parametrize("flag", ["1", "true", "ON", "yes"])
def test_dev_mode_keeps_streamlit_default_watcher(flag: str) -> None:
    assert file_watcher_args({"TRANSCRIPTX_DEV": flag}) == []


@pytest.mark.unit
def test_explicit_watcher_type_wins() -> None:
    env = {"TRANSCRIPTX_DEV": "1", "TRANSCRIPTX_FILE_WATCHER": "poll"}
    assert file_watcher_args(env) == ["--server.fileWatcherType", "poll"]
