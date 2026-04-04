"""
Report renderer: report.md (primary) and report.txt (plain-text linearized from MD).

Uses stable section ordering; sections appear only when report_contribution_status
is full_section (sufficient canonical input). One renderer produces MD; one converter
produces TXT from MD to prevent drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

from transcriptx.core.analysis.stats.report_input_resolver import (
    REPORT_CONTRIBUTION_MENTION_ONLY,
)


@dataclass(frozen=True)
class SectionSpec:
    """Spec for one report section: name, source module(s), render priority."""

    name: str
    module: str
    priority: str = "normal"  # "always_prominent" | "normal" | "mention_only"


# Stable section order: renderer respects this order; missing sections are skipped.
# Order: header/speakers first (always prominent), then module-driven sections.
SECTION_ORDER: tuple[str, ...] = (
    "header",
    "speakers",
    "sentiment",
    "emotion",
    "acts",
    "interactions",
    "ner",
    "entity_sentiment",
    "conversation_loops",
    "contagion",
    "temporal_dynamics",
    "pauses",
    "momentum",
    "highlights",
    "summary",
    "tics",
    "understandability",
    "wordclouds",
    "affect_tension",
    "additional_outputs",
    "warnings",
    "footer",
)


def _render_section_content(
    module_id: str, section_payload: Dict[str, Any]
) -> List[str]:
    """Render a short summary from section_payload (module-specific or generic)."""
    lines: List[str] = []
    if not section_payload:
        return lines
    # Module-specific brief rendering
    if module_id == "sentiment":
        c = section_payload.get("mean_compound")
        if c is not None:
            lines.append(f"- Mean compound sentiment: {c:.3f}")
    elif module_id == "emotion":
        dom = section_payload.get("dominant_emotion")
        if dom:
            lines.append(f"- Dominant emotion: {dom}")
    elif module_id == "acts":
        counts = section_payload.get("act_counts") or {}
        if counts:
            top = sorted(counts.items(), key=lambda x: -x[1])[:5]
            lines.append(
                "- Top dialogue acts: " + ", ".join(f"{k} ({v})" for k, v in top)
            )
    elif module_id == "summary":
        brief = section_payload.get("brief") or section_payload.get("summary")
        if brief:
            lines.append(f"- {brief[:500]}" + ("..." if len(str(brief)) > 500 else ""))
    else:
        # Generic: show first few keys
        for k, v in list(section_payload.items())[:5]:
            if (
                v is not None
                and not isinstance(v, (dict, list))
                or (isinstance(v, (dict, list)) and v)
            ):
                lines.append(f"- {k}: {v}")
    return lines


def render_report_md(payload: Dict[str, Any]) -> str:
    """
    Render report.v1 payload to markdown (primary human-readable report).

    Respects stable section order; only includes sections where the resolver
    found sufficient canonical input (full_section). No placeholder text.
    """
    meta = payload.get("meta", {})
    overview = payload.get("overview", {})
    modules = payload.get("modules", {})
    report_summary_index = payload.get("report_summary_index", [])
    speakers = payload.get("speakers", [])
    warnings = payload.get("warnings", [])
    run_id = meta.get("run_id", "")

    full_section_modules = {
        e["source_modules"][0] for e in report_summary_index if e.get("source_modules")
    }
    mention_only_modules = [
        mid
        for mid, m in modules.items()
        if m.get("report_contribution_status") == REPORT_CONTRIBUTION_MENTION_ONLY
    ]

    lines: List[str] = []

    # --- Header (always prominent) ---
    lines.append(f"# Report: {meta.get('base_name', '')}")
    lines.append("")
    lines.append(f"Generated: {meta.get('generated_at', '')}")
    if run_id:
        lines.append(f"Run ID: {run_id}")
    lines.append(
        f"Duration: {overview.get('total_duration_sec', 0):.0f}s | "
        f"Words: {overview.get('total_words', 0)} | "
        f"Speakers: {overview.get('speaker_count_named', 0)}"
    )
    lines.append("")

    # --- Speakers (always prominent when present) ---
    if speakers:
        lines.append("## Speaker breakdown")
        lines.append("")
        for s in speakers:
            name = s.get("name", "")
            words = s.get("words", 0)
            pct = s.get("pct_total_words", 0) * 100
            dur = s.get("duration_hhmmss", "")
            wpm = s.get("words_per_min", 0)
            lines.append(
                f"- **{name}**: {words} words ({pct:.0f}%), {dur}, {wpm:.0f} wpm"
            )
        lines.append("")

    # --- Module sections in stable order (skip if not full_section) ---
    section_titles = {
        "sentiment": "Sentiment",
        "emotion": "Emotional tone",
        "acts": "Dialogue acts",
        "interactions": "Speaker dynamics",
        "ner": "Named entities",
        "entity_sentiment": "Entity framing",
        "conversation_loops": "Conversation loops",
        "contagion": "Contagion",
        "temporal_dynamics": "Temporal dynamics",
        "pauses": "Pauses",
        "momentum": "Momentum",
        "highlights": "Highlights",
        "summary": "Executive summary",
        "tics": "Verbal tics",
        "understandability": "Understandability",
        "wordclouds": "Word frequency",
        "affect_tension": "Affect tension",
    }
    for module_id in SECTION_ORDER:
        if module_id in (
            "header",
            "speakers",
            "additional_outputs",
            "warnings",
            "footer",
        ):
            continue
        if module_id not in full_section_modules:
            continue
        mod = modules.get(module_id, {})
        section_payload = mod.get("section_payload")
        title = section_titles.get(module_id, module_id.replace("_", " ").title())
        lines.append(f"## {title}")
        lines.append("")
        block = _render_section_content(module_id, section_payload or {})
        if block:
            lines.extend(block)
        else:
            lines.append("- Summary available in report.json.")
        lines.append("")

    # --- Additional outputs (mention_only) ---
    if mention_only_modules:
        lines.append("## Additional outputs available")
        lines.append("")
        lines.append(
            "The following modules produced outputs that are not summarized in this report:"
        )
        for mid in sorted(mention_only_modules):
            lines.append(f"- {mid}")
        lines.append("")

    # --- Warnings ---
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append(
        f"Generated by TranscriptX | Run ID: {run_id} | Full artifact index: manifest.json"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def md_to_txt(md_text: str) -> str:
    """
    Convert markdown to plain text (linearized, no markdown syntax).

    Single converter from MD → TXT; not a separate renderer. Prevents drift.
    """
    if not md_text:
        return ""
    text = md_text

    # Headers: ## X -> X with underline
    def replace_header(match: re.Match) -> str:
        level = len(match.group(1))
        title = match.group(2).strip()
        if level == 1:
            return title + "\n" + "=" * min(len(title), 60) + "\n\n"
        return title + "\n" + "-" * min(len(title), 60) + "\n\n"

    text = re.sub(r"^(#{1,6})\s+(.+)$", replace_header, text, flags=re.MULTILINE)
    # **bold** -> plain
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Lists: keep - and bullets
    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
