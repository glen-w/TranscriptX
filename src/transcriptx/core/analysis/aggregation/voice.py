"""
Group aggregation for voice mismatch, tension, and fingerprint modules.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.aggregation.common import extract_payload
from transcriptx.core.analysis.aggregation.rows import (
    _build_display_to_canonical,
    _fallback_canonical_id,
    _session_row_base,
)
from transcriptx.core.analysis.aggregation.schema import get_transcript_id
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _artifact_relpath(result: Dict[str, Any], needle: str) -> Optional[str]:
    artifacts = result.get("artifacts") or []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rel = artifact.get("relative_path") or artifact.get("path")
        if isinstance(rel, str) and needle in rel and rel.endswith(".json"):
            return rel
    return None


def aggregate_voice_mismatch_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Aggregate tone–text mismatch moments across sessions."""
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    content_rows: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "voice_mismatch")
        if not payload:
            continue
        summary = (
            payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        )
        moments = payload.get("moments") or []
        if not isinstance(moments, list):
            moments = []
        transcript_id = get_transcript_id(result, transcript_set)
        session_row = _session_row_base(result, transcript_set)
        session_row["moments_count"] = int(
            summary.get("moments_count", len(moments)) or 0
        )
        scores = [
            float(m.get("mismatch_score"))
            for m in moments
            if isinstance(m, dict) and m.get("mismatch_score") is not None
        ]
        if scores:
            session_row["mismatch_score_mean"] = sum(scores) / len(scores)
            session_row["mismatch_score_max"] = max(scores)
        session_rows.append(session_row)

        source_rel = _artifact_relpath(
            result.module_results.get("voice_mismatch", {}), "voice_mismatch"
        )
        for moment in moments:
            if not isinstance(moment, dict):
                continue
            text = str(moment.get("text") or "")
            start = moment.get("start_s")
            end = moment.get("end_s")
            score = moment.get("mismatch_score")
            hash_payload = f"{transcript_id}:{start}:{end}:{text[:200]}"
            content_rows.append(
                {
                    "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                    "order_index": result.order_index,
                    "start_time": start,
                    "end_time": end,
                    "speaker": moment.get("speaker"),
                    "text": text,
                    "score": score,
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                    "source_artifact_relpath": source_rel,
                }
            )

    if not session_rows:
        return None
    content_rows.sort(
        key=lambda row: (
            -(float(row.get("score") or 0.0)),
            row.get("order_index", 0),
        )
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": content_rows,
        "content_rows_name": "mismatch_moment_rows",
        "metrics_spec": [
            {
                "name": "moments_count",
                "format": "int",
                "description": "Mismatch moments in session",
            },
            {
                "name": "score",
                "format": "float",
                "description": "Mismatch score",
            },
        ],
    }


