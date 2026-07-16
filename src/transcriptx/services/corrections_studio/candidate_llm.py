"""Soft-gated LLM discovery, annotation, and cross-kind merge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.services.corrections_studio.candidate_generation_inputs import (
    GenerationInputs,
)
from transcriptx.services.corrections_studio.llm.discovery import (
    LlmDiscoveryResult,
    run_llm_discovery,
)
from transcriptx.services.corrections_studio.llm.merge import (
    AnnotatedCandidate,
    annotate_engine_candidates,
    cross_kind_merge,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateSource,
    LlmGenerationDiagnostics,
)

logger = get_logger()


@dataclass
class LlmMergeResult:
    merged: List[AnnotatedCandidate]
    conflicts: int
    llm_result: LlmDiscoveryResult
    llm_diag: LlmGenerationDiagnostics


def run_soft_gated_discovery_and_merge(
    inp: GenerationInputs,
    det_annotated: List[AnnotatedCandidate],
    *,
    get_config_fn=None,
) -> LlmMergeResult:
    _get_config = get_config_fn or get_config
    config = _get_config()
    llm_cfg = getattr(config, "llm", None)
    corrections_llm = (
        getattr(inp.corrections_config, "llm", None) if inp.corrections_config else None
    )
    memory_pairs = [
        (",".join(r.wrong), r.right)
        for r in inp.engine_rules
        if getattr(r, "wrong", None)
    ]
    speaker_names = list(inp.fuzzy_resolution.display_names_for_fuzzy)
    known_acronyms = (
        list(getattr(inp.corrections_config, "known_acronyms", []) or [])
        if inp.corrections_config
        else []
    )
    org_phrases = (
        dict(getattr(inp.corrections_config, "known_org_phrases", {}) or {})
        if inp.corrections_config
        else {}
    )
    try:
        llm_result = run_llm_discovery(
            segments=inp.segments,
            transcript_key=inp.transcript_key,
            llm_cfg=llm_cfg,
            corrections_llm=corrections_llm,
            speaker_names=speaker_names,
            memory_pairs=memory_pairs,
            known_acronyms=known_acronyms,
            known_org_phrases=org_phrases,
        )
    except Exception:
        logger.exception("corrections_llm_discovery_call_site_guard")
        llm_result = LlmDiscoveryResult(
            candidates=[],
            diagnostics=LlmGenerationDiagnostics(
                enabled=bool(
                    corrections_llm and getattr(corrections_llm, "enabled", False)
                ),
                attempted=True,
                available=False,
                outcome="failed",
                error_code="unexpected_error",
            ),
            provenance_by_index=[],
            evidence_by_index=[],
            llm_fingerprint_material={},
        )
    llm_annotated = annotate_engine_candidates(
        llm_result.candidates,
        default_source=CandidateSource.llm_discovery,
    )
    for i, ann in enumerate(llm_annotated):
        if i < len(llm_result.evidence_by_index) and llm_result.evidence_by_index[i]:
            ann.evidence = llm_result.evidence_by_index[i]

    rules_by_id = {r.id: r for r in inp.engine_rules if r.id}
    merged, conflicts = cross_kind_merge(
        det_annotated + llm_annotated, rules_by_id=rules_by_id
    )
    llm_diag = llm_result.diagnostics
    llm_diag.overlapping_conflicts = conflicts
    llm_diag.candidates_after_merge = len(
        [a for a in merged if CandidateSource.llm_discovery in a.sources]
    )
    return LlmMergeResult(
        merged=merged,
        conflicts=conflicts,
        llm_result=llm_result,
        llm_diag=llm_diag,
    )
