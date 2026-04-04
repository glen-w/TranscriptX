"""
Canonical module resolution. GUI and Python API both use this — no parallel implementations.
"""

from __future__ import annotations

from typing import Optional

from transcriptx.core.pipeline.module_registry import (
    get_module_info,
    ModuleInfo,
    get_available_modules,
    get_default_modules,
)
from transcriptx.core.utils.audio_availability import has_resolvable_audio


def resolve_modules(
    transcript_paths: list[str],
    mode: str = "quick",
    profile: Optional[str] = None,
    custom_ids: Optional[list[str]] = None,
    for_group: bool = False,
) -> list[str]:
    """
    Resolve effective module list. Single source of truth for GUI and API callers.
    """
    available = get_available_modules()
    if custom_ids is not None and len(custom_ids) > 0:
        invalid = [m for m in custom_ids if m not in available]
        if invalid:
            raise ValueError(f"Invalid modules: {', '.join(invalid)}")
        selected = list(custom_ids)
    else:
        selected = get_default_modules(
            transcript_paths,
            audio_resolver=has_resolvable_audio,
            for_group=for_group,
        )
    from transcriptx.core.analysis.selection import filter_modules_by_mode

    return filter_modules_by_mode(selected, mode)


def get_module_info_list() -> list[ModuleInfo]:
    """Return module info for all available modules."""
    available = get_available_modules()
    result = []
    for m in available:
        info = get_module_info(m)
        if info:
            result.append(info)
    return result
