"""Compatibility entrypoint for canonical TRANSCRIPTX_* env overrides."""

from __future__ import annotations

from typing import Any

from transcriptx.core.utils.config.env_key_registry import apply_env_to_config


def apply_env_overrides(cfg: Any) -> None:
    """Apply TRANSCRIPTX_* environment overrides to a config instance."""
    apply_env_to_config(cfg)
