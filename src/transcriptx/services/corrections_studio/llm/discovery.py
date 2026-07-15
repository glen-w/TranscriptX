"""Soft-gated LLM discovery orchestration for Corrections Studio."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from transcriptx.core.analysis.llm_support.hashing import sha256_llm_request
from transcriptx.core.analysis.llm_support.prompts import build_bounded_user_prompt
from transcriptx.core.analysis.llm_support.runtime import (
    build_ollama_analysis_client,
    resolve_llm_runtime,
)
from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.core.llm.errors import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMModelMissingError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from transcriptx.core.llm.prompting import require_prompt_budget
from transcriptx.core.utils.logger import get_logger
from transcriptx.services.corrections_studio.llm import (
    CONTEXT_PACK_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from transcriptx.services.corrections_studio.llm.budgets import (
    DEFAULT_TRANSPORT_MAX_ATTEMPTS,
    BudgetTracker,
)
from transcriptx.services.corrections_studio.llm.chunking import build_segment_chunks
from transcriptx.services.corrections_studio.llm.contract import (
    SYSTEM_PROMPT,
    build_discovery_instruction,
    parse_discovery_json,
)
from transcriptx.services.corrections_studio.llm.context_pack import (
    build_context_pack,
    collect_repeated_capitalized_pairs,
)
from transcriptx.services.corrections_studio.llm.grounding import (
    ground_discovery_candidates,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateEvidence,
    EvidenceSignal,
    EvidenceStrength,
    LlmCandidateProvenance,
    LlmGenerationDiagnostics,
)

logger = get_logger()

_CODED_LLM_ERRORS = (
    LLMTimeoutError,
    LLMUnavailableError,
    LLMResponseError,
    LLMGenerationError,
    LLMModelMissingError,
    LLMConfigurationError,
)


@dataclass
class LlmDiscoveryResult:
    candidates: List[EngineCandidate]
    diagnostics: LlmGenerationDiagnostics
    provenance_by_index: List[Optional[LlmCandidateProvenance]]
    evidence_by_index: List[Optional[CandidateEvidence]]
    llm_fingerprint_material: Dict[str, Any]
    endpoint_is_local: bool = True


def _soft_gate_enabled(llm_cfg: Any, corrections_llm: Any) -> bool:
    if corrections_llm is None or not getattr(corrections_llm, "enabled", False):
        return False
    if llm_cfg is None or not getattr(llm_cfg, "enabled", False):
        return False
    provider = (getattr(llm_cfg, "provider", None) or "null").strip().lower()
    return provider == "ollama"


def _endpoint_is_local(base_url: str) -> bool:
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except Exception:
        return True
    # host.docker.internal is the Docker Desktop bridge to host Ollama.
    return host in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _error_code(exc: BaseException) -> str:
    return getattr(exc, "error_code", None) or type(exc).__name__


def _empty_fingerprint_material(corrections_llm: Any) -> Dict[str, Any]:
    return {
        "model": "",
        "effort": (
            getattr(corrections_llm, "effort", "low") if corrections_llm else "low"
        ),
        "chunk_max_segments": (
            getattr(corrections_llm, "chunk_max_segments", 40)
            if corrections_llm
            else 40
        ),
        "chunk_overlap_segments": (
            getattr(corrections_llm, "chunk_overlap_segments", 4)
            if corrections_llm
            else 4
        ),
        "max_candidates_per_chunk": (
            getattr(corrections_llm, "max_candidates_per_chunk", 10)
            if corrections_llm
            else 10
        ),
        "max_candidates_per_transcript": (
            getattr(corrections_llm, "max_candidates_per_transcript", 80)
            if corrections_llm
            else 80
        ),
        "max_chunks": (
            getattr(corrections_llm, "max_chunks", 25) if corrections_llm else 25
        ),
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "context_pack_version": CONTEXT_PACK_VERSION,
        "assess_deterministic": (
            bool(getattr(corrections_llm, "assess_deterministic", False))
            if corrections_llm
            else False
        ),
    }


def _run_llm_discovery_inner(
    *,
    segments: Sequence[Dict[str, Any]],
    transcript_key: str,
    llm_cfg: Any,
    corrections_llm: Any,
    speaker_names: Sequence[str],
    memory_pairs: Sequence[tuple[str, str]],
    known_acronyms: Sequence[str],
    known_org_phrases: Dict[str, List[str]],
    empty_fp: Dict[str, Any],
    local: bool,
    diag: LlmGenerationDiagnostics,
) -> LlmDiscoveryResult:
    continue_on_failure = bool(getattr(corrections_llm, "continue_on_failure", True))

    effort = str(getattr(corrections_llm, "effort", "low") or "low")
    runtime = resolve_llm_runtime(llm_cfg=llm_cfg, effort=effort)
    req_timeout = float(getattr(corrections_llm, "request_timeout_seconds", 120.0))
    runtime = replace(runtime, request_timeout=req_timeout)
    empty_fp["model"] = runtime.model
    empty_fp["effort"] = runtime.effort

    client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime)
    if not client.is_available():
        diag.outcome = "unavailable"
        diag.error_code = "llm_unavailable"
        return LlmDiscoveryResult(
            candidates=[],
            diagnostics=diag,
            provenance_by_index=[],
            evidence_by_index=[],
            llm_fingerprint_material=empty_fp,
            endpoint_is_local=local,
        )
    diag.available = True

    budget = BudgetTracker.start(
        request_timeout_seconds=req_timeout,
        total_wall_clock_seconds=float(
            getattr(corrections_llm, "total_wall_clock_seconds", 180.0)
        ),
        max_chunks=int(getattr(corrections_llm, "max_chunks", 25)),
        # Interactive path: keep total retries within remaining wall by
        # apportioning per-attempt timeout across transport retries.
        transport_max_attempts=DEFAULT_TRANSPORT_MAX_ATTEMPTS,
    )
    chunks = build_segment_chunks(
        list(segments),
        chunk_max_segments=int(getattr(corrections_llm, "chunk_max_segments", 40)),
        chunk_overlap_segments=int(
            getattr(corrections_llm, "chunk_overlap_segments", 4)
        ),
        max_chunks=int(getattr(corrections_llm, "max_chunks", 25)),
    )
    diag.chunks_total = len(chunks)
    max_per_chunk = int(getattr(corrections_llm, "max_candidates_per_chunk", 10))
    max_total = int(getattr(corrections_llm, "max_candidates_per_transcript", 80))

    context = build_context_pack(
        speaker_names=speaker_names,
        memory_pairs=memory_pairs,
        known_acronyms=known_acronyms,
        known_org_phrases=known_org_phrases,
        repeated_forms=collect_repeated_capitalized_pairs(segments),
    )
    instruction = build_discovery_instruction(max_candidates=max_per_chunk)
    try:
        require_prompt_budget(
            max_input_chars=runtime.max_input_chars,
            instruction=instruction + "\n" + context,
            module_name="corrections_llm",
        )
    except Exception:
        logger.info("corrections_llm_prompt_budget_warning; continuing")

    run_id = str(uuid.uuid4())
    all_cands: List[EngineCandidate] = []
    provenances: List[Optional[LlmCandidateProvenance]] = []
    evidences: List[Optional[CandidateEvidence]] = []
    temperature = float(getattr(llm_cfg, "default_temperature", 0.0) or 0.0)

    for chunk in chunks:
        if len(all_cands) >= max_total:
            diag.budget_reason = diag.budget_reason or "max_candidates_per_transcript"
            break
        ok, reason = budget.can_start_chunk()
        if not ok:
            diag.budget_reason = reason
            # Design §D6: budget exhaustion is partial even with zero candidates.
            diag.outcome = "partial"
            break
        per_timeout = budget.note_chunk_started()
        runtime_chunk = replace(runtime, request_timeout=per_timeout)
        client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime_chunk)

        lines = []
        for abs_i in chunk.segment_indices:
            seg = segments[abs_i]
            speaker = seg.get("speaker") or "?"
            text = str(seg.get("text") or "")
            lines.append(f"[{abs_i}] {speaker}: {text}")
        transcript_block = "\n".join(lines)
        user_prompt, _trunc = build_bounded_user_prompt(
            instruction=instruction + "\n\nCONTEXT:\n" + context,
            transcript_block=transcript_block,
            max_input_chars=runtime.max_input_chars,
        )
        req_hash = sha256_llm_request(user_prompt, system_prompt=SYSTEM_PROMPT)
        try:
            raw = client.generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=runtime.max_output_tokens,
            )
            parsed = parse_discovery_json(raw)
            grounded = ground_discovery_candidates(
                parsed,
                segments=list(segments),
                transcript_key=transcript_key,
                chunk_segment_indices=chunk.segment_indices,
                max_per_chunk=max_per_chunk,
            )
            diag.chunks_succeeded += 1
            diag.candidates_raw += grounded.raw_count
            diag.candidates_rejected += grounded.rejected
            diag.candidates_grounded += len(grounded.accepted)
            for eng in grounded.accepted:
                if len(all_cands) >= max_total:
                    break
                all_cands.append(eng)
                provenances.append(
                    LlmCandidateProvenance(
                        llm_run_id=run_id,
                        prompt_version=PROMPT_VERSION,
                        schema_version=SCHEMA_VERSION,
                        model=runtime.model,
                        effort=runtime.effort,
                        llm_request_sha256=req_hash,
                        chunk_index=chunk.chunk_index,
                    )
                )
                evidences.append(
                    CandidateEvidence(
                        strength=EvidenceStrength.weak,
                        signals=[EvidenceSignal.model_suggestion],
                        rationale="",
                        review_priority="inspect",
                        model_certainty_label="tentative",
                    )
                )
            logger.info(
                "corrections_llm_chunk chunk=%s/%s grounded=%s rejected=%s",
                chunk.chunk_index + 1,
                diag.chunks_total,
                len(grounded.accepted),
                grounded.rejected,
            )
        except _CODED_LLM_ERRORS as exc:
            diag.chunks_failed += 1
            diag.error_code = _error_code(exc)
            logger.info(
                "corrections_llm_chunk_failed chunk=%s code=%s",
                chunk.chunk_index,
                diag.error_code,
            )
            if not continue_on_failure:
                diag.outcome = "failed"
                break
        except Exception:
            diag.chunks_failed += 1
            diag.error_code = "unexpected_error"
            logger.exception("corrections_llm_chunk_unexpected")
            if not continue_on_failure:
                diag.outcome = "failed"
                break

    if diag.outcome not in ("failed", "partial"):
        if diag.chunks_failed == 0 and diag.chunks_succeeded == diag.chunks_total:
            diag.outcome = "success"
        elif all_cands:
            diag.outcome = "partial"
        elif diag.available and diag.chunks_succeeded > 0:
            diag.outcome = "success"
        elif diag.chunks_failed > 0:
            diag.outcome = "failed"
        else:
            diag.outcome = "partial" if diag.budget_reason else "success"

    diag.candidates_after_merge = len(all_cands)
    return LlmDiscoveryResult(
        candidates=all_cands,
        diagnostics=diag,
        provenance_by_index=provenances,
        evidence_by_index=evidences,
        llm_fingerprint_material=empty_fp,
        endpoint_is_local=local,
    )


def run_llm_discovery(
    *,
    segments: Sequence[Dict[str, Any]],
    transcript_key: str,
    llm_cfg: Any,
    corrections_llm: Any,
    speaker_names: Sequence[str],
    memory_pairs: Sequence[tuple[str, str]],
    known_acronyms: Sequence[str],
    known_org_phrases: Dict[str, List[str]],
) -> LlmDiscoveryResult:
    empty_fp = _empty_fingerprint_material(corrections_llm)

    if not _soft_gate_enabled(llm_cfg, corrections_llm):
        return LlmDiscoveryResult(
            candidates=[],
            diagnostics=LlmGenerationDiagnostics(
                enabled=False, attempted=False, available=False, outcome="skipped"
            ),
            provenance_by_index=[],
            evidence_by_index=[],
            llm_fingerprint_material=empty_fp,
            endpoint_is_local=True,
        )

    local = _endpoint_is_local(str(getattr(llm_cfg, "base_url", "") or ""))
    diag = LlmGenerationDiagnostics(
        enabled=True, attempted=True, available=False, outcome="unavailable"
    )

    try:
        return _run_llm_discovery_inner(
            segments=segments,
            transcript_key=transcript_key,
            llm_cfg=llm_cfg,
            corrections_llm=corrections_llm,
            speaker_names=speaker_names,
            memory_pairs=memory_pairs,
            known_acronyms=known_acronyms,
            known_org_phrases=known_org_phrases,
            empty_fp=empty_fp,
            local=local,
            diag=diag,
        )
    except _CODED_LLM_ERRORS as exc:
        diag.outcome = "failed"
        diag.error_code = _error_code(exc)
        logger.info("corrections_llm_setup_failed code=%s", diag.error_code)
        return LlmDiscoveryResult(
            candidates=[],
            diagnostics=diag,
            provenance_by_index=[],
            evidence_by_index=[],
            llm_fingerprint_material=empty_fp,
            endpoint_is_local=local,
        )
    except Exception as exc:
        # Soft gate: never let setup/runtime errors kill deterministic generation.
        diag.outcome = "failed"
        diag.error_code = (
            _error_code(exc) if hasattr(exc, "error_code") else "unexpected_error"
        )
        logger.exception("corrections_llm_discovery_unexpected")
        return LlmDiscoveryResult(
            candidates=[],
            diagnostics=diag,
            provenance_by_index=[],
            evidence_by_index=[],
            llm_fingerprint_material=empty_fp,
            endpoint_is_local=local,
        )
