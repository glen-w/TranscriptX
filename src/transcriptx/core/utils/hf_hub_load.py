"""Bounded Hugging Face Hub loads: timeout, retry, then fail closed.

Analysis modules must skip (not hang the pipeline) when huggingface.co is slow
or unreachable. Hub clients retry internally with long cumulative waits; this
helper caps HTTP timeouts/retries and applies a small number of outer attempts.
"""

from __future__ import annotations

import concurrent.futures
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

from transcriptx.core.utils.logger import log_warning

T = TypeVar("T")

HUB_LOAD_ATTEMPTS = 2
HUB_ATTEMPT_TIMEOUT_SECONDS = 25.0
HUB_RETRY_BACKOFF_SECONDS = 1.0
HUB_HTTP_TIMEOUT_SECONDS = 10.0
HUB_HTTP_MAX_RETRIES = 1

_OFFLINE_ENV_KEYS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
_RETRYABLE_MARKERS = (
    "timed out",
    "timeout",
    "temporarily unavailable",
    "connection aborted",
    "connection reset",
    "connecterror",
    "connectionerror",
    "httpsconnectionpool",
    "name resolution",
    "nodename nor servname",
    "failed to establish",
    "network is unreachable",
    "max retries exceeded",
    "temporarily disabled",
    "service unavailable",
)


class HubLoadTimeoutError(TimeoutError):
    """Wall-clock budget for one Hub load attempt was exhausted."""


def is_retryable_hub_error(exc: BaseException) -> bool:
    """True when a Hub/network failure is worth another bounded attempt."""
    if isinstance(exc, HubLoadTimeoutError):
        # The abandoned worker may still hold Hub cache locks; do not retry.
        return False
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _RETRYABLE_MARKERS)


@contextmanager
def huggingface_offline_scope() -> Iterator[None]:
    """Force Hub/transformers clients to use local files only for this scope."""
    environ = os.environ
    previous = {key: environ.get(key) for key in _OFFLINE_ENV_KEYS}
    try:
        for key in _OFFLINE_ENV_KEYS:
            environ[key] = "1"
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                environ.pop(key, None)
            else:
                environ[key] = value


@contextmanager
def huggingface_hub_bounded_http_scope() -> Iterator[None]:
    """Cap Hub HTTP timeouts and per-request retries for one load attempt."""
    patched: list[tuple[object, str, object]] = []
    try:
        import huggingface_hub.constants as hf_constants
        from huggingface_hub.utils import _http as hf_http

        timeout_s = int(HUB_HTTP_TIMEOUT_SECONDS)
        max_retries = int(HUB_HTTP_MAX_RETRIES)
        orig_backoff = hf_http.http_backoff

        def bounded_backoff(*args: object, **kwargs: object) -> object:
            current = kwargs.get("max_retries", max_retries)
            try:
                current_i = int(current)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                current_i = max_retries
            kwargs["max_retries"] = min(current_i, max_retries)
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = timeout_s
            return orig_backoff(*args, **kwargs)

        for attr in ("HF_HUB_ETAG_TIMEOUT", "HF_HUB_DOWNLOAD_TIMEOUT"):
            if hasattr(hf_constants, attr):
                patched.append((hf_constants, attr, getattr(hf_constants, attr)))
                setattr(hf_constants, attr, timeout_s)

        patched.append((hf_http, "http_backoff", orig_backoff))
        hf_http.http_backoff = bounded_backoff  # type: ignore[method-assign]

        try:
            import huggingface_hub.file_download as hf_download

            if getattr(hf_download, "http_backoff", None) is orig_backoff:
                patched.append((hf_download, "http_backoff", orig_backoff))
                hf_download.http_backoff = bounded_backoff  # type: ignore[method-assign]
        except Exception:
            pass
    except Exception:
        yield
        return

    try:
        yield
    finally:
        for target, attr, previous in reversed(patched):
            setattr(target, attr, previous)


def _call_with_timeout(load_fn: Callable[[], T], timeout_seconds: float) -> T:
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(load_fn)
        try:
            return future.result(timeout=float(timeout_seconds))
        except concurrent.futures.TimeoutError as exc:
            raise HubLoadTimeoutError(
                f"Hugging Face Hub load timed out after {timeout_seconds:.0f}s"
            ) from exc
    finally:
        # Do not wait: a hung HTTP read must not block later modules.
        executor.shutdown(wait=False, cancel_futures=True)


def load_from_hub_with_retries(
    load_fn: Callable[[], T],
    *,
    log_prefix: str = "HF_HUB",
) -> T:
    """Run ``load_fn`` with bounded Hub HTTP, timeout, and a single retry."""
    attempts = max(1, int(HUB_LOAD_ATTEMPTS))
    timeout_s = float(HUB_ATTEMPT_TIMEOUT_SECONDS)
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            with huggingface_hub_bounded_http_scope():
                return _call_with_timeout(load_fn, timeout_s)
        except Exception as exc:
            last_exc = exc
            retryable = is_retryable_hub_error(exc)
            if retryable and attempt < attempts:
                log_warning(
                    log_prefix,
                    f"Hub load failed (attempt {attempt}/{attempts}): {exc}; retrying",
                )
                time.sleep(float(HUB_RETRY_BACKOFF_SECONDS))
                continue
            if attempt > 1 or retryable:
                log_warning(
                    log_prefix,
                    f"Hub load failed after {attempt} attempt(s): {exc}",
                )
            raise
    assert last_exc is not None
    raise last_exc
