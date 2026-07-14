"""Tests for settings draft state contracts."""

from __future__ import annotations

from transcriptx.web.ui.settings.configuration_panel import (
    _DRAFT_STATE_KEY,
    _RUN_CACHE_KEY,
    _SCOPE_CACHE_KEY,
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
