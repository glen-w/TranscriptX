"""Tests for llm_action_items user-facing failure / truncation guidance."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_support.action_items_contract import (
    parse_action_items_json,
)
from transcriptx.core.analysis.llm_support.action_items_guidance import (
    ACTION_ITEMS_RETRY_GUIDANCE,
    empty_extracts_user_warning,
    format_invalid_json_error,
    format_module_failure_for_user,
    format_oversized_output_error,
    is_likely_truncated_json_failure,
    truncated_output_user_warning,
)
from transcriptx.core.llm.errors import LLMResponseError


@pytest.mark.unit
def test_invalid_json_error_includes_retry_guidance() -> None:
    msg = format_invalid_json_error(
        json.JSONDecodeError(
            "Unterminated string starting at: line 760 column 13 (char 26531)",
            "x",
            0,
        )
    )
    assert "likely truncated" in msg.lower()
    assert ACTION_ITEMS_RETRY_GUIDANCE in msg
    assert "same settings will usually fail" in msg.lower()


@pytest.mark.unit
def test_oversized_output_error_includes_retry_guidance() -> None:
    msg = format_oversized_output_error(length=90_000, char_limit=32_768)
    assert "exceeds expected length" in msg
    assert ACTION_ITEMS_RETRY_GUIDANCE in msg


@pytest.mark.unit
def test_parse_unsalvageable_json_raises_guided_error() -> None:
    truncated = '{"items":[{"record_type":"action_item","text":"Only a fragment'
    with pytest.raises(
        LLMResponseError, match="same settings will usually fail"
    ) as exc:
        parse_action_items_json(truncated)
    assert "not valid JSON" in str(exc.value)


@pytest.mark.unit
def test_format_module_failure_for_user_action_items() -> None:
    msg = format_module_failure_for_user(
        module_id="llm_action_items",
        error_message="Unterminated string starting at: line 760",
        error_code="llm_invalid_response",
    )
    assert "`llm_action_items` failed" in msg
    assert "truncated/invalid JSON" in msg
    assert ACTION_ITEMS_RETRY_GUIDANCE in msg


@pytest.mark.unit
def test_format_module_failure_avoids_duplicate_guidance() -> None:
    already = (
        "Action items output is not valid JSON: boom. " + ACTION_ITEMS_RETRY_GUIDANCE
    )
    msg = format_module_failure_for_user(
        module_id="llm_action_items",
        error_message=already,
        error_code="llm_invalid_response",
    )
    assert msg.count("same settings will usually fail") == 1


@pytest.mark.unit
def test_truncated_output_user_warning() -> None:
    assert truncated_output_user_warning({"output_truncated": 0}) is None
    warn = truncated_output_user_warning({"output_truncated": 1})
    assert warn is not None
    assert "incomplete" in warn.lower()
    assert ACTION_ITEMS_RETRY_GUIDANCE in warn
    assert "llama3.2:3b" in warn


@pytest.mark.unit
def test_empty_extracts_user_warning_explains_invalid_drops() -> None:
    assert empty_extracts_user_warning(None) is None
    assert empty_extracts_user_warning({"items_raw": 0, "items_committed": 0}) is None
    assert (
        empty_extracts_user_warning(
            {"items_raw": 2, "items_committed": 2, "items_invalid_dropped": 0}
        )
        is None
    )
    warn = empty_extracts_user_warning(
        {
            "items_raw": 1,
            "items_parsed_valid": 0,
            "items_invalid_dropped": 1,
            "items_committed": 0,
        }
    )
    assert warn is not None
    assert "1 raw record" in warn
    assert "schema validation" in warn.lower()
    assert "same settings will usually fail" in warn.lower()
    assert "JSON-capable model" in warn
    # Schema-only drops should not push the truncation/effort remediation.
    assert "effort to max" not in warn
    assert "llama3.2:3b" not in warn


@pytest.mark.unit
def test_empty_extracts_user_warning_covers_other_drop_buckets() -> None:
    warn = empty_extracts_user_warning(
        {
            "items_raw": 3,
            "items_committed": 0,
            "items_invalid_dropped": 1,
            "status_unsupported_dropped": 1,
            "items_ungrounded_dropped": 1,
        }
    )
    assert warn is not None
    assert "schema validation" in warn.lower()
    assert "unsupported status" in warn.lower()
    assert "grounded" in warn.lower()


@pytest.mark.unit
def test_is_likely_truncated_json_failure() -> None:
    assert is_likely_truncated_json_failure(
        "Unterminated string starting at: line 760 column 13"
    )
    assert is_likely_truncated_json_failure("Action items output is not valid JSON")
    assert not is_likely_truncated_json_failure("LLM service is unreachable")
