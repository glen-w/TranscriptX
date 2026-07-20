"""
Understandability Analysis Module for TranscriptX.
"""

import json
from pathlib import Path

import pandas as pd
from nltk.tokenize import sent_tokenize, word_tokenize
from textstat import (
    automated_readability_index,
    flesch_reading_ease,
    gunning_fog,
    smog_index,
)

from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    create_summary_json,
)
from transcriptx.core.output.output_service import create_output_service
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.notifications import notify_user


# Ensure NLTK punkt tokenizer is available
def _ensure_nltk_punkt():
    """Ensure NLTK punkt tokenizer is downloaded before using tokenize functions."""
    try:
        import nltk

        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            # Tokenizer not found, try to download it
            try:
                notify_user(
                    "📥 Downloading NLTK punkt tokenizer (required for understandability analysis)...",
                    technical=True,
                    section="understandability",
                )
            except Exception:
                # Fallback to print if notify_user isn't available yet
                print(
                    "📥 Downloading NLTK punkt tokenizer (required for understandability analysis)..."
                )
            nltk.download("punkt", quiet=True)
            # Also download punkt_tab if available (newer NLTK versions)
            try:
                nltk.download("punkt_tab", quiet=True)
            except Exception:
                # punkt_tab may not be available in older NLTK versions, that's okay
                pass
    except Exception as e:
        error_msg = (
            f"⚠️ Could not download NLTK punkt tokenizer: {e}. "
            "Please run: python -c \"import nltk; nltk.download('punkt')\""
        )
        try:
            notify_user(error_msg, technical=True, section="understandability")
        except Exception:
            print(error_msg)
        raise


def _ensure_nltk_cmudict():
    """Ensure NLTK cmudict corpus is available for textstat syllable counting."""
    try:
        import nltk

        try:
            nltk.data.find("corpora/cmudict")
        except LookupError:
            try:
                notify_user(
                    "📥 Downloading NLTK cmudict corpus (required for readability metrics)...",
                    technical=True,
                    section="understandability",
                )
            except Exception:
                print(
                    "📥 Downloading NLTK cmudict corpus (required for readability metrics)..."
                )
            nltk.download("cmudict", quiet=True)
    except Exception as e:
        error_msg = (
            f"⚠️ Could not download NLTK cmudict corpus: {e}. "
            "Please run: python -c \"import nltk; nltk.download('cmudict')\""
        )
        try:
            notify_user(error_msg, technical=True, section="understandability")
        except Exception:
            print(error_msg)
        raise


# Ensure NLTK data is available before module functions are used
_ensure_nltk_punkt()
_ensure_nltk_cmudict()


def compute_understandability_metrics(text: str) -> dict:
    sentences = sent_tokenize(text)
    words = word_tokenize(text)
    sentence_count = len(sentences)
    word_count = len(words)
    avg_sentence_length = word_count / sentence_count if sentence_count else 0
    lexical_density = len(set(words)) / word_count if word_count else 0

    return {
        "flesch_reading_ease": flesch_reading_ease(text),
        "gunning_fog_index": gunning_fog(text),
        "smog_index": smog_index(text),
        "automated_readability_index": automated_readability_index(text),
        "avg_sentence_length": avg_sentence_length,
        "lexical_density": lexical_density,
        "word_count": word_count,
        "sentence_count": sentence_count,
    }


def save_understandability_csv(all_scores: dict, output_structure, base_name: str):
    # Only include named speakers
    filtered_scores = {s: v for s, v in all_scores.items() if is_named_speaker(s)}

    # Check if we have any scores to save
    if not filtered_scores:
        notify_user(
            "⚠️ No named speaker scores available for understandability CSV. Skipping CSV generation.",
            technical=True,
            section="analyze",
        )
        return

    df = pd.DataFrame.from_dict(filtered_scores, orient="index")
    df.index.name = "speaker"
    df.reset_index(inplace=True)

    out_path = output_structure.global_data_dir / f"{base_name}_understandability.csv"
    df.to_csv(out_path, index=False)
    notify_user(
        f"✅ Global CSV saved to {out_path}", technical=False, section="analyze"
    )

    # Ensure speakers directory exists
    output_structure.speaker_data_dir.mkdir(parents=True, exist_ok=True)

    for speaker, metrics in filtered_scores.items():
        speaker_safe = str(speaker).replace(" ", "_")
        speaker_df = pd.DataFrame([metrics])
        speaker_out = (
            output_structure.speaker_data_dir
            / f"{base_name}_understandability_{speaker_safe}.csv"
        )
        speaker_df.to_csv(speaker_out, index=False)
        notify_user(
            f"📄 Speaker CSV saved to {speaker_out}", technical=True, section="analyze"
        )


