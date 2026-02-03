"""Output and report generation helpers for acts analysis."""

from __future__ import annotations

import os
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from transcriptx.core.analysis.acts.classification import classify_utterance
from transcriptx.core.analysis.acts.config import (
    ClassificationMethod,
    get_act_config,
    get_all_act_types,
)
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.notifications import notify_user
from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    create_summary_json,
)
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec
from transcriptx.core.utils.path_utils import get_enriched_transcript_path
from transcriptx.io import save_csv, save_json, save_transcript
from transcriptx.utils.text_utils import is_named_speaker

plt = lazy_pyplot()

# Get act types from configuration
ACT_TYPES = get_all_act_types()


def generate_acts_charts(
    output_service: Any,
    tagged_segments: list,
    act_counts_global: dict,
    act_counts_per_speaker: dict,
    base_name: str,
) -> None:
    """Generate all acts charts (pie, bar, timeline per speaker and global) via output_service."""
    from transcriptx.core.utils.speaker_extraction import (
        extract_speaker_info,
        get_speaker_display_name,
    )

    speakers = sorted(
        [s for s in act_counts_per_speaker.keys() if is_named_speaker(s)]
    )

    # Per-speaker pie + bar charts
    for speaker, counter in act_counts_per_speaker.items():
        acts = sorted(counter.keys())
        counts = [counter[act] for act in acts]
        total = sum(counts)
        filtered = [
            (a, c) for a, c in zip(acts, counts, strict=False) if c / total > 0.05
        ]
        if filtered:
            acts_filt, counts_filt = zip(*filtered, strict=False)
            acts_filt, counts_filt = list(acts_filt), list(counts_filt)
        else:
            acts_filt, counts_filt = [], []

        if acts_filt:
            output_service.save_chart(
                BarCategoricalSpec(
                    viz_id="acts.acts_pie.speaker",
                    module="acts",
                    name="acts_pie",
                    scope="speaker",
                    speaker=speaker,
                    chart_intent="bar_categorical",
                    title=f"Dialogue Acts (Filtered) – {speaker}",
                    x_label="Act Type",
                    y_label="Count",
                    categories=acts_filt,
                    values=counts_filt,
                ),
                chart_type="pie",
            )
        if acts:
            output_service.save_chart(
                BarCategoricalSpec(
                    viz_id="acts.acts_bar.speaker",
                    module="acts",
                    name="acts_bar",
                    scope="speaker",
                    speaker=speaker,
                    chart_intent="bar_categorical",
                    title=f"Dialogue Acts – {speaker}",
                    x_label="Act Type",
                    y_label="Count",
                    categories=acts,
                    values=counts,
                ),
                chart_type="bar",
            )

    # Global pie chart
    if act_counts_global:
        acts = sorted(act_counts_global.keys())
        counts = [act_counts_global[act] for act in acts]
        total = sum(counts)
        filtered = [
            (a, c) for a, c in zip(acts, counts, strict=False) if c / total > 0.05
        ]
        if filtered:
            acts_filt, counts_filt = zip(*filtered, strict=False)
            acts_filt, counts_filt = list(acts_filt), list(counts_filt)
        else:
            acts_filt, counts_filt = [], []
        if acts_filt:
            output_service.save_chart(
                BarCategoricalSpec(
                    viz_id="acts.global_acts_pie.global",
                    module="acts",
                    name="global_acts_pie",
                    scope="global",
                    chart_intent="bar_categorical",
                    title="Dialogue Acts (Filtered) – All Speakers",
                    x_label="Act Type",
                    y_label="Count",
                    categories=acts_filt,
                    values=counts_filt,
                ),
                chart_type="pie",
            )

    # Global bar chart: act types × speakers
    all_acts = sorted(set(ACT_TYPES))
    if not speakers:
        notify_user(
            "⚠️ No named speakers found for dialogue act bar chart. Skipping plot.",
            technical=True,
            section="acts",
        )
    else:
        bar_series = [
            {
                "name": s,
                "categories": all_acts,
                "values": [act_counts_per_speaker[s].get(act, 0) for act in all_acts],
            }
            for s in speakers
        ]
        output_service.save_chart(
            BarCategoricalSpec(
                viz_id="acts.global_acts_bar.global",
                module="acts",
                name="global_acts_bar",
                scope="global",
                chart_intent="bar_categorical",
                title="Dialogue Acts by Speaker",
                x_label="Dialogue Act",
                y_label="Count",
                categories=all_acts,
                values=[0] * len(all_acts),
                series=bar_series,
            ),
            chart_type="bar",
        )

    # Global temporal: acts over time, all speakers (use separate list, not bar series)
    if act_counts_global and speakers:
        total = sum(act_counts_global.values())
        acts_over_5 = [a for a, c in act_counts_global.items() if c / total > 0.05]
        act_idx_map = {a: i for i, a in enumerate(acts_over_5)}
        temporal_series = []
        for speaker in speakers:
            times = []
            acts_list = []
            for seg in tagged_segments:
                speaker_info = extract_speaker_info(seg)
                if speaker_info is None:
                    continue
                spk = get_speaker_display_name(
                    speaker_info.grouping_key, [seg], tagged_segments
                )
                if spk != speaker:
                    continue
                act = seg.get("dialogue_act", "")
                if act in acts_over_5:
                    acts_list.append(act)
                    times.append(seg.get("start", 0) / 60.0)
            y_vals = [act_idx_map[a] for a in acts_list]
            temporal_series.append({"name": speaker, "x": times, "y": y_vals})
        if temporal_series:
            output_service.save_chart(
                LineTimeSeriesSpec(
                    viz_id="acts.acts_temporal_all.global",
                    module="acts",
                    name="acts_temporal_all",
                    scope="global",
                    chart_intent="line_timeseries",
                    title="Dialogue Acts Over Time – All Speakers",
                    x_label="Time (minutes)",
                    y_label="Dialogue Act (index)",
                    markers=True,
                    series=temporal_series,
                ),
                chart_type="temporal",
            )

    # Per-speaker temporal plots
    for speaker in speakers:
        counter = act_counts_per_speaker[speaker]
        total = sum(counter.values())
        acts_over_5 = [a for a, c in counter.items() if c / total > 0.05]
        act_idx_map = {a: i for i, a in enumerate(acts_over_5)}
        times = []
        acts_list = []
        for seg in tagged_segments:
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue
            spk = get_speaker_display_name(
                speaker_info.grouping_key, [seg], tagged_segments
            )
            if spk != speaker:
                continue
            act = seg.get("dialogue_act", "")
            if act in acts_over_5:
                acts_list.append(act)
                times.append(seg.get("start", 0) / 60.0)
        y_vals = [act_idx_map[a] for a in acts_list]
        if not y_vals:
            continue
        output_service.save_chart(
            LineTimeSeriesSpec(
                viz_id="acts.acts_temporal.speaker",
                module="acts",
                name="acts_temporal",
                scope="speaker",
                speaker=speaker,
                chart_intent="line_timeseries",
                title=f"Dialogue Acts Over Time – {speaker}",
                x_label="Time (minutes)",
                y_label="Dialogue Act (index)",
                markers=True,
                series=[{"name": speaker, "x": times, "y": y_vals}],
            ),
            chart_type="temporal",
        )


