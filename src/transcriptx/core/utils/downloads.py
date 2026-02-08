"""
Utilities for controlling optional downloads.
"""

from __future__ import annotations

import os


def downloads_disabled(env_var: str = "TRANSCRIPTX_DISABLE_DOWNLOADS") -> bool:
    """
    Return True when optional downloads are disabled.

    Defaults to disabled unless explicitly opted in.
    """
    value = os.getenv(env_var, "").strip().lower()
    if value == "":
        return True
    return value in {"1", "true", "yes", "on"}
