"""Group aggregation for transcript_quality (ASR confidence)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.rows import _session_row_base
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


def _extract_tq_payload(
    module_results: Dict[str, Any], module_id: str
) -> Optional[Dict[str, Any]]:
    raw = module_results.get(module_id)
    if not isinstance(raw, dict):
        return None
    if "asr_confidence" in raw:
        return raw
    nested = raw.get("results")
    if isinstance(nested, dict) and "asr_confidence" in nested:
        return nested
    return raw


def _session_base(
    result: PerTranscriptResult, transcript_set: TranscriptSet
) -> Dict[str, Any]:
    return _session_row_base(result, transcript_set)


def aggregate_transcript_quality(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: Any,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """
    Provenance-aware weighted aggregation for ASR confidence.

    Members with different ``provenance.comparable_key`` are not pooled together.
    Within a cohort:
      coverage = sum(scored) / sum(eligible)
      mean_score = sum(mean_i * scored_i) / sum(scored_i)
      low_score_ratio = sum(low_score_words) / sum(scored)
    """
    del canonical_speaker_map  # unused; signature matches AggregationFn
    session_rows: List[Dict[str, Any]] = []
    cohorts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for result in per_transcript_results:
        payload = _extract_tq_payload(result.module_results, "transcript_quality")
        if not payload:
            continue
        asr = payload.get("asr_confidence") or {}
        provenance = payload.get("provenance") or {}
        if not isinstance(asr, dict):
            continue
        row = _session_base(result, transcript_set)
        comparable_key = str(provenance.get("comparable_key") or "")
        row.update(
            {
                "status": asr.get("status"),
                "eligible_word_count": int(asr.get("eligible_word_count") or 0),
                "scored_word_count": int(asr.get("scored_word_count") or 0),
                "coverage_ratio": asr.get("coverage_ratio"),
                "mean_score": asr.get("mean_score"),
                "low_score_word_count": int(asr.get("low_score_word_count") or 0),
                "low_score_ratio": asr.get("low_score_ratio"),
                "comparable_key": comparable_key,
                "import_adapter": provenance.get("import_adapter"),
                "asr_engine": provenance.get("asr_engine"),
                "model_identifier": provenance.get("model_identifier"),
                "normalisation_policy": provenance.get("normalisation_policy"),
            }
        )
        session_rows.append(row)
        cohorts[comparable_key].append(row)

    if not session_rows:
        return None

    member_count = len(session_rows)

    def _cohort_rank(key: str) -> tuple[int, int, str]:
        rows = cohorts[key]
        scored = sum(int(r.get("scored_word_count") or 0) for r in rows)
        # Largest cohort first; on ties prefer evidence-rich (scored words), then key.
        return (len(rows), scored, key)

    # Primary cohort = largest compatible set; others marked incompatible for that pool.
    primary_key = max(cohorts.keys(), key=_cohort_rank)
    pooled_rows = cohorts[primary_key]
    incompatible_member_count = member_count - len(pooled_rows)

    sum_scored = sum(int(r.get("scored_word_count") or 0) for r in pooled_rows)
    sum_eligible = sum(int(r.get("eligible_word_count") or 0) for r in pooled_rows)
    sum_low = sum(int(r.get("low_score_word_count") or 0) for r in pooled_rows)
    weighted_mean_num = 0.0
    for r in pooled_rows:
        mean = r.get("mean_score")
        scored = int(r.get("scored_word_count") or 0)
        if isinstance(mean, (int, float)) and scored > 0:
            weighted_mean_num += float(mean) * scored

    pooled = {
        "schema_version": 1,
        "comparable_key": primary_key,
        "member_count": member_count,
        "pooled_member_count": len(pooled_rows),
        "incompatible_member_count": incompatible_member_count,
        "cohort_count": len(cohorts),
        "coverage": (sum_scored / sum_eligible) if sum_eligible > 0 else None,
        "mean_score": (weighted_mean_num / sum_scored) if sum_scored > 0 else None,
        "low_score_ratio": (sum_low / sum_scored) if sum_scored > 0 else None,
        "sum_scored_word_count": sum_scored,
        "sum_eligible_word_count": sum_eligible,
        "sum_low_score_word_count": sum_low,
        "disclaimer": (
            "ASR confidence is model-produced uncertainty evidence, not an "
            "estimated word error rate. Sessions with different provenance "
            "comparable_key values are not pooled together."
        ),
    }

    cohort_summaries = []
    for key, rows in sorted(cohorts.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        s_scored = sum(int(r.get("scored_word_count") or 0) for r in rows)
        s_eligible = sum(int(r.get("eligible_word_count") or 0) for r in rows)
        s_low = sum(int(r.get("low_score_word_count") or 0) for r in rows)
        w_num = 0.0
        for r in rows:
            mean = r.get("mean_score")
            scored = int(r.get("scored_word_count") or 0)
            if isinstance(mean, (int, float)) and scored > 0:
                w_num += float(mean) * scored
        cohort_summaries.append(
            {
                "comparable_key": key,
                "pooled_member_count": len(rows),
                "coverage": (s_scored / s_eligible) if s_eligible > 0 else None,
                "mean_score": (w_num / s_scored) if s_scored > 0 else None,
                "low_score_ratio": (s_low / s_scored) if s_scored > 0 else None,
            }
        )

    return {
        "session_rows": session_rows,
        "transcript_quality_pooled": pooled,
        "cohort_summaries": cohort_summaries,
    }