def tag_acts(
    segments: list,
    base_name: str,
    transcript_dir: str,
    speaker_map: dict,
    transcript_path: str,
):
    # --- Directory structure ---
    config = get_act_config()

    # Use output standards for directory structure
    output_structure = create_standard_output_structure(transcript_dir, "acts")
    output_service = create_output_service(
        transcript_path,
        "acts",
        output_dir=transcript_dir,
        run_id=Path(transcript_dir).name,
    )

    tagged_segments = []
    act_counts_global = Counter()
    act_counts_per_speaker = defaultdict(Counter)
    act_confidence_scores = defaultdict(list)

    # For both methods, track separate results
    ml_segments = []
    rules_segments = []
    comparison_data = []

    # Build conversation context for better classification
    conversation_context = {
        "previous_utterances": [],
        "speaker_roles": {},
        "conversation_topic": "",
    }

    for i, seg in enumerate(segments):
        text = seg.get("text", "")

        # Create context for this utterance
        context = {
            "previous_utterances": conversation_context["previous_utterances"][-3:],
            "speaker_role": conversation_context["speaker_roles"].get(
                seg.get("speaker", "UNKNOWN"), ""
            ),
            "conversation_topic": conversation_context["conversation_topic"],
            "utterance_index": i,
            "total_utterances": len(segments),
        }

        # Classify with context
        classification_result = classify_utterance(text, context)

        # Extract act type and confidence from the result
        act = classification_result["act_type"]
        confidence = classification_result["confidence"]

        # Store results
        seg["dialogue_act"] = act
        seg["act_confidence"] = confidence
        seg["act_method"] = classification_result.get("method", "unknown")
        seg["act_probabilities"] = classification_result.get("probabilities", {})

        # Handle both methods results
        if config.method == ClassificationMethod.BOTH:
            ml_result = classification_result.get("ml_result", {})
            rules_result = classification_result.get("rules_result", {})

            # Create separate segments for each method
            ml_seg = seg.copy()
            ml_seg["dialogue_act"] = ml_result.get("act_type", "statement")
            ml_seg["act_confidence"] = ml_result.get("confidence", 0.5)
            ml_seg["act_method"] = "ml"
            ml_segments.append(ml_seg)

            rules_seg = seg.copy()
            rules_seg["dialogue_act"] = rules_result.get("act_type", "statement")
            rules_seg["act_confidence"] = rules_result.get("confidence", 0.5)
            rules_seg["act_method"] = "rules"
            rules_segments.append(rules_seg)

            # Store comparison data
            comparison_data.append(
                {
                    "utterance_index": i,
                    "text": text,
                    "speaker": seg.get("speaker", "UNKNOWN"),
                    "ml_act": ml_result.get("act_type", "statement"),
                    "ml_confidence": ml_result.get("confidence", 0.5),
                    "rules_act": rules_result.get("act_type", "statement"),
                    "rules_confidence": rules_result.get("confidence", 0.5),
                    "methods_agreed": classification_result.get(
                        "methods_agreed", False
                    ),
                    "confidence_difference": classification_result.get(
                        "confidence_difference", 0.0
                    ),
                }
            )

        # Update conversation context
        conversation_context["previous_utterances"].append(text)
        if len(conversation_context["previous_utterances"]) > 10:  # Keep last 10 utterances
            conversation_context["previous_utterances"] = conversation_context[
                "previous_utterances"
            ][-10:]

        # Use database-driven speaker extraction
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        speaker_info = extract_speaker_info(seg)
        if speaker_info is None:
            continue
        speaker = get_speaker_display_name(speaker_info.grouping_key, [seg], segments)
        if not is_named_speaker(speaker):
            continue

        act_counts_global[act] += 1
        act_counts_per_speaker[speaker][act] += 1
        act_confidence_scores[act].append(confidence)
        tagged_segments.append(seg)

    # --- Save tagged transcript ---
    transcript_out = get_enriched_transcript_path(transcript_path, "acts")
    save_transcript(tagged_segments, transcript_out)

    # Save separate outputs for both methods
    if config.method == ClassificationMethod.BOTH and config.create_separate_outputs:
        both_dir = os.path.join(transcript_dir, "acts", config.both_methods_output_dir)
        ml_dir = os.path.join(both_dir, "ml")
        rules_dir = os.path.join(both_dir, "rules")
        comparison_dir = os.path.join(both_dir, "comparison")
        os.makedirs(ml_dir, exist_ok=True)
        os.makedirs(rules_dir, exist_ok=True)
        os.makedirs(comparison_dir, exist_ok=True)

        ml_transcript_out = os.path.join(ml_dir, f"{base_name}_ml_acts.json")
        rules_transcript_out = os.path.join(rules_dir, f"{base_name}_rules_acts.json")
        comparison_out = os.path.join(comparison_dir, f"{base_name}_comparison.json")

        save_transcript(ml_segments, ml_transcript_out)
        save_transcript(rules_segments, rules_transcript_out)
        save_json({"comparison_data": comparison_data}, comparison_out)

        # Generate separate summaries for each method
        _generate_method_summary(ml_segments, base_name, ml_dir, None, "ML")
        _generate_method_summary(rules_segments, base_name, rules_dir, None, "Rules")
        _generate_comparison_summary(comparison_data, base_name, comparison_dir)

    # --- Per-speaker summaries with confidence scores ---
    summary_txt = os.path.join(
        output_structure.data_dir, f"{base_name}_acts_summary.txt"
    )
    summary_json = os.path.join(
        output_structure.data_dir, f"{base_name}_acts_summary.json"
    )
    csv_rows = []

    import io

    summary_buffer = io.StringIO()
    summary_dict = {}
    f_txt = summary_buffer
    f_txt.write("=== DIALOGUE ACT ANALYSIS ===\n\n")

    # Classification method statistics
    method_counts = Counter()
    for seg in tagged_segments:
        method = seg.get("act_method", "unknown")
        method_counts[method] += 1

    f_txt.write("CLASSIFICATION METHODS USED:\n")
    f_txt.write("-" * 30 + "\n")
    for method, count in method_counts.most_common():
        percentage = (count / len(tagged_segments)) * 100
        f_txt.write(f"  • {method}: {count} ({percentage:.1f}%)\n")
    f_txt.write("\n")

    # Global statistics
    f_txt.write("GLOBAL STATISTICS:\n")
    f_txt.write("-" * 20 + "\n")
    for act in sorted(ACT_TYPES):
        count = act_counts_global.get(act, 0)
        if count > 0:
            avg_confidence = sum(act_confidence_scores[act]) / len(
                act_confidence_scores[act]
            )
            f_txt.write(f"  • {act}: {count} (avg confidence: {avg_confidence:.3f})\n")
    f_txt.write("\n")

    # Per-speaker statistics
    f_txt.write("PER-SPEAKER STATISTICS:\n")
    f_txt.write("-" * 25 + "\n")
    if len(act_counts_per_speaker) == 0:
        f_txt.write("No speaker data available.\n")
    for speaker in sorted(act_counts_per_speaker):
        f_txt.write(f"{speaker}:\n")
        counter = act_counts_per_speaker[speaker]
        row = {"speaker": speaker}
        for act in sorted(ACT_TYPES):
            count = counter.get(act, 0)
            f_txt.write(f"  • {act}: {count}\n")
            row[act] = count
        f_txt.write("\n")
        csv_rows.append(row)
        summary_dict[speaker] = dict(counter)

    write_text(summary_txt, summary_buffer.getvalue())
    save_json(summary_dict, summary_json)
    save_csv(
        csv_rows,
        os.path.join(output_structure.data_dir, f"{base_name}_acts_summary.csv"),
    )

    # --- Confidence analysis ---
    confidence_analysis = {}
    for act in ACT_TYPES:
        if act_confidence_scores[act]:
            confidence_analysis[act] = {
                "count": len(act_confidence_scores[act]),
                "avg_confidence": sum(act_confidence_scores[act])
                / len(act_confidence_scores[act]),
                "min_confidence": min(act_confidence_scores[act]),
                "max_confidence": max(act_confidence_scores[act]),
            }

    confidence_file = os.path.join(
        output_structure.data_dir, f"{base_name}_acts_confidence.json"
    )
    save_json(confidence_analysis, confidence_file)

    # --- Charts: pie, bar, timeline per speaker and global ---
    generate_acts_charts(
        output_service,
        tagged_segments,
        dict(act_counts_global),
        {k: dict(v) for k, v in act_counts_per_speaker.items()},
        base_name,
    )

    # Aggregate per-speaker stats
    speaker_stats = {
        speaker: dict(counter) for speaker, counter in act_counts_per_speaker.items()
    }
    # Aggregate global stats
    global_stats = {"total_segments": len(tagged_segments)}
    for act in ACT_TYPES:
        global_stats[act] = act_counts_global.get(act, 0)
    # Write standardized summary
    create_summary_json(
        module_name="acts",
        base_name=base_name,
        global_data=global_stats,
        speaker_data=speaker_stats,
        analysis_metadata={},
        output_structure=output_structure,
    )


