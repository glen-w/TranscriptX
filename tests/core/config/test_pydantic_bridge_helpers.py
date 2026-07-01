"""Behavioral tests for pydantic_bridge_helpers (dotpath routing, override extraction)."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.config.models.analysis_entity import AnalysisEntitySettingsModel
from transcriptx.core.config.models.analysis_ner import AnalysisNerSettingsModel
from transcriptx.core.config.models.analysis_sentiment import (
    AnalysisSentimentSettingsModel,
)
from transcriptx.core.config.models.dashboard_display import (
    DashboardDisplaySettingsModel,
)
from transcriptx.core.config.models.dashboard_overview import (
    DashboardOverviewSettingsModel,
)
from transcriptx.core.config.models.workflow import WorkflowSettingsModel
from transcriptx.core.config.pydantic_bridge import find_pilot_for_dotpath_key
from transcriptx.core.config.pydantic_bridge_helpers import (
    dotpath_belongs_to_model,
    extract_subtree_overrides,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_dotpath_belongs_leaf_field() -> None:
    assert dotpath_belongs_to_model(
        "workflow.timeout_quick_seconds",
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )


def test_dotpath_belongs_nested_leaf() -> None:
    assert dotpath_belongs_to_model(
        "workflow.speaker_gate.threshold_value",
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )


def test_dotpath_rejects_prefix_only() -> None:
    assert not dotpath_belongs_to_model(
        "workflow.",
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )


def test_dotpath_rejects_mid_tree_non_leaf() -> None:
    assert not dotpath_belongs_to_model(
        "workflow.speaker_gate",
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )


def test_dotpath_rejects_sibling_path() -> None:
    assert not dotpath_belongs_to_model(
        "workflow.not_a_field",
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )


def test_extract_subtree_overrides_rebuilds_nested_dict() -> None:
    flattened = {
        "workflow.speaker_gate.threshold_value": 5.0,
        "workflow.speaker_gate.mode": "enforce",
        "workflow.timeout_quick_seconds": 7200,
        "output.format": "json",
    }
    overrides = extract_subtree_overrides(
        flattened,
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )
    assert overrides == {
        "speaker_gate": {"threshold_value": 5.0, "mode": "enforce"},
        "timeout_quick_seconds": 7200,
    }


def test_extract_subtree_overrides_filters_non_model_keys() -> None:
    flattened = {
        "workflow.speaker_gate.threshold_value": 1.0,
        "workflow.speaker_gate.bogus": "x",
    }
    overrides = extract_subtree_overrides(
        flattened,
        dotpath_prefix="workflow",
        model=WorkflowSettingsModel,
    )
    assert overrides == {"speaker_gate": {"threshold_value": 1.0}}


def test_dashboard_display_key_belongs_to_display_not_overview() -> None:
    key = "dashboard.duration_summary_style"
    assert dotpath_belongs_to_model(
        key,
        dotpath_prefix="dashboard",
        model=DashboardDisplaySettingsModel,
    )
    assert not dotpath_belongs_to_model(
        key,
        dotpath_prefix="dashboard",
        model=DashboardOverviewSettingsModel,
    )


def test_dashboard_overview_key_belongs_to_overview_not_display() -> None:
    key = "dashboard.overview_max_items"
    assert dotpath_belongs_to_model(
        key,
        dotpath_prefix="dashboard",
        model=DashboardOverviewSettingsModel,
    )
    assert not dotpath_belongs_to_model(
        key,
        dotpath_prefix="dashboard",
        model=DashboardDisplaySettingsModel,
    )


def test_analysis_partial_keys_route_to_correct_pilot() -> None:
    sentiment_key = "analysis.sentiment_window_size"
    ner_key = "analysis.ner_labels"
    entity_key = "analysis.entity_min_mentions"

    assert dotpath_belongs_to_model(
        sentiment_key,
        dotpath_prefix="analysis",
        model=AnalysisSentimentSettingsModel,
    )
    assert not dotpath_belongs_to_model(
        sentiment_key,
        dotpath_prefix="analysis",
        model=AnalysisNerSettingsModel,
    )

    assert dotpath_belongs_to_model(
        ner_key,
        dotpath_prefix="analysis",
        model=AnalysisNerSettingsModel,
    )
    assert not dotpath_belongs_to_model(
        ner_key,
        dotpath_prefix="analysis",
        model=AnalysisSentimentSettingsModel,
    )

    assert dotpath_belongs_to_model(
        entity_key,
        dotpath_prefix="analysis",
        model=AnalysisEntitySettingsModel,
    )
    assert not dotpath_belongs_to_model(
        entity_key,
        dotpath_prefix="analysis",
        model=AnalysisNerSettingsModel,
    )


def test_find_pilot_for_shared_prefix_keys() -> None:
    display_spec = find_pilot_for_dotpath_key("dashboard.duration_summary_style")
    overview_spec = find_pilot_for_dotpath_key("dashboard.overview_max_items")
    assert display_spec is not None
    assert overview_spec is not None
    assert display_spec.pilot_id == "dashboard_display"
    assert overview_spec.pilot_id == "dashboard_overview"


def test_partial_pilot_golden_keys_have_consistent_find_pilot() -> None:
    for pilot_id, sample_key in (
        ("analysis_sentiment", "analysis.sentiment_window_size"),
        ("analysis_ner", "analysis.ner_labels"),
        ("analysis_entity", "analysis.entity_min_mentions"),
    ):
        golden = json.loads((FIXTURES / f"{pilot_id}_registry_golden.json").read_text())
        for key in golden:
            spec = find_pilot_for_dotpath_key(key)
            assert spec is not None, key
            assert spec.pilot_id == pilot_id, f"{key} -> {spec.pilot_id}"
