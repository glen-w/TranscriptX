"""Curated Guided configuration allowlist (not COMMON_SETTINGS_SCHEMA)."""

from __future__ import annotations

from transcriptx.core.config.gui_support import CommonSettingField

# Approachable output/workflow knobs only — no model names or specialist similarity.
GUIDED_SETTINGS_SCHEMA: tuple[CommonSettingField, ...] = (
    CommonSettingField(
        key="output.dynamic_charts",
        group="Output",
        label="Dynamic chart generation mode",
    ),
    CommonSettingField(
        key="output.dynamic_views",
        group="Output",
        label="Dynamic view generation mode",
    ),
    CommonSettingField(
        key="workflow.default_config_save_path",
        group="Workflow",
        label="Default config save path",
    ),
)