def save_understandability_json(all_scores: dict, output_structure, base_name: str):
    # Only include named speakers
    filtered_scores = {s: v for s, v in all_scores.items() if is_named_speaker(s)}
    global_path = (
        output_structure.global_data_dir / f"{base_name}_understandability.json"
    )
    with open(global_path, "w") as f:
        json.dump(filtered_scores, f, indent=2)
    notify_user(
        f"✅ Global JSON saved to {global_path}", technical=False, section="analyze"
    )

    # Ensure speakers directory exists
    output_structure.speaker_data_dir.mkdir(parents=True, exist_ok=True)

    for speaker, metrics in filtered_scores.items():
        speaker_safe = str(speaker).replace(" ", "_")
        speaker_path = (
            output_structure.speaker_data_dir
            / f"{base_name}_understandability_{speaker_safe}.json"
        )
        with open(speaker_path, "w") as f:
            json.dump(metrics, f, indent=2)
        notify_user(
            f"📄 Speaker JSON saved to {speaker_path}",
            technical=True,
            section="analyze",
        )


def plot_understandability_charts(
    all_scores: dict, output_structure, base_name: str, output_service
):
    """Plot and persist understandability charts.

    ``output_service`` is required. Charts are only written via
    ``output_service.save_chart``; calling without a service previously
    plotted figures and discarded them silently.
    """
    if output_service is None:
        raise ValueError(
            "output_service is required to persist understandability charts"
        )

    # Only include named speakers (consistent with save_understandability_csv)
    filtered_scores = {s: v for s, v in all_scores.items() if is_named_speaker(s)}

    # Check if we have any scores to plot
    if not filtered_scores:
        notify_user(
            "⚠️ No named speaker scores available for understandability charts. Skipping chart generation.",
            technical=True,
            section="analyze",
        )
        return

    df = pd.DataFrame.from_dict(filtered_scores, orient="index")
    df.index.name = "speaker"

    flesch_reading_ease_metrics = ["flesch_reading_ease"]
    readability_indices = [
        "gunning_fog_index",
        "smog_index",
        "automated_readability_index",
    ]
    readability_metrics = flesch_reading_ease_metrics + readability_indices
    structure_metrics = [
        "lexical_density",
        "avg_sentence_length",
        "sentence_count",
    ]
    word_count_metrics = ["word_count"]

    # Check if DataFrame has the required columns
    missing_cols = [col for col in readability_metrics if col not in df.columns]
    if missing_cols:
        notify_user(
            f"⚠️ Missing required columns for understandability charts: {missing_cols}. Skipping chart generation.",
            technical=True,
            section="analyze",
        )
        return

    # Check if DataFrame is empty or has no data
    if df.empty:
        notify_user(
            "⚠️ Empty DataFrame for understandability charts. Skipping chart generation.",
            technical=True,
            section="analyze",
        )
        return

    # Safely access columns with error handling
    try:
        df["avg_score_indices"] = df[readability_indices].mean(axis=1)
        df = df.sort_values(by="word_count", ascending=False).reset_index()
    except KeyError as e:
        notify_user(
            f"⚠️ Error accessing required columns for understandability charts: {e}. Skipping chart generation.",
            technical=True,
            section="analyze",
        )
        return

    def plot_metric_group(metrics, filename_suffix, title, chart_type, color_by):
        # Check if metrics list is empty
        if not metrics:
            notify_user(
                f"⚠️ No metrics provided for {filename_suffix}. Skipping chart generation.",
                technical=True,
                section="analyze",
            )
            return

        # Check if color_by column exists
        if color_by not in df.columns:
            notify_user(
                f"⚠️ Column '{color_by}' not found for {filename_suffix}. Skipping chart generation.",
                technical=True,
                section="analyze",
            )
            return

        # Check if we have valid data in color_by column
        if df[color_by].isna().all() or df[color_by].empty:
            notify_user(
                f"⚠️ No valid data in '{color_by}' column for {filename_suffix}. Skipping chart generation.",
                technical=True,
                section="analyze",
            )
            return

        melted = df.melt(
            id_vars=["speaker", color_by],
            value_vars=metrics,
            var_name="metric",
            value_name="score",
        )

        # Check if melted DataFrame is empty or has no valid data
        if melted.empty or melted["score"].isna().all():
            notify_user(
                f"⚠️ No valid data to plot for {filename_suffix}. Skipping chart generation.",
                technical=True,
                section="analyze",
            )
            return

        speakers = [str(s) for s in df["speaker"].tolist()]
        series = []
        for metric in metrics:
            metric_rows = melted[melted["metric"] == metric]
            if metric_rows.empty or metric_rows["score"].isna().all():
                continue
            by_speaker = {
                str(row["speaker"]): float(row["score"])
                for _, row in metric_rows.iterrows()
                if pd.notna(row["score"])
            }
            series.append(
                {
                    "name": str(metric),
                    "categories": speakers,
                    "values": [by_speaker.get(speaker, 0.0) for speaker in speakers],
                }
            )
        if not series:
            notify_user(
                f"⚠️ Cannot create chart for {filename_suffix}: no valid data points. Skipping.",
                technical=True,
                section="analyze",
            )
            return

        spec = BarCategoricalSpec(
            viz_id=f"understandability.{filename_suffix}.global",
            module="understandability",
            name=filename_suffix,
            scope="global",
            chart_intent="bar_categorical",
            title=title,
            x_label="Speaker",
            y_label="Score",
            categories=speakers,
            series=series,
            notes=f"Grouped bars by metric (color_by={color_by}).",
        )
        output_service.save_chart(spec, chart_type=chart_type)
        notify_user(
            f"📊 Chart saved for {filename_suffix}", technical=True, section="analyze"
        )

    plot_metric_group(
        flesch_reading_ease_metrics,
        "flesch-reading-ease-bars",
        "Flesch Reading Ease per Speaker",
        "understandability",
        "flesch_reading_ease",
    )
    plot_metric_group(
        readability_indices,
        "readability-indices-bars",
        "Readability Indices per Speaker",
        "understandability",
        "avg_score_indices",
    )
    plot_metric_group(
        structure_metrics,
        "structure-bars",
        "Structural Features per Speaker",
        "structure",
        "avg_score_indices",
    )
    plot_metric_group(
        word_count_metrics,
        "word-count-bars",
        "Word Count per Speaker",
        "structure",
        "avg_score_indices",
    )


