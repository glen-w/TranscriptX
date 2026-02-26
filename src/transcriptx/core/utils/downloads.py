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


def downloads_disabled_failfast_message(
    resource_name: str,
    extra_hint: str = "",
) -> str:
    """
    Return a single actionable message when a required resource is missing and
    downloads are disabled. Use this so Docker/CI users get one clear next step.
    """
    msg = (
        f"{resource_name} is not available and downloads are disabled "
        "(TRANSCRIPTX_DISABLE_DOWNLOADS=1). "
        "Set TRANSCRIPTX_DISABLE_DOWNLOADS=0 and run once to populate the cache, "
        "or mount a cache volume (e.g. HF_HOME, TRANSCRIPTX_CACHE_DIR, or NLTK_DATA) "
        "that already contains the resource."
    )
    if extra_hint:
        msg += f" {extra_hint}"
    return msg
