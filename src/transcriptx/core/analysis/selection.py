"""
Analysis mode, profile, and module selection logic (core policy).

This module holds the single source of truth for:
- Applying analysis mode (quick/full) and profile to config
- Filtering modules by mode (e.g. semantic_similarity_v2 basic vs advanced)
- Recommended/default module list policy
- UI analysis presets (quick / balanced / thorough / custom)

Web UI and Python API callers use this; they do not duplicate this logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Literal, Optional, Sequence

from transcriptx.core.utils.config import get_config
from transcriptx.core.pipeline.module_registry import (
    effective_min_named_speakers,
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

AnalysisPreset = Literal["quick", "balanced", "thorough", "custom"]
AnalysisTarget = Literal["transcript", "group", "batch"]
VALID_PRESETS: tuple[AnalysisPreset, ...] = (
    "quick",
    "balanced",
    "thorough",
    "custom",
)
_UI_DEFAULT_PROFILE = "balanced"
_CUSTOM_QA_MODULE = "llm_custom_qa"


@dataclass(frozen=True)
class ResolvedAnalysisPreset:
    """Deterministic preset resolution for one analysis launch configuration."""

    preset: AnalysisPreset
    mode: str
    profile: str
    module_ids: tuple[str, ...]


@dataclass(frozen=True)
class EffectiveModulePlan:
    """Single authoritative module list for summary, footer, gates, and request."""

    module_ids: tuple[str, ...]
    llm_count: int
    heavy_count: int
    custom_qa_execution: bool

_LEGACY_SEMANTIC_IDS = frozenset(
    {"semantic_similarity", "semantic_similarity_advanced"}
)


def is_legacy_module(module_id: str) -> bool:
    """Return True if the registry marks this module as legacy."""
    info = get_module_info(module_id)
    return bool(info and info.legacy)


def _dedupe_preserve_order(modules: List[str]) -> List[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in modules:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


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
        config.analysis.max_segments_for_semantic = settings[
            "max_segments_for_semantic"
        ]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings.get(
            "skip_geocoding", False
        )
        config.analysis.quality_filtering_profile = settings.get(
            "semantic_profile", "balanced"
        )
    else:
        settings = config.analysis.full_analysis_settings
        config.analysis.analysis_mode = "full"
        config.analysis.semantic_similarity_method = settings["semantic_method"]
        config.analysis.max_segments_for_semantic = settings[
            "max_segments_for_semantic"
        ]
        config.analysis.max_semantic_comparisons = settings["max_semantic_comparisons"]
        config.analysis.ner_use_light_model = settings["ner_use_light_model"]
        config.analysis.ner_max_segments = settings["ner_max_segments"]
        config.analysis.ner_include_geocoding = not settings.get(
            "skip_geocoding", False
        )
        if "max_segments_per_speaker" in settings:
            config.analysis.max_segments_per_speaker = settings[
                "max_segments_per_speaker"
            ]
        if "max_segments_for_cross_speaker" in settings:
            config.analysis.max_segments_for_cross_speaker = settings[
                "max_segments_for_cross_speaker"
            ]
        profile_choice = profile or "balanced"
        if profile_choice not in VALID_PROFILES:
            profile_choice = "balanced"
        config.analysis.quality_filtering_profile = profile_choice

    # Drive semantic_similarity_v2.mode from the same semantic_method knob.
    method = settings.get("semantic_method", "simple")
    config.analysis.semantic_similarity_v2.mode = (
        "advanced" if method == "advanced" else "basic"
    )


def filter_modules_by_mode(modules: List[str], mode: str) -> List[str]:
    """
    Filter module list for the given analysis mode.

    Legacy semantic modules (`semantic_similarity`, `semantic_similarity_advanced`)
    are only kept when they appear explicitly in ``modules`` (user override).
    Default plans use ``semantic_similarity_v2`` instead (via registry defaults).

    Quick mode: if the list explicitly contained only
    ``semantic_similarity_advanced``, substitute ``semantic_similarity`` (legacy
    quick path), matching the historical contract.
    """
    if mode not in VALID_MODES:
        mode = "quick"
    config = get_config()
    settings = (
        config.analysis.quick_analysis_settings
        if mode == "quick"
        else config.analysis.full_analysis_settings
    )

    modules = list(modules)
    explicit_legacy_semantic = bool(_LEGACY_SEMANTIC_IDS.intersection(modules))

    if explicit_legacy_semantic:
        if mode == "quick" and settings.get("skip_advanced_semantic", True):
            out: list[str] = []
            had_advanced_only = "semantic_similarity_advanced" in modules
            for m in modules:
                if m == "semantic_similarity_advanced":
                    continue
                out.append(m)
            if had_advanced_only and "semantic_similarity" not in out:
                out.append("semantic_similarity")
            return _dedupe_preserve_order(out)
        return _dedupe_preserve_order(modules)

    # Default path: strip legacy semantic ids (should already be absent from defaults).
    modules = [m for m in modules if m not in _LEGACY_SEMANTIC_IDS]
    return _dedupe_preserve_order(modules)


def filter_modules_for_speaker_count(
    modules: List[str], named_speaker_count: int
) -> List[str]:
    """Filter modules that require more named speakers than available."""
    filtered: list[str] = []
    for module in modules:
        info = get_module_info(module)
        if info is None:
            filtered.append(module)
            continue
        if named_speaker_count < effective_min_named_speakers(info):
            continue
        filtered.append(module)
    return filtered


def get_recommended_modules(
    transcript_targets: Optional[Iterable[Any]] = None,
    *,
    audio_resolver: Optional[Callable[[Any], bool]] = None,
    dep_resolver: Optional[Callable[[ModuleInfo], bool]] = None,
    include_heavy: bool = True,
    include_excluded_from_default: bool = False,
    include_legacy: Optional[bool] = None,
    for_group: bool = False,
) -> List[str]:
    """
    Return the recommended/default module list for analysis (single source of truth).

    Definition of "recommended" (same contract across GUI and API): safe, non-heavy
    (unless include_heavy=True), runnable-now. Explicitly excludes: heavy modules
    unless include_heavy=True; audio-required modules when audio is unavailable;
    modules that require optional deps (e.g. voice) when those deps are missing.
    When include_excluded_from_default=True, modules marked exclude_from_default
    are included (e.g. for custom preset in web UI).

    ``include_legacy`` defaults to ``config.analysis.include_legacy_modules`` when
    omitted.
    """
    return list(
        get_default_modules(
            transcript_targets,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_heavy=include_heavy,
            include_excluded_from_default=include_excluded_from_default,
            include_legacy=include_legacy,
            for_group=for_group,
        )
    )


def _for_group_target(target: AnalysisTarget) -> bool:
    return target == "group"


def _suitable_module_ids(
    transcript_targets: Optional[Iterable[Any]],
    *,
    target: AnalysisTarget,
    include_heavy: bool,
    include_excluded_from_default: bool,
    audio_resolver: Optional[Callable[[Any], bool]] = None,
    dep_resolver: Optional[Callable[[ModuleInfo], bool]] = None,
    include_legacy: Optional[bool] = None,
) -> tuple[str, ...]:
    """User-facing suitable modules for a target (excludes legacy by default)."""
    modules = get_default_modules(
        transcript_targets,
        audio_resolver=audio_resolver,
        dep_resolver=dep_resolver,
        include_heavy=include_heavy,
        include_excluded_from_default=include_excluded_from_default,
        include_legacy=include_legacy,
        for_group=_for_group_target(target),
    )
    return tuple(_dedupe_preserve_order(list(modules)))


def reconcile_custom_modules(
    selected: Sequence[str],
    *,
    suitable: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Keep Custom selection that remains suitable; return (kept, removed)."""
    suitable_set = set(suitable)
    kept: list[str] = []
    removed: list[str] = []
    seen: set[str] = set()
    for mid in selected:
        if mid in seen:
            continue
        seen.add(mid)
        if mid in suitable_set:
            kept.append(mid)
        else:
            removed.append(mid)
    return tuple(kept), tuple(removed)


