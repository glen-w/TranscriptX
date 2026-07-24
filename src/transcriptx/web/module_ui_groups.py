"""
Web-only analysis module grouping and ordering (presentation layer).

Does not import module_registry to avoid circular imports. Callers apply
ordering at UI boundaries; discovery helpers stay separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Sequence

# Sentinel bucket labels used by some viewers (explorer/overview) for missing module.
_SENTINEL_OTHER = frozenset({"other"})
TECHNICAL_OTHER_TITLE = "Technical / Other"
TECHNICAL_OTHER_KEY = "technical_other"


@dataclass(frozen=True)
class ModuleUIGroup:
    """One cognitive group in the analysis module picker / viewer."""

    key: str
    title: str
    module_ids: tuple[str, ...]


MODULE_UI_GROUPS: tuple[ModuleUIGroup, ...] = (
    ModuleUIGroup(
        "summary_synthesis",
        "Summary & Synthesis",
        (
            "llm_summary",
            "narrative_summary",
            "llm_speaker_summary",
            "llm_action_items",
            "llm_custom_qa",
            "chart_descriptions",
            "summary",
            "highlights",
            "insights",
        ),
    ),
    ModuleUIGroup(
        "foundations",
        "Foundations",
        (
            "stats",
            "transcript_output",
            "simplified_transcript",
            "tics",
            "transcript_quality",
            "pauses",
            "temporal_dynamics",
            "insight_eligibility",
        ),
    ),
    ModuleUIGroup(
        "language_meaning",
        "Language & Meaning",
        (
            "sentiment",
            "emotion",
            "contextual_emotion",
            "fine_grained_emotion",
            "ner",
            "entity_sentiment",
            "topic_modeling",
            "bertopic",
            "semantic_similarity",
            "understandability",
            "lexical_diversity",
            "epistemic_markers",
            "keyphrases",
        ),
    ),
    ModuleUIGroup(
        "speakers_interaction",
        "Speakers & Interaction",
        (
            "acts",
            "interactions",
            "conversation_loops",
            "qa_analysis",
            "echoes",
            "contagion",
            "politeness",
        ),
    ),
        ModuleUIGroup(
            "dynamics_flow",
            "Dynamics & Flow",
            ("momentum", "topic_shift", "moments", "affect_tension"),
        ),
    ModuleUIGroup(
        "voice_audio",
        "Voice & Audio",
        (
            "voice_features",
            "voice_mismatch",
            "voice_tension",
            "voice_fingerprint",
            "voice_charts_core",
            "voice_contours",
            "prosody_dashboard",
        ),
    ),
    ModuleUIGroup(
        "visualizations",
        "Visualisations",
        ("wordclouds",),
    ),
)


def _build_maps() -> (
    tuple[tuple[str, ...], dict[str, int], Mapping[str, ModuleUIGroup]]
):
    flat: list[str] = []
    index: dict[str, int] = {}
    by_id: dict[str, ModuleUIGroup] = {}
    pos = 0
    for group in MODULE_UI_GROUPS:
        for mid in group.module_ids:
            flat.append(mid)
            index[mid] = pos
            by_id[mid] = group
            pos += 1
    return tuple(flat), index, by_id


_FLAT_SPEC_ORDER, _KNOWN_INDEX, _MODULE_TO_GROUP = _build_maps()
_SPEC_SET = frozenset(_FLAT_SPEC_ORDER)


def flattened_spec_module_ids() -> tuple[str, ...]:
    """All module ids in UI spec order (group order, then within-group order)."""
    return _FLAT_SPEC_ORDER


def group_title_for_module_id(module_id: str) -> str | None:
    """Human group title for a known spec module; None if not in the UI spec."""
    g = _MODULE_TO_GROUP.get(module_id)
    return g.title if g else None


def group_key_for_module_id(module_id: str | None) -> str:
    """Stable presentation group key; unknown modules map to Technical / Other."""
    if not module_id or not isinstance(module_id, str):
        return TECHNICAL_OTHER_KEY
    g = _MODULE_TO_GROUP.get(module_id)
    if g is not None:
        return g.key
    return TECHNICAL_OTHER_KEY


def presentation_group_for_module(module_id: str | None) -> tuple[str, str]:
    """Return (group_key, display_title) for a module id."""
    key = group_key_for_module_id(module_id)
    if key == TECHNICAL_OTHER_KEY:
        return TECHNICAL_OTHER_KEY, TECHNICAL_OTHER_TITLE
    g = _MODULE_TO_GROUP.get(module_id or "")
    if g is None:
        return TECHNICAL_OTHER_KEY, TECHNICAL_OTHER_TITLE
    return g.key, g.title


def is_known_spec_module_id(module_id: str) -> bool:
    return module_id in _SPEC_SET


def _str_ids_only(iterable: Iterable[Any]) -> Iterator[str]:
    for item in iterable:
        if isinstance(item, str) and item:
            yield item


def order_module_ids(iterable: Iterable[str]) -> list[str]:
    """
    Flat list: known ids in spec order, then unknown ids alphabetically.
    """
    want = frozenset(_str_ids_only(iterable))
    if not want:
        return []
    out: list[str] = []
    for mid in _FLAT_SPEC_ORDER:
        if mid in want:
            out.append(mid)
    unknown = sorted(want - _SPEC_SET)
    out.extend(unknown)
    return out


def group_modules_for_ui(iterable: Iterable[Any]) -> list[tuple[str, list[str]]]:
    """
    Non-empty (group title, [module ids]) in spec group order.

    Only real non-empty str module ids; None and non-str entries are ignored.
    Unknown ids are emitted under Technical / Other (alphabetically).
    """
    want = frozenset(_str_ids_only(iterable))
    if not want:
        return []
    result: list[tuple[str, list[str]]] = []
    for group in MODULE_UI_GROUPS:
        present = [mid for mid in group.module_ids if mid in want]
        if present:
            result.append((group.title, present))
    unknown = sorted(want - _SPEC_SET)
    if unknown:
        result.append((TECHNICAL_OTHER_TITLE, unknown))
    return result


def module_sort_key(module_id: str | None) -> tuple[Any, ...]:
    """
    Sort key: known spec order, then unknown strings alphabetically, then
    missing/empty/sentinel \"other\" buckets last.
    """
    if module_id is None:
        return (2, 0, "")
    if not isinstance(module_id, str):
        return (2, 0, str(module_id))
    if module_id == "":
        return (2, 1, "")
    if module_id.lower() in _SENTINEL_OTHER:
        return (2, 2, module_id.casefold())
    idx = _KNOWN_INDEX.get(module_id)
    if idx is not None:
        return (0, idx)
    return (1, module_id)


def order_strings_like_modules(values: Sequence[str]) -> list[str]:
    """Order arbitrary strings that represent module ids using module_sort_key tiers."""
    return sorted(values, key=lambda v: module_sort_key(v))
