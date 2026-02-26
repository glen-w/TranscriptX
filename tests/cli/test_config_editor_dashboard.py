"""Tests for dashboard configuration editor."""

from unittest.mock import patch

from transcriptx.cli.config_editors.dashboard import (
    _sanitize_overview_charts,
    edit_dashboard_config,
)
from transcriptx.core.utils.chart_registry import get_default_overview_charts
from transcriptx.core.utils.config import TranscriptXConfig


def test_sanitize_overview_charts_filters_invalid():
    cleaned, removed = _sanitize_overview_charts(["valid", "invalid", 123], ["valid"])
    assert cleaned == ["valid"]
    assert removed == ["invalid", "123"]


def test_edit_dashboard_config_marks_checked_choices():
    config = TranscriptXConfig()
    config.dashboard.overview_charts = get_default_overview_charts()[:2]
    captured = {}

    def fake_checkbox(*_args, **kwargs):
        captured["choices"] = kwargs["choices"]

        class Dummy:
            def ask(self):
                return None

        return Dummy()

    with (
        patch(
            "transcriptx.cli.config_editors.dashboard.questionary.select"
        ) as mock_select,
        patch(
            "transcriptx.cli.config_editors.dashboard.questionary.checkbox"
        ) as mock_checkbox,
    ):
        mock_select.return_value.ask.side_effect = ["add_remove", "back"]
        mock_checkbox.side_effect = fake_checkbox

        edit_dashboard_config(config)

    checked = [choice.value for choice in captured["choices"] if choice.checked]
    assert set(checked) == set(config.dashboard.overview_charts)


def test_edit_dashboard_config_removes_invalid_ids():
    config = TranscriptXConfig()
    config.dashboard.overview_charts = ["invalid.chart"]

    with patch("transcriptx.cli.config_editors.dashboard.questionary") as mock_q:
        mock_q.select.return_value.ask.return_value = "back"

        edit_dashboard_config(config)

    assert config.dashboard.overview_charts == []