def _generate_method_summary(
    segments: list,
    base_name: str,
    output_dir: str,
    speaker_map: dict | None,
    method_name: str,
):
    """Generate summary for a specific classification method.

    Args:
        segments: List of transcript segments
        base_name: Base name for file naming
        output_dir: Output directory
        speaker_map: Deprecated - no longer used (kept for backward compatibility)
        method_name: Name of the classification method
    """
    from transcriptx.core.utils.speaker_extraction import (
        extract_speaker_info,
        get_speaker_display_name,
    )

    act_counts_global = Counter()
    act_counts_per_speaker = defaultdict(Counter)
    act_confidence_scores = defaultdict(list)

    for seg in segments:
        act = seg.get("dialogue_act", "statement")
        confidence = seg.get("act_confidence", 0.5)

        speaker_info = extract_speaker_info(seg)
        if speaker_info is None:
            continue
        speaker = get_speaker_display_name(speaker_info.grouping_key, [seg], segments)
        if not is_named_speaker(speaker):
            continue

        act_counts_global[act] += 1
        act_counts_per_speaker[speaker][act] += 1
        act_confidence_scores[act].append(confidence)

    # Generate summary text
    summary_txt = os.path.join(
        output_dir, f"{base_name}_{method_name.lower()}_summary.txt"
    )
    summary_json = os.path.join(
        output_dir, f"{base_name}_{method_name.lower()}_summary.json"
    )
    csv_rows = []
    import io

    summary_buffer = io.StringIO()
    summary_dict = {}
    f_txt = summary_buffer
    f_txt.write(f"=== {method_name.upper()} DIALOGUE ACT ANALYSIS ===\n\n")

    # Global statistics
    f_txt.write("GLOBAL STATISTICS:\n")
    f_txt.write("-" * 20 + "\n")
    for act in sorted(ACT_TYPES):
        count = act_counts_global.get(act, 0)
        if count > 0:
            avg_confidence = sum(act_confidence_scores[act]) / len(
                act_confidence_scores[act]
            )
            f_txt.write(f"  • {act}: {count} (avg confidence: {avg_confidence:.3f})\n")
    f_txt.write("\n")

    # Per-speaker statistics
    f_txt.write("PER-SPEAKER STATISTICS:\n")
    f_txt.write("-" * 25 + "\n")
    for speaker in sorted(act_counts_per_speaker):
        f_txt.write(f"{speaker}:\n")
        counter = act_counts_per_speaker[speaker]
        row = {"speaker": speaker}
        for act in sorted(ACT_TYPES):
            count = counter.get(act, 0)
            f_txt.write(f"  • {act}: {count}\n")
            row[act] = count
        f_txt.write("\n")
        csv_rows.append(row)
        summary_dict[speaker] = dict(counter)

    write_text(summary_txt, summary_buffer.getvalue())
    save_json(summary_dict, summary_json)
    save_csv(
        csv_rows,
        os.path.join(output_dir, f"{base_name}_{method_name.lower()}_summary.csv"),
    )


