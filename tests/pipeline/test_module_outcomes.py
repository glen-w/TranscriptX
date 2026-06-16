"""Module outcome projections and group aggregation."""

from __future__ import annotations

import pytest

from transcriptx.core.pipeline.module_outcomes import (
    RUN_RESULTS_SCHEMA_VERSION,
    aggregate_group_module_lists,
    assert_run_results_schema_supported,
    build_canonical_rows_from_run_lists,
    normalize_raw_outcomes,
    normalize_skipped_entries,
    project_failed_modules,
    RawModuleOutcome,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


@pytest.mark.unit
def test_project_failed_modules_respects_skipped_and_blocked() -> None:
    skipped = [
        {"module": "acts", "reason": "gate", "execution_status": "skipped"},
        {"module": "ner", "reason": "deps", "execution_status": "blocked"},
    ]
    failed = project_failed_modules(
        ["stats", "acts", "ner", "emotion"],
        modules_run=["stats"],
        skipped_modules=skipped,
    )
    assert "emotion" in failed
    assert "acts" not in failed
    assert "ner" not in failed
    assert "stats" not in failed


@pytest.mark.unit
def test_project_failed_modules_case_insensitive_ids() -> None:
    failed = project_failed_modules(
        ["Stats", "acts"],
        modules_run=["stats"],
        skipped_modules=[],
    )
    assert failed == ["acts"]


@pytest.mark.unit
def test_aggregate_group_module_lists_union() -> None:
    r0 = PerTranscriptResult(
        transcript_path="/a.json",
        transcript_key="k0",
        run_id="r0",
        order_index=0,
        output_dir="/o0",
        module_results={},
        modules_run=["stats"],
        skipped_modules=[{"module": "emotion", "reason": "x"}],
    )
    r1 = PerTranscriptResult(
        transcript_path="/b.json",
        transcript_key="k1",
        run_id="r1",
        order_index=1,
        output_dir="/o1",
        module_results={},
        modules_run=["sentiment"],
        skipped_modules=[],
    )
    run, sk = aggregate_group_module_lists(["stats", "sentiment", "emotion"], [r0, r1])
    assert set(run) == {"stats", "sentiment"}
    assert any(s["module"] == "emotion" for s in sk)


@pytest.mark.unit
def test_aggregate_group_module_lists_skip_precedence_blocked_over_skipped() -> None:
    r0 = PerTranscriptResult(
        transcript_path="/a.json",
        transcript_key="k0",
        run_id="r0",
        order_index=0,
        output_dir="/o0",
        module_results={},
        modules_run=[],
        skipped_modules=[
            {"module": "emotion", "reason": "preset", "execution_status": "skipped"}
        ],
    )
    r1 = PerTranscriptResult(
        transcript_path="/b.json",
        transcript_key="k1",
        run_id="r1",
        order_index=1,
        output_dir="/o1",
        module_results={},
        modules_run=[],
        skipped_modules=[
            {"module": "emotion", "reason": "deps", "execution_status": "blocked"}
        ],
    )
    _run, sk = aggregate_group_module_lists(["emotion"], [r0, r1])
    assert len(sk) == 1
    assert sk[0]["module"] == "emotion"
    assert sk[0]["execution_status"] == "blocked"


@pytest.mark.unit
def test_assert_run_results_schema_supported_requires_exact_v2() -> None:
    with pytest.raises(ValueError, match="Unsupported run_results"):
        assert_run_results_schema_supported({"schema_version": 1})
    with pytest.raises(ValueError, match="Unsupported run_results"):
        assert_run_results_schema_supported({"schema_version": 3})


@pytest.mark.unit
def test_build_canonical_rows_blocked_vs_failed() -> None:
    rows = build_canonical_rows_from_run_lists(
        modules_enabled=["m1", "m2"],
        modules_run=["m1"],
        skipped_modules=[
            {"module": "m2", "reason": "blocked:deps", "execution_status": "blocked"}
        ],
        errors=[],
    )
    by_id = {r.module_id: r for r in rows}
    assert by_id["m1"].execution_status == "run"
    assert by_id["m2"].execution_status == "blocked"


@pytest.mark.unit
def test_schema_version_constant() -> None:
    assert RUN_RESULTS_SCHEMA_VERSION == 2


@pytest.mark.unit
def test_normalize_raw_outcomes_maps_key_execution_states() -> None:
    rows = normalize_raw_outcomes(
        [
            RawModuleOutcome(
                "stats", decision="selected", used_cache=True, timing_ms=3.0
            ),
            RawModuleOutcome(
                "emotion",
                decision="blocked",
                started=False,
                block_reason="deps_missing",
            ),
            RawModuleOutcome("ner", decision="skipped", skip_reason="speaker_gate"),
            RawModuleOutcome(
                "acts",
                decision="selected",
                started=True,
                finished=True,
                failure={"message": "boom"},
                timing_ms=7.0,
            ),
            RawModuleOutcome(
                "highlights",
                decision="selected",
                started=True,
                finished=True,
                timing_ms=5.0,
            ),
            RawModuleOutcome("moments", decision="selected", started=False),
        ]
    )
    by_id = {row.module_id: row for row in rows}
    assert by_id["stats"].execution_status == "run"
    assert by_id["stats"].reason_code == "cache_hit"
    assert by_id["stats"].used_cache is True
    assert by_id["emotion"].execution_status == "blocked"
    assert by_id["emotion"].reason_code == "deps_missing"
    assert by_id["ner"].execution_status == "skipped"
    assert by_id["ner"].reason_code == "speaker_gate"
    assert by_id["acts"].execution_status == "failed"
    assert by_id["acts"].error_message == "boom"
    assert by_id["highlights"].execution_status == "run"
    assert by_id["moments"].execution_status == "not_requested"
    assert by_id["moments"].reason_code == "not_started"


@pytest.mark.unit
def test_normalize_raw_outcomes_unknown_shape_falls_back_to_not_requested() -> None:
    rows = normalize_raw_outcomes(
        [RawModuleOutcome("stats", decision="selected", started=True, finished=False)]
    )
    assert len(rows) == 1
    assert rows[0].module_id == "stats"
    assert rows[0].execution_status == "not_requested"
    assert rows[0].reason_code == "unknown_raw_shape"


@pytest.mark.unit
def test_normalize_skipped_entries_string_and_invalid_status_paths() -> None:
    normalized = normalize_skipped_entries(
        [
            {"module": "ner", "reason": "deps", "execution_status": "blocked"},
            {"module": "acts", "reason": "legacy", "execution_status": "unexpected"},
            "stats",
            {"not_module": "ignored"},
        ]
    )
    assert normalized == [
        {"module": "ner", "reason": "deps", "execution_status": "blocked"},
        {"module": "acts", "reason": "legacy", "execution_status": "skipped"},
        {"module": "stats", "reason": "Not in registry", "execution_status": "skipped"},
    ]
