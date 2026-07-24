"""Tests for strict dashboard config loading."""

import json

import pytest

from transcriptx.core.utils.config import load_config
from transcriptx.core.utils.config.config_errors import ConfigLoadError


def test_load_config_rejects_legacy_overview_chart_types(tmp_path):
    config_path = tmp_path / "config.json"
    payload = {
        "dashboard": {"overview_chart_types": ["multispeaker_sentiment"]},
    }
    config_path.write_text(json.dumps(payload))

    with pytest.raises(ConfigLoadError) as exc_info:
        load_config(str(config_path))
    assert "overview_chart_types" in str(exc_info.value)
    assert "overview_charts" in str(exc_info.value)
    assert exc_info.value.code == "unsupported_legacy_shape"


def test_load_config_accepts_dashboard_v1(tmp_path):
    config_path = tmp_path / "config.json"
    payload = {
        "dashboard": {
            "schema_version": 1,
            "overview_charts": ["sentiment.multi_speaker_sentiment.global"],
            "overview_missing_behavior": "skip",
        },
    }
    config_path.write_text(json.dumps(payload))

    config = load_config(str(config_path))

    assert (
        "sentiment.multi_speaker_sentiment.global" in config.dashboard.overview_charts
    )
    assert config.dashboard.schema_version == 1