def _generate_comparison_summary(
    comparison_data: list, base_name: str, output_dir: str
):
    """Generate comparison summary between ML and Rules methods."""
    summary_txt = os.path.join(output_dir, f"{base_name}_comparison_summary.txt")
    summary_json = os.path.join(output_dir, f"{base_name}_comparison_summary.json")

    # Calculate statistics
    total_utterances = len(comparison_data)
    agreements = sum(1 for item in comparison_data if item.get("methods_agreed", False))
    disagreements = total_utterances - agreements
    agreement_rate = (
        (agreements / total_utterances) * 100 if total_utterances > 0 else 0
    )

    # Average confidence differences
    confidence_differences = [
        item.get("confidence_difference", 0.0) for item in comparison_data
    ]
    avg_confidence_diff = (
        sum(confidence_differences) / len(confidence_differences)
        if confidence_differences
        else 0.0
    )

    # Count act types for each method
    ml_acts = Counter(item.get("ml_act", "statement") for item in comparison_data)
    rules_acts = Counter(item.get("rules_act", "statement") for item in comparison_data)

    # Find disagreements
    disagreements_list = [
        item for item in comparison_data if not item.get("methods_agreed", False)
    ]

    import io

    summary_buffer = io.StringIO()
    f_txt = summary_buffer
    f_txt.write("=== ML vs RULES COMPARISON ANALYSIS ===\n\n")

    f_txt.write("OVERALL STATISTICS:\n")
    f_txt.write("-" * 20 + "\n")
    f_txt.write(f"Total utterances: {total_utterances}\n")
    f_txt.write(f"Methods agreed: {agreements} ({agreement_rate:.1f}%)\n")
    f_txt.write(f"Methods disagreed: {disagreements} ({100-agreement_rate:.1f}%)\n")
    f_txt.write(f"Average confidence difference: {avg_confidence_diff:.3f}\n\n")

    f_txt.write("ML METHOD ACT DISTRIBUTION:\n")
    f_txt.write("-" * 30 + "\n")
    for act, count in ml_acts.most_common():
        percentage = (count / total_utterances) * 100
        f_txt.write(f"  • {act}: {count} ({percentage:.1f}%)\n")
    f_txt.write("\n")

    f_txt.write("RULES METHOD ACT DISTRIBUTION:\n")
    f_txt.write("-" * 32 + "\n")
    for act, count in rules_acts.most_common():
        percentage = (count / total_utterances) * 100
        f_txt.write(f"  • {act}: {count} ({percentage:.1f}%)\n")
    f_txt.write("\n")

    if disagreements_list:
        f_txt.write("SAMPLE DISAGREEMENTS:\n")
        f_txt.write("-" * 20 + "\n")
        for i, item in enumerate(disagreements_list[:10]):  # Show first 10 disagreements
            f_txt.write(f"{i+1}. Text: \"{item.get('text', '')[:50]}...\"\n")
            f_txt.write(
                f"   ML: {item.get('ml_act', '')} (conf: {item.get('ml_confidence', 0):.2f})\n"
            )
            f_txt.write(
                f"   Rules: {item.get('rules_act', '')} (conf: {item.get('rules_confidence', 0):.2f})\n"
            )
            f_txt.write(
                f"   Confidence diff: {item.get('confidence_difference', 0):.3f}\n\n"
            )

    write_text(summary_txt, summary_buffer.getvalue())

    # Save summary as JSON
    summary_dict = {
        "total_utterances": total_utterances,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate": agreement_rate,
        "avg_confidence_difference": avg_confidence_diff,
        "ml_act_distribution": dict(ml_acts),
        "rules_act_distribution": dict(rules_acts),
        "sample_disagreements": disagreements_list[:10],
    }

    save_json(summary_dict, summary_json)
