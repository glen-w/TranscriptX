"""
Tests for module result error classification.
"""

import pytest

from transcriptx.core.utils.module_result import (
    build_module_result,
    capture_exception,
    now_iso,
)


@pytest.mark.unit
def test_capture_exception_includes_type_and_message():
    """Captured exceptions should include type and message for classification."""
    try:
        raise ValueError("bad input")
    except Exception as exc:
        payload = capture_exception(exc)

    assert payload["error_type"] == "ValueError"
    assert payload["error_message"] == "bad input"
    assert "error_code" not in payload


@pytest.mark.unit
def test_capture_exception_includes_error_context_for_dependency_errors() -> None:
    from transcriptx.core.analysis.llm_module_errors import ModuleDependencyMissingError

    try:
        raise ModuleDependencyMissingError(
            "summary missing",
            dependency="summary",
            state="missing",
        )
    except Exception as exc:
        payload = capture_exception(exc)

    assert payload["error_code"] == "llm_dependency_missing"
    assert payload["error_context"] == {"dependency": "summary", "state": "missing"}


@pytest.mark.unit
def test_capture_exception_includes_error_code_for_coded_errors():
    from transcriptx.core.llm.errors import LLMUnavailableError

    try:
        raise LLMUnavailableError("daemon down")
    except Exception as exc:
        payload = capture_exception(exc)

    assert payload["error_type"] == "LLMUnavailableError"
    assert payload["error_message"] == "daemon down"
    assert payload["error_code"] == "llm_unavailable"


@pytest.mark.unit
def test_build_module_result_with_error_payload():
    """Module result should include error envelope and module context."""
    err = capture_exception(RuntimeError("module failed"))
    result = build_module_result(
        module_name="sentiment",
        status="error",
        started_at=now_iso(),
        finished_at=now_iso(),
        artifacts=[],
        metrics={"duration_seconds": 1.0},
        payload_type="analysis_results",
        payload={},
        error=err,
    )

    assert result["module_name"] == "sentiment"
    assert result["status"] == "error"
    assert result["error"]["error_message"] == "module failed"


@pytest.mark.unit
def test_capture_exception_json_round_trip_preserves_error_code() -> None:
    import json

    from transcriptx.core.llm.errors import LLMUnavailableError

    err = capture_exception(LLMUnavailableError("daemon down"))
    result = build_module_result(
        module_name="llm_summary",
        status="error",
        started_at=now_iso(),
        finished_at=now_iso(),
        artifacts=[],
        metrics={"duration_seconds": 0.0},
        payload_type="analysis_results",
        payload={},
        error=err,
    )
    reloaded = json.loads(json.dumps(result))
    assert reloaded["error"]["error_code"] == "llm_unavailable"


@pytest.mark.unit
def test_run_results_round_trip_preserves_error_code(tmp_path) -> None:
    import json

    from transcriptx.core.pipeline.manifest_builder import build_run_results_summary
    from transcriptx.core.pipeline.manifest_loader import load_run_results
    from transcriptx.core.utils.module_result import (
        build_module_result,
        capture_exception,
    )

    from transcriptx.core.llm.errors import LLMUnavailableError

    module_result = build_module_result(
        module_name="llm_summary",
        status="error",
        started_at=now_iso(),
        finished_at=now_iso(),
        artifacts=[],
        metrics={"duration_seconds": 1.0},
        payload_type="analysis_results",
        payload={},
        error=capture_exception(LLMUnavailableError("down")),
    )
    payload = build_run_results_summary(
        run_id="run-1",
        transcript_key="mini",
        modules_enabled=["llm_summary"],
        modules_run=[],
        skipped_modules=[],
        errors=["llm_summary: down"],
        module_results={"llm_summary": module_result},
    )
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_run_results(path)
    failed_row = next(
        row for row in loaded["module_outcomes"] if row["module_id"] == "llm_summary"
    )
    assert failed_row["execution_status"] == "failed"
    assert failed_row["error_code"] == "llm_unavailable"