def aggregate_voice_tension_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Aggregate tension curve summaries and points across sessions."""
    del canonical_speaker_map
    session_rows: List[Dict[str, Any]] = []
    content_rows: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "voice_tension")
        if not payload:
            continue
        summary = (
            payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        )
        curve = payload.get("curve") or []
        if not isinstance(curve, list):
            curve = []
        transcript_id = get_transcript_id(result, transcript_set)
        session_row = _session_row_base(result, transcript_set)
        session_row["bins"] = int(summary.get("bins", len(curve)) or 0)
        session_row["bin_seconds"] = summary.get("bin_seconds")
        session_row["smoothing_alpha"] = summary.get("smoothing_alpha")
        tensions = [
            float(point.get("tension"))
            for point in curve
            if isinstance(point, dict) and point.get("tension") is not None
        ]
        if tensions:
            session_row["tension_mean"] = sum(tensions) / len(tensions)
            session_row["tension_max"] = max(tensions)
        session_rows.append(session_row)

        for point in curve:
            if not isinstance(point, dict):
                continue
            start = point.get("start_s") or point.get("bin_start_s") or point.get("t")
            tension = point.get("tension")
            hash_payload = f"{transcript_id}:{start}:{tension}"
            content_rows.append(
                {
                    "id": hashlib.sha1(str(hash_payload).encode("utf-8")).hexdigest(),
                    "order_index": result.order_index,
                    "start_time": start,
                    "score": tension,
                    "source_transcript_id": transcript_id,
                    "source_run_relpath": result.output_dir,
                }
            )

    if not session_rows:
        return None
    content_rows.sort(
        key=lambda row: (row.get("order_index", 0), row.get("start_time") or 0)
    )
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": content_rows,
        "content_rows_name": "tension_curve_rows",
        "metrics_spec": [
            {"name": "bins", "format": "int", "description": "Tension bins"},
            {
                "name": "tension_mean",
                "format": "float",
                "description": "Mean tension",
            },
            {"name": "score", "format": "float", "description": "Bin tension"},
        ],
    }


def _baseline_median(baseline: Any, key: str) -> float | None:
    if not isinstance(baseline, dict):
        return None
    stats = baseline.get(key)
    if not isinstance(stats, dict):
        return None
    value = stats.get("median")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def aggregate_voice_fingerprint_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    """Aggregate speaker voice baselines and drift moments across sessions."""
    session_rows: List[Dict[str, Any]] = []
    speaker_rows: List[Dict[str, Any]] = []
    content_rows: List[Dict[str, Any]] = []

    for result in per_transcript_results:
        payload = extract_payload(result.module_results, "voice_fingerprint")
        if not payload:
            continue
        summary = (
            payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        )
        fingerprints = payload.get("fingerprints") or {}
        drift_moments = payload.get("drift_moments") or {}
        if not isinstance(fingerprints, dict):
            fingerprints = {}
        if not isinstance(drift_moments, dict):
            drift_moments = {}

        transcript_id = get_transcript_id(result, transcript_set)
        session_row = _session_row_base(result, transcript_set)
        session_row["speakers"] = int(summary.get("speakers", len(fingerprints)) or 0)
        session_row["drift_moment_count"] = sum(
            len(v) for v in drift_moments.values() if isinstance(v, list)
        )
        session_rows.append(session_row)

        display_to_canonical = _build_display_to_canonical(
            result.transcript_path, canonical_speaker_map
        )
        source_rel = _artifact_relpath(
            result.module_results.get("voice_fingerprint", {}), "voice_fingerprint"
        )

        for speaker, fp in fingerprints.items():
            if not isinstance(fp, dict):
                continue
            canonical_id = display_to_canonical.get(
                str(speaker), _fallback_canonical_id(str(speaker))
            )
            baseline = fp.get("baseline") or {}
            speaker_rows.append(
                {
                    "canonical_speaker_id": canonical_id,
                    "display_name": canonical_speaker_map.canonical_to_display.get(
                        canonical_id, str(speaker)
                    ),
                    "source_transcript_id": transcript_id,
                    "order_index": result.order_index,
                    "n_segments": fp.get("n_segments"),
                    "rms_db_median": _baseline_median(baseline, "rms_db"),
                    "f0_range_semitones_median": _baseline_median(
                        baseline, "f0_range_semitones"
                    ),
                    "speech_rate_wps_median": _baseline_median(
                        baseline, "speech_rate_wps"
                    ),
                }
            )

            moments = drift_moments.get(speaker) or []
            if not isinstance(moments, list):
                continue
            for moment in moments:
                if not isinstance(moment, dict):
                    continue
                start = moment.get("start_s")
                score = moment.get("drift_score") or moment.get("score")
                text = str(moment.get("text") or "")
                hash_payload = f"{transcript_id}:{speaker}:{start}:{score}:{text[:120]}"
                content_rows.append(
                    {
                        "id": hashlib.sha1(hash_payload.encode("utf-8")).hexdigest(),
                        "order_index": result.order_index,
                        "start_time": start,
                        "end_time": moment.get("end_s"),
                        "speaker": speaker,
                        "canonical_speaker_id": canonical_id,
                        "text": text,
                        "score": score,
                        "source_transcript_id": transcript_id,
                        "source_run_relpath": result.output_dir,
                        "source_artifact_relpath": source_rel,
                    }
                )

    if not session_rows:
        return None
    return {
        "session_rows": session_rows,
        "speaker_rows": speaker_rows,
        "content_rows": content_rows,
        "content_rows_name": "drift_moment_rows",
        "metrics_spec": [
            {
                "name": "speakers",
                "format": "int",
                "description": "Speakers with fingerprints",
            },
            {
                "name": "drift_moment_count",
                "format": "int",
                "description": "Drift moments in session",
            },
            {"name": "score", "format": "float", "description": "Drift score"},
        ],
    }
