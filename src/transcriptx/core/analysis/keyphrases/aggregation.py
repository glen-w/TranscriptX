"""Group aggregation for keyphrases — pool by canonical_key (never concat-reparse)."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _min_member_sessions() -> int:
    try:
        from transcriptx.core.utils.config import get_config

        return int(get_config().analysis.keyphrases.min_member_sessions)
    except Exception:
        return 2


def aggregate_keyphrases(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    from transcriptx.core.analysis.aggregation.registry import (
        _extract_payload,
        _warning_payload_shape,
    )
    from transcriptx.core.analysis.aggregation.schema import get_transcript_id
    from transcriptx.core.analysis.keyphrases.contract import (
        SCHEMA_ID,
        SEMANTICS_VERSION,
    )
    from transcriptx.core.analysis.keyphrases.scoring import (
        min_max_weights,
        round_score,
    )

    pool: dict[str, dict[str, Any]] = {}
    session_rows: List[Dict[str, Any]] = []
    deferred_methods = ("yake", "keybert")

    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "keyphrases")
        if not payload:
            continue
        if not isinstance(payload, dict):
            return _warning_payload_shape(
                "keyphrases", ["global_by_method", "schema_id"]
            )
        if payload.get("schema_id") not in (None, SCHEMA_ID):
            continue
        member_id = str(get_transcript_id(result, transcript_set))
        gbm = payload.get("global_by_method") or {}
        nc = gbm.get("noun_chunks") if isinstance(gbm, dict) else None
        phrases = (nc or {}).get("phrases") if isinstance(nc, dict) else None
        phrase_count = len(phrases) if isinstance(phrases, list) else 0
        session_rows.append(
            {
                "transcript_id": member_id,
                "usable": payload.get("usable"),
                "evaluation_state": payload.get("evaluation_state"),
                "noun_chunk_phrase_count": phrase_count,
            }
        )
        if not isinstance(phrases, list):
            continue
        for phrase in phrases:
            if not isinstance(phrase, dict):
                continue
            key = str(phrase.get("canonical_key") or "").strip()
            if not key:
                continue
            entry = pool.setdefault(
                key,
                {
                    "canonical_key": key,
                    "display_counts": {},
                    "occurrence_count": 0,
                    "rank_weight_sum": 0.0,
                    "segment_support": 0,
                    "member_ids": set(),
                    "token_count": int(phrase.get("token_count") or 1),
                },
            )
            display = str(phrase.get("phrase") or key)
            entry["display_counts"][display] = (
                entry["display_counts"].get(display, 0) + 1
            )
            entry["occurrence_count"] += int(phrase.get("occurrence_count") or 0)
            entry["rank_weight_sum"] += float(phrase.get("rank_weight") or 0.0)
            entry["segment_support"] += int(phrase.get("segment_support") or 0)
            entry["member_ids"].add(member_id)
            entry["token_count"] = max(
                int(entry["token_count"]), int(phrase.get("token_count") or 1)
            )

    if not session_rows:
        return None

    min_sessions = _min_member_sessions()
    candidates: list[dict[str, Any]] = []
    for entry in pool.values():
        members = entry["member_ids"]
        if len(members) < min_sessions:
            continue
        counts = entry["display_counts"]
        display = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        candidates.append(
            {
                "phrase": display,
                "canonical_key": entry["canonical_key"],
                "token_count": int(entry["token_count"]),
                "raw_score": float(entry["rank_weight_sum"]),
                "occurrence_count": int(entry["occurrence_count"]),
                "segment_support": int(entry["segment_support"]),
                "member_session_support": len(members),
            }
        )

    weights = min_max_weights([c["raw_score"] for c in candidates])
    for cand, weight in zip(candidates, weights):
        cand["rank_weight"] = round_score(weight)
    candidates.sort(
        key=lambda c: (
            -c["rank_weight"],
            -c["occurrence_count"],
            -c["token_count"],
            c["canonical_key"],
        )
    )
    pooled_phrases = []
    for idx, cand in enumerate(candidates, start=1):
        pooled_phrases.append(
            {
                "phrase": cand["phrase"],
                "canonical_key": cand["canonical_key"],
                "token_count": cand["token_count"],
                "rank": idx,
                "rank_weight": cand["rank_weight"],
                "occurrence_count": cand["occurrence_count"],
                "segment_support": cand["segment_support"],
                "member_session_support": cand["member_session_support"],
                "raw_score": round_score(cand["raw_score"]),
                "score_direction": "higher_is_better",
            }
        )

    _ = canonical_speaker_map

    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "keyphrases_pooled": {
            "schema_id": SCHEMA_ID,
            "semantics_version": SEMANTICS_VERSION,
            "method": "noun_chunks",
            "pool_basis": "canonical_key_sum_rank_weight",
            "no_cross_session_span": True,
            "deferred_methods": list(deferred_methods),
            "phrases": pooled_phrases,
            "min_member_sessions": min_sessions,
        },
        "keyphrase_noun_chunk_pool": pooled_phrases,
    }
