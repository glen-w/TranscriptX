"""Lexical diversity analysis module."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.lexical_diversity import (
    TIME_BUCKET_SECONDS,
    build_metadata,
    compute_lexical_diversity_metrics,
)
from transcriptx.core.utils.notifications import notify_user
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)
from transcriptx.core.utils.viz_ids import (
    VIZ_LEXICAL_DIVERSITY_HAPAX_RATE_SPEAKER,
    VIZ_LEXICAL_DIVERSITY_MTLD_SPEAKER,
    VIZ_LEXICAL_DIVERSITY_TTR_SPEAKER,
)
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.utils.text_utils import (
    is_named_speaker,
    is_turn_taking_speaker_label,
)

if TYPE_CHECKING:
    from transcriptx.core.output.output_service import OutputService


def _segment_sort_key(segment: Dict[str, Any], index: int) -> Tuple[float, float, int]:
    start = segment.get("start")
    end = segment.get("end")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return (float(start), float(end), index)
    return (float(index), 0.0, index)


def _valid_timestamp(segment: Dict[str, Any]) -> bool:
    start = segment.get("start")
    end = segment.get("end")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return False
    if start != start or end != end:
        return False
    if start < 0 or end < 0 or start > end:
        return False
    return True


class LexicalDiversityAnalysis(AnalysisModule):
    """Lexical diversity metrics (TTR, MTLD, hapax rate) per speaker and globally."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "lexical_diversity"

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        grouped_segments: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        eligible_segments: List[Tuple[int, Dict[str, Any]]] = []
        exclusions = {
            "skipped_segments": 0,
            "skipped_reasons": {"no_speaker": 0, "ineligible_speaker": 0},
            "eligible_segment_count": 0,
        }

        for index, seg in enumerate(segments):
            info = extract_speaker_info(seg)
            if info is not None:
                grouping_key = info.grouping_key
            else:
                label = seg.get("speaker")
                grouping_key = str(label) if label else None
            if grouping_key is None:
                exclusions["skipped_segments"] += 1
                exclusions["skipped_reasons"]["no_speaker"] += 1
                continue
            grouped_segments[grouping_key].append(seg)

        speaker_stats: Dict[str, Dict[str, Any]] = {}
        for grouping_key, segs in grouped_segments.items():
            display_name = get_speaker_display_name(grouping_key, segs, segments)
            if not display_name or not is_turn_taking_speaker_label(display_name):
                exclusions["skipped_segments"] += len(segs)
                exclusions["skipped_reasons"]["ineligible_speaker"] += len(segs)
                continue
            ordered = sorted(
                enumerate(segs),
                key=lambda pair: _segment_sort_key(pair[1], pair[0]),
            )
            text = " ".join(str(pair[1].get("text", "")) for pair in ordered)
            speaker_stats[display_name] = compute_lexical_diversity_metrics(text)
            for pair in ordered:
                eligible_segments.append((pair[0], pair[1]))
                exclusions["eligible_segment_count"] += 1

        eligible_segments.sort(key=lambda pair: _segment_sort_key(pair[1], pair[0]))
        global_text = " ".join(str(seg.get("text", "")) for _, seg in eligible_segments)
        global_stats = compute_lexical_diversity_metrics(global_text)
        time_buckets = self._build_time_buckets(eligible_segments)

        return {
            "metadata": build_metadata(),
            "speaker_stats": speaker_stats,
            "global_stats": global_stats,
            "time_buckets": time_buckets,
            "exclusions": exclusions,
        }

    def _build_time_buckets(
        self, eligible_segments: List[Tuple[int, Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        if not eligible_segments:
            return []
        if not all(_valid_timestamp(seg) for _, seg in eligible_segments):
            return []
        t0 = min(float(seg["start"]) for _, seg in eligible_segments)
        bucket_text: Dict[int, List[str]] = defaultdict(list)
        for _, seg in eligible_segments:
            start = float(seg["start"])
            bucket_index = int((start - t0) // TIME_BUCKET_SECONDS)
            bucket_text[bucket_index].append(str(seg.get("text", "")))
        buckets: List[Dict[str, Any]] = []
        for bucket_index in sorted(bucket_text):
            text = " ".join(bucket_text[bucket_index])
            metrics = compute_lexical_diversity_metrics(text)
            bucket_start = t0 + bucket_index * TIME_BUCKET_SECONDS
            bucket_end = bucket_start + TIME_BUCKET_SECONDS
            buckets.append(
                {
                    "bucket_index": bucket_index,
                    "bucket_start": bucket_start,
                    "bucket_end": bucket_end,
                    **metrics,
                }
            )
        return buckets

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()
        payload = {
            "schema_id": results["metadata"]["schema_id"],
            "metadata": results["metadata"],
            "speaker_stats": results["speaker_stats"],
            "global_stats": results["global_stats"],
            "time_buckets": results["time_buckets"],
            "exclusions": results["exclusions"],
        }
        output_service.save_data(payload, "lexical_diversity", format_type="json")
        csv_path = Path(output_structure.global_data_dir) / (
            f"{base_name}_lexical_diversity.csv"
        )
        _save_lexical_diversity_csv(payload, csv_path)
        output_service.record_file(csv_path, "csv")
        _plot_lexical_diversity_charts(payload, output_service)
        output_service.save_summary(
            results["global_stats"],
            results["speaker_stats"],
            analysis_metadata=results["metadata"],
        )
        skipped = results["exclusions"].get("skipped_segments", 0)
        if skipped:
            notify_user(
                f"⚠️ Skipped {skipped} segments for lexical diversity eligibility.",
                technical=True,
                section="lexical_diversity",
            )


def _save_lexical_diversity_csv(payload: Dict[str, Any], csv_path: Path) -> None:
    fieldnames = [
        "scope",
        "speaker",
        "bucket_start",
        "bucket_end",
        "token_count",
        "type_count",
        "hapax_count",
        "ttr",
        "mtld",
        "hapax_rate",
    ]
    rows: List[Dict[str, Any]] = []

    def append_row(
        scope: str, speaker: str, metrics: Dict[str, Any], **extra: Any
    ) -> None:
        rows.append(
            {
                "scope": scope,
                "speaker": speaker,
                "bucket_start": extra.get("bucket_start", ""),
                "bucket_end": extra.get("bucket_end", ""),
                "token_count": metrics.get("token_count", 0),
                "type_count": metrics.get("type_count", 0),
                "hapax_count": metrics.get("hapax_count", 0),
                "ttr": _csv_number(metrics.get("ttr")),
                "mtld": _csv_number(metrics.get("mtld")),
                "hapax_rate": _csv_number(metrics.get("hapax_rate")),
            }
        )

    append_row("global", "", payload.get("global_stats") or {})
    for speaker in sorted((payload.get("speaker_stats") or {}).keys()):
        append_row("speaker", speaker, payload["speaker_stats"][speaker])
    for bucket in payload.get("time_buckets") or []:
        append_row(
            "time_bucket",
            "",
            bucket,
            bucket_start=f"{bucket.get('bucket_start', ''):.6f}",
            bucket_end=f"{bucket.get('bucket_end', ''):.6f}",
        )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _csv_number(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"


def _plot_lexical_diversity_charts(
    payload: Dict[str, Any],
    output_service: "OutputService",
) -> None:
    # Charts are named-speaker only (output-contract); JSON may still keep
    # turn-taking labels such as SPEAKER_03 for completeness.
    speaker_stats = {
        speaker: stats
        for speaker, stats in (payload.get("speaker_stats") or {}).items()
        if is_named_speaker(str(speaker)) and isinstance(stats, dict)
    }
    if not speaker_stats:
        return

    def plot_ratio(
        metric: str,
        viz_id: str,
        chart_name: str,
        *,
        skip_null: bool = False,
    ) -> None:
        labels: List[str] = []
        values: List[float] = []
        for speaker in sorted(speaker_stats):
            value = speaker_stats[speaker].get(metric)
            if value is None and skip_null:
                continue
            if value is None:
                continue
            labels.append(speaker)
            values.append(float(value))
        if not labels:
            return
        spec = BarCategoricalSpec(
            viz_id=viz_id,
            module="lexical_diversity",
            name=chart_name,
            scope="global",
            chart_intent="bar_categorical",
            title=f"Lexical diversity: {metric} by speaker",
            x_label="Speaker",
            y_label=metric,
            categories=labels,
            values=values,
        )
        output_service.save_chart(spec, chart_type="lexical_diversity")

    plot_ratio("ttr", VIZ_LEXICAL_DIVERSITY_TTR_SPEAKER, "lexical-ttr")
    plot_ratio(
        "mtld",
        VIZ_LEXICAL_DIVERSITY_MTLD_SPEAKER,
        "lexical-mtld",
        skip_null=True,
    )
    plot_ratio(
        "hapax_rate",
        VIZ_LEXICAL_DIVERSITY_HAPAX_RATE_SPEAKER,
        "lexical-hapax-rate",
    )
