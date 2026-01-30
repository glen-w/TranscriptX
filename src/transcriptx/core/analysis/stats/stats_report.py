"""Generate deterministic stats report payload and renderers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import importlib.metadata
import math
import statistics

from transcriptx.core.analysis.sentiment import score_sentiment
from transcriptx.core.utils.speaker_extraction import (
    get_speaker_display_name,
    group_segments_by_speaker,
)
from transcriptx.utils.text_utils import format_time, is_named_speaker
from transcriptx.core.presentation import (
    build_md_provenance,
    render_intensity_line,
    render_provenance_footer_md,
)


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    label: str
    expected_outputs: Tuple[str, ...]


_MODULE_SPECS: Tuple[ModuleSpec, ...] = (
    ModuleSpec(
        "sentiment",
        "Sentiment",
        ("sentiment/data/global/{base}_sentiment_summary.json",),
    ),
    ModuleSpec(
        "emotion",
        "Emotion",
        ("emotion/data/global/{base}_emotion_summary.json",),
    ),
    ModuleSpec(
        "acts",
        "Dialogue Acts",
        (
            "acts/data/global/{base}_acts_summary.json",
            "acts/data/{base}_acts_summary.json",
        ),
    ),
    ModuleSpec(
        "interactions",
        "Networks / Interruption",
        ("interactions/data/global/{base}_speaker_summary.json",),
    ),
    ModuleSpec(
        "ner",
        "Named Entities",
        ("ner/{base}_ner-entities.json",),
    ),
    ModuleSpec(
        "entity_sentiment",
        "Entity Sentiment",
        (
            "entity_sentiment/data/global/{base}_summary.json",
            "entity_sentiment/data/{base}_entity_sentiment_summary.json",
        ),
    ),
    ModuleSpec(
        "conversation_loops",
        "Conversation Loops",
        ("conversation_loops/data/{base}_conversation_loops_summary.json",),
    ),
    ModuleSpec(
        "contagion",
        "Contagion",
        ("contagion/data/{base}_contagion_summary.json",),
    ),
    ModuleSpec(
        "wordclouds",
        "Wordclouds",
        ("wordclouds/data/global/{base}_wordcloud_summary.json",),
    ),
    ModuleSpec(
        "tics",
        "Tics",
        ("tics/data/global/{base}_tics_summary.json",),
    ),
    ModuleSpec(
        "understandability",
        "Understandability",
        ("understandability/data/global/{base}_understandability.json",),
    ),
)


def build_stats_payload(
    context: Any,
    segments: List[Dict[str, Any]],
    stats_results: Dict[str, Any],
    module_data: Optional[Dict[str, Any]],
    *,
    config_hash: Optional[str] = None,
    generator_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base_name = context.get_base_name()
    transcript_dir = context.get_transcript_dir()
    run_id = context.get_run_id()
    transcript_key = context.get_transcript_key()

    module_data = module_data or {}

    speaker_groups = group_segments_by_speaker(segments)
    display_map: Dict[str, str] = {}
    for grouping_key, segs in speaker_groups.items():
        display_name = get_speaker_display_name(grouping_key, segs, segments)
        if display_name:
            display_map[str(grouping_key)] = display_name

    named_speakers = sorted(
        [name for name in display_map.values() if is_named_speaker(name)]
    )
    total_speakers = sorted(display_map.values())
    excluded_speakers = [name for name in total_speakers if name not in named_speakers]

    speaker_stats = stats_results.get("speaker_stats") or []
    sentiment_summary = stats_results.get("sentiment_summary") or {}

    total_words_named = sum(row[2] for row in speaker_stats)
    total_duration_named = sum(row[0] for row in speaker_stats)
    total_segments_named = sum(row[3] for row in speaker_stats)

    segment_stats = _segment_quality_stats(segments)
    warnings = list(segment_stats["warnings"])

    if excluded_speakers:
        warnings.append(
            "Excluded unnamed speakers from analysis; see provenance.exclusions."
        )

    provenance = {
        "input_source": _resolve_input_source(segments),
        "segment_count": len(segments),
        "speaker_count_total": len(total_speakers),
        "speaker_count_named": len(named_speakers),
        "exclusions": [
            {
                "type": "unnamed_speakers",
                "rule": "is_named_speaker",
                "excluded_speakers": excluded_speakers,
                "why": "non-attributed speaker",
            }
        ]
        if excluded_speakers
        else [],
    }

    modules_payload = _build_modules_payload(
        context, transcript_dir, base_name, module_data
    )
    outputs_index_set = set()
    for spec in _MODULE_SPECS:
        module_outputs = modules_payload[spec.module_id]["outputs"]
        if module_outputs:
            outputs_index_set.add(f"{spec.module_id}/")
            outputs_index_set.update(module_outputs)
    outputs_index = sorted(outputs_index_set)

    speakers_payload = _build_speakers_payload(
        speaker_stats,
        sentiment_summary,
        total_words_named,
        total_duration_named,
    )

    sentiment_payload, sentiment_warnings = _build_sentiment_payload(segments)
    if sentiment_warnings:
        warnings.extend(sentiment_warnings)

    insights_payload = _build_insights_payload(speakers_payload, sentiment_payload)

    generator = _resolve_generator_metadata(generator_overrides)

    payload = {
        "meta": {
            "schema_version": "stats_report.v1",
            "generator": generator,
            "generated_at": _now_iso(),
            "transcript_key": transcript_key,
            "base_name": base_name,
            "run_id": run_id,
            "input_source": provenance["input_source"],
            "config_hash": config_hash,
            "units": {
                "duration": "seconds",
                "words": "count",
                "words_per_min": "words/min",
                "percentages": "fraction_0_1",
            },
        },
        "provenance": provenance,
        "modules": modules_payload,
        "overview": {
            "total_words": total_words_named,
            "total_segments": total_segments_named,
            "total_segments_all": len(segments),
            "total_duration_sec": total_duration_named,
            "speaker_count_named": len(named_speakers),
            "speaker_count_total": len(total_speakers),
            "exclusions": provenance["exclusions"],
        },
        "speakers": speakers_payload,
        "insights": insights_payload,
        "warnings": warnings,
        "outputs_index": outputs_index,
    }

    if sentiment_payload:
        payload["sentiment"] = sentiment_payload

    return payload


def render_stats_markdown(payload: Dict[str, Any]) -> str:
    meta = payload.get("meta", {})
    provenance = payload.get("provenance", {})
    lines: List[str] = []

    lines.append(f"# Overall Stats Report: {meta.get('base_name', '')}")
    lines.append("")
    speakers = payload.get("speakers", [])
    dominance = None
    if speakers:
        dominance = max(
            (float(row.get("pct_total_words", 0.0)) for row in speakers),
            default=None,
        )
    lines.append(render_intensity_line("Dominance", dominance))
    lines.append("")
    lines.append(f"Generated: {meta.get('generated_at', '')}")
    if meta.get("run_id"):
        lines.append(f"Run ID: {meta.get('run_id')}")
    if meta.get("transcript_key"):
        lines.append(f"Transcript Key: {meta.get('transcript_key')}")
    lines.append("")

    lines.append("## Provenance")
    lines.append(
        f"- Input source: {provenance.get('input_source', 'unknown')}"
    )
    lines.append(
        f"- Segments: {provenance.get('segment_count', 0)}"
    )
    lines.append(
        f"- Speakers (named / total): {provenance.get('speaker_count_named', 0)} / {provenance.get('speaker_count_total', 0)}"
    )
    exclusions = provenance.get("exclusions", [])
    if exclusions:
        lines.append("- Exclusions:")
        for exclusion in exclusions:
            excluded = ", ".join(exclusion.get("excluded_speakers", [])) or "none"
            lines.append(
                f"  - {exclusion.get('type', '')}: {excluded} ({exclusion.get('why', '')})"
            )
    lines.append("")

    lines.append("## Module Status")
    lines.append("| Module | Status | Reason | Outputs |")
    lines.append("| --- | --- | --- | --- |")
    for spec in _MODULE_SPECS:
        module_info = payload.get("modules", {}).get(spec.module_id, {})
        outputs = ", ".join(module_info.get("outputs", [])) or "-"
        lines.append(
            f"| {spec.label} | {module_info.get('status', 'missing_input')} | {module_info.get('reason', '')} | {outputs} |"
        )
    lines.append("")

    if speakers:
        lines.append("## Speaker Statistics")
        lines.append(
            "| Speaker | Words | Segments | Duration | Words/Min | Avg Seg Len | Avg Seg Dur | % Words | % Duration | Tic Rate |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
        )
        for speaker in speakers:
            lines.append(
                "| {name} | {words} | {segments} | {duration_hhmmss} | {wpm:.2f} | {avg_len:.2f} | {avg_dur:.2f} | {pct_words:.0%} | {pct_dur:.0%} | {tic:.2%} |".format(
                    name=speaker.get("name", ""),
                    words=speaker.get("words", 0),
                    segments=speaker.get("segments", 0),
                    duration_hhmmss=speaker.get("duration_hhmmss", "00:00"),
                    wpm=speaker.get("words_per_min", 0),
                    avg_len=speaker.get("avg_segment_length_words", 0),
                    avg_dur=speaker.get("avg_segment_duration_sec", 0),
                    pct_words=speaker.get("pct_total_words", 0),
                    pct_dur=speaker.get("pct_total_duration", 0),
                    tic=speaker.get("tic_rate", 0),
                )
            )
        lines.append("")

    sentiment = payload.get("sentiment")
    if sentiment:
        lines.append("## Sentiment")
        lines.append(f"- Mean compound: {sentiment.get('mean_compound', 0):.3f}")
        spread = sentiment.get("spread", {})
        if "std_compound" in spread:
            lines.append(
                f"- Spread (std): {spread.get('std_compound', 0):.3f}"
            )
        delta = sentiment.get("opening_vs_closing_delta", {})
        if "delta_by_time" in delta:
            lines.append(
                f"- Opening vs closing delta (by_time): {delta.get('delta_by_time', 0):.3f}"
            )
        if "delta_by_count" in delta:
            lines.append(
                f"- Opening vs closing delta (by_count): {delta.get('delta_by_count', 0):.3f}"
            )
        lines.append("")

    insights = payload.get("insights", [])
    if insights:
        lines.append("## Derived Insights")
        for insight in insights:
            lines.append(f"- {insight.get('title', '')}")
        lines.append("")

    warnings = payload.get("warnings", [])
    if warnings:
        lines.append("## Warnings")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    outputs_index = payload.get("outputs_index", [])
    if outputs_index:
        lines.append("## Outputs Index")
        for output in outputs_index:
            lines.append(f"- {output}")
        lines.append("")

    prov = build_md_provenance("stats", payload=payload)
    lines.append(render_provenance_footer_md(prov).rstrip())
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_stats_txt(payload: Dict[str, Any]) -> str:
    meta = payload.get("meta", {})
    provenance = payload.get("provenance", {})
    lines: List[str] = []

    lines.append(f"OVERALL STATS REPORT: {meta.get('base_name', '')}")
    lines.append("=" * 60)
    lines.append(f"Generated: {meta.get('generated_at', '')}")
    if meta.get("run_id"):
        lines.append(f"Run ID: {meta.get('run_id')}")
    lines.append("")
    lines.append("PROVENANCE")
    lines.append(f"  Input source: {provenance.get('input_source', 'unknown')}")
    lines.append(f"  Segments: {provenance.get('segment_count', 0)}")
    lines.append(
        f"  Speakers (named / total): {provenance.get('speaker_count_named', 0)} / {provenance.get('speaker_count_total', 0)}"
    )
    exclusions = provenance.get("exclusions", [])
    if exclusions:
        lines.append("  Exclusions:")
        for exclusion in exclusions:
            excluded = ", ".join(exclusion.get("excluded_speakers", [])) or "none"
            lines.append(
                f"    - {exclusion.get('type', '')}: {excluded} ({exclusion.get('why', '')})"
            )
    lines.append("")

    lines.append("MODULE STATUS")
    for spec in _MODULE_SPECS:
        module_info = payload.get("modules", {}).get(spec.module_id, {})
        outputs = ", ".join(module_info.get("outputs", [])) or "-"
        lines.append(
            f"  {spec.label}: {module_info.get('status', 'missing_input')} ({module_info.get('reason', '')})"
        )
        if outputs != "-":
            lines.append(f"    outputs: {outputs}")
    lines.append("")

    speakers = payload.get("speakers", [])
    if speakers:
        lines.append("SPEAKER STATISTICS")
        header = (
            f"{'Speaker':<24} {'Words':>7} {'Segs':>6} {'Dur':>8} "
            f"{'WPM':>7} {'AvgLen':>8} {'AvgDur':>8} {'%W':>6} {'%D':>6} {'Tic':>6}"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for speaker in speakers:
            lines.append(
                f"{speaker.get('name',''):<24} "
                f"{speaker.get('words',0):>7} "
                f"{speaker.get('segments',0):>6} "
                f"{speaker.get('duration_hhmmss','00:00'):>8} "
                f"{speaker.get('words_per_min',0):>7.2f} "
                f"{speaker.get('avg_segment_length_words',0):>8.2f} "
                f"{speaker.get('avg_segment_duration_sec',0):>8.2f} "
                f"{speaker.get('pct_total_words',0):>6.0%} "
                f"{speaker.get('pct_total_duration',0):>6.0%} "
                f"{speaker.get('tic_rate',0):>6.2%}"
            )
        lines.append("")

    sentiment = payload.get("sentiment")
    if sentiment:
        lines.append("SENTIMENT")
        lines.append(f"  Mean compound: {sentiment.get('mean_compound', 0):.3f}")
        spread = sentiment.get("spread", {})
        if "std_compound" in spread:
            lines.append(f"  Spread (std): {spread.get('std_compound', 0):.3f}")
        delta = sentiment.get("opening_vs_closing_delta", {})
        if "delta_by_time" in delta:
            lines.append(
                f"  Delta by time: {delta.get('delta_by_time', 0):.3f}"
            )
        if "delta_by_count" in delta:
            lines.append(
                f"  Delta by count: {delta.get('delta_by_count', 0):.3f}"
            )
        lines.append("")

    insights = payload.get("insights", [])
    if insights:
        lines.append("DERIVED INSIGHTS")
        for insight in insights:
            lines.append(f"  - {insight.get('title', '')}")
        lines.append("")

    warnings = payload.get("warnings", [])
    if warnings:
        lines.append("WARNINGS")
        for warning in warnings:
            lines.append(f"  - {warning}")
        lines.append("")

    outputs_index = payload.get("outputs_index", [])
    if outputs_index:
        lines.append("OUTPUTS INDEX")
        for output in outputs_index:
            lines.append(f"  - {output}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_modules_payload(
    context: Any, transcript_dir: str, base_name: str, module_data: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    modules_payload: Dict[str, Dict[str, Any]] = {}
    for spec in _MODULE_SPECS:
        status, reason, outputs = _resolve_module_status(
            context, transcript_dir, base_name, spec, module_data
        )
        modules_payload[spec.module_id] = {
            "status": status,
            "reason": reason,
            "outputs": outputs,
        }
    return modules_payload


def _resolve_module_status(
    context: Any,
    transcript_dir: str,
    base_name: str,
    spec: ModuleSpec,
    module_data: Dict[str, Any],
) -> Tuple[str, str, List[str]]:
    result = context.get_analysis_result(spec.module_id)
    outputs = _existing_outputs(transcript_dir, base_name, spec.expected_outputs)

    if result is not None:
        status, reason = _interpret_context_result(result)
        if status == "ok" and not outputs and spec.module_id in module_data:
            outputs = _existing_outputs(
                transcript_dir, base_name, spec.expected_outputs
            )
        if status == "ok" and not outputs:
            return "missing_outputs", "result present, outputs missing", []
        return status, reason, outputs

    if outputs:
        return "ok", "outputs present", outputs

    return "missing_input", "no result and no outputs", []


def _interpret_context_result(result: Any) -> Tuple[str, str]:
    if isinstance(result, dict):
        status = result.get("status")
        if status in {"success", "ok"}:
            return "ok", "result success"
        if status == "skipped":
            return "skipped", str(result.get("reason", "skipped"))
        if status == "error" or result.get("error"):
            return "error", str(result.get("error", "error"))
        if result:
            return "ok", "result present"
        return "missing_outputs", "empty result"

    if result:
        return "ok", "result present"
    return "missing_outputs", "empty result"


def _existing_outputs(
    transcript_dir: str, base_name: str, expected_outputs: Iterable[str]
) -> List[str]:
    existing: List[str] = []
    for template in expected_outputs:
        rel_path = template.format(base=base_name)
        path = Path(transcript_dir) / rel_path
        if path.exists():
            existing.append(rel_path)
    return sorted(existing)


def _build_speakers_payload(
    speaker_stats: List[Tuple[Any, Any, Any, Any, Any, Any]],
    sentiment_summary: Dict[str, Dict[str, float]],
    total_words: int,
    total_duration: float,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for duration, name, word_count, segment_count, tic_rate, avg_segment_len in (
        speaker_stats or []
    ):
        if not is_named_speaker(name):
            continue
        duration_sec = float(duration or 0)
        word_count = int(word_count or 0)
        segment_count = int(segment_count or 0)
        avg_segment_len = float(avg_segment_len or 0)
        avg_segment_duration = (
            duration_sec / segment_count if segment_count else 0.0
        )
        words_per_min = (
            word_count / (duration_sec / 60) if duration_sec > 0 else 0.0
        )
        sentiment = sentiment_summary.get(name, {})
        rows.append(
            {
                "name": name,
                "words": word_count,
                "segments": segment_count,
                "duration_sec": duration_sec,
                "duration_hhmmss": format_time(duration_sec),
                "words_per_min": words_per_min,
                "avg_segment_length_words": avg_segment_len,
                "avg_segment_duration_sec": avg_segment_duration,
                "pct_total_words": (word_count / total_words) if total_words else 0.0,
                "pct_total_duration": (
                    duration_sec / total_duration if total_duration else 0.0
                ),
                "tic_rate": float(tic_rate or 0),
                "sentiment": {
                    "compound": sentiment.get("compound", 0),
                    "pos": sentiment.get("pos", 0),
                    "neu": sentiment.get("neu", 0),
                    "neg": sentiment.get("neg", 0),
                },
                "warnings": [],
            }
        )

    rows.sort(key=lambda r: (-r["words"], r["name"]))
    return rows


def _build_sentiment_payload(
    segments: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    sentiments: List[Dict[str, Any]] = []
    warnings: List[str] = []
    has_timestamps = True

    for idx, seg in enumerate(segments):
        text = seg.get("text") or ""
        if not text.strip():
            continue
        start = seg.get("start")
        end = seg.get("end")
        if start is None or end is None or end <= start:
            has_timestamps = False
        score = score_sentiment(text)
        sentiments.append(
            {
                "index": idx,
                "start": start,
                "end": end,
                "compound": score.get("compound", 0),
            }
        )

    if not sentiments:
        return None, warnings

    compounds = [s["compound"] for s in sentiments]
    mean_compound = sum(compounds) / len(compounds) if compounds else 0.0
    std_compound = statistics.pstdev(compounds) if len(compounds) > 1 else 0.0

    delta_by_count = _delta_by_count(sentiments)
    delta_by_time = None
    method = "by_count"

    if has_timestamps:
        delta_by_time = _delta_by_time(sentiments)
        method = "by_time"
    else:
        warnings.append("Missing timestamps; sentiment delta computed by count.")

    delta_payload: Dict[str, Any] = {"method": method, "delta_by_count": delta_by_count}
    if delta_by_time is not None:
        delta_payload["delta_by_time"] = delta_by_time

    payload = {
        "mean_compound": mean_compound,
        "spread": {"std_compound": std_compound},
        "opening_vs_closing_delta": delta_payload,
    }
    return payload, warnings


def _delta_by_count(sentiments: List[Dict[str, Any]]) -> float:
    ordered = sorted(sentiments, key=lambda s: s["index"])
    total = len(ordered)
    window = max(1, int(math.ceil(total * 0.2)))
    first = ordered[:window]
    last = ordered[-window:]
    return _mean_compound(last) - _mean_compound(first)


def _delta_by_time(sentiments: List[Dict[str, Any]]) -> Optional[float]:
    valid = [s for s in sentiments if s["start"] is not None and s["end"] is not None]
    valid = [s for s in valid if s["end"] > s["start"]]
    if not valid:
        return None
    ordered = sorted(valid, key=lambda s: s["start"])
    durations = [s["end"] - s["start"] for s in ordered]
    total_duration = sum(durations)
    if total_duration <= 0:
        return None
    cutoff = total_duration * 0.2
    first_bucket: List[Dict[str, Any]] = []
    last_bucket: List[Dict[str, Any]] = []

    elapsed = 0.0
    for entry, dur in zip(ordered, durations):
        if elapsed < cutoff:
            first_bucket.append(entry)
        elapsed += dur

    elapsed = 0.0
    for entry, dur in zip(reversed(ordered), reversed(durations)):
        if elapsed < cutoff:
            last_bucket.append(entry)
        elapsed += dur

    if not first_bucket or not last_bucket:
        return None
    return _mean_compound(last_bucket) - _mean_compound(first_bucket)


def _mean_compound(entries: List[Dict[str, Any]]) -> float:
    if not entries:
        return 0.0
    return sum(entry["compound"] for entry in entries) / len(entries)


def _build_insights_payload(
    speakers: List[Dict[str, Any]],
    sentiment: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []

    if speakers:
        top_speaker = speakers[0]
        pct_words = top_speaker.get("pct_total_words", 0.0)
        insights.append(
            {
                "id": "top_speaker_word_share",
                "title": f"{top_speaker.get('name', '')} has {pct_words:.0%} of words",
                "severity": "high" if pct_words >= 0.5 else "medium",
                "evidence": [
                    {
                        "kind": "stat",
                        "key": "speakers[0].pct_total_words",
                        "value": pct_words,
                    }
                ],
            }
        )

    if sentiment:
        delta = sentiment.get("opening_vs_closing_delta", {})
        delta_value = delta.get("delta_by_time")
        method = "by_time"
        if delta_value is None:
            delta_value = delta.get("delta_by_count")
            method = "by_count"
        if delta_value is not None:
            insights.append(
                {
                    "id": "sentiment_opening_closing_delta",
                    "title": f"Opening vs closing sentiment delta ({method}) = {delta_value:.3f}",
                    "severity": "medium" if abs(delta_value) >= 0.2 else "low",
                    "evidence": [
                        {
                            "kind": "stat",
                            "key": f"sentiment.opening_vs_closing_delta.{method}",
                            "value": delta_value,
                        }
                    ],
                }
            )

    severity_rank = {"high": 3, "medium": 2, "low": 1, "info": 0}
    insights.sort(
        key=lambda item: (-severity_rank.get(item.get("severity", "low"), 1), item["id"])
    )
    return insights


def _resolve_input_source(segments: List[Dict[str, Any]]) -> str:
    for seg in segments:
        if seg.get("speaker_db_id") is not None or seg.get("transcript_file_id") is not None:
            return "db"
    return "json"


def _segment_quality_stats(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing_timestamps = 0
    zero_duration = 0
    for seg in segments:
        start = seg.get("start")
        end = seg.get("end")
        if start is None or end is None:
            missing_timestamps += 1
            continue
        if end <= start:
            zero_duration += 1

    warnings = []
    if missing_timestamps:
        warnings.append(f"{missing_timestamps} segments missing timestamps.")
    if zero_duration:
        warnings.append(f"{zero_duration} segments have zero or negative duration.")

    return {
        "missing_timestamps": missing_timestamps,
        "zero_duration": zero_duration,
        "warnings": warnings,
    }


def _resolve_generator_metadata(
    overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    metadata = {"name": "transcriptx", "version": None, "git_sha": None}
    try:
        metadata["version"] = importlib.metadata.version("transcriptx")
    except Exception:
        metadata["version"] = None
    if overrides:
        metadata.update({k: v for k, v in overrides.items() if v is not None})
    return metadata


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
