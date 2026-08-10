"""Detector counts, diagnostics assembly, and generation logging."""

from __future__ import annotations

import json
from typing import List

from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.core.utils.logger import get_logger
from transcriptx.services.corrections_studio.candidate_generation_inputs import (
    GenerationInputs,
)
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (
    compute_fuzzy_skipped_reason,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateGenerationDiagnostics,
    DetectorCountsByKind,
)

logger = get_logger()


def detector_counts_sum(d: DetectorCountsByKind) -> int:
    return (
        d.memory_hit
        + d.acronym
        + d.consistency
        + d.fuzzy
        + d.ner_variant
        + d.manual
        + d.other
    )


def detector_counts_from_candidates(
    cands: List[EngineCandidate],
) -> DetectorCountsByKind:
    d = DetectorCountsByKind()
    for c in cands:
        k = str(c.kind)
        if k == "memory_hit":
            d.memory_hit += 1
        elif k == "acronym":
            d.acronym += 1
        elif k == "consistency":
            d.consistency += 1
        elif k == "fuzzy":
            d.fuzzy += 1
        elif k == "ner_variant":
            d.ner_variant += 1
        elif k == "manual":
            d.manual += 1
        else:
            d.other += 1
    return d


def build_diagnostics(
    inp: GenerationInputs,
    pre_dedupe: DetectorCountsByKind,
    total_pre: int,
    post_by_kind: DetectorCountsByKind,
    total_post: int,
) -> CandidateGenerationDiagnostics:
    fuzzy_named_count = len(inp.fuzzy_resolution.display_names_for_fuzzy)
    skipped = compute_fuzzy_skipped_reason(
        inp.fuzzy_enabled, inp.fuzzy_resolution, fuzzy_named_count
    )
    known_acronyms = (
        list(getattr(inp.corrections_config, "known_acronyms", []) or [])
        if inp.corrections_config
        else []
    )
    org_phrases = (
        getattr(inp.corrections_config, "known_org_phrases", {}) or {}
        if inp.corrections_config
        else {}
    )
    return CandidateGenerationDiagnostics(
        pre_dedupe=pre_dedupe,
        total_pre_dedupe=total_pre,
        post_dedupe_counts_by_kind=post_by_kind,
        total_after_dedupe=total_post,
        fuzzy_enabled=inp.fuzzy_enabled,
        fuzzy_similarity_threshold=inp.fuzzy_threshold,
        consistency_similarity_threshold=inp.consistency_threshold,
        known_acronym_count=len(known_acronyms),
        known_org_phrase_count=len(org_phrases),
        fuzzy_named_speaker_count=fuzzy_named_count,
        fuzzy_skipped_reason=skipped,
        observed_named_speaker_count=len(inp.fuzzy_resolution.observed_named_speakers),
    )


def log_generation(
    *,
    transcript_path: str,
    transcript_key: str,
    new_gen: int,
    inp: GenerationInputs,
    pre_dedupe: DetectorCountsByKind,
    total_pre: int,
    total_post: int,
    mh: str,
) -> None:
    fuzzy_named_count = len(inp.fuzzy_resolution.display_names_for_fuzzy)
    log_payload = {
        "event": "corrections_studio_generation",
        "transcript_path": transcript_path,
        "transcript_identity_hash": transcript_key[:16],
        "generation_id": new_gen,
        "pre_dedupe": pre_dedupe.model_dump(mode="json"),
        "total_pre_dedupe": total_pre,
        "total_after_dedupe": total_post,
        "fuzzy_enabled": inp.fuzzy_enabled,
        "fuzzy_named_speaker_count": fuzzy_named_count,
        "generation_manifest_hash_prefix": mh[:12],
    }
    logger.info("%s", json.dumps(log_payload, sort_keys=True))
