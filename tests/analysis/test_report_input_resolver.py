"""Tests for report input resolver (run-aware report input resolution)."""

from __future__ import annotations

import json
from pathlib import Path


from transcriptx.core.analysis.stats.report_input_resolver import (
    CANONICAL_REPORT_INPUT_SPECS,
    MODULE_STATUS_FAILED,
    MODULE_STATUS_BLOCKED,
    MODULE_STATUS_SUCCEEDED,
    MODULE_STATUS_SKIPPED,
    REPORT_CONTRIBUTION_FULL_SECTION,
    REPORT_CONTRIBUTION_MENTION_ONLY,
    REPORT_CONTRIBUTION_OMITTED,
    resolve_report_inputs,
    _load_run_results,
    _module_status_from_run_results,
    _passes_minimum_viable_contract,
)


def test_module_status_from_run_results() -> None:
    run_results = {
        "modules_run": ["sentiment", "acts"],
        "modules_skipped": [{"module": "contagion", "reason": "missing emotion"}],
        "modules_failed": ["topic_modeling"],
        "modules_enabled": ["sentiment", "acts", "contagion", "topic_modeling"],
    }
    assert (
        _module_status_from_run_results("sentiment", run_results)
        == MODULE_STATUS_SUCCEEDED
    )
    assert (
        _module_status_from_run_results("acts", run_results) == MODULE_STATUS_SUCCEEDED
    )
    assert (
        _module_status_from_run_results("contagion", run_results)
        == MODULE_STATUS_SKIPPED
    )
    assert (
        _module_status_from_run_results("topic_modeling", run_results)
        == MODULE_STATUS_FAILED
    )
    assert (
        _module_status_from_run_results("unknown", run_results) == MODULE_STATUS_SKIPPED
    )


def test_passes_minimum_viable_contract_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    passed, data, err = _passes_minimum_viable_contract(path, ("mean_compound",))
    assert passed is False
    assert data is None
    assert "missing" in (err or "")


def test_passes_minimum_viable_contract_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text("")
    passed, data, err = _passes_minimum_viable_contract(path, ("mean_compound",))
    assert passed is False
    assert "empty" in (err or "")


def test_passes_minimum_viable_contract_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json")
    passed, data, err = _passes_minimum_viable_contract(path, ("mean_compound",))
    assert passed is False
    assert "JSON" in (err or "")


def test_passes_minimum_viable_contract_missing_key(tmp_path: Path) -> None:
    path = tmp_path / "no_key.json"
    path.write_text(json.dumps({"other": 1}))
    passed, data, err = _passes_minimum_viable_contract(path, ("mean_compound",))
    assert passed is False
    assert data is not None
    assert "mean_compound" in (err or "")


def test_passes_minimum_viable_contract_null_key(tmp_path: Path) -> None:
    path = tmp_path / "null_key.json"
    path.write_text(json.dumps({"mean_compound": None}))
    passed, data, err = _passes_minimum_viable_contract(path, ("mean_compound",))
    assert passed is False
    assert "null" in (err or "").lower()


def test_passes_minimum_viable_contract_ok(tmp_path: Path) -> None:
    path = tmp_path / "ok.json"
    path.write_text(json.dumps({"mean_compound": 0.5}))
    passed, data, err = _passes_minimum_viable_contract(path, ("mean_compound",))
    assert passed is True
    assert data == {"mean_compound": 0.5}
    assert err is None


def test_resolve_report_inputs_no_run_results(tmp_path: Path) -> None:
    results, warnings = resolve_report_inputs(tmp_path, "base")
    assert isinstance(results, dict)
    assert isinstance(warnings, list)
    # No run_results.json -> no modules from run; only specs we know
    assert len(results) >= len(CANONICAL_REPORT_INPUT_SPECS)


