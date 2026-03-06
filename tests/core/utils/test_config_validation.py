"""Tests for config validation (dict-based registry)."""

from transcriptx.core.config import get_default_config_dict, validate_config


def test_validate_default_dashboard_config_has_no_errors():
    config = get_default_config_dict()
    errors = validate_config(config)
    assert "dashboard.overview_charts" not in errors
    assert "dashboard.overview_missing_behavior" not in errors
    assert "dashboard.overview_max_items" not in errors


def test_validate_dashboard_overview_charts_invalid():
    config = get_default_config_dict()
    config["dashboard"]["overview_charts"] = ["invalid.chart"]
    errors = validate_config(config)
    assert "dashboard.overview_charts" in errors


def test_validate_dashboard_missing_behavior_invalid():
    config = get_default_config_dict()
    config["dashboard"]["overview_missing_behavior"] = "unexpected"
    errors = validate_config(config)
    assert "dashboard.overview_missing_behavior" in errors


def test_validate_dashboard_overview_max_items_invalid():
    config = get_default_config_dict()
    config["dashboard"]["overview_max_items"] = 0
    errors = validate_config(config)
    assert "dashboard.overview_max_items" in errors
