"""Single entry for building GenerationManifest (generation + live staleness)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Tuple

from transcriptx.core.corrections.memory import load_memory
from transcriptx.core.store.corrections_session_store import session_path_for_transcript
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.config import get_config
from transcriptx.io import load_segments
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver, SpeakerMapState
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (
    compute_speaker_map_fingerprint,
)
from transcriptx.services.corrections_studio.identity import (
    compute_generation_manifest_hash,
)
from transcriptx.services.corrections_studio.schema import (
    GenerationManifest,
    StalenessStatus,
    StudioRule,
    StudioSessionDocument,
)

STUDIO_DETECTOR_VERSION = "3"
CONTEXT_PACK_VERSION = "1"
LLM_PROMPT_VERSION = "corrections_discovery_v1"
LLM_SCHEMA_VERSION = "corrections_candidates_v1"


def corrections_config_fingerprint(corrections_config: Any) -> str:
    if corrections_config is None:
        return ""
    payload = {
        "acronyms": list(getattr(corrections_config, "known_acronyms", []) or []),
        "org_phrases": sorted(
            (getattr(corrections_config, "known_org_phrases", {}) or {}).keys()
        ),
        "consistency": getattr(
            corrections_config, "consistency_similarity_threshold", None
        ),
        "fuzzy": getattr(corrections_config, "fuzzy_similarity_threshold", None),
        "enable_fuzzy": getattr(corrections_config, "enable_fuzzy", False),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:32]


def memory_rule_fingerprint(memory: Any) -> str:
    ids = sorted((memory.rules or {}).keys())
    raw = ",".join(ids).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def studio_session_rules_fingerprint(rules: Dict[str, StudioRule]) -> str:
    """Canonical ordered representation; do not rely on dict iteration order."""
    items: list[dict[str, Any]] = []
    for rid in sorted(rules.keys()):
        r = rules[rid]
        items.append(
            {
                "rule_id": r.rule_id,
                "rule_type": r.rule_type,
                "wrong_variants": sorted(r.wrong_variants),
                "replacement_text": r.replacement_text,
                "scope": r.scope,
                "confidence": r.confidence,
                "auto_apply": r.auto_apply,
                "is_person_name": r.is_person_name,
            }
        )
    raw = json.dumps(items, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def load_speaker_map_state(transcript_path: str) -> SpeakerMapState:
    try:
        return SpeakerMapResolver().load_mapping(transcript_path)
    except Exception:
        return SpeakerMapState(has_sidecar=False)


def build_generation_manifest(
    *,
    transcript_identity_hash: str,
    corrections_config: Any,
    memory: Any,
    studio_rules: Dict[str, StudioRule],
    speaker_map_state: SpeakerMapState,
    detector_version: str,
    llm_fingerprint: str = "",
    llm_prompt_version: str = "",
    llm_schema_version: str = "",
    context_pack_version: str = "",
) -> GenerationManifest:
    sm_fp = ""
    if speaker_map_state.has_sidecar:
        sm_fp = compute_speaker_map_fingerprint(speaker_map_state)
    rules_fp = studio_session_rules_fingerprint(studio_rules)
    return GenerationManifest(
        transcript_identity_hash=transcript_identity_hash,
        corrections_config_fingerprint=corrections_config_fingerprint(
            corrections_config
        ),
        detector_version=detector_version,
        memory_rule_fingerprint=memory_rule_fingerprint(memory),
        speaker_map_fingerprint=sm_fp,
        studio_session_rules_fingerprint=rules_fp,
        llm_fingerprint=llm_fingerprint or "",
        llm_prompt_version=llm_prompt_version or "",
        llm_schema_version=llm_schema_version or "",
        context_pack_version=context_pack_version or "",
    )


def compute_llm_fingerprint(
    *,
    model: str,
    effort: str,
    chunk_max_segments: int,
    chunk_overlap_segments: int,
    max_candidates_per_chunk: int,
    max_candidates_per_transcript: int,
    max_chunks: int,
    prompt_version: str,
    schema_version: str,
    context_pack_version: str,
    assess_deterministic: bool,
) -> str:
    import hashlib

    payload = {
        "model": model,
        "effort": effort,
        "chunk_max_segments": chunk_max_segments,
        "chunk_overlap_segments": chunk_overlap_segments,
        "max_candidates_per_chunk": max_candidates_per_chunk,
        "max_candidates_per_transcript": max_candidates_per_transcript,
        "max_chunks": max_chunks,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "context_pack_version": context_pack_version,
        "assess_deterministic": assess_deterministic,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]


def compute_live_manifest_and_hash(
    doc: StudioSessionDocument,
) -> Tuple[GenerationManifest, str]:
    """Live manifest from current disk transcript, config, memory, maps, and session rules."""
    transcript_path = doc.transcript_path
    segments = load_segments(transcript_path)
    transcript_key = compute_transcript_identity_hash(segments)
    config = get_config()
    corrections_config = getattr(config.analysis, "corrections", None)
    memory = load_memory(
        transcript_path=transcript_path,
        transcript_decisions_path=str(session_path_for_transcript(transcript_path)),
    )
    speaker_state = load_speaker_map_state(transcript_path)

    llm_fp = ""
    llm_prompt_v = ""
    llm_schema_v = ""
    ctx_v = ""
    llm_cfg = getattr(config, "llm", None)
    corrections_llm = (
        getattr(corrections_config, "llm", None) if corrections_config else None
    )
    # Soft gate on → recompute fingerprint from live config so unchanged
    # LLM settings do not falsely stale the session. Soft gate off → empty
    # fields match deterministic generations.
    if (
        corrections_llm is not None
        and getattr(corrections_llm, "enabled", False)
        and llm_cfg is not None
        and getattr(llm_cfg, "enabled", False)
        and (getattr(llm_cfg, "provider", None) or "null").strip().lower() == "ollama"
    ):
        model = str(getattr(llm_cfg, "model", "") or "")
        llm_fp = compute_llm_fingerprint(
            model=model,
            effort=str(getattr(corrections_llm, "effort", "low") or "low"),
            chunk_max_segments=int(getattr(corrections_llm, "chunk_max_segments", 40)),
            chunk_overlap_segments=int(
                getattr(corrections_llm, "chunk_overlap_segments", 4)
            ),
            max_candidates_per_chunk=int(
                getattr(corrections_llm, "max_candidates_per_chunk", 10)
            ),
            max_candidates_per_transcript=int(
                getattr(corrections_llm, "max_candidates_per_transcript", 80)
            ),
            max_chunks=int(getattr(corrections_llm, "max_chunks", 25)),
            prompt_version=LLM_PROMPT_VERSION,
            schema_version=LLM_SCHEMA_VERSION,
            context_pack_version=CONTEXT_PACK_VERSION,
            assess_deterministic=bool(
                getattr(corrections_llm, "assess_deterministic", False)
            ),
        )
        llm_prompt_v = LLM_PROMPT_VERSION
        llm_schema_v = LLM_SCHEMA_VERSION
        ctx_v = CONTEXT_PACK_VERSION

    manifest = build_generation_manifest(
        transcript_identity_hash=transcript_key,
        corrections_config=corrections_config,
        memory=memory,
        studio_rules=doc.rules,
        speaker_map_state=speaker_state,
        detector_version=STUDIO_DETECTOR_VERSION,
        llm_fingerprint=llm_fp,
        llm_prompt_version=llm_prompt_v,
        llm_schema_version=llm_schema_v,
        context_pack_version=ctx_v,
    )
    return manifest, compute_generation_manifest_hash(manifest)


def evaluate_session_staleness(
    doc: StudioSessionDocument,
) -> Tuple[StalenessStatus, bool, bool]:
    """
    Returns (staleness_status, generation_inputs_stale, detector_version_stale).

    generation_inputs_stale: manifest hash or detector version differs from stored generation.
    detector_version_stale: stored detector_version != current STUDIO_DETECTOR_VERSION.
    """
    if not doc.current_generation:
        return StalenessStatus.ok, False, False

    try:
        live_manifest, live_hash = compute_live_manifest_and_hash(doc)
    except Exception:
        return StalenessStatus.stale_generation, True, True

    stored = doc.current_generation.generation_manifest
    stored_hash = doc.current_generation.generation_manifest_hash
    detector_stale = stored.detector_version != STUDIO_DETECTOR_VERSION
    manifest_stale = live_hash != stored_hash

    if live_manifest.transcript_identity_hash != doc.recorded_transcript_identity_hash:
        return StalenessStatus.incompatible_transcript, True, detector_stale

    if detector_stale or manifest_stale:
        return StalenessStatus.stale_generation, True, detector_stale

    return StalenessStatus.ok, False, False
