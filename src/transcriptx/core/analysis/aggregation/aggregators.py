"""Group aggregation implementations (row and blob aggregators).

Catalog / DAG wiring lives in ``registry.py``. Callers and tests may still
import the ``_aggregate_*`` names from ``registry``; this module is the
implementation home.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.common import (
    build_rows_from_stats as _build_rows_from_stats,
    extract_payload as _extract_payload,
    warning_payload_shape as _warning_payload_shape,
)
from transcriptx.core.analysis.aggregation.contagion import (
    build_contagion_pooled_for_group,
)
from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    _session_row_base,
)
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils._path_core import get_canonical_base_name


def _aggregate_wordclouds(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    from transcriptx.core.analysis.aggregation.wordclouds import (
        aggregate_wordclouds_group,
    )
    from transcriptx.core.analysis.keyphrases.aggregation import aggregate_keyphrases
    from transcriptx.core.analysis.wordclouds.analysis import run_group_wordclouds

    grouped, summary = aggregate_wordclouds_group(
        per_transcript_results, canonical_speaker_map
    )
    keyphrase_pool: list | None = None
    try:
        kp_agg = aggregate_keyphrases(
            per_transcript_results, canonical_speaker_map, transcript_set
        )
        if isinstance(kp_agg, dict):
            pool = kp_agg.get("keyphrase_noun_chunk_pool")
            if isinstance(pool, list):
                keyphrase_pool = pool
    except Exception:
        keyphrase_pool = None
    if summary is not None:
        summary["transcript_set_key"] = transcript_set.key
        summary["transcript_set_name"] = transcript_set.name
    if grouped:
        group_output_dir = transcript_set.metadata.get("group_output_dir")
        if not group_output_dir:
            return {
                "warning": build_warning(
                    code="MISSING_ARTIFACT",
                    message="Group output directory missing for wordclouds.",
                    aggregation_key="wordclouds",
                    details={"missing_keys": ["group_output_dir"]},
                )
            }
        base_name = transcript_set.metadata.get("group_uuid") or transcript_set.key
        run_id = transcript_set.metadata.get("group_run_id") or "group"
        wc_extra = run_group_wordclouds(
            grouped,
            Path(str(group_output_dir)),
            base_name,
            run_id,
            group_uuid=transcript_set.metadata.get("group_uuid"),
            per_transcript_results=per_transcript_results,
            aggregation_summary=summary,
            keyphrase_noun_chunk_pool=keyphrase_pool,
        )
        if summary is not None:
            p = wc_extra.get("pooled_cross_session_summary_path")
            if p:
                summary["pooled_cross_session_summary_path"] = p
            sk = wc_extra.get("skipped_variants") or []
            if sk:
                prev = summary.get("skipped_variants") or []
                summary["skipped_variants"] = list(prev) + list(sk)
    if summary is None:
        return None
    return {
        "session_rows": [
            {
                "transcript_id": "group",
                "order_index": -1,
                **summary,
            }
        ],
        "speaker_rows": [],
    }


def _aggregate_acts(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "acts")
        if not payload:
            continue
        speaker_stats = payload.get("speaker_stats") or {}
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape("acts", ["global_stats", "speaker_stats"])
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, global_stats, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


def _aggregate_tics(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    total_tics = 0
    by_tic: Dict[str, int] = {}
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "tics")
        if not payload:
            continue
        speaker_stats = payload.get("speaker_stats") or {}
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape("tics", ["global_stats", "speaker_stats"])
        tt = global_stats.get("total_tics")
        if isinstance(tt, (int, float)):
            total_tics += int(tt)
        for k, v in global_stats.items():
            if k == "total_tics" or not isinstance(v, (int, float)):
                continue
            by_tic[k] = by_tic.get(k, 0) + int(v)
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, global_stats, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    tics_pooled = {
        "schema_version": 1,
        "total_tics": total_tics,
        "by_tic": dict(sorted(by_tic.items(), key=lambda kv: -kv[1])),
    }
    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "tics_pooled": tics_pooled,
    }


def _aggregate_understandability(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "understandability")
        if not payload:
            continue
        speaker_stats = payload.get("speaker_stats") or {}
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape(
                "understandability", ["global_stats", "speaker_stats"]
            )
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, global_stats, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


def _aggregate_lexical_diversity(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "lexical_diversity")
        if not payload:
            continue
        speaker_stats = payload.get("speaker_stats") or {}
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape(
                "lexical_diversity", ["global_stats", "speaker_stats"]
            )
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, global_stats, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "aggregation_note": (
            "Group lexical metrics are descriptive per-transcript means; "
            "token_count sums are additive; ttr/mtld/hapax_rate are not pooled exactly."
        ),
    }


def _aggregate_pauses(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "pauses")
        if not payload:
            continue
        stats = payload.get("stats") or {}
        speaker_stats = payload.get("speaker_stats") or {}
        if not isinstance(stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape("pauses", ["stats", "speaker_stats"])
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, stats, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


def _aggregate_momentum(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "momentum")
        if not payload:
            continue
        stats = payload.get("stats") or {}
        if not isinstance(stats, dict):
            return _warning_payload_shape("momentum", ["stats"])
        session_row = _session_row_base(result, transcript_set)
        session_row.update(stats)
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_affect_tension(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "affect_tension")
        if not payload:
            continue
        derived = payload.get("derived_indices") or {}
        if not isinstance(derived, dict):
            return _warning_payload_shape("affect_tension", ["derived_indices"])
        global_stats = derived.get("global") or {}
        by_speaker = derived.get("by_speaker") or {}
        if not isinstance(global_stats, dict) or not isinstance(by_speaker, dict):
            return _warning_payload_shape("affect_tension", ["global", "by_speaker"])
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, global_stats, by_speaker
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


def _aggregate_contagion(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "contagion")
        if not payload:
            continue
        summary = payload.get("contagion_summary") or {}
        speaker_stats = payload.get("speaker_emotions") or {}
        if not isinstance(summary, dict):
            return _warning_payload_shape("contagion", ["contagion_summary"])
        if not isinstance(speaker_stats, dict):
            speaker_stats = {}
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, summary, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    pooled, agg_warns = build_contagion_pooled_for_group(
        per_transcript_results, canonical_speaker_map
    )
    out: Dict[str, Any] = {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "contagion_pooled": pooled,
    }
    if agg_warns:
        out["aggregation_warnings"] = agg_warns
    return out


def _aggregate_conversation_loops(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "conversation_loops")
        if not payload:
            continue
        summary = payload.get("summary") or payload.get("statistics") or {}
        if not isinstance(summary, dict):
            return _warning_payload_shape("conversation_loops", ["summary"])
        session_row = _session_row_base(result, transcript_set)
        session_row.update(summary)
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_temporal_dynamics(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "temporal_dynamics")
        if not payload:
            continue
        if not isinstance(payload, dict):
            return _warning_payload_shape("temporal_dynamics", ["payload"])
        session_row = _session_row_base(result, transcript_set)
        for key in ["total_duration", "window_size", "num_windows", "phase_detection"]:
            if key in payload:
                session_row[key] = payload.get(key)
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_qa_analysis(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "qa_analysis")
        if not payload:
            continue
        stats = payload.get("statistics") or {}
        if not isinstance(stats, dict):
            return _warning_payload_shape("qa_analysis", ["statistics"])
        session_row = _session_row_base(result, transcript_set)
        session_row.update(stats)
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_echoes(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "echoes")
        if not payload:
            continue
        stats = payload.get("stats") or {}
        counts_by_speaker = stats.get("counts_by_speaker") or {}
        if not isinstance(stats, dict) or not isinstance(counts_by_speaker, dict):
            return _warning_payload_shape("echoes", ["stats", "counts_by_speaker"])
        session_row = _session_row_base(result, transcript_set)
        session_row.update({k: v for k, v in stats.items() if k != "counts_by_speaker"})
        session_rows.append(session_row)

        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        for speaker, counts in counts_by_speaker.items():
            if not isinstance(counts, dict):
                continue
            canonical_id = display_to_canonical.get(
                speaker, _fallback_canonical_id(str(speaker))
            )
            row = {
                "canonical_speaker_id": canonical_id,
                "display_name": canonical_speaker_map.canonical_to_display.get(
                    canonical_id, speaker
                ),
            }
            row.update(counts)
            speaker_rows.append(row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


def _extract_highlight_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    sections = payload.get("sections", {}) or {}
    cold_open = sections.get("cold_open", {}) or {}
    conflict = sections.get("conflict_points", {}) or {}
    for item in cold_open.get("items", []) or []:
        if isinstance(item, dict):
            items.append(item)
    for event in conflict.get("events", []) or []:
        anchor = (event or {}).get("anchor_quote") if isinstance(event, dict) else None
        if isinstance(anchor, dict):
            items.append(anchor)
    return items


def _artifact_relpath(result: Dict[str, Any], needle: str) -> Optional[str]:
    artifacts = result.get("artifacts") or []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rel = artifact.get("relative_path") or artifact.get("path")
        if isinstance(rel, str) and needle in rel and rel.endswith(".json"):
            return rel
    return None


def _aggregate_highlights(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    highlight_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "highlights")
        if not payload:
            continue
        items = _extract_highlight_items(payload)
        transcript_id = get_transcript_id(result, transcript_set)
        session_rows.append(_session_row_base(result, transcript_set))
        source_rel = _artifact_relpath(
            result.module_results.get("highlights", {}), "highlights"
        )
        for item in items:
            start = item.get("start")
            end = item.get("end")
            text = item.get("quote") or item.get("text") or ""
            score = None
            score_dict = item.get("score") or {}
            if isinstance(score_dict, dict):
                score = score_dict.get("total")
            speaker = item.get("speaker")
            hash_payload = f"{transcript_id}:{start}:{end}:{str(text)[:200]}"
            row_id = hashlib.sha1(hash_payload.encode("utf-8")).hexdigest()
            highlight_rows.append(
                {
                    "id": row_id,
                    "order_index": result.order_index,
                    "start_time": start,
                    "end_time": end,
                    "speaker": speaker,
                    "text": text,
                    "score": score,
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                    "source_artifact_relpath": source_rel,
                }
            )
    if not highlight_rows:
        return None
    highlight_rows.sort(
        key=lambda row: (row.get("order_index", 0), row.get("start_time") or 0)
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": highlight_rows,
        "content_rows_name": "highlight_rows",
        "metrics_spec": [
            {"name": "score", "format": "float", "description": "Highlight score"}
        ],
    }


def _aggregate_moments(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    moment_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "moments")
        if not payload:
            continue
        moments = payload.get("moments") or []
        if not isinstance(moments, list):
            return _warning_payload_shape("moments", ["moments"])
        transcript_id = get_transcript_id(result, transcript_set)
        session_rows.append(_session_row_base(result, transcript_set))
        source_rel = _artifact_relpath(
            result.module_results.get("moments", {}), "moments"
        )
        for moment in moments:
            if not isinstance(moment, dict):
                continue
            start = moment.get("time_start")
            end = moment.get("time_end")
            text = moment.get("summary") or ""
            score = moment.get("score")
            hash_payload = f"{transcript_id}:{start}:{end}:{str(text)[:200]}"
            row_id = hashlib.sha1(hash_payload.encode("utf-8")).hexdigest()
            moment_rows.append(
                {
                    "id": row_id,
                    "order_index": result.order_index,
                    "start_time": start,
                    "end_time": end,
                    "speaker": None,
                    "text": text,
                    "score": score,
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                    "source_artifact_relpath": source_rel,
                }
            )
    if not moment_rows:
        return None
    moment_rows.sort(
        key=lambda row: (
            -(row.get("score") or 0),
            row.get("order_index", 0),
            row.get("start_time") or 0,
        )
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": moment_rows,
        "content_rows_name": "moment_rows",
        "metrics_spec": [
            {"name": "score", "format": "float", "description": "Moment score"}
        ],
    }


def _member_artifact_relpaths(module_result: Dict[str, Any]) -> List[str]:
    artifacts = module_result.get("artifacts") or []
    relpaths: List[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rel = artifact.get("relative_path") or artifact.get("path")
        if isinstance(rel, str) and rel:
            relpaths.append(rel)
    return relpaths


def _aggregate_insight_eligibility(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "insight_eligibility")
        if not payload:
            continue
        filtered = payload.get("filtered_segments") or []
        tic_mask = payload.get("tic_mask") or []
        phrases = payload.get("content_phrases") or []
        densities = payload.get("content_densities") or {}
        density_vals = [
            float(v)
            for v in (densities.values() if isinstance(densities, dict) else [])
            if isinstance(v, (int, float))
        ]
        mean_density = sum(density_vals) / len(density_vals) if density_vals else 0.0
        session_row = _session_row_base(result, transcript_set)
        session_row.update(
            {
                "filtered_segment_count": (
                    len(filtered) if isinstance(filtered, list) else 0
                ),
                "tic_mask_count": len(tic_mask) if isinstance(tic_mask, list) else 0,
                "phrase_count": len(phrases) if isinstance(phrases, list) else 0,
                "mean_content_density": mean_density,
            }
        )
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_transcript_output_blob(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    del canonical_speaker_map
    members: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        module_result = result.module_results.get("transcript_output") or {}
        if not isinstance(module_result, dict):
            continue
        payload = _extract_payload(result.module_results, "transcript_output")
        if not payload and not module_result:
            continue
        members.append(
            {
                "transcript_id": get_transcript_id(result, transcript_set),
                "run_id": result.run_id,
                "order_index": result.order_index,
                "total_segments": payload.get("total_segments"),
                "artifact_relpaths": _member_artifact_relpaths(module_result),
            }
        )
    if not members:
        return None
    members.sort(key=lambda row: row.get("order_index", 0))
    return {
        "blob_name": "transcript_output",
        "blob_payload": {
            "schema_version": 1,
            "aggregation_key": "transcript_output",
            "members": members,
        },
    }


def _aggregate_simplified_transcript(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "simplified_transcript")
        if not payload:
            continue
        total_original = int(payload.get("total_original") or 0)
        total_simplified = int(payload.get("total_simplified") or 0)
        removed_count = payload.get("removed_count")
        if not isinstance(removed_count, (int, float)):
            removed_count = total_original - total_simplified
        session_row = _session_row_base(result, transcript_set)
        session_row.update(
            {
                "total_original": total_original,
                "total_simplified": total_simplified,
                "removed_count": int(removed_count),
            }
        )
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_voice_contours(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "voice_contours")
        if not payload:
            continue
        slopes = payload.get("f0_slopes") or []
        slope_vals = [
            float(item.get("slope"))
            for item in slopes
            if isinstance(item, dict) and isinstance(item.get("slope"), (int, float))
        ]
        selected_ids = payload.get("selected_segment_ids") or []
        session_row = _session_row_base(result, transcript_set)
        session_row.update(
            {
                "status": payload.get("status"),
                "skipped_reason": payload.get("skipped_reason"),
                "selected_segment_count": (
                    len(selected_ids) if isinstance(selected_ids, list) else 0
                ),
                "f0_slope_count": len(slope_vals),
                "f0_slope_mean": (
                    sum(slope_vals) / len(slope_vals) if slope_vals else None
                ),
            }
        )
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


def _aggregate_summary_blob(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    summary_payloads = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "summary")
        if payload:
            summary_payloads.append(payload)
    if not summary_payloads:
        return None
    return {
        "blob_name": "summary",
        "blob_payload": {
            "schema_version": 1,
            "aggregation_key": "summary",
            "summaries": summary_payloads,
        },
    }


def _resolve_prosody_summary_path(
    output_dir: str, module_name: str, base_name: str
) -> Optional[Path]:
    if not output_dir:
        return None
    candidate = (
        Path(output_dir)
        / module_name
        / "data"
        / "global"
        / f"{base_name}_{module_name}_summary.json"
    )
    return candidate if candidate.exists() else None


def _aggregate_prosody(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    searched_paths: List[str] = []
    for result in per_transcript_results:
        summary_path = None
        base_name = get_canonical_base_name(result.transcript_path)
        for module_name in ["prosody_dashboard", "voice_charts_core", "voice_features"]:
            path = _resolve_prosody_summary_path(
                result.output_dir, module_name, base_name
            )
            if path:
                summary_path = path
                break
            if path is None and result.output_dir:
                searched_paths.append(
                    str(
                        Path(result.output_dir)
                        / module_name
                        / "data"
                        / "global"
                        / f"{base_name}_{module_name}_summary.json"
                    )
                )
        if summary_path is None:
            return {
                "warning": build_warning(
                    code="MISSING_ARTIFACT",
                    message="Prosody summary artifact not found.",
                    aggregation_key="prosody",
                    details={"searched_paths": searched_paths},
                )
            }
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "warning": build_warning(
                    code="MISSING_ARTIFACT",
                    message="Prosody summary artifact unreadable.",
                    aggregation_key="prosody",
                    details={"searched_paths": searched_paths},
                )
            }
        if not isinstance(payload, dict):
            return _warning_payload_shape("prosody", ["summary metrics"])
        allow_prefixes = ("prosody.", "voice_features.", "voice_charts_core.")
        metrics: Dict[str, Any] = {}
        raw: Dict[str, Any] = {}
        for key, value in payload.items():
            if any(str(key).startswith(prefix) for prefix in allow_prefixes):
                metrics[str(key)] = value
            else:
                raw[str(key)] = value
        session_row = _session_row_base(result, transcript_set)
        session_row.update(metrics)
        if raw:
            session_row["raw"] = raw
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "drop_csv_keys": ["raw"],
    }
