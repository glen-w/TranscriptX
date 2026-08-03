"""Contract tests for optional-dependency blocked module results."""

from __future__ import annotations

import pytest

from transcriptx.core.pipeline.contracts import ErrorKind
from transcriptx.core.pipeline.optional_dep_outcomes import (
    broken_extra_reason,
    build_optional_dep_blocked_result,
    install_hint_for_extra,
    missing_extra_reason,
)


@pytest.mark.unit
def test_extra_reason_string_formats_are_stable() -> None:
    assert missing_extra_reason("bertopic") == "missing_extra:bertopic"
    assert broken_extra_reason("semantic_v2") == "broken_extra:semantic_v2"


@pytest.mark.unit
def test_install_hint_for_extra_is_editable_checkout_pip() -> None:
    hint = install_hint_for_extra("bertopic")
    assert "pip install -e '.[bertopic]'" in hint
    assert "not on PyPI" in hint


@pytest.mark.unit
def test_build_optional_dep_blocked_result_envelope() -> None:
    hint = install_hint_for_extra("bertopic")
    result = build_optional_dep_blocked_result(
        module_name="bertopic",
        reason=missing_extra_reason("bertopic"),
        install_hint=hint,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    assert result["status"] == "blocked"
    assert result["module_name"] == "bertopic"
    assert result["metrics"]["reason"] == "missing_extra:bertopic"
    assert result["metrics"]["error_kind"] == ErrorKind.DEPENDENCY.value
    assert result["metrics"]["install_hint"] == hint
    assert result["artifacts"] == []
    assert result["payload"] == {}


@pytest.mark.unit
def test_extra_metrics_merge_keeps_reason_kind_and_adds_fields() -> None:
    result = build_optional_dep_blocked_result(
        module_name="topic_modeling",
        reason=broken_extra_reason("bertopic"),
        error_kind=ErrorKind.DEPENDENCY,
        extra_metrics={"detail": "import failed", "retryable": False},
        install_hint=None,
        started_at="t0",
        finished_at="t1",
    )
    assert result["metrics"]["reason"] == "broken_extra:bertopic"
    assert result["metrics"]["error_kind"] == ErrorKind.DEPENDENCY.value
    assert result["metrics"]["detail"] == "import failed"
    assert result["metrics"]["retryable"] is False
    assert "install_hint" not in result["metrics"]
