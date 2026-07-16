"""Deterministic detector runs and pre-dedupe aggregates."""

from __future__ import annotations

from typing import List, Tuple

from transcriptx.core.corrections.detect import (
    detect_acronym_candidates,
    detect_consistency_candidates,
    detect_fuzzy_candidates,
    detect_memory_hits,
)
from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.services.corrections_studio.candidate_diagnostics import (
    detector_counts_from_candidates,
)
from transcriptx.services.corrections_studio.candidate_generation_inputs import (
    GenerationInputs,
)
from transcriptx.services.corrections_studio.schema import DetectorCountsByKind


def run_detectors(
    inp: GenerationInputs,
    *,
    detect_memory_hits_fn=None,
    detect_acronym_fn=None,
    detect_consistency_fn=None,
    detect_fuzzy_fn=None,
) -> Tuple[
    List[EngineCandidate],
    List[EngineCandidate],
    List[EngineCandidate],
    List[EngineCandidate],
]:
    _mem = detect_memory_hits_fn or detect_memory_hits
    _ac = detect_acronym_fn or detect_acronym_candidates
    _co = detect_consistency_fn or detect_consistency_candidates
    _fz = detect_fuzzy_fn or detect_fuzzy_candidates
    mem_hits = _mem(inp.segments, inp.transcript_key, inp.engine_rules)
    ac: List[EngineCandidate] = []
    co: List[EngineCandidate] = []
    fz: List[EngineCandidate] = []
    if inp.corrections_config:
        ac = _ac(
            inp.segments,
            inp.transcript_key,
            inp.corrections_config.known_acronyms,
            inp.corrections_config.known_org_phrases,
        )
        co = _co(
            inp.segments,
            inp.transcript_key,
            inp.corrections_config.consistency_similarity_threshold,
        )
        fz = _fz(
            inp.segments,
            inp.transcript_key,
            list(inp.fuzzy_resolution.display_names_for_fuzzy),
            inp.fuzzy_threshold,
            inp.fuzzy_enabled,
        )
    return mem_hits, ac, co, fz


def pre_dedupe_aggregate(
    mem_hits: List[EngineCandidate],
    ac: List[EngineCandidate],
    co: List[EngineCandidate],
    fz: List[EngineCandidate],
) -> Tuple[DetectorCountsByKind, int]:
    pre_mem = detector_counts_from_candidates(mem_hits)
    pre_ac = detector_counts_from_candidates(ac)
    pre_co = detector_counts_from_candidates(co)
    pre_fz = detector_counts_from_candidates(fz)
    pre_dedupe = DetectorCountsByKind(
        memory_hit=pre_mem.memory_hit,
        acronym=pre_ac.acronym,
        consistency=pre_co.consistency,
        fuzzy=pre_fz.fuzzy,
        ner_variant=pre_mem.ner_variant
        + pre_ac.ner_variant
        + pre_co.ner_variant
        + pre_fz.ner_variant,
        other=pre_mem.other + pre_ac.other + pre_co.other + pre_fz.other,
    )
    total_pre = len(mem_hits) + len(ac) + len(co) + len(fz)
    return pre_dedupe, total_pre
