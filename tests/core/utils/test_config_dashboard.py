"""Tests for dashboard config loading and migration."""

import json

from transcriptx.core.utils.chart_registry import get_default_overview_charts
from transcriptx.core.utils.config import load_config
from transcriptx.core.utils.config.workflow import migrate_dashboard_config


def test_migrate_dashboard_config_legacy_mapping():
    legacy = {
        "overview_chart_types": [
            "multispeaker_sentiment",
            "wordcloud_all",
        ]
    }
    migrated, changed = migrate_dashboard_config(legacy)
    assert changed is True
    assert migrated["schema_version"] == 2
    assert "overview_chart_types" not in migrated
    assert "sentiment.multi_speaker_sentiment.global" in migrated["overview_charts"]
    assert "wordcloud.wordcloud.global.basic" in migrated["overview_charts"]


def test_migrate_dashboard_config_falls_back_to_defaults():
    legacy = {"overview_chart_types": ["unknown_type"]}
    migrated, changed = migrate_dashboard_config(legacy)
    assert changed is True
    assert migrated["overview_charts"] == get_default_overview_charts()


def test_load_config_migrates_dashboard(tmp_path):
    config_path = tmp_path / "config.json"
    payload = {
        "dashboard": {"overview_chart_types": ["multispeaker_sentiment"]},
    }
    config_path.write_text(json.dumps(payload))

    config = load_config(str(config_path))

    assert (
        "sentiment.multi_speaker_sentiment.global" in config.dashboard.overview_charts
    )
    assert config.dashboard.schema_version == 2
