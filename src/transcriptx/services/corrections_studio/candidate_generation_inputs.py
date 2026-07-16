"""Load generation inputs for Corrections Studio candidate generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from transcriptx.core.corrections.memory import load_memory
from transcriptx.core.corrections.models import CorrectionRule
from transcriptx.core.store.corrections_session_store import session_path_for_transcript
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.config import get_config
from transcriptx.io import load_segments
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver, SpeakerMapState
from transcriptx.services.corrections_studio.candidate_mapping import (
    db_rule_to_engine_rule,
)
from transcriptx.services.corrections_studio.fuzzy_speaker_inputs import (
    FuzzySpeakerNameResolution,
    resolve_fuzzy_speaker_inputs,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    load_speaker_map_state,
)
from transcriptx.services.corrections_studio.schema import StudioSessionDocument


@dataclass(frozen=True)
class GenerationInputs:
    segments: List[Dict[str, Any]]
    transcript_key: str
    corrections_config: Any
    memory: Any
    engine_rules: List[CorrectionRule]
    fuzzy_resolution: FuzzySpeakerNameResolution
    speaker_map_state: SpeakerMapState
    fuzzy_enabled: bool
    fuzzy_threshold: float
    consistency_threshold: float


def load_generation_inputs(
    transcript_path: str,
    doc: StudioSessionDocument,
    *,
    get_config_fn=None,
    load_segments_fn=None,
    load_memory_fn=None,
    resolve_fuzzy_fn=None,
    load_speaker_map_fn=None,
    db_rule_fn=None,
    compute_identity_hash_fn=None,
) -> GenerationInputs:
    _get_config = get_config_fn or get_config
    _load_segments = load_segments_fn or load_segments
    _load_memory = load_memory_fn or load_memory
    _resolve_fuzzy = resolve_fuzzy_fn or resolve_fuzzy_speaker_inputs
    _load_speaker_map = load_speaker_map_fn or load_speaker_map_state
    _db_rule = db_rule_fn or db_rule_to_engine_rule
    _identity = compute_identity_hash_fn or compute_transcript_identity_hash

    segments = _load_segments(transcript_path)
    transcript_key = _identity(segments)
    config = _get_config()
    corrections_config = getattr(config.analysis, "corrections", None)
    memory = _load_memory(
        transcript_path=transcript_path,
        transcript_decisions_path=str(session_path_for_transcript(transcript_path)),
    )
    engine_rules = [_db_rule(rule.model_dump()) for rule in memory.rules.values()]
    for sr in doc.rules.values():
        try:
            engine_rules.append(
                _db_rule(
                    {
                        "id": sr.rule_id,
                        "type": sr.rule_type,
                        "wrong": sr.wrong_variants,
                        "right": sr.replacement_text,
                        "scope": sr.scope,
                        "confidence": sr.confidence,
                        "auto_apply": sr.auto_apply,
                        "conditions_json": sr.conditions_json,
                        "is_person_name": sr.is_person_name,
                    }
                )
            )
        except Exception:
            continue
    fuzzy_resolution = _resolve_fuzzy(transcript_path, segments)
    speaker_map_state = _load_speaker_map(transcript_path)
    # Prefer identified display names on segments so occurrence labels (and LLM
    # context) show real speaker names instead of SPEAKER_00 placeholders.
    if speaker_map_state.has_sidecar and speaker_map_state.speaker_map:
        segments = SpeakerMapResolver().resolve_segments(segments, speaker_map_state)
    fuzzy_enabled = bool(
        corrections_config and getattr(corrections_config, "enable_fuzzy", False)
    )
    fuzzy_threshold = (
        float(getattr(corrections_config, "fuzzy_similarity_threshold", 0.85))
        if corrections_config
        else 0.85
    )
    consistency_threshold = (
        float(getattr(corrections_config, "consistency_similarity_threshold", 0.0))
        if corrections_config
        else 0.0
    )
    return GenerationInputs(
        segments=segments,
        transcript_key=transcript_key,
        corrections_config=corrections_config,
        memory=memory,
        engine_rules=engine_rules,
        fuzzy_resolution=fuzzy_resolution,
        speaker_map_state=speaker_map_state,
        fuzzy_enabled=fuzzy_enabled,
        fuzzy_threshold=fuzzy_threshold,
        consistency_threshold=consistency_threshold,
    )