def compute_and_save_understandability(
    segments: list,
    out_dir: str,
    base_name: str,
    speaker_map: dict = None,
) -> dict:
    from transcriptx.core.utils.speaker_extraction import (
        group_segments_by_speaker,
        get_speaker_display_name,
    )

    # Group segments by speaker using speaker_db_id when available
    grouped_segments = group_segments_by_speaker(segments)

    # Aggregate text by speaker (using grouping_key for uniqueness)
    grouped_texts = {}
    skipped = 0

    for grouping_key, segs in grouped_segments.items():
        display_name = get_speaker_display_name(grouping_key, segs, segments)
        if not display_name or not is_named_speaker(display_name):
            skipped += len(segs)
            continue

        # Combine text from all segments for this speaker
        text = " ".join(seg.get("text", "") for seg in segs)
        grouped_texts[display_name] = text

    scores = {
        speaker: compute_understandability_metrics(text)
        for speaker, text in grouped_texts.items()
    }

    # Use output standards for directory structure
    output_structure = create_standard_output_structure(out_dir, "understandability")
    output_service = create_output_service(
        str(Path(out_dir) / f"{base_name}.json"),
        "understandability",
        output_dir=out_dir,
        run_id=Path(out_dir).name,
    )

    save_understandability_json(scores, output_structure, base_name)
    save_understandability_csv(scores, output_structure, base_name)
    plot_understandability_charts(scores, output_structure, base_name, output_service)

    # After scores is populated
    speaker_stats = {speaker: metrics for speaker, metrics in scores.items()}
    # Aggregate global stats
    if speaker_stats:
        global_stats = {
            k: sum(d[k] for d in speaker_stats.values()) / len(speaker_stats)
            for k in next(iter(speaker_stats.values())).keys()
        }
    else:
        global_stats = {}
    create_summary_json(
        module_name="understandability",
        base_name=base_name,
        global_data=global_stats,
        speaker_data=speaker_stats,
        analysis_metadata={},
        output_structure=output_structure,
    )

    if skipped:
        notify_user(
            f"⚠️ Skipped {skipped} segments with no speaker label.",
            technical=True,
            section="analyze",
        )

    return scores


def score_from_file(input_path: str):
    from transcriptx.io import load_segments

    from transcriptx.core.utils._path_core import get_base_name, get_transcript_dir

    base_name = get_base_name(input_path)
    out_dir = Path(get_transcript_dir(input_path))

    segments = load_segments(str(input_path))

    # Extract speaker information from segments (speaker_map files are deprecated)
    from transcriptx.core.utils.speaker_extraction import get_unique_speakers

    speaker_map = get_unique_speakers(segments)

    return compute_and_save_understandability(segments, out_dir, base_name, speaker_map)


def score_segments(
    segments: list, base_name: str, transcript_dir: str, speaker_map: dict
):
    """
    Wrapper for compute_and_save_understandability to match the pipeline interface.
    """
    return compute_and_save_understandability(
        segments, transcript_dir, base_name, speaker_map
    )
