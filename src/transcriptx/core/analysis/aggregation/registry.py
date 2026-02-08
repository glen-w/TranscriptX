"""
Registry for group aggregation modules.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
from transcriptx.core.utils.path_utils import get_canonical_base_name


AggregationContext = Dict[str, Any]
AggregationFn = Callable[
    [
        List[PerTranscriptResult],
        CanonicalSpeakerMap,
        TranscriptSet,
        Optional[AggregationContext],
    ],
    Dict[str, Any] | None,
]


@dataclass(frozen=True)
class AggregationEntry:
    agg_id: str
    selector: Callable[[List[str]], bool]
    deps: List[str]
    aggregate_fn: AggregationFn
    output_type: str = "rows"  # "rows" or "blob"


def _extract_payload(module_results: Dict[str, Any], module_name: str) -> Dict[str, Any]:
    result = module_results.get(module_name, {})
    if not isinstance(result, dict):
        return {}
    payload = result.get("payload") or result.get("results") or {}
    return payload if isinstance(payload, dict) else {}


def _build_rows_from_stats(
    result: PerTranscriptResult,
    transcript_set: TranscriptSet,
    canonical_speaker_map: CanonicalSpeakerMap,
    global_stats: Dict[str, Any],
    speaker_stats: Dict[str, Any],
) -> Dict[str, Any]:
    session_row = _session_row_base(result, transcript_set)
    session_row.update(global_stats)
    display_to_canonical = _build_display_to_canonical(
        result.transcript_path, canonical_speaker_map
    )
    speaker_rows: List[Dict[str, Any]] = []
    for speaker, stats in speaker_stats.items():
        if not isinstance(stats, dict):
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
        row.update(stats)
        speaker_rows.append(row)
    return {"session_rows": [session_row], "speaker_rows": speaker_rows}


def _warning_payload_shape(
    agg_id: str, expected_keys: List[str]
) -> Dict[str, Any]:
    return {
        "warning": build_warning(
            code="PAYLOAD_SHAPE_UNSUPPORTED",
            message=f"Expected keys missing: {', '.join(expected_keys)}",
            aggregation_key=agg_id,
            details={"missing_keys": expected_keys},
        )
    }


def _aggregate_wordclouds(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    from transcriptx.core.analysis.aggregation.wordclouds import (
        aggregate_wordclouds_group,
    )
    from transcriptx.core.analysis.wordclouds.analysis import run_group_wordclouds

    grouped, summary = aggregate_wordclouds_group(
        per_transcript_results, canonical_speaker_map
    )
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
        run_group_wordclouds(
            grouped,
            Path(str(group_output_dir)),
            base_name,
            run_id,
        )
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
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "tics")
        if not payload:
            continue
        speaker_stats = payload.get("speaker_stats") or {}
        global_stats = payload.get("global_stats") or {}
        if not isinstance(global_stats, dict) or not isinstance(speaker_stats, dict):
            return _warning_payload_shape("tics", ["global_stats", "speaker_stats"])
        rows = _build_rows_from_stats(
            result, transcript_set, canonical_speaker_map, global_stats, speaker_stats
        )
        session_rows.extend(rows["session_rows"])
        speaker_rows.extend(rows["speaker_rows"])
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


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
    return {"session_rows": session_rows, "speaker_rows": speaker_rows}


def _aggregate_convokit(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
    transcript_set: TranscriptSet,
) -> Dict[str, Any] | None:
    session_rows: List[Dict[str, Any]] = []
    for result in per_transcript_results:
        payload = _extract_payload(result.module_results, "convokit")
        if not payload:
            continue
        summary = payload.get("coordination_summary") or {}
        reply = payload.get("reply_linking") or {}
        if not isinstance(summary, dict) or not isinstance(reply, dict):
            return _warning_payload_shape("convokit", ["coordination_summary", "reply_linking"])
        session_row = _session_row_base(result, transcript_set)
        session_row.update({"coordination_summary": summary, "reply_linking": reply})
        session_rows.append(session_row)
    if not session_rows:
        return None
    return {"session_rows": session_rows, "speaker_rows": []}


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
        source_rel = _artifact_relpath(result.module_results.get("highlights", {}), "highlights")
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
    highlight_rows.sort(key=lambda row: (row.get("order_index", 0), row.get("start_time") or 0))
    return {
        "session_rows": session_rows,
        "speaker_rows": [],
        "content_rows": highlight_rows,
        "content_rows_name": "highlight_rows",
        "metrics_spec": [{"name": "score", "format": "float", "description": "Highlight score"}],
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
        source_rel = _artifact_relpath(result.module_results.get("moments", {}), "moments")
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
        "metrics_spec": [{"name": "score", "format": "float", "description": "Moment score"}],
    }


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


def build_registry() -> List[AggregationEntry]:
    from transcriptx.core.analysis.stats.aggregation import aggregate_stats_group
    from transcriptx.core.analysis.aggregation.sentiment import aggregate_sentiment_group
    from transcriptx.core.analysis.aggregation.ner import aggregate_ner_group
    from transcriptx.core.analysis.aggregation.entity_sentiment import (
        aggregate_entity_sentiment_group,
    )
    from transcriptx.core.analysis.aggregation.topics import aggregate_topics_group
    from transcriptx.core.analysis.aggregation.emotion import aggregate_emotion_group
    from transcriptx.core.analysis.aggregation.interactions import (
        aggregate_interactions_group,
    )

    def any_of(ids: List[str]) -> Callable[[List[str]], bool]:
        return lambda selected: any(module_id in selected for module_id in ids)

    registry: List[AggregationEntry] = [
        AggregationEntry(
            agg_id="stats",
            selector=any_of(["stats"]),
            deps=[],
            aggregate_fn=aggregate_stats_group,
        ),
        AggregationEntry(
            agg_id="sentiment",
            selector=any_of(["sentiment"]),
            deps=[],
            aggregate_fn=aggregate_sentiment_group,
        ),
        AggregationEntry(
            agg_id="ner",
            selector=any_of(["ner"]),
            deps=[],
            aggregate_fn=aggregate_ner_group,
        ),
        AggregationEntry(
            agg_id="entity_sentiment",
            selector=any_of(["entity_sentiment"]),
            deps=["ner"],
            aggregate_fn=aggregate_entity_sentiment_group,
        ),
        AggregationEntry(
            agg_id="topic_modeling",
            selector=any_of(["topic_modeling"]),
            deps=[],
            aggregate_fn=aggregate_topics_group,
        ),
        AggregationEntry(
            agg_id="emotion",
            selector=any_of(["emotion"]),
            deps=[],
            aggregate_fn=aggregate_emotion_group,
        ),
        AggregationEntry(
            agg_id="interactions",
            selector=any_of(["interactions"]),
            deps=[],
            aggregate_fn=aggregate_interactions_group,
        ),
        AggregationEntry(
            agg_id="wordclouds",
            selector=any_of(["wordclouds"]),
            deps=[],
            aggregate_fn=_aggregate_wordclouds,
        ),
        AggregationEntry(
            agg_id="acts",
            selector=any_of(["acts"]),
            deps=[],
            aggregate_fn=_aggregate_acts,
        ),
        AggregationEntry(
            agg_id="tics",
            selector=any_of(["tics"]),
            deps=[],
            aggregate_fn=_aggregate_tics,
        ),
        AggregationEntry(
            agg_id="understandability",
            selector=any_of(["understandability"]),
            deps=[],
            aggregate_fn=_aggregate_understandability,
        ),
        AggregationEntry(
            agg_id="pauses",
            selector=any_of(["pauses"]),
            deps=["acts"],
            aggregate_fn=_aggregate_pauses,
        ),
        AggregationEntry(
            agg_id="momentum",
            selector=any_of(["momentum"]),
            deps=["pauses"],
            aggregate_fn=_aggregate_momentum,
        ),
        AggregationEntry(
            agg_id="affect_tension",
            selector=any_of(["affect_tension"]),
            deps=["emotion", "sentiment"],
            aggregate_fn=_aggregate_affect_tension,
        ),
        AggregationEntry(
            agg_id="contagion",
            selector=any_of(["contagion"]),
            deps=["emotion"],
            aggregate_fn=_aggregate_contagion,
        ),
        AggregationEntry(
            agg_id="convokit",
            selector=any_of(["convokit"]),
            deps=[],
            aggregate_fn=_aggregate_convokit,
        ),
        AggregationEntry(
            agg_id="conversation_loops",
            selector=any_of(["conversation_loops"]),
            deps=[],
            aggregate_fn=_aggregate_conversation_loops,
        ),
        AggregationEntry(
            agg_id="temporal_dynamics",
            selector=any_of(["temporal_dynamics"]),
            deps=[],
            aggregate_fn=_aggregate_temporal_dynamics,
        ),
        AggregationEntry(
            agg_id="qa_analysis",
            selector=any_of(["qa_analysis"]),
            deps=["acts"],
            aggregate_fn=_aggregate_qa_analysis,
        ),
        AggregationEntry(
            agg_id="echoes",
            selector=any_of(["echoes"]),
            deps=[],
            aggregate_fn=_aggregate_echoes,
        ),
        AggregationEntry(
            agg_id="highlights",
            selector=any_of(["highlights"]),
            deps=[],
            aggregate_fn=_aggregate_highlights,
        ),
        AggregationEntry(
            agg_id="moments",
            selector=any_of(["moments"]),
            deps=["pauses", "echoes", "momentum", "qa_analysis"],
            aggregate_fn=_aggregate_moments,
        ),
        AggregationEntry(
            agg_id="summary",
            selector=any_of(["summary"]),
            deps=["highlights"],
            aggregate_fn=_aggregate_summary_blob,
            output_type="blob",
        ),
        AggregationEntry(
            agg_id="prosody",
            selector=any_of(["voice_features", "voice_charts_core", "prosody_dashboard"]),
            deps=[],
            aggregate_fn=_aggregate_prosody,
        ),
    ]
    return registry
