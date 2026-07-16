"""Test-only fault-injection seams for cleanup execute (default no-op).

Not part of the public cleanup API. Hooks are process-global and must be
cleared after each test.
"""

from __future__ import annotations

from typing import Callable

# Named points matching the hardening plan.
FAULT_POINTS = (
    "after_initial_journal",
    "before_per_run_lock",
    "after_all_locks",
    "after_locked_rediscovery",
    "before_first_rename",
    "after_first_rename",
    "before_staged_lstat",
    "after_staged_lstat",
    "before_post_rename_journal",
    "before_physical_verify",
    "after_physical_verify",
    "during_delete",
    "before_cache_invalidation",
    "before_terminal_journal",
    "before_terminal_result_store",
)

_hooks: dict[str, Callable[[], None]] = {}


def fault_point(name: str) -> None:
    """Invoke a registered hook for ``name`` if present."""
    hook = _hooks.get(name)
    if hook is not None:
        hook()


def set_fault_hook(name: str, hook: Callable[[], None]) -> None:
    """Register a test hook. Raises if name is unknown."""
    if name not in FAULT_POINTS:
        raise ValueError(f"unknown fault point: {name!r}")
    _hooks[name] = hook


def clear_fault_hooks() -> None:
    _hooks.clear()
