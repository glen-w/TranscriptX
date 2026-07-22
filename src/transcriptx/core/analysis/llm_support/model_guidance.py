"""Static guidance for installed Ollama models (UI table).

Helps users pick a tag per LLM module. Matching is intentionally loose:
family/prefix + size-class heuristics, not a hard allow-list of tags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

SizeClass = Literal["tiny", "small", "mid", "large", "unknown"]


@dataclass(frozen=True)
class LlmModelGuidance:
    model: str
    size_class: SizeClass
    strengths: str
    best_for: str
    notes: str


@dataclass(frozen=True)
class _FamilyRule:
    """First matching prefix wins; keep more-specific prefixes first."""

    prefixes: tuple[str, ...]
    family_label: str
    strengths: str
    best_for: str
    notes: str
    # Optional overrides keyed by size class.
    by_size: dict[SizeClass, tuple[str, str, str]] | None = None


_SIZE_RE = re.compile(
    r"(?:^|[:\-_/])(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>[bm])\b",
    re.IGNORECASE,
)

# Approximate parameter budgets for transcript LLM work on local Ollama.
_SIZE_CLASS_BY_B: tuple[tuple[float, SizeClass], ...] = (
    (2.0, "tiny"),
    (5.0, "small"),
    (14.0, "mid"),
    (float("inf"), "large"),
)

_FAMILY_RULES: tuple[_FamilyRule, ...] = (
    _FamilyRule(
        prefixes=("qwen3-coder", "qwen2.5-coder", "deepcoder"),
        family_label="code specialist",
        strengths="Code generation and repair.",
        best_for="Not recommended for TranscriptX LLM modules.",
        notes="Prefer a general chat/instruct model for summaries and JSON extraction.",
    ),
    _FamilyRule(
        prefixes=("qwen3.6",),
        family_label="Qwen3.6",
        strengths="Strong long-context reasoning (thinking family).",
        best_for=(
            "Plain-text llm_summary / llm_speaker_summary only when you accept "
            "thinking-model quirks."
        ),
        notes=(
            "Thinking model: often leaves Ollama `response` empty under "
            "format=json — do not use for narrative_summary, llm_action_items, "
            "chart_descriptions, or group_llm_synthesis."
        ),
        by_size={
            "mid": (
                "Reasoning-heavy; JSON modules are unreliable.",
                "Plain-text summaries only.",
                "Prefer gemma3 / qwen2.5 for JSON consumers.",
            ),
            "large": (
                "Highest local reasoning cost; still JSON-unsafe.",
                "Plain-text digests only.",
                "Exclude from shared picks when JSON modules are selected.",
            ),
        },
    ),
    _FamilyRule(
        prefixes=("qwen3",),
        family_label="Qwen3",
        strengths="Instruct following with thinking-mode behaviour on many tags.",
        best_for="Plain-text llm_summary / llm_speaker_summary when JSON modules are off.",
        notes=(
            "Thinking family: often empty `response` with format=json. "
            "Not safe as a shared default when narrative_summary, "
            "llm_action_items, or chart_descriptions are selected."
        ),
        by_size={
            "tiny": (
                "Very fast, limited fidelity; JSON-unsafe.",
                "Avoid for production TranscriptX LLM modules.",
                "Prefer non-thinking mid tags.",
            ),
            "small": (
                "Fast drafts; JSON-unsafe.",
                "Plain-text short summaries only.",
                "Prefer gemma3 / qwen2.5 for JSON.",
            ),
            "mid": (
                "Capable prose; still thinking/JSON-unsafe.",
                "llm_summary / llm_speaker_summary only.",
                "Do not use as shared model with JSON modules.",
            ),
            "large": (
                "Higher fidelity prose; still JSON-unsafe.",
                "Plain-text digests only.",
                "Prefer non-thinking models for structured extraction.",
            ),
        },
    ),
    _FamilyRule(
        prefixes=("qwen2.5", "qwen2"),
        family_label="Qwen2.5",
        strengths="Solid mid-size generalist; stable JSON for extraction.",
        best_for="llm_summary, llm_speaker_summary, llm_action_items as a shared model.",
        notes="Slightly older than Qwen3; still a strong local workhorse.",
    ),
    _FamilyRule(
        prefixes=("gemma3", "gemma2", "gemma"),
        family_label="Gemma",
        strengths=(
            "Strong instruction following, stable JSON, and long context "
            "(128K on 4b+); multilingual on larger tags."
        ),
        best_for=(
            "Preferred shared picks for JSON modules "
            "(narrative_summary, llm_action_items, chart_descriptions)."
        ),
        notes=(
            "Non-thinking family — safer than qwen3/deepseek-r1/gpt-oss when "
            "format=json is required. Tiny tags are smoke-only."
        ),
        by_size={
            "tiny": (
                "Minimal capacity.",
                "Local smoke / connectivity checks.",
                "Do not use for production summaries.",
            ),
            "small": (
                "Fast captions with usable 128K context (e.g. gemma3:4b).",
                "chart_descriptions; short llm_speaker_summary / drafts.",
                "Upgrade to 12b/27b for long digests and action items.",
            ),
            "mid": (
                "Good structured output and readable captions.",
                "All modules as a shared mid pick (e.g. gemma3:12b).",
                "Strong default when thinking models are filtered out.",
            ),
            "large": (
                "Stronger prose, multi-speaker briefs, and multilingual coverage.",
                "llm_summary, narrative_summary, llm_action_items, group synthesis.",
                "Heavier than mid; prefer for quality over chart-only latency.",
            ),
        },
    ),
    _FamilyRule(
        prefixes=("llama3.2", "llama3.1", "llama3", "llama2", "llama"),
        family_label="Llama",
        strengths="Fast general chat; light footprint on small tags.",
        best_for="chart_descriptions and quick drafts.",
        notes="Small tags struggle with long digests and strict action-item JSON.",
        by_size={
            "tiny": (
                "Very fast, shallow understanding.",
                "chart_descriptions only.",
                "Prefer mid+ for summaries and action items.",
            ),
            "small": (
                "Quick overviews when hardware is constrained.",
                "chart_descriptions; short llm_summary.",
                "Upgrade for narrative_summary / llm_action_items.",
            ),
            "mid": (
                "Competent shared model for most modules.",
                "llm_summary, llm_speaker_summary, chart_descriptions.",
                "Strong non-thinking alternative to Qwen3 for JSON modules.",
            ),
            "large": (
                "Stronger long-form digests.",
                "llm_summary, narrative_summary, group_llm_synthesis.",
                "Heavier RAM/latency cost.",
            ),
        },
    ),
    _FamilyRule(
        prefixes=("mistral-nemo",),
        family_label="Mistral NeMo",
        strengths=(
            "12B instruct with very long context (up to ~1M tokens in Ollama); "
            "stable non-thinking JSON."
        ),
        best_for=(
            "llm_summary and llm_speaker_summary on long sessions; also solid "
            "shared mid for narrative_summary / llm_action_items."
        ),
        notes=(
            "Complements gemma3:12b with extreme context headroom for long "
            "meetings; ~7GB download."
        ),
    ),
    _FamilyRule(
        prefixes=("mistral", "mixtral"),
        family_label="Mistral",
        strengths="Capable general mid-size chat and summarisation.",
        best_for="llm_summary and llm_speaker_summary as a shared mid model.",
        notes="Fine default alternative; validate JSON action items on your hardware.",
    ),
    _FamilyRule(
        prefixes=("deepseek-r1", "deepseek"),
        family_label="DeepSeek",
        strengths="Reasoning-oriented; careful multi-step extraction.",
        best_for="Avoid for TranscriptX JSON modules; plain-text summaries only if needed.",
        notes=(
            "deepseek-r1 is a thinking model and often returns empty Ollama "
            "`response` under format=json. Prefer gemma3 / qwen2.5 / mistral."
        ),
    ),
    _FamilyRule(
        prefixes=("gpt-oss",),
        family_label="GPT-OSS",
        strengths="Large general local model; thinking-family behaviour.",
        best_for="Avoid for JSON modules; not recommended as a shared TranscriptX pick.",
        notes=(
            "Often leaves `response` empty with format=json. Prefer non-thinking "
            "mid/large tags for shared LLM runs."
        ),
    ),
)

_GENERIC_BY_SIZE: dict[SizeClass, tuple[str, str, str]] = {
    "tiny": (
        "Minimal capacity; mostly connectivity smoke.",
        "chart_descriptions only (if anything).",
        "Pull a mid-size non-thinking model (e.g. gemma3:12b or qwen2.5:7b) "
        "for real runs.",
    ),
    "small": (
        "Fast drafts on constrained hardware.",
        "chart_descriptions; short summaries when speed matters.",
        "Prefer mid+ for narrative_summary and llm_action_items.",
    ),
    "mid": (
        "Balanced local quality for transcript LLM work.",
        "All modules as a shared model.",
        "Good starting class — prefer gemma3 / qwen2.5 / mistral over thinking tags.",
    ),
    "large": (
        "Highest local fidelity; slower and heavier.",
        "narrative_summary, llm_summary, llm_action_items, group synthesis.",
        "Use smaller tags for short chart captions if latency matters.",
    ),
    "unknown": (
        "General local instruct model (size unknown).",
        "Try as shared model; validate JSON modules first.",
        "Prefer known non-thinking mid tags such as gemma3:12b when unsure.",
    ),
}


def infer_size_class(model_tag: str) -> SizeClass:
    """Infer a coarse size class from an Ollama tag like ``qwen3:8b``."""
    text = (model_tag or "").strip().lower()
    if not text:
        return "unknown"
    match = _SIZE_RE.search(text.replace(" ", ""))
    if match is None:
        return "unknown"
    value = float(match.group("size"))
    unit = match.group("unit").lower()
    billions = value if unit == "b" else value / 1000.0
    for ceiling, label in _SIZE_CLASS_BY_B:
        if billions < ceiling:
            return label
    return "unknown"


def _match_family(model_tag: str) -> _FamilyRule | None:
    base = (model_tag or "").strip().lower().split(":", 1)[0]
    for rule in _FAMILY_RULES:
        for prefix in rule.prefixes:
            if base == prefix or base.startswith(prefix):
                return rule
    return None


def guidance_for_model(model_tag: str) -> LlmModelGuidance:
    """Return guidance for one installed Ollama tag."""
    tag = (model_tag or "").strip()
    size = infer_size_class(tag)
    rule = _match_family(tag)
    if rule is None:
        strengths, best_for, notes = _GENERIC_BY_SIZE[size]
        return LlmModelGuidance(
            model=tag,
            size_class=size,
            strengths=strengths,
            best_for=best_for,
            notes=notes,
        )
    strengths, best_for, notes = rule.strengths, rule.best_for, rule.notes
    if rule.by_size and size in rule.by_size:
        strengths, best_for, notes = rule.by_size[size]
    return LlmModelGuidance(
        model=tag,
        size_class=size,
        strengths=strengths,
        best_for=best_for,
        notes=notes,
    )


def list_llm_model_guidance(
    installed_models: Sequence[str],
) -> list[LlmModelGuidance]:
    """Return guidance rows for installed tags (stable input order, de-duped)."""
    rows: list[LlmModelGuidance] = []
    seen: set[str] = set()
    for raw in installed_models:
        tag = (raw or "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        rows.append(guidance_for_model(tag))
    return rows
