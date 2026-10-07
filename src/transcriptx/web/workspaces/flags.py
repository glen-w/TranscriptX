"""Feature flags for Theme C workspace components."""

from __future__ import annotations

import os
from typing import Any

# Phase 9: Speaker ID CCv2 is the only naming/playback surface. Missing package
# is an error, not a classic-UI fallthrough.
_CORRECTIONS_WORKSPACE_DEFAULT = True
_READER_WORKSPACE_DEFAULT = True


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _falsy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"0", "false", "no", "off"}


def corrections_workspace_component_enabled(session_state: Any | None = None) -> bool:
    """Return True when the CCv2 Corrections review workspace should mount.

    Priority: env ``TX_CORRECTIONS_WORKSPACE_COMPONENT`` → session override →
    default on. Rollback with env ``0`` / ``false`` / ``off``.
    """
    env = os.environ.get("TX_CORRECTIONS_WORKSPACE_COMPONENT")
    if env is not None and env.strip() != "":
        if _falsy(env):
            return False
        return _truthy(env)
    if session_state is not None:
        override = session_state.get("corrections_workspace_component")
        if override is not None:
            return bool(override)
    return bool(_CORRECTIONS_WORKSPACE_DEFAULT)


def reader_workspace_component_enabled(session_state: Any | None = None) -> bool:
    """Return True when the Theme D CCv2 reader workspace should mount.

    Priority: env ``TX_READER_WORKSPACE_COMPONENT`` → session override →
    default on. Rollback with env ``0`` / ``false`` / ``off``.
    """
    env = os.environ.get("TX_READER_WORKSPACE_COMPONENT")
    if env is not None and env.strip() != "":
        if _falsy(env):
            return False
        return _truthy(env)
    if session_state is not None:
        override = session_state.get("reader_workspace_component")
        if override is not None:
            return bool(override)
    return bool(_READER_WORKSPACE_DEFAULT)
