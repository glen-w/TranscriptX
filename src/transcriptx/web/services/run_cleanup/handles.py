"""Opaque, session-bound, single-use cleanup plan handles."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    HANDLE_STORE_FULL,
    CleanupPlan,
    CleanupResult,
    RootIdentity,
)

_MAX_ENTRIES = 64
_DEFAULT_TTL_SECONDS = 3600

_lock = threading.RLock()
_store: dict[str, "_HandleEntry"] = {}


class HandleStoreFullError(RuntimeError):
    """Handle store at capacity with only protected entries."""

    def __init__(self, message: str = HANDLE_STORE_FULL) -> None:
        super().__init__(message)
        self.code = HANDLE_STORE_FULL


@dataclass
class _HandleEntry:
    plan: CleanupPlan
    session_id: str
    created_at: float
    expires_at: float
    claimed: bool = False
    result: CleanupResult | None = None
    root_fingerprint: tuple[tuple[Any, ...], ...] = field(default_factory=tuple)


def _root_fingerprint(roots: tuple[RootIdentity, ...]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            r.kind.value,
            r.configured_path,
            r.canonical_path,
            r.dev,
            r.ino,
            r.is_symlink,
        )
        for r in roots
    )


def _purge_expired_locked(now: float | None = None) -> None:
    now = time.time() if now is None else now
    expired = [
        k
        for k, v in _store.items()
        if v.expires_at <= now and not v.claimed and v.result is None
    ]
    for k in expired:
        del _store[k]


def _evict_oldest_unclaimed_locked() -> bool:
    """Evict oldest expired-or-oldest unclaimed entry. Never touches claimed/completed."""
    candidates = [
        (k, v) for k, v in _store.items() if not v.claimed and v.result is None
    ]
    if not candidates:
        return False
    # Prefer expired unclaimed
    now = time.time()
    expired = [(k, v) for k, v in candidates if v.expires_at <= now]
    pool = expired if expired else candidates
    oldest_key = min(pool, key=lambda kv: kv[1].created_at)[0]
    del _store[oldest_key]
    return True


def create_handle(
    plan: CleanupPlan,
    session_id: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> str:
    """Create a cryptographically unguessable handle bound to session_id.

    Raises HandleStoreFullError if capacity is exhausted by protected entries.
    """
    token = secrets.token_urlsafe(32)
    now = time.time()
    entry = _HandleEntry(
        plan=plan,
        session_id=session_id,
        created_at=now,
        expires_at=now + max(1, int(ttl_seconds)),
        root_fingerprint=_root_fingerprint(plan.roots),
    )
    with _lock:
        _purge_expired_locked(now)
        while len(_store) >= _MAX_ENTRIES:
            if not _evict_oldest_unclaimed_locked():
                raise HandleStoreFullError(
                    f"{HANDLE_STORE_FULL}: cleanup handle store at capacity"
                )
        _store[token] = entry
    return token


def get_plan(token: str, session_id: str) -> CleanupPlan | None:
    with _lock:
        _purge_expired_locked()
        entry = _store.get(token)
        if entry is None:
            return None
        if entry.session_id != session_id:
            return None
        if entry.expires_at <= time.time() and not entry.claimed:
            del _store[token]
            return None
        return entry.plan


def peek_handle(
    token: str, session_id: str
) -> tuple[str, CleanupPlan | None, CleanupResult | None]:
    """Non-mutating handle inspection.

    Returns ``(state, plan_or_none, result_or_none)`` where state is one of:
    ``missing``, ``issued``, ``in_progress``, ``completed``.
    """
    with _lock:
        _purge_expired_locked()
        entry = _store.get(token)
        if entry is None:
            return "missing", None, None
        if entry.session_id != session_id:
            return "missing", None, None
        if entry.expires_at <= time.time() and not entry.claimed:
            del _store[token]
            return "missing", None, None
        if entry.claimed and entry.result is not None:
            return "completed", entry.plan, entry.result
        if entry.claimed:
            return "in_progress", entry.plan, None
        return "issued", entry.plan, None


def claim_handle(
    token: str, session_id: str
) -> tuple[CleanupPlan | None, CleanupResult | None]:
    """Single-use claim. Returns (plan, None) on first claim, or (None, prior_result).

    Missing/expired/wrong session → (None, None).
    Already claimed with stored result → (None, result) for ALREADY_EXECUTED.
    Already claimed without result (in-flight) → (None, None); caller maps via peek.
    """
    with _lock:
        _purge_expired_locked()
        entry = _store.get(token)
        if entry is None:
            return None, None
        if entry.session_id != session_id:
            return None, None
        if entry.expires_at <= time.time() and not entry.claimed:
            del _store[token]
            return None, None
        if entry.claimed:
            return None, entry.result
        entry.claimed = True
        return entry.plan, None


def store_result(token: str, session_id: str, result: CleanupResult) -> None:
    """Attach execution result for ALREADY_EXECUTED replay (terminal)."""
    with _lock:
        entry = _store.get(token)
        if entry is None:
            return
        if entry.session_id != session_id:
            return
        entry.result = result
        entry.claimed = True


def invalidate_all() -> None:
    with _lock:
        _store.clear()


def invalidate_on_policy_change(policy_version: int = CLEANUP_POLICY_VERSION) -> int:
    """Drop unclaimed handles whose plan policy_version differs from current."""
    with _lock:
        to_drop = [
            k
            for k, v in _store.items()
            if v.plan.policy_version != policy_version
            and not v.claimed
            and v.result is None
        ]
        for k in to_drop:
            del _store[k]
        return len(to_drop)


def invalidate_on_root_change(
    roots: tuple[RootIdentity, ...] | list[RootIdentity],
) -> int:
    """Drop unclaimed handles whose stored root fingerprint no longer matches."""
    expected = _root_fingerprint(tuple(roots))
    with _lock:
        to_drop = [
            k
            for k, v in _store.items()
            if v.root_fingerprint != expected and not v.claimed and v.result is None
        ]
        for k in to_drop:
            del _store[k]
        return len(to_drop)


def _reset_for_tests() -> None:
    """Clear the in-memory store (tests only)."""
    with _lock:
        _store.clear()
