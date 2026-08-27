"""Static guidance for installed Ollama models (UI table).

Helps users pick a tag per LLM module. Matching is intentionally loose:
family/prefix + size-class heuristics, not a hard allow-list of tags.

Parameter / context / disk size come from the live Ollama ``/api/tags``
(and ``/api/show`` when needed). Producer and release month are filled from
a curated catalog keyed by tag family, optionally refined by the public
Ollama library page meta description when a fetcher is provided.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal, Mapping, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen

from transcriptx.core.llm.ollama_client import OllamaModelInfo

SizeClass = Literal["tiny", "small", "mid", "large", "unknown"]

LibraryMetaFetcher = Callable[[str], "LibraryMeta | None"]


@dataclass(frozen=True)
class LibraryMeta:
    """Optional metadata scraped/fetched from the public Ollama library."""

    producer: str | None = None
    released: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class LlmModelGuidance:
    model: str
    size_class: SizeClass
    strengths: str
    best_for: str
    notes: str
    parameters: str | None = None
    context_window: str | None = None
    producer: str | None = None
    released: str | None = None
    disk_size: str | None = None


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
_PARAM_SIZE_RE = re.compile(
    r"^\s*(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>[bmk])\s*$",
    re.IGNORECASE,
)
_PRODUCER_FROM_DESC_RE = re.compile(
    r"(?:released by|from|by)\s+([A-Z][A-Za-z0-9 .&'/+-]{1,48})",
    re.IGNORECASE,
)

# Approximate parameter budgets for transcript LLM work on local Ollama.
_SIZE_CLASS_BY_B: tuple[tuple[float, SizeClass], ...] = (
    (2.0, "tiny"),
    (5.0, "small"),
    (14.0, "mid"),
    (float("inf"), "large"),
)

# First matching prefix wins. Values are (producer, release YYYY-MM).
_CATALOG_BY_PREFIX: tuple[tuple[str, str, str], ...] = (
    ("qwen3-coder", "Alibaba", "2025-04"),
    ("qwen2.5-coder", "Alibaba", "2024-09"),
    ("qwen3-vl", "Alibaba", "2025-08"),
    ("qwen2.5vl", "Alibaba", "2025-01"),
    ("qwen3.8", "Alibaba", "2026-08"),
    ("qwen3.6", "Alibaba", "2026-04"),
    ("qwen3", "Alibaba", "2025-04"),
    ("qwen2.5", "Alibaba", "2024-09"),
    ("qwen2", "Alibaba", "2024-06"),
    ("devstral-small-2", "Mistral AI", "2025-12"),
    ("devstral", "Mistral AI", "2025-12"),
    ("gemma4", "Google", "2026-04"),
    ("gemma3", "Google", "2025-03"),
    ("gemma2", "Google", "2024-06"),
    ("gemma", "Google", "2024-02"),
    ("llama3.2-vision", "Meta", "2024-11"),
    ("llama3.2", "Meta", "2024-09"),
    ("llama3.1", "Meta", "2024-07"),
    ("llama3", "Meta", "2024-04"),
    ("llama2", "Meta", "2023-07"),
    ("llama", "Meta", "2023-02"),
    ("mistral-nemo", "Mistral AI", "2024-07"),
    ("mistral-small", "Mistral AI", "2025-03"),
    ("mistral-large", "Mistral AI", "2024-07"),
    ("mixtral", "Mistral AI", "2023-12"),
    ("mistral", "Mistral AI", "2023-09"),
    ("phi4", "Microsoft", "2024-12"),
    ("phi3", "Microsoft", "2024-04"),
    ("phi", "Microsoft", "2023-09"),
    ("command-r7b", "Cohere", "2024-12"),
    ("command-r", "Cohere", "2024-03"),
    ("command", "Cohere", "2024-03"),
    ("granite3.3", "IBM", "2025-04"),
    ("granite3.2-vision", "IBM", "2025-02"),
    ("granite3.2", "IBM", "2025-02"),
    ("granite3", "IBM", "2024-10"),
    ("granite", "IBM", "2024-05"),
    ("deepseek-ocr", "DeepSeek", "2025-10"),
    ("deepseek-r1", "DeepSeek", "2025-01"),
    ("deepseek", "DeepSeek", "2024-05"),
    ("gpt-oss", "OpenAI", "2025-08"),
    ("deepcoder", "Agentica", "2025-04"),
    ("glm-ocr", "Zhipu AI", "2025-08"),
    ("minicpm-v", "OpenBMB", "2024-05"),
    ("llava", "LLaVA", "2024-02"),
)

# Family strings returned by Ollama ``details.family`` (when tag prefix is vague).
_PRODUCER_BY_FAMILY: dict[str, str] = {
    "gemma4": "Google",
    "gemma3": "Google",
    "gemma2": "Google",
    "gemma": "Google",
    "llama": "Meta",
    "mllama": "Meta",
    "qwen2": "Alibaba",
    "qwen25vl": "Alibaba",
    "qwen3": "Alibaba",
    "qwen35": "Alibaba",
    "qwen3moe": "Alibaba",
    "qwen3vl": "Alibaba",
    "mistral3": "Mistral AI",
    "phi3": "Microsoft",
    "cohere2": "Cohere",
    "granite": "IBM",
    "glmocr": "Zhipu AI",
    "gptoss": "OpenAI",
}

_FAMILY_RULES: tuple[_FamilyRule, ...] = (
    _FamilyRule(
        prefixes=(
            "qwen3-coder",
            "qwen2.5-coder",
            "deepcoder",
            "devstral-small-2",
            "devstral",
        ),
        family_label="code specialist",
        strengths="Code generation and repair.",
        best_for="Not recommended for TranscriptX LLM modules.",
        notes="Prefer a general chat/instruct model for summaries and JSON extraction.",
    ),
    _FamilyRule(
        prefixes=(
            "qwen3-vl",
            "qwen2.5vl",
            "llama3.2-vision",
            "llava",
            "minicpm-v",
            "deepseek-ocr",
            "glm-ocr",
            "granite3.2-vision",
        ),
        family_label="vision / OCR",
        strengths="Multimodal vision or OCR specialist.",
        best_for="Not recommended for TranscriptX LLM modules.",
        notes=(
            "TranscriptX analysis is text-only — image input is unused. "
            "Prefer a text instruct model (gemma3, gemma4, qwen2.5, mistral)."
        ),
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
        prefixes=("qwen3.8",),
        family_label="Qwen3.8",
        strengths="Long-context Qwen3.5-class reasoning (thinking family).",
        best_for=(
            "Plain-text llm_summary / llm_speaker_summary only when you accept "
            "thinking-model quirks."
        ),
        notes=(
            "Thinking / vision-capable family: often leaves Ollama `response` "
            "empty under format=json — do not use for narrative_summary, "
            "llm_action_items, chart_descriptions, or group_llm_synthesis."
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
        prefixes=("gemma4",),
        family_label="Gemma 4",
        strengths=(
            "Frontier Gemma with long context and strong instruction following "
            "on larger tags."
        ),
        best_for=(
            "Shared text picks (gemma4:12b+) for narrative_summary, "
            "llm_action_items, and chart_descriptions when thinking is off."
        ),
        notes=(
            "Configurable thinking modes can leave Ollama `response` empty "
            "under format=json — prefer gemma3:12b when unsure. Multimodal "
            "tags are not used by TranscriptX."
        ),
        by_size={
            "small": (
                "Fast edge-class Gemma 4 (e.g. e4b).",
                "chart_descriptions; short drafts.",
                "Validate llm_action_items JSON before production use.",
            ),
            "mid": (
                "Strong structured output on text modules.",
                "All modules as a shared mid pick (e.g. gemma4:12b).",
                "Disable thinking for JSON consumers.",
            ),
            "large": (
                "Highest Gemma 4 fidelity; MoE or dense workstation tags.",
                "llm_summary, narrative_summary, llm_action_items, group synthesis.",
                "Heavier RAM/latency; confirm thinking is off for JSON modules.",
            ),
        },
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
                "Too small for reliable llm_action_items — upgrade to 12b/27b "
                "for long digests and meeting extracts.",
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
                "chart_descriptions only — not llm_action_items.",
                "Cannot reliably emit valid meeting-extract JSON; prefer mid+ "
                "(e.g. gemma3:12b).",
            ),
            "small": (
                "Quick overviews when hardware is constrained.",
                "chart_descriptions; short llm_summary — not llm_action_items.",
                "Often fails llm_action_items schema validation (empty extracts). "
                "Upgrade to mid+ for meeting extracts.",
            ),
            "mid": (
                "Competent shared model for most modules.",
                "llm_summary, llm_speaker_summary, chart_descriptions, "
                "llm_action_items.",
                "Strong non-thinking alternative to Qwen3 for JSON modules.",
            ),
            "large": (
                "Stronger long-form digests.",
                "llm_summary, narrative_summary, llm_action_items, "
                "group_llm_synthesis.",
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
            "meetings; ~7GB download. For llm_custom_qa, TranscriptX caps the "
            "citation corpus (~24k chars, meeting tail) — full-meeting dumps "
            "make NeMo skip questions and invent quotes."
        ),
    ),
    _FamilyRule(
        prefixes=("mistral-small",),
        family_label="Mistral Small",
        strengths=(
            "Higher-quality Mistral instruct (~22–24B class); non-thinking with "
            "strong structured output."
        ),
        best_for=(
            "Shared high-quality JSON + prose: narrative_summary, "
            "llm_action_items, llm_summary, group_llm_synthesis."
        ),
        notes=(
            "Step up from mistral-nemo / gemma3:12b when you want better digests "
            "without thinking-family tags. Heavier RAM/latency than mid 7–12B."
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
        prefixes=("phi4", "phi3", "phi"),
        family_label="Phi",
        strengths=(
            "Strong instruction following for size; non-thinking; usually solid "
            "JSON when prompted strictly."
        ),
        best_for=(
            "Shared mid pick for narrative_summary, llm_action_items, "
            "chart_descriptions, and llm_custom_qa (phi4 ~14B)."
        ),
        notes=(
            "Good alternative when gemma3/qwen2.5 are already installed. Tiny "
            "phi tags remain smoke-only — prefer phi4 for meeting extracts."
        ),
        by_size={
            "tiny": (
                "Minimal capacity.",
                "Local smoke only.",
                "Prefer phi4 / gemma3:12b for TranscriptX JSON modules.",
            ),
            "small": (
                "Fast drafts; limited meeting-extract fidelity.",
                "chart_descriptions; short summaries.",
                "Upgrade to phi4 for llm_action_items.",
            ),
        },
    ),
    _FamilyRule(
        prefixes=("command-r7b", "command-r", "command"),
        family_label="Command R",
        strengths=(
            "Cohere instruct oriented toward retrieval-style summarisation; "
            "non-thinking."
        ),
        best_for=(
            "llm_summary, llm_speaker_summary, narrative_summary; validate "
            "llm_action_items JSON on your hardware."
        ),
        notes=(
            "command-r7b (~7B) is a useful diversity pick beside gemma3/qwen2.5. "
            "Larger Command R tags exceed the usual mid local budget."
        ),
    ),
    _FamilyRule(
        prefixes=("granite3.3", "granite3.2", "granite3", "granite"),
        family_label="Granite",
        strengths=(
            "IBM instruct family; non-thinking mid tags with steady JSON " "behaviour."
        ),
        best_for=(
            "Shared mid alternative (e.g. granite3.3:8b) for llm_summary, "
            "chart_descriptions, and llm_action_items."
        ),
        notes=(
            "Complements Llama/Gemma libraries when you want another JSON-safe "
            "family without qwen3 thinking quirks."
        ),
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
        "Cannot handle llm_action_items. Pull a mid-size non-thinking model "
        "(e.g. gemma3:12b or qwen2.5:7b) for real runs.",
    ),
    "small": (
        "Fast drafts on constrained hardware.",
        "chart_descriptions; short summaries when speed matters.",
        "Not reliable for llm_action_items (schema drops → empty extracts). "
        "Prefer mid+ for narrative_summary and meeting extracts.",
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
        "Prefer known non-thinking mid tags such as gemma3:12b when unsure. "
        "Tiny/small tags often fail llm_action_items.",
    ),
}


def _billions_from_size_unit(value: float, unit: str) -> float:
    unit_l = unit.lower()
    if unit_l == "b":
        return value
    if unit_l == "m":
        return value / 1000.0
    if unit_l == "k":
        return value / 1_000_000.0
    return value


def _size_class_from_billions(billions: float) -> SizeClass:
    for ceiling, label in _SIZE_CLASS_BY_B:
        if billions < ceiling:
            return label
    return "unknown"


def parse_parameter_billions(parameter_size: str | None) -> float | None:
    """Parse Ollama ``parameter_size`` labels like ``7.2B`` / ``999.89M``."""
    if not parameter_size:
        return None
    match = _PARAM_SIZE_RE.match(parameter_size.strip())
    if match is None:
        return None
    return _billions_from_size_unit(float(match.group("size")), match.group("unit"))


def format_parameter_size(parameter_size: str | None) -> str | None:
    """Normalize parameter labels for the UI (``12.2B``, ``7.2B``, ``1B``)."""
    billions = parse_parameter_billions(parameter_size)
    if billions is None:
        text = (parameter_size or "").strip()
        return text or None
    if billions >= 0.95:
        if abs(billions - round(billions)) < 0.05:
            return f"{int(round(billions))}B"
        return f"{billions:.1f}".rstrip("0").rstrip(".") + "B"
    millions = billions * 1000.0
    if abs(millions - round(millions)) < 0.5:
        return f"{int(round(millions))}M"
    return f"{millions:.0f}M"


def format_context_window(tokens: int | None) -> str | None:
    if tokens is None or tokens <= 0:
        return None
    if tokens >= 1_000_000:
        value = tokens / 1_000_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}M"
    # Prefer binary-K for power-of-two windows (32_768 → 32K, 131_072 → 128K).
    kib = tokens / 1024
    if abs(kib - round(kib)) < 0.05:
        return f"{int(round(kib))}K"
    if tokens >= 1000:
        value = tokens / 1000
        if abs(value - round(value)) < 0.05:
            return f"{int(round(value))}K"
        return f"{value:.1f}".rstrip("0").rstrip(".") + "K"
    return str(tokens)


def format_disk_size(size_bytes: int | None) -> str | None:
    if size_bytes is None or size_bytes < 0:
        return None
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ("KB", "MB", "GB", "TB")
    value = float(size_bytes)
    for unit in units:
        value /= 1024.0
        if value < 1024.0 or unit == units[-1]:
            if value >= 100 or abs(value - round(value)) < 0.05:
                return f"{int(round(value))} {unit}"
            return f"{value:.1f} {unit}"
    return f"{size_bytes} B"


def format_released_month(yyyy_mm: str | None) -> str | None:
    """Format ``YYYY-MM`` as ``Mar 2025``."""
    text = (yyyy_mm or "").strip()
    if not text:
        return None
    try:
        dt = datetime.strptime(text, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        return text
    return dt.strftime("%b %Y")


def infer_size_class(
    model_tag: str,
    *,
    parameter_size: str | None = None,
) -> SizeClass:
    """Infer a coarse size class from an Ollama tag and/or ``parameter_size``."""
    text = (model_tag or "").strip().lower()
    if text:
        match = _SIZE_RE.search(text.replace(" ", ""))
        if match is not None:
            billions = _billions_from_size_unit(
                float(match.group("size")), match.group("unit")
            )
            return _size_class_from_billions(billions)
    from_params = parse_parameter_billions(parameter_size)
    if from_params is not None:
        return _size_class_from_billions(from_params)
    return "unknown"


def _model_base(model_tag: str) -> str:
    return (model_tag or "").strip().lower().split(":", 1)[0]


def _prefix_matches(base: str, prefix: str) -> bool:
    """Match a catalog/family prefix without ``llava``→``llama``-style collisions."""
    if base == prefix:
        return True
    if not base.startswith(prefix):
        return False
    suffix = base[len(prefix) :]
    if not suffix:
        return True
    return suffix[0] in ".-_/"


def _match_catalog(model_tag: str) -> tuple[str, str] | None:
    base = _model_base(model_tag)
    for prefix, producer, released in _CATALOG_BY_PREFIX:
        if _prefix_matches(base, prefix):
            return producer, released
    return None


def producer_for_model(
    model_tag: str,
    *,
    family: str | None = None,
) -> str | None:
    catalog = _match_catalog(model_tag)
    if catalog is not None:
        return catalog[0]
    fam = (family or "").strip().lower()
    if fam and fam in _PRODUCER_BY_FAMILY:
        return _PRODUCER_BY_FAMILY[fam]
    return None


def released_for_model(model_tag: str) -> str | None:
    catalog = _match_catalog(model_tag)
    if catalog is None:
        return None
    return format_released_month(catalog[1])


def _match_family(model_tag: str) -> _FamilyRule | None:
    base = _model_base(model_tag)
    for rule in _FAMILY_RULES:
        for prefix in rule.prefixes:
            if _prefix_matches(base, prefix):
                return rule
    return None


def guidance_for_model(
    model_tag: str,
    *,
    info: OllamaModelInfo | None = None,
    library_meta: LibraryMeta | None = None,
) -> LlmModelGuidance:
    """Return guidance for one installed Ollama tag."""
    tag = (model_tag or "").strip()
    parameter_size = info.parameter_size if info is not None else None
    size = infer_size_class(tag, parameter_size=parameter_size)
    rule = _match_family(tag)
    if rule is None:
        strengths, best_for, notes = _GENERIC_BY_SIZE[size]
    else:
        strengths, best_for, notes = rule.strengths, rule.best_for, rule.notes
        if rule.by_size and size in rule.by_size:
            strengths, best_for, notes = rule.by_size[size]

    producer = producer_for_model(tag, family=info.family if info is not None else None)
    released = released_for_model(tag)
    if library_meta is not None:
        if library_meta.producer:
            producer = library_meta.producer
        if library_meta.released:
            released = library_meta.released

    return LlmModelGuidance(
        model=tag,
        size_class=size,
        strengths=strengths,
        best_for=best_for,
        notes=notes,
        parameters=format_parameter_size(parameter_size),
        context_window=format_context_window(
            info.context_length if info is not None else None
        ),
        producer=producer,
        released=released,
        disk_size=format_disk_size(info.size_bytes if info is not None else None),
    )


def parse_library_html_meta(html: str) -> LibraryMeta | None:
    """Extract producer / description hints from an Ollama library HTML page."""
    if not html:
        return None
    desc_match = re.search(
        r'<meta\s+name="description"\s+content="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    description = desc_match.group(1).strip() if desc_match else None
    producer: str | None = None
    if description:
        prod_match = _PRODUCER_FROM_DESC_RE.search(description)
        if prod_match is not None:
            producer = prod_match.group(1).strip(" .,;")
            # Trim trailing clause fragments.
            for stop in (" updated", " designed", " built", " available"):
                idx = producer.lower().find(stop)
                if idx > 0:
                    producer = producer[:idx].strip(" .,;")
    if producer is None and description is None:
        return None
    return LibraryMeta(producer=producer, description=description)


def fetch_ollama_library_meta(
    model_tag: str,
    *,
    timeout: float = 3.0,
) -> LibraryMeta | None:
    """Soft-fetch public library metadata for a model base name. Never raises."""
    base = _model_base(model_tag)
    if not base:
        return None
    url = f"https://ollama.com/library/{quote(base)}"
    try:
        req = Request(url, headers={"User-Agent": "transcriptx-model-guidance/1.0"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed host
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — optional enrichment
        return None
    return parse_library_html_meta(raw)


def list_llm_model_guidance(
    installed_models: Sequence[str],
    *,
    infos: Sequence[OllamaModelInfo] | Mapping[str, OllamaModelInfo] | None = None,
    library_meta_by_base: Mapping[str, LibraryMeta] | None = None,
    library_fetcher: LibraryMetaFetcher | None = None,
) -> list[LlmModelGuidance]:
    """Return guidance rows for installed tags (stable input order, de-duped)."""
    info_map: dict[str, OllamaModelInfo] = {}
    if isinstance(infos, Mapping):
        info_map = {str(k): v for k, v in infos.items()}
    elif infos is not None:
        for row in infos:
            info_map[row.name] = row

    rows: list[LlmModelGuidance] = []
    seen: set[str] = set()
    library_cache: dict[str, LibraryMeta | None] = {}
    if library_meta_by_base:
        library_cache.update(dict(library_meta_by_base))

    for raw in installed_models:
        tag = (raw or "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        base = _model_base(tag)
        meta = library_cache.get(base)
        if base not in library_cache and library_fetcher is not None:
            meta = library_fetcher(tag)
            library_cache[base] = meta
        rows.append(
            guidance_for_model(
                tag,
                info=info_map.get(tag),
                library_meta=meta,
            )
        )
    return rows