def test_resolve_report_inputs_with_run_results_and_valid_file(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment"],
                "modules_run": ["sentiment"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    sentiment_dir = tmp_path / "sentiment" / "data" / "global"
    sentiment_dir.mkdir(parents=True)
    (sentiment_dir / "base_sentiment_summary.json").write_text(
        json.dumps({"mean_compound": 0.2})
    )
    results, warnings = resolve_report_inputs(tmp_path, "base")
    sent = results.get("sentiment")
    assert sent is not None
    assert sent.module_status == MODULE_STATUS_SUCCEEDED
    assert sent.report_contribution_status == REPORT_CONTRIBUTION_FULL_SECTION
    assert sent.parsed_data == {"mean_compound": 0.2}
    assert sent.best_input_path is not None


def test_resolve_report_inputs_zero_byte_file_does_not_trigger_full_section(
    tmp_path: Path,
) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["tics"],
                "modules_run": ["tics"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    tics_dir = tmp_path / "tics" / "data" / "global"
    tics_dir.mkdir(parents=True)
    (tics_dir / "base_tics_summary.json").write_text("")  # zero-byte
    results, warnings = resolve_report_inputs(tmp_path, "base")
    tics = results.get("tics")
    assert tics is not None
    assert tics.module_status == MODULE_STATUS_SUCCEEDED
    assert tics.report_contribution_status != REPORT_CONTRIBUTION_FULL_SECTION
    assert tics.report_contribution_status == REPORT_CONTRIBUTION_MENTION_ONLY
    assert any("tics" in w for w in warnings)


def test_load_run_results_missing(tmp_path: Path) -> None:
    out = _load_run_results(tmp_path)
    assert out is None


def test_load_run_results_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text("not json")
    out = _load_run_results(tmp_path)
    assert out is None


def test_load_run_results_valid(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_run": ["sentiment"],
                "modules_enabled": ["sentiment"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    out = _load_run_results(tmp_path)
    assert out is not None
    assert out.get("modules_run") == ["sentiment"]


def test_passes_minimum_viable_contract_empty_list_key_fails(tmp_path: Path) -> None:
    path = tmp_path / "empty_list.json"
    path.write_text(json.dumps({"entities": []}))
    passed, data, err = _passes_minimum_viable_contract(path, ("entities",))
    assert passed is False
    assert "empty" in (err or "").lower()


def test_resolve_report_inputs_skipped_module_omitted(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["contagion"],
                "modules_run": [],
                "modules_skipped": [
                    {"module": "contagion", "reason": "missing emotion"}
                ],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    results, warnings = resolve_report_inputs(tmp_path, "base")
    cont = results.get("contagion")
    assert cont is not None
    assert cont.module_status == MODULE_STATUS_SKIPPED
    assert cont.report_contribution_status == REPORT_CONTRIBUTION_OMITTED
    assert cont.reason == "module skipped"


def test_resolve_report_inputs_blocked_module_omitted(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["contagion"],
                "modules_run": [],
                "modules_skipped": [
                    {
                        "module": "contagion",
                        "reason": "missing emotion",
                        "execution_status": "blocked",
                    }
                ],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    results, _ = resolve_report_inputs(tmp_path, "base")
    cont = results.get("contagion")
    assert cont is not None
    assert cont.module_status == MODULE_STATUS_BLOCKED
    assert cont.report_contribution_status == REPORT_CONTRIBUTION_OMITTED
    assert cont.reason == "module blocked"


def test_resolve_report_inputs_failed_module_omitted(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["topic_modeling"],
                "modules_run": [],
                "modules_skipped": [],
                "modules_failed": ["topic_modeling"],
                "errors": [],
            }
        )
    )
    results, warnings = resolve_report_inputs(tmp_path, "base")
    topic = results.get("topic_modeling")
    if topic is not None:
        assert topic.module_status == MODULE_STATUS_FAILED
        assert topic.report_contribution_status == REPORT_CONTRIBUTION_OMITTED


def test_resolve_report_inputs_preferred_path_over_fallback(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["acts"],
                "modules_run": ["acts"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    acts_global = tmp_path / "acts" / "data" / "global"
    acts_global.mkdir(parents=True)
    (acts_global / "base_acts_summary.json").write_text(
        json.dumps({"act_counts": {"question": 5}})
    )
    results, _ = resolve_report_inputs(tmp_path, "base")
    acts = results.get("acts")
    assert acts is not None
    assert acts.report_contribution_status == REPORT_CONTRIBUTION_FULL_SECTION
    assert acts.best_input_path == "acts/data/global/base_acts_summary.json"


def test_resolve_report_inputs_multiple_modules_mixed_status(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment", "acts", "contagion"],
                "modules_run": ["sentiment", "acts"],
                "modules_skipped": [
                    {"module": "contagion", "reason": "missing emotion"}
                ],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    (tmp_path / "sentiment" / "data" / "global").mkdir(parents=True)
    (
        tmp_path / "sentiment" / "data" / "global" / "base_sentiment_summary.json"
    ).write_text(json.dumps({"mean_compound": 0.1}))
    (tmp_path / "acts" / "data" / "global").mkdir(parents=True)
    (tmp_path / "acts" / "data" / "global" / "base_acts_summary.json").write_text(
        json.dumps({"act_counts": {"statement": 10}})
    )
    results, warnings = resolve_report_inputs(tmp_path, "base")
    assert (
        results["sentiment"].report_contribution_status
        == REPORT_CONTRIBUTION_FULL_SECTION
    )
    assert (
        results["acts"].report_contribution_status == REPORT_CONTRIBUTION_FULL_SECTION
    )
    assert (
        results["contagion"].report_contribution_status == REPORT_CONTRIBUTION_OMITTED
    )
    assert results["contagion"].module_status == MODULE_STATUS_SKIPPED


def test_canonical_specs_cover_expected_modules() -> None:
    expected = {
        "sentiment",
        "emotion",
        "acts",
        "interactions",
        "ner",
        "entity_sentiment",
        "conversation_loops",
        "contagion",
        "wordclouds",
        "tics",
        "understandability",
        "temporal_dynamics",
        "pauses",
        "momentum",
        "highlights",
        "summary",
        "affect_tension",
    }
    spec_ids = {s.module_id for s in CANONICAL_REPORT_INPUT_SPECS}
    for mod in expected:
        assert mod in spec_ids, f"Expected canonical spec for {mod}"
    assert all(s.preferred_paths for s in CANONICAL_REPORT_INPUT_SPECS)
    assert all(s.required_keys for s in CANONICAL_REPORT_INPUT_SPECS)
