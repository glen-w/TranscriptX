"""
Analysis mode, profile, and module selection logic (core policy).

This module holds the single source of truth for:
- Applying analysis mode (quick/full) and profile to config
- Filtering modules by mode (e.g. skip semantic_similarity_advanced in quick)
- Recommended/default module list policy

CLI and web UIs call this; they do not duplicate this logic.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional

from transcriptx.core.utils.config import get_config
from transcriptx.core.pipeline.module_registry import (
    get_default_modules,
    get_module_info,
    ModuleInfo,
)

VALID_MODES = ("quick", "full")
VALID_PROFILES = (
    "balanced",
    "academic",
    "business",
    "casual",
    "technical",
    "interview",
)


def apply_analysis_mode_settings(
    mode: str,
    profile: Optional[str] = None,
) -> None:
    """
    Apply analysis mode and optional profile to config (non-interactive).

    Args:
        mode: 'quick' or 'full'
        profile: For full mode only - one of VALID_PROFILES. Ignored for quick.
    """
    config = get_config()
    if mode not in VALID_MODES:
        mode = "quick"
    if mode == "quick":
        settings = config.analysis.quick_analysis_settings
        config.analysis.analysis_mode = "quick"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings["max_segments_for_semantic"]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings.get("skip_geocoding", False)
        config.analysis.quality_filtering_profile = settings.get("semantic_profile", "balanced")
    else:
        settings = config.analysis.full_analysis_settings
        config.analysis.analysis_mode = "full"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings["max_segments_for_semantic"]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings.get("skip_geocoding", False)
        if "max_segments_per_speaker" in settings:
            config.analysis.max_segments_per_speaker = settings["max_segments_per_speaker"]
        if "max_segments_for_cross_speaker" in settings:
            config.analysis.max_segments_for_cross_speaker = settings["max_segments_for_cross_speaker"]
        profile_choice = profile or "balanced"
        if profile_choice not in VALID_PROFILES:
            profile_choice = "balanced"
        config.analysis.quality_filtering_profile = profile_choice


def filter_modules_by_mode(modules: List[str], mode: str) -> List[str]:
    """
    Filter module list for the given analysis mode.

    E.g. quick mode may drop semantic_similarity_advanced and use semantic_similarity instead.
    """
    if mode not in VALID_MODES:
        mode = "quick"
    config = get_config()
    if mode == "quick":
        settings = getattr(config.analysis, "quick_analysis_settings", None) or {}
        if settings.get("skip_advanced_semantic", True):
            filtered = [m for m in modules if m != "semantic_similarity_advanced"]
            if "semantic_similarity_advanced" in modules and "semantic_similarity" not in filtered:
                filtered.append("semantic_similarity")
            return filtered
    return list(modules)


def get_recommended_modules(
    transcript_targets: Optional[Iterable[Any]] = None,
    *,
    audio_resolver: Optional[Callable[[Any], bool]] = None,
    dep_resolver: Optional[Callable[[ModuleInfo], bool]] = None,
    include_heavy: bool = True,
    include_excluded_from_default: bool = False,
) -> List[str]:
    """
    Return the recommended/default module list for analysis (single source of truth).

    Definition of "recommended" (same contract across CLI and web): safe, non-heavy
    (unless include_heavy=True), runnable-now. Explicitly excludes: heavy modules
    unless include_heavy=True; audio-required modules when audio is unavailable;
    modules that require optional deps (e.g. voice) when those deps are missing.
    When include_excluded_from_default=True, modules marked exclude_from_default
    are included (e.g. for custom preset in web UI).
    """
    return list(
        get_default_modules(
            transcript_targets,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_heavy=include_heavy,
            include_excluded_from_default=include_excluded_from_default,
        )
    )
