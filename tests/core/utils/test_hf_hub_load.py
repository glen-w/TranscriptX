"""Bounded Hub load: timeout, retry, skip-without-hang."""

from __future__ import annotations

import time

import pytest

from transcriptx.core.utils.hf_hub_load import (
    HubLoadTimeoutError,
    is_retryable_hub_error,
    load_from_hub_with_retries,
)


def test_is_retryable_hub_error_matches_urllib3_read_timeout() -> None:
    exc = Exception(
        "HTTPSConnectionPool(host='huggingface.co', port=443): Read timed out."
    )
    assert is_retryable_hub_error(exc) is True


def test_is_retryable_hub_error_rejects_validation_errors() -> None:
    assert is_retryable_hub_error(RuntimeError("label index mismatch")) is False


def test_is_retryable_hub_error_rejects_wall_clock_timeout() -> None:
    assert is_retryable_hub_error(HubLoadTimeoutError("timed out after 25s")) is False


def test_load_from_hub_retries_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.hf_hub_load.HUB_RETRY_BACKOFF_SECONDS", 0
    )
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError(
                "HTTPSConnectionPool(host='huggingface.co', port=443): Read timed out."
            )
        return "ok"

    assert load_from_hub_with_retries(flaky, log_prefix="TEST") == "ok"
    assert calls["n"] == 2


def test_load_from_hub_raises_after_retry_exhausted(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.hf_hub_load.HUB_RETRY_BACKOFF_SECONDS", 0
    )
    monkeypatch.setattr("transcriptx.core.utils.hf_hub_load.HUB_LOAD_ATTEMPTS", 2)

    def always_timeout() -> str:
        raise ConnectionError("HTTPSConnectionPool Read timed out")

    with pytest.raises(ConnectionError, match="timed out"):
        load_from_hub_with_retries(always_timeout, log_prefix="TEST")


def test_load_from_hub_does_not_retry_wall_clock_timeout(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.hf_hub_load.HUB_ATTEMPT_TIMEOUT_SECONDS", 0.2
    )
    calls = {"n": 0}

    def hang() -> str:
        calls["n"] += 1
        time.sleep(2.0)
        return "late"

    with pytest.raises(HubLoadTimeoutError, match="timed out"):
        load_from_hub_with_retries(hang, log_prefix="TEST")
    assert calls["n"] == 1
