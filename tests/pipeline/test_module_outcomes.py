"""Module outcome projections and group aggregation."""

from __future__ import annotations

import pytest

from transcriptx.core.pipeline.module_outcomes import (
    RUN_RESULTS_SCHEMA_VERSION,
    aggregate_group_module_lists,
    assert_run_results_schema_supported,
    build_canonical_rows_from_run_lists,
    project_failed_modules,
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