def resolve_analysis_preset(
    preset: AnalysisPreset | str,
    *,
    target: AnalysisTarget = "transcript",
    transcript_targets: Optional[Iterable[Any]] = None,
    custom_modules: Optional[Sequence[str]] = None,
    audio_resolver: Optional[Callable[[Any], bool]] = None,
    dep_resolver: Optional[Callable[[ModuleInfo], bool]] = None,
    include_legacy: Optional[bool] = None,
) -> ResolvedAnalysisPreset:
    """
    Resolve a UI analysis preset into mode, profile, and module ids.

    ``profile`` is always ``\"balanced\"`` for UI presets (including Quick) so
    request construction has no None / ignored special case.
    """
    if preset not in VALID_PRESETS:
        preset = "balanced"
    preset_key: AnalysisPreset = preset  # type: ignore[assignment]

    if preset_key == "quick":
        modules = _suitable_module_ids(
            transcript_targets,
            target=target,
            include_heavy=False,
            include_excluded_from_default=False,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_legacy=include_legacy,
        )
        return ResolvedAnalysisPreset(
            preset="quick",
            mode="quick",
            profile=_UI_DEFAULT_PROFILE,
            module_ids=modules,
        )

    if preset_key == "thorough":
        modules = _suitable_module_ids(
            transcript_targets,
            target=target,
            include_heavy=True,
            include_excluded_from_default=True,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_legacy=include_legacy,
        )
        return ResolvedAnalysisPreset(
            preset="thorough",
            mode="full",
            profile=_UI_DEFAULT_PROFILE,
            module_ids=modules,
        )

    if preset_key == "custom":
        suitable = _suitable_module_ids(
            transcript_targets,
            target=target,
            include_heavy=True,
            include_excluded_from_default=True,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_legacy=include_legacy,
        )
        kept, _removed = reconcile_custom_modules(
            list(custom_modules or ()), suitable=suitable
        )
        if not kept:
            # Seed Custom from Balanced when empty.
            kept = _suitable_module_ids(
                transcript_targets,
                target=target,
                include_heavy=True,
                include_excluded_from_default=False,
                audio_resolver=audio_resolver,
                dep_resolver=dep_resolver,
                include_legacy=include_legacy,
            )
        return ResolvedAnalysisPreset(
            preset="custom",
            mode="full",
            profile=_UI_DEFAULT_PROFILE,
            module_ids=kept,
        )

    # balanced (default)
    modules = _suitable_module_ids(
        transcript_targets,
        target=target,
        include_heavy=True,
        include_excluded_from_default=False,
        audio_resolver=audio_resolver,
        dep_resolver=dep_resolver,
        include_legacy=include_legacy,
    )
    return ResolvedAnalysisPreset(
        preset="balanced",
        mode="full",
        profile=_UI_DEFAULT_PROFILE,
        module_ids=modules,
    )


