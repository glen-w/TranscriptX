"""Feature flags for Theme C workspace components."""

from __future__ import annotations

import os
from typing import Any

# Phase 5 gate: default-off until Docker/web install of transcriptx-workspaces is
# proven in the running image AND the Streamlit browser suite covers plan gates.
# Enable with TX_SPEAKER_ID_WORKSPACE_COMPONENT=1 or session override.
_SPEAKER_ID_WORKSPACE_DEFAULT = False


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _falsy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"0", "false", "no", "off"}


def speaker_id_workspace_component_enabled(session_state: Any | None = None) -> bool:
    """Return True when the CCv2 Speaker ID workspace should mount.

    Priority: env ``TX_SPEAKER_ID_WORKSPACE_COMPONENT`` → session override →
    default (off until Phase 5 install + Streamlit browser gates).
    """
    env = os.environ.get("TX_SPEAKER_ID_WORKSPACE_COMPONENT")
    if env is not None and env.strip() != "":
        if _falsy(env):
            return False
        return _truthy(env)
    if session_state is not None:
        override = session_state.get("speaker_id_workspace_component")
        if override is not None:
            return bool(override)
    return bool(_SPEAKER_ID_WORKSPACE_DEFAULT)


def corrections_workspace_component_enabled(session_state: Any | None = None) -> bool:
    env = os.environ.get("TX_CORRECTIONS_WORKSPACE_COMPONENT")
    if env is not None and env.strip() != "":
        if _falsy(env):
            return False
        return _truthy(env)
    if session_state is not None:
        override = session_state.get("corrections_workspace_component")
        if override is not None:
            return bool(override)
    return False
