"""Static guidance for LLM-backed analysis consumers (UI table)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.analysis.llm_support.model_selection import (
    LLM_MODEL_CONSUMER_IDS,
)

LlmPhase = Literal["dag", "finalize"]


@dataclass(frozen=True)
class LlmModuleGuidance:
    consumer_id: str
    title: str
    description: str
    best_for: str
    phase: LlmPhase
    group_only: bool = False


LLM_MODULE_GUIDANCE: dict[str, LlmModuleGuidance] = {
    "narrative_summary": LlmModuleGuidance(
        consumer_id="narrative_summary",
        title="Narrative summary",
        description="Grounded executive narrative from the deterministic summary chain.",
        best_for=(
            "Readable executive briefs that must stay faithful to highlights/"
            "summary evidence already computed."
        ),
        phase="dag",
    ),
    "llm_summary": LlmModuleGuidance(
        consumer_id="llm_summary",
        title="LLM transcript summary",
        description="Abstractive summary of the full readable transcript text.",
        best_for=(
            "Whole-session overviews, meeting digests, and long-form condensation "
            "when you want a free-form narrative of the transcript."
        ),
        phase="dag",
    ),
    "llm_speaker_summary": LlmModuleGuidance(
        consumer_id="llm_speaker_summary",
        title="LLM speaker summaries",
        description="Abstractive summary per named speaker from that speaker's turns.",
        best_for=(
            "Speaker-centric briefs, interview write-ups, and comparing what each "
            "participant contributed (requires named speakers)."
        ),
        phase="dag",
    ),
    "llm_action_items": LlmModuleGuidance(
        consumer_id="llm_action_items",
        title="LLM action items",
        description="Structured action items (owner, deadline, status, quote) as JSON.",
        best_for=(
            "Extracting commitments, follow-ups, and task lists from meetings or "
            "working sessions."
        ),
        phase="dag",
    ),
    "chart_descriptions": LlmModuleGuidance(
        consumer_id="chart_descriptions",
        title="Chart descriptions",
        description="Per-chart LLM narratives written after charts exist (finalize).",
        best_for=(
            "Gallery captions and accessible chart explanations for overview/"
            "insight dashboards."
        ),
        phase="finalize",
    ),
    "group_llm_synthesis": LlmModuleGuidance(
        consumer_id="group_llm_synthesis",
        title="Group LLM synthesis",
        description=(
            "Cross-session rollup of member llm_summary / llm_speaker_summary texts."
        ),
        best_for=(
            "Group-level themes and synthesis across related transcripts "
            "(Group target only)."
        ),
        phase="finalize",
        group_only=True,
    ),
}


def list_llm_module_guidance(
    *,
    include_group: bool = True,
) -> list[LlmModuleGuidance]:
    """Return guidance rows in stable consumer order."""
    rows: list[LlmModuleGuidance] = []
    for consumer_id in LLM_MODEL_CONSUMER_IDS:
        row = LLM_MODULE_GUIDANCE.get(consumer_id)
        if row is None:
            continue
        if row.group_only and not include_group:
            continue
        rows.append(row)
    return rows
