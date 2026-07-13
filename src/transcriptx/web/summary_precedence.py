"""
Primary summary resolution with explicit precedence to avoid duplicate heroes.

Precedence (first successful wins):
1. llm_summary
2. narrative_summary
3. deterministic executive summary (summary module)
4. quiet unavailable
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from transcriptx.web.run_health_presentation import module_outcome_state

SummaryKind = Literal["llm_summary", "narrative_summary", "executive_summary"]


class _SummaryLoader(Protocol):
    def load_text(
        self, module: str, suffix: str, *, instance_id: str | None = None
    ) -> str | None: ...

    def load_json(
        self, module: str, suffix: str, *, instance_id: str | None = None
    ) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class SummaryCandidate:
    kind: SummaryKind
    module: str
    title: str
    markdown: str | None
    payload: dict[str, Any] | None
    available: bool
    outcome: str
    empty_hint: str
    artifact_stem: str
    text_field: str


@dataclass(frozen=True)
class PrimarySummaryResult:
    primary: SummaryCandidate | None
    others: tuple[SummaryCandidate, ...]
    unavailable_message: str = "Summary was unavailable for this run."


def _candidate_from_loader(
    loader: _SummaryLoader,
    *,
    kind: SummaryKind,
    module: str,
    title: str,
    artifact_stem: str,
    text_field: str,
    empty_hint: str,
    run_root: Path | None,
    run_results: dict[str, Any] | None,
) -> SummaryCandidate:
    md = loader.load_text(module, f"{artifact_stem}.md")
    payload = loader.load_json(module, f"{artifact_stem}.json")
    # Executive: md or any json counts as available content
    if kind == "executive_summary":
        available = bool(md) or bool(payload)
    else:
        available = bool(md) or bool(payload and payload.get(text_field))
        if not available and payload and not payload.get(text_field):
            # Raw payload without expected field — treat as available for display
            available = bool(payload)

    outcome = module_outcome_state(run_root, module, run_results=run_results)
    return SummaryCandidate(
        kind=kind,
        module=module,
        title=title,
        markdown=md,
        payload=payload,
        available=available and outcome != "failed",
        outcome=outcome,
        empty_hint=empty_hint,
        artifact_stem=artifact_stem,
        text_field=text_field,
    )


def resolve_primary_summary(
    loader: _SummaryLoader | None,
    *,
    run_root: Path | None = None,
    run_results: dict[str, Any] | None = None,
) -> PrimarySummaryResult:
    if loader is None:
        return PrimarySummaryResult(primary=None, others=())

    specs: list[tuple[SummaryKind, str, str, str, str, str]] = [
        (
            "llm_summary",
            "llm_summary",
            "LLM Transcript Summary",
            "_llm_summary",
            "summary",
            "Run the `llm_summary` module (with LLM enabled) to populate this view.",
        ),
        (
            "narrative_summary",
            "narrative_summary",
            "Narrative Summary",
            "_narrative_summary",
            "narrative",
            "Run the `narrative_summary` module (with LLM enabled) to populate this view.",
        ),
        (
            "executive_summary",
            "summary",
            "Executive Summary",
            "_summary",
            "summary",
            "Run the `summary` module to populate this view.",
        ),
    ]

    candidates: list[SummaryCandidate] = []
    for kind, module, title, stem, field, hint in specs:
        candidates.append(
            _candidate_from_loader(
                loader,
                kind=kind,
                module=module,
                title=title,
                artifact_stem=stem,
                text_field=field,
                empty_hint=hint,
                run_root=run_root,
                run_results=run_results,
            )
        )

    primary: SummaryCandidate | None = None
    others: list[SummaryCandidate] = []
    for cand in candidates:
        if primary is None and cand.available:
            primary = cand
        elif cand.available or cand.outcome in {"failed", "skipped", "blocked"}:
            others.append(cand)
        elif cand.payload or cand.markdown:
            others.append(cand)

    return PrimarySummaryResult(primary=primary, others=tuple(others))


def quiet_unavailable_message(
    label: str,
    *,
    outcome: str | None = None,
) -> str:
    if outcome == "failed":
        return f"{label} were unavailable for this run."
    if outcome == "skipped":
        return f"{label} were skipped for this run."
    if outcome == "blocked":
        return f"{label} were blocked for this run."
    return f"{label} were unavailable for this run."