def _count_llm_and_heavy(module_ids: Sequence[str]) -> tuple[int, int]:
    llm = 0
    heavy = 0
    for mid in module_ids:
        info = get_module_info(mid)
        if info is None:
            continue
        if getattr(info, "requires_llm", False):
            llm += 1
        if getattr(info, "cost_tier", "") == "heavy":
            heavy += 1
    return llm, heavy


def compute_effective_modules(
    resolved: ResolvedAnalysisPreset,
    *,
    custom_qa_execution: bool,
) -> EffectiveModulePlan:
    """
    Build the single authoritative module list for UI summary and launch.

    When custom-question execution is requested, ensure ``llm_custom_qa`` is
    present exactly once. When Skip is active (``custom_qa_execution=False``),
    strip ``llm_custom_qa`` if the preset included it.
    """
    modules = list(resolved.module_ids)
    if custom_qa_execution:
        if _CUSTOM_QA_MODULE not in modules:
            modules.append(_CUSTOM_QA_MODULE)
    else:
        modules = [m for m in modules if m != _CUSTOM_QA_MODULE]
    deduped = tuple(_dedupe_preserve_order(modules))
    llm_count, heavy_count = _count_llm_and_heavy(deduped)
    return EffectiveModulePlan(
        module_ids=deduped,
        llm_count=llm_count,
        heavy_count=heavy_count,
        custom_qa_execution=bool(custom_qa_execution),
    )
