"""Topic modeling module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from collections import Counter, defaultdict

from transcriptx.core.utils.output_standards import save_speaker_data
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
)

from transcriptx.core.analysis.topic_modeling.utils import _safe_numpy_array
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.utils.lazy_imports import (
    lazy_pyplot,
    lazy_module,
    optional_import,
)

plt = lazy_pyplot()
sns = lazy_module("seaborn", "plotting", "visualization")
pd = lazy_module("pandas", "data processing", "visualization")
mpl = lazy_module("matplotlib", "plotting", "visualization")


def _build_topic_label_map(topics: list[dict[str, Any]] | None) -> dict[int, str]:
    """
    Build a mapping from topic_id -> human label.

    Best UX is: keep stable ids (T0, T1, ...) + add a short label when available.
    """
    label_map: dict[int, str] = {}
    if not topics:
        return label_map

    for topic in topics:
        try:
            topic_id = int(topic.get("topic_id"))
        except Exception:
            continue

        label = str(topic.get("label") or "").strip()
        if label:
            label_map[topic_id] = label

    return label_map


def _truncate_label(label: str, max_len: int) -> str:
    label = " ".join(str(label).split())
    if max_len <= 0:
        return ""
    if len(label) <= max_len:
        return label
    # Unicode ellipsis keeps things compact in charts.
    return label[: max(0, max_len - 1)].rstrip() + "…"


def format_topic_display(
    topic_id: int,
    label_map: dict[int, str] | None = None,
    *,
    include_label: bool = True,
    max_label_len: int = 28,
) -> str:
    """
    Format a topic label for charts.

    Example: "T3 – Project Discussion"
    """
    base = f"T{int(topic_id)}"
    if not include_label or not label_map:
        return base
    label = label_map.get(int(topic_id))
    if not label:
        return base
    return f"{base} – {_truncate_label(label, max_label_len)}"


def _apply_plot_style() -> None:
    mpl.rcdefaults()
    sns.reset_defaults()
    sns.set_theme(style="whitegrid")


def _get_plotly():
    try:
        return optional_import(
            "plotly.graph_objects", "interactive charts", "visualization"
        )
    except ImportError:
        return None


# --- Robust JSON serialization for numpy types ---
def create_diagnostic_plots(
    diagnostics: dict[str, Any],
    algorithm: str,
    base_name: str,
    output_structure: dict[str, Path],
    output_service=None,
) -> list[str]:
    """
    Create diagnostic plots for topic modeling evaluation.

    Args:
        diagnostics: Diagnostic metrics from optimal k selection
        algorithm: 'lda' or 'nmf'
        base_name: Base name for output files
        output_structure: Output directory structure

    Returns:
        List of created chart paths
    """
    chart_paths = []

    if not diagnostics or "k_values" not in diagnostics:
        return chart_paths

    try:
        _apply_plot_style()
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        k_values = diagnostics["k_values"]

        # Plot 1: Held-out Likelihood
        if diagnostics.get("held_out_likelihood"):
            ax1.plot(
                k_values,
                diagnostics["held_out_likelihood"],
                "bo-",
                linewidth=2,
                markersize=6,
            )
            ax1.set_title(f"{algorithm.upper()} Held-out Likelihood", fontweight="bold")
            ax1.set_xlabel("Number of Topics (k)")
            ax1.set_ylabel("Log Likelihood")
            ax1.grid(True, alpha=0.3)

        # Plot 2: Coherence Scores
        if diagnostics.get("coherence_scores"):
            ax2.plot(
                k_values,
                diagnostics["coherence_scores"],
                "ro-",
                linewidth=2,
                markersize=6,
            )
            ax2.set_title(f"{algorithm.upper()} Topic Coherence", fontweight="bold")
            ax2.set_xlabel("Number of Topics (k)")
            ax2.set_ylabel("Coherence Score")
            ax2.grid(True, alpha=0.3)

        # Plot 3: Silhouette Scores
        if diagnostics.get("silhouette_scores"):
            ax3.plot(
                k_values,
                diagnostics["silhouette_scores"],
                "go-",
                linewidth=2,
                markersize=6,
            )
            ax3.set_title(f"{algorithm.upper()} Topic Separation", fontweight="bold")
            ax3.set_xlabel("Number of Topics (k)")
            ax3.set_ylabel("Silhouette Score")
            ax3.grid(True, alpha=0.3)

        # Plot 4: Residuals
        if diagnostics.get("residuals"):
            ax4.plot(
                k_values, diagnostics["residuals"], "mo-", linewidth=2, markersize=6
            )
            ax4.set_title(
                f"{algorithm.upper()} Reconstruction Error", fontweight="bold"
            )
            ax4.set_xlabel("Number of Topics (k)")
            ax4.set_ylabel("Residuals")
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save diagnostic plots
        if output_service:
            result = output_service.save_chart(
                chart_id=f"{algorithm}_diagnostic_plots",
                scope="global",
                static_fig=fig,
                chart_type="diagnostic",
                viz_id=f"topic_modeling.{algorithm}_diagnostic_plots.global",
                title=f"{algorithm.upper()} Diagnostic Plots",
            )
            if result.get("static"):
                chart_paths.append(str(result["static"]))
        plt.close(fig)

        print(f"[TOPICS] Created {algorithm.upper()} diagnostic plots")

    except Exception as e:
        print(f"[TOPICS] Warning: Could not create diagnostic plots: {e}")

    return chart_paths


def create_discourse_analysis_charts(
    discourse_analysis: dict[str, Any],
    base_name: str,
    output_structure: dict[str, Path],
    output_service=None,
) -> list[str]:
    """
    Create charts for discourse-aware topic analysis.

    Args:
        discourse_analysis: Results from analyze_discourse_topics
        base_name: Base name for output files
        output_structure: Output directory structure

    Returns:
        List of created chart paths
    """
    chart_paths = []

    try:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # Plot 1: Topic Prevalence by Discourse
        topic_prevalence = discourse_analysis.get("topic_prevalence", {})
        if topic_prevalence:
            discourses = list(topic_prevalence.keys())
            topics = set()
            for discourse_topics in topic_prevalence.values():
                topics.update(discourse_topics.keys())
            topics = sorted(list(topics))

            prevalence_matrix = np.zeros((len(discourses), len(topics)))
            for i, discourse in enumerate(discourses):
                for j, topic in enumerate(topics):
                    prevalence_matrix[i, j] = topic_prevalence[discourse].get(topic, 0)

            im1 = ax1.imshow(prevalence_matrix, cmap="Blues", aspect="auto")
            ax1.set_xticks(range(len(topics)))
            ax1.set_xticklabels([f"T{t}" for t in topics])
            ax1.set_yticks(range(len(discourses)))
            ax1.set_yticklabels(discourses)
            ax1.set_title("Topic Prevalence by Discourse", fontweight="bold")
            ax1.set_xlabel("Topics")
            ax1.set_ylabel("Discourse Phase")
            plt.colorbar(im1, ax=ax1)

        # Plot 2: Topic Confidence by Discourse
        topic_confidence = discourse_analysis.get("topic_confidence", {})
        if topic_confidence:
            confidence_matrix = np.zeros((len(discourses), len(topics)))
            for i, discourse in enumerate(discourses):
                for j, topic in enumerate(topics):
                    confidence_matrix[i, j] = topic_confidence[discourse].get(topic, 0)

            im2 = ax2.imshow(confidence_matrix, cmap="Reds", aspect="auto")
            ax2.set_xticks(range(len(topics)))
            ax2.set_xticklabels([f"T{t}" for t in topics])
            ax2.set_yticks(range(len(discourses)))
            ax2.set_yticklabels(discourses)
            ax2.set_title("Topic Confidence by Discourse", fontweight="bold")
            ax2.set_xlabel("Topics")
            ax2.set_ylabel("Discourse Phase")
            plt.colorbar(im2, ax=ax2)

        # Plot 3: Discourse Summary
        discourse_summary = discourse_analysis.get("discourse_summary", {})
        if discourse_summary:
            discourse_names = list(discourse_summary.keys())
            total_segments = [
                discourse_summary[d]["total_segments"] for d in discourse_names
            ]
            topic_diversity = [
                discourse_summary[d]["topic_diversity"] for d in discourse_names
            ]

            x = np.arange(len(discourse_names))
            width = 0.35

            ax3.bar(
                x - width / 2, total_segments, width, label="Total Segments", alpha=0.8
            )
            ax3.bar(
                x + width / 2,
                topic_diversity,
                width,
                label="Topic Diversity",
                alpha=0.8,
            )

            ax3.set_xlabel("Discourse Phase")
            ax3.set_ylabel("Count")
            ax3.set_title("Discourse Summary", fontweight="bold")
            ax3.set_xticks(x)
            ax3.set_xticklabels(discourse_names)
            ax3.legend()
            ax3.grid(True, alpha=0.3)

        # Plot 4: Average Confidence by Discourse
        if discourse_summary:
            avg_confidence = [
                discourse_summary[d]["avg_confidence"] for d in discourse_names
            ]

            ax4.bar(discourse_names, avg_confidence, alpha=0.8, color="green")
            ax4.set_xlabel("Discourse Phase")
            ax4.set_ylabel("Average Confidence")
            ax4.set_title("Average Topic Confidence by Discourse", fontweight="bold")
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save discourse analysis charts
        if output_service:
            result = output_service.save_chart(
                chart_id="discourse_analysis",
                scope="global",
                static_fig=fig,
                chart_type="discourse",
                viz_id="topic_modeling.discourse_analysis.global",
                title="Discourse Analysis",
            )
            if result.get("static"):
                chart_paths.append(str(result["static"]))
        plt.close(fig)

        print("[TOPICS] Created discourse analysis charts")

    except Exception as e:
        print(f"[TOPICS] Warning: Could not create discourse analysis charts: {e}")

    return chart_paths


def create_enhanced_global_heatmaps(
    lda_results,
    nmf_results,
    base_name,
    output_structure,
    html_imgs=None,
    output_service=None,
):
    """
    Create enhanced global heatmaps with topic labels and coherence scores.
    """
    # LDA
    try:
        fig, ax = plt.subplots(figsize=(14, 10))
        topics = lda_results["topics"]
        if not topics:
            print("[TOPICS] Warning: No LDA topics found for heatmap")
            return

        lda_label_map = _build_topic_label_map(topics)
        top_words_per_topic = min(10, min(len(topic["words"]) for topic in topics))
        word_labels = topics[0]["words"][:top_words_per_topic]
        y_labels = []
        topic_word_matrix = np.zeros(
            (len(topics), top_words_per_topic), dtype=np.float64
        )

        for i, topic in enumerate(topics):
            word_to_weight = dict(zip(topic["words"], topic["weights"], strict=False))
            for j, word in enumerate(word_labels):
                topic_word_matrix[i, j] = word_to_weight.get(word, 0.0)

            # Enhanced label with topic name and coherence
            topic_label = format_topic_display(
                int(topic["topic_id"]), lda_label_map, max_label_len=34
            )
            coherence = topic.get("coherence", 0.0)
            y_labels.append(f"{topic_label}\n(Coherence: {coherence:.3f})")

        topic_word_matrix = np.asarray(topic_word_matrix, dtype=np.float64)
        im = ax.imshow(topic_word_matrix, cmap="Blues", aspect="auto")

        ax.set_xticks(range(len(word_labels)))
        ax.set_xticklabels(word_labels, rotation=90, ha="center", fontsize=10)
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels, fontsize=10)

        ax.set_title("Enhanced LDA Topic-Word Distribution", fontweight="bold")
        ax.set_xlabel("Words")
        ax.set_ylabel("Topics (with Labels and Coherence)")

        plt.tight_layout()

        if output_service:
            spec = HeatmapMatrixSpec(
                viz_id="topic_modeling.enhanced_lda_topic_word_heatmap.global",
                module="topic_modeling",
                name="enhanced_lda_topic_word_heatmap",
                scope="global",
                chart_intent="heatmap_matrix",
                title="Enhanced LDA Topic-Word Distribution",
                x_label="Words",
                y_label="Topics (with Labels and Coherence)",
                z=topic_word_matrix.tolist(),
                x_labels=word_labels,
                y_labels=y_labels,
            )
            result = output_service.save_chart(spec, chart_type="heatmap")
            if result.get("static") and html_imgs is not None:
                html_imgs.append(str(result["static"]))

        plt.close(fig)

    except Exception as e:
        print(f"[TOPICS] Error creating enhanced LDA heatmap: {e}")

    # NMF
    try:
        fig, ax = plt.subplots(figsize=(14, 10))
        topics = nmf_results["topics"]
        if not topics:
            print("[TOPICS] Warning: No NMF topics found for heatmap")
            return

        nmf_label_map = _build_topic_label_map(topics)
        top_words_per_topic = min(10, min(len(topic["words"]) for topic in topics))
        word_labels = topics[0]["words"][:top_words_per_topic]
        y_labels = []
        topic_word_matrix = np.zeros(
            (len(topics), top_words_per_topic), dtype=np.float64
        )

        for i, topic in enumerate(topics):
            word_to_weight = dict(zip(topic["words"], topic["weights"], strict=False))
            for j, word in enumerate(word_labels):
                topic_word_matrix[i, j] = word_to_weight.get(word, 0.0)

            # Enhanced label with topic name and coherence
            topic_label = format_topic_display(
                int(topic["topic_id"]), nmf_label_map, max_label_len=34
            )
            coherence = topic.get("coherence", 0.0)
            y_labels.append(f"{topic_label}\n(Coherence: {coherence:.3f})")

        topic_word_matrix = np.asarray(topic_word_matrix, dtype=np.float64)
        im = ax.imshow(topic_word_matrix, cmap="Reds", aspect="auto")

        ax.set_xticks(range(len(word_labels)))
        ax.set_xticklabels(word_labels, rotation=90, ha="center", fontsize=10)
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels, fontsize=10)

        ax.set_title("Enhanced NMF Topic-Word Distribution", fontweight="bold")
        ax.set_xlabel("Words")
        ax.set_ylabel("Topics (with Labels and Coherence)")

        plt.tight_layout()

        if output_service:
            spec = HeatmapMatrixSpec(
                viz_id="topic_modeling.enhanced_nmf_topic_word_heatmap.global",
                module="topic_modeling",
                name="enhanced_nmf_topic_word_heatmap",
                scope="global",
                chart_intent="heatmap_matrix",
                title="Enhanced NMF Topic-Word Distribution",
                x_label="Words",
                y_label="Topics (with Labels and Coherence)",
                z=topic_word_matrix.tolist(),
                x_labels=word_labels,
                y_labels=y_labels,
            )
            result = output_service.save_chart(spec, chart_type="heatmap")
            if result.get("static") and html_imgs is not None:
                html_imgs.append(str(result["static"]))

        plt.close(fig)

    except Exception as e:
        print(f"[TOPICS] Error creating enhanced NMF heatmap: {e}")


def create_speaker_charts(
    lda_results,
    nmf_results,
    speaker_labels,
    base_name,
    output_structure,
    html_imgs=None,
    output_service=None,
):
    """
    Create speaker-specific topic charts.

    Args:
        lda_results: LDA topic modeling results
        nmf_results: NMF topic modeling results
        speaker_labels: List of speaker display names (already resolved from segments)
        base_name: Base name for output files
        output_structure: Output directory structure
        html_imgs: Optional list of HTML image paths
    """
    from transcriptx.utils.text_utils import is_named_speaker

    # speaker_labels already contain display names from prepare_text_data()
    # Filter out any None or unnamed speakers
    display_labels = [s for s in speaker_labels if s and is_named_speaker(s)]
    speaker_topic_data = defaultdict(lambda: {"lda": [], "nmf": []})
    lda_label_map = _build_topic_label_map(lda_results.get("topics"))

    try:
        for i, speaker in enumerate(display_labels):
            # Use safe numpy conversion to prevent type conflicts
            lda_topic_dist = _safe_numpy_array(
                lda_results["doc_topics"][i], dtype=np.float64
            )
            nmf_topic_dist = _safe_numpy_array(
                nmf_results["doc_topics"][i], dtype=np.float64
            )
            speaker_topic_data[speaker]["lda"].append(int(np.argmax(lda_topic_dist)))
            speaker_topic_data[speaker]["nmf"].append(int(np.argmax(nmf_topic_dist)))

        for speaker, data in speaker_topic_data.items():
            safe_speaker = str(speaker).replace(" ", "_").replace("/", "_")
            lda_counts = Counter(data["lda"])
            nmf_counts = Counter(data["nmf"])
            save_speaker_data(
                {"lda": list(lda_counts.items()), "nmf": list(nmf_counts.items())},
                output_structure,
                base_name,
                safe_speaker,
                "topic_counts",
                "json",
            )

            if output_service and lda_counts:
                categories = [
                    format_topic_display(int(topic_id), lda_label_map, max_label_len=24)
                    for topic_id in lda_counts.keys()
                ]
                values = [count for count in lda_counts.values()]
                spec = BarCategoricalSpec(
                    viz_id="topic_modeling.topic_bar.speaker",
                    module="topic_modeling",
                    name="topic_bar",
                    scope="speaker",
                    speaker=speaker,
                    chart_intent="bar_categorical",
                    title=f"Topic Distribution (LDA) - {speaker}",
                    x_label="Topic",
                    y_label="Count",
                    categories=categories,
                    values=values,
                )
                result = output_service.save_chart(spec, chart_type="bar")
                if result.get("static") and html_imgs is not None:
                    html_imgs.append(str(result["static"]))

    except Exception as e:
        print(f"[TOPICS] Warning: Could not process speaker topic data: {e}")
        plt.close("all")  # Close any open figures


def create_html_report(html_path, chart_paths):
    lines = [
        "<html><head><title>Topic Modeling Report</title></head><body>\n",
        "<h1>Topic Modeling Charts</h1>\n",
    ]
    for chart in chart_paths:
        if os.path.exists(chart):
            lines.append(
                f'<div><img src="{chart}" style="max-width:700px;"><br>{os.path.basename(chart)}</div>\n'
            )
    lines.append("</body></html>")
    write_text(html_path, "".join(lines))


def create_plotly_heatmap(topic_word_matrix, word_labels, y_labels, title, output_path):
    """
    Create a plotly heatmap as an alternative to matplotlib.

    Args:
        topic_word_matrix: 2D numpy array of topic-word weights
        word_labels: List of word labels for x-axis
        y_labels: List of topic labels for y-axis
        title: Chart title
        output_path: Path to save the HTML file
    """
    go = _get_plotly()
    if go is None:
        print("[WARNING] Plotly not available, cannot create plotly heatmap")
        return False

    try:
        # Create heatmap using plotly
        fig = go.Figure(
            data=go.Heatmap(
                z=topic_word_matrix,
                x=word_labels,
                y=y_labels,
                colorscale="Blues",
                showscale=True,
                text=np.round(topic_word_matrix, 3),
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False,
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Words",
            yaxis_title="Topics",
            xaxis={"tickangle": 45},
            width=800,
            height=600,
        )

        # Save as HTML file
        fig.write_html(str(output_path))
        print(f"[PLOTLY] Successfully created heatmap: {output_path}")
        return True

    except Exception as e:
        print(f"[PLOTLY] Error creating heatmap: {e}")
        return False


def create_plotly_speaker_chart(speaker_data, speaker_name, output_path):
    """
    Create a plotly bar chart for speaker topic distribution.

    Args:
        speaker_data: Dictionary with 'lda' and 'nmf' topic counts
        speaker_name: Name of the speaker
        output_path: Path to save the HTML file
    """
    go = _get_plotly()
    if go is None:
        print("[WARNING] Plotly not available, cannot create plotly speaker chart")
        return False

    try:
        # Create subplots for LDA and NMF
        fig = go.Figure()

        # Add LDA data
        lda_counts = Counter(speaker_data["lda"])
        if lda_counts:
            fig.add_trace(
                go.Bar(
                    x=list(lda_counts.keys()),
                    y=list(lda_counts.values()),
                    name="LDA",
                    marker_color="skyblue",
                )
            )

        # Add NMF data
        nmf_counts = Counter(speaker_data["nmf"])
        if nmf_counts:
            fig.add_trace(
                go.Bar(
                    x=list(nmf_counts.keys()),
                    y=list(nmf_counts.values()),
                    name="NMF",
                    marker_color="lightcoral",
                )
            )

        fig.update_layout(
            title=f"{speaker_name} - Topic Distribution",
            xaxis_title="Topic Number",
            yaxis_title="Count",
            barmode="group",
            width=600,
            height=400,
        )

        # Save as HTML file
        fig.write_html(str(output_path))
        print(f"[PLOTLY] Successfully created speaker chart: {output_path}")
        return True

    except Exception as e:
        print(f"[PLOTLY] Error creating speaker chart: {e}")
        return False


def create_topic_evolution_timeline(
    lda_doc_topics,
    base_name,
    output_structure,
    lda_topics: list[dict[str, Any]] | None = None,
    output_service=None,
):
    import numpy as np

    print(
        f"[DEBUG] create_topic_evolution_timeline: received {len(lda_doc_topics)} doc topics"
    )
    try:
        df = pd.DataFrame(lda_doc_topics)
        print(f"[DEBUG] DataFrame head:\n{df.head()}")
        if "dominant_topic" not in df or "time" not in df:
            print("[TOPICS] Not enough data for topic evolution timeline.")
            return None
        df = df.sort_values("time")
        window_size = max(1, len(df) // 20)
        df["window"] = np.arange(len(df)) // window_size
        topic_counts = (
            df.groupby(["window", "dominant_topic"]).size().unstack(fill_value=0)
        )
        if output_service:
            label_map = _build_topic_label_map(lda_topics)
            series = []
            for topic in topic_counts.columns:
                series.append(
                    {
                        "name": format_topic_display(
                            int(topic), label_map, max_label_len=30
                        ),
                        "x": list(topic_counts.index),
                        "y": topic_counts[topic].tolist(),
                    }
                )
            spec = LineTimeSeriesSpec(
                viz_id="topic_modeling.topic_evolution_timeline.global",
                module="topic_modeling",
                name="topic_evolution_timeline",
                scope="global",
                chart_intent="line_timeseries",
                title="Topic Evolution Timeline",
                x_label="Time Window",
                y_label="Topic Frequency",
                markers=True,
                series=series,
            )
            result = output_service.save_chart(spec, chart_type="timeline")
            if result.get("static"):
                print(f"[TOPICS] Created topic evolution timeline: {result['static']}")
            return result.get("static")
    except Exception as e:
        print(f"[ERROR] Exception in create_topic_evolution_timeline: {e}")


def create_speaker_topic_engagement_heatmap(
    lda_doc_topics,
    base_name,
    output_structure,
    lda_topics: list[dict[str, Any]] | None = None,
    output_service=None,
):

    print(
        f"[DEBUG] create_speaker_topic_engagement_heatmap: received {len(lda_doc_topics)} doc topics"
    )
    try:
        df = pd.DataFrame(lda_doc_topics)
        print(f"[DEBUG] DataFrame head:\n{df.head()}")
        if "dominant_topic" not in df or "speaker" not in df:
            print("[TOPICS] Not enough data for speaker-topic engagement heatmap.")
            return None
        engagement = pd.crosstab(df["speaker"], df["dominant_topic"])
        if output_service:
            label_map = _build_topic_label_map(lda_topics)
            spec = HeatmapMatrixSpec(
                viz_id="topic_modeling.speaker_topic_engagement_heatmap.global",
                module="topic_modeling",
                name="speaker_topic_engagement_heatmap",
                scope="global",
                chart_intent="heatmap_matrix",
                title="Speaker-Topic Engagement Heatmap",
                x_label="Topic",
                y_label="Speaker",
                z=engagement.values.tolist(),
                x_labels=[
                    format_topic_display(int(t), label_map, max_label_len=18)
                    for t in engagement.columns
                ],
                y_labels=list(engagement.index),
            )
            result = output_service.save_chart(spec, chart_type="heatmap")
            if result.get("static"):
                print(
                    f"[TOPICS] Created speaker-topic engagement heatmap: {result['static']}"
                )
            return result.get("static")
    except Exception as e:
        print(f"[ERROR] Exception in create_speaker_topic_engagement_heatmap: {e}")


def create_expected_topic_proportions_bar(
    lda_doc_topics, lda_topics, base_name, output_structure, output_service=None
):

    print(
        f"[DEBUG] create_expected_topic_proportions_bar: received {len(lda_doc_topics)} doc topics"
    )
    try:
        df = pd.DataFrame(lda_doc_topics)
        print(f"[DEBUG] DataFrame head:\n{df.head()}")
        if "dominant_topic" not in df:
            print("[TOPICS] Not enough data for expected topic proportions.")
            return None
        topic_props = (
            df["dominant_topic"]
            .value_counts(normalize=True)
            .sort_values(ascending=False)
        )
        label_map = _build_topic_label_map(
            lda_topics if isinstance(lda_topics, list) else None
        )
        topic_labels = [
            format_topic_display(int(i), label_map, max_label_len=28)
            for i in topic_props.index
        ]
        if output_service:
            spec = BarCategoricalSpec(
                viz_id="topic_modeling.expected_topic_proportions.global",
                module="topic_modeling",
                name="expected_topic_proportions",
                scope="global",
                chart_intent="bar_categorical",
                title="Expected Topic Proportions",
                x_label="Topic",
                y_label="Expected Topic Proportion",
                categories=topic_labels,
                values=topic_props.values.tolist(),
            )
            result = output_service.save_chart(spec, chart_type="bar")
            if result.get("static"):
                print(
                    f"[TOPICS] Created expected topic proportions bar chart: {result['static']}"
                )
            return result.get("static")
    except Exception as e:
        print(f"[ERROR] Exception in create_expected_topic_proportions_bar: {e}")


def create_enhanced_html_report(
    html_path: Path,
    chart_paths: list[str],
    lda_results: dict[str, Any],
    nmf_results: dict[str, Any],
    discourse_analysis: dict[str, Any],
):
    """
    Create an enhanced HTML report with comprehensive topic modeling results.

    Args:
        html_path: Path to save the HTML report
        chart_paths: List of chart file paths
        lda_results: LDA analysis results
        nmf_results: NMF analysis results
        discourse_analysis: Discourse analysis results
    """
    try:
        lines = [
            "<!DOCTYPE html>\n<html>\n<head>\n",
            "<title>Enhanced Topic Modeling Report</title>\n",
            "<style>\n",
            "body { font-family: Arial, sans-serif; margin: 20px; }\n",
            ".header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }\n",
            ".section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }\n",
            ".topic { background-color: #f9f9f9; padding: 10px; margin: 5px 0; border-radius: 3px; }\n",
            ".chart { margin: 20px 0; text-align: center; }\n",
            ".chart img { max-width: 100%; height: auto; border: 1px solid #ddd; }\n",
            ".stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }\n",
            ".stat-box { background-color: #e8f4f8; padding: 15px; border-radius: 5px; text-align: center; }\n",
            "</style>\n</head>\n<body>\n",
            '<div class="header">\n',
            "<h1>🎯 Enhanced Topic Modeling Analysis Report</h1>\n",
            "<p><strong>STM-Inspired Topic Modeling with Optimal k Selection and Discourse Analysis</strong></p>\n",
            "</div>\n",
            '<div class="section">\n',
            "<h2>📊 Analysis Summary</h2>\n",
            '<div class="stats">\n',
            f'<div class="stat-box"><h3>LDA Topics</h3><p>{lda_results["optimal_k"]}</p></div>\n',
            f'<div class="stat-box"><h3>NMF Topics</h3><p>{nmf_results["optimal_k"]}</p></div>\n',
            f'<div class="stat-box"><h3>Total Segments</h3><p>{len(lda_results["doc_topic_data"])}</p></div>\n',
            f'<div class="stat-box"><h3>Unique Speakers</h3><p>{len(set([doc["speaker"] for doc in lda_results["doc_topic_data"]]))}</p></div>\n',
            "</div>\n</div>\n",
            '<div class="section">\n',
            "<h2>📋 LDA Topics (with Labels and Coherence)</h2>\n",
        ]
        for topic in lda_results["topics"]:
            lines.extend(
                [
                    '<div class="topic">\n',
                    f'<h3>Topic {topic["topic_id"]}: {topic["label"]}</h3>\n',
                    f'<p><strong>Coherence Score:</strong> {topic["coherence"]:.3f}</p>\n',
                    f'<p><strong>Top Words:</strong> {", ".join(topic["words"][:5])}</p>\n',
                    "</div>\n",
                ]
            )
        lines.append("</div>\n")
        lines.extend(
            [
                '<div class="section">\n',
                "<h2>📋 NMF Topics (with Labels and Coherence)</h2>\n",
            ]
        )
        for topic in nmf_results["topics"]:
            lines.extend(
                [
                    '<div class="topic">\n',
                    f'<h3>Topic {topic["topic_id"]}: {topic["label"]}</h3>\n',
                    f'<p><strong>Coherence Score:</strong> {topic["coherence"]:.3f}</p>\n',
                    f'<p><strong>Top Words:</strong> {", ".join(topic["words"][:5])}</p>\n',
                    "</div>\n",
                ]
            )
        lines.append("</div>\n")

        if discourse_analysis.get("discourse_summary"):
            lines.extend(
                [
                    '<div class="section">\n',
                    "<h2>🗣️ Discourse Analysis</h2>\n",
                ]
            )
            for discourse, summary in discourse_analysis["discourse_summary"].items():
                lines.extend(
                    [
                        '<div class="topic">\n',
                        f"<h3>{discourse.title()} Phase</h3>\n",
                        f'<p><strong>Total Segments:</strong> {summary["total_segments"]}</p>\n',
                        f'<p><strong>Topic Diversity:</strong> {summary["topic_diversity"]}</p>\n',
                        f'<p><strong>Average Confidence:</strong> {summary["avg_confidence"]}:.3f</p>\n',
                        "</div>\n",
                    ]
                )
            lines.append("</div>\n")

        lines.extend(
            [
                '<div class="section">\n',
                "<h2>📈 Visualizations</h2>\n",
            ]
        )
        for chart in chart_paths:
            if os.path.exists(chart):
                chart_name = os.path.basename(chart)
                lines.extend(
                    [
                        '<div class="chart">\n',
                        f"<h3>{chart_name}</h3>\n",
                        f'<img src="{chart}" alt="{chart_name}">\n',
                        "</div>\n",
                    ]
                )
        lines.extend(["</div>\n", "</body>\n</html>"])
        write_text(html_path, "".join(lines))

        print(f"[TOPICS] Enhanced HTML report created: {html_path}")

    except Exception as e:
        print(f"[TOPICS] Warning: Could not create enhanced HTML report: {e}")
        # Fallback to simple report
        create_html_report(html_path, chart_paths)
