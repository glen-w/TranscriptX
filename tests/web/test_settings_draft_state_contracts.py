"""Tests for settings draft state contracts."""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.web.ui.settings.configuration_panel import (
    _DRAFT_STATE_KEY,
    _RUN_CACHE_KEY,
    _SCOPE_CACHE_KEY,
    _effective_rows,
    _humanize_category,
    _sanitize_scope_config,
    _strip_activation_keys,
    _scope_labels,
    _scope_name_from_index,
    _should_reset_draft_state,
)


def test_should_reset_when_draft_state_missing() -> None:
    assert _should_reset_draft_state({}, scope="Project", current_run_cache="r1")


def test_should_reset_when_scope_changes() -> None:
    state = {
        _DRAFT_STATE_KEY: {"analysis": {}},
        _SCOPE_CACHE_KEY: "Project",
        _RUN_CACHE_KEY: "r1",
    }
    assert _should_reset_draft_state(
        state, scope="Run override", current_run_cache="r1"
    )


def test_should_reset_when_run_changes() -> None:
    state = {
        _DRAFT_STATE_KEY: {"analysis": {}},
        _SCOPE_CACHE_KEY: "Run override",
        _RUN_CACHE_KEY: "r1",
    }
    assert _should_reset_draft_state(
        state, scope="Run override", current_run_cache="r2"
    )


def test_should_not_reset_when_scope_and_run_match() -> None:
    state = {
        _DRAFT_STATE_KEY: {"analysis": {}},
        _SCOPE_CACHE_KEY: "Run override",
        _RUN_CACHE_KEY: "r1",
    }
    assert not _should_reset_draft_state(
        state, scope="Run override", current_run_cache="r1"
    )


def test_should_not_reset_when_activation_and_advanced_flags_change() -> None:
    state = {
        _DRAFT_STATE_KEY: {
            "analysis": {"active_acts_profile": "team"},
            "output": {"dynamic_views": "auto"},
        },
        _SCOPE_CACHE_KEY: "Run override",
        _RUN_CACHE_KEY: "run-42",
        # UI-only flags that should not force draft reset:
        "settings_config_show_advanced_editor": True,
        "run_override_active_profile_acts": "team",
    }
    assert not _should_reset_draft_state(
        state, scope="Run override", current_run_cache="run-42"
    )


def test_scope_labels_include_run_hint_when_run_not_selected() -> None:
    labels = _scope_labels(run_dir=None)
    assert labels[3] == "Run override — select a run in the sidebar"


def test_scope_labels_keep_run_override_when_run_selected(tmp_path) -> None:
    labels = _scope_labels(run_dir=tmp_path)
    assert labels[3] == "Run override"


def test_scope_name_mapping_contract() -> None:
    assert _scope_name_from_index(0) == "Default"
    assert _scope_name_from_index(1) == "Project"
    assert _scope_name_from_index(2) == "Draft override"
    assert _scope_name_from_index(3) == "Run override"


def test_strip_activation_keys_removes_adapter_owned_keys_only() -> None:
    config_map = {
        "analysis.active_acts_profile": "team",
        "active_workflow_profile": "nightly",
        "analysis.semantic_model_name": "x",
    }
    stripped = _strip_activation_keys(config_map)
    assert "analysis.active_acts_profile" not in stripped
    assert "active_workflow_profile" not in stripped
    assert stripped["analysis.semantic_model_name"] == "x"


def test_sanitize_scope_config_removes_nested_activation_keys_in_draft_scope() -> None:
    nested = {
        "analysis": {
            "active_acts_profile": "team",
            "semantic_model_name": "x",
        },
        "active_workflow_profile": "nightly",
    }
    sanitized = _sanitize_scope_config("Draft override", nested)
    assert "active_acts_profile" not in sanitized["analysis"]
    assert "active_workflow_profile" not in sanitized
    assert sanitized["analysis"]["semantic_model_name"] == "x"


def test_sanitize_scope_config_keeps_activation_keys_outside_draft_scope() -> None:
    nested = {
        "analysis": {"active_acts_profile": "team"},
        "active_workflow_profile": "nightly",
    }
    unchanged = _sanitize_scope_config("Project", nested)
    assert unchanged == nested


def test_effective_rows_are_compact_strings_with_source() -> None:
    """Readout is one table per category: strings verbatim, others JSON, long values clipped."""
    keys = ["llm.model", "llm.enabled", "llm.timeout", "llm.extra", "llm.long"]
    effective = {
        "llm.model": "/mnt/outputs",
        "llm.enabled": True,
        "llm.timeout": None,
        "llm.extra": {"a": 1},
        "llm.long": "x" * 500,
    }
    sources = {"llm.model": "project"}
    rows = _effective_rows(keys, effective, sources, prefix="llm.")
    assert [r["Setting"] for r in rows] == [
        "model",
        "enabled",
        "timeout",
        "extra",
        "long",
    ]
    assert rows[0] == {"Setting": "model", "Value": "/mnt/outputs", "Source": "project"}
    assert rows[1]["Value"] == "true" and rows[1]["Source"] == "default"
    assert rows[2]["Value"] == "null"
    assert rows[3]["Value"] == '{"a": 1}'
    assert len(rows[4]["Value"]) <= 200 and rows[4]["Value"].endswith("…")


def test_humanize_category_titles() -> None:
    assert _humanize_category("llm") == "LLM"
    assert _humanize_category("audio_preprocessing") == "Audio preprocessing"
    assert _humanize_category("group_analysis") == "Group analysis"
    assert _humanize_category("output") == "Output"
