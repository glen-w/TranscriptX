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
