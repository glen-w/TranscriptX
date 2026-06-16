"""Compatibility entrypoint for canonical TRANSCRIPTX_* env overrides."""

from __future__ import annotations

from typing import Any

from transcriptx.core.utils.config.env_key_registry import (
    apply_env_to_config,
)


def apply_transcriptx_env(config: Any) -> None:
    """Apply TRANSCRIPTX_* environment values onto ``config``."""
    apply_env_to_config(config)
