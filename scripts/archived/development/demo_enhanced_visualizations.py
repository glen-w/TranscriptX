#!/usr/bin/env python3
"""
Demonstration of Enhanced Topic Modeling Visualizations

This script shows how the 5 proposed visualizations would work
with the existing topic modeling data structure.
"""

import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity

# Configure matplotlib
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


def load_topic_data(base_path="example_transcript/topic_modeling/data/global"):
    """Load existing topic modeling data."""
    try:
        with open(f"{base_path}/example_transcript_lda_topics.json") as f:
            lda_topics = json.load(f)

        with open(f"{base_path}/example_transcript_lda_document_topics.json") as f:
            doc_topics = json.load(f)

        # Load speaker map if available
        speaker_map = {}
        speaker_map_path = "example_transcript/example_transcript_speaker_map.json"
        if Path(speaker_map_path).exists():
            with open(speaker_map_path) as f:
                speaker_map = json.load(f)

        return lda_topics, doc_topics, speaker_map

    except FileNotFoundError as e:
        print(f"⚠️ Could not load topic data: {e}")
        print(
            "Please run topic modeling first: python -c \"from transcriptx.core.topic_modeling import analyze_topics_from_file; analyze_topics_from_file('example_transcript.json')\""
        )
        return None, None, None


def demo_topic_evolution_timeline(
    lda_topics, doc_topics, speaker_map, output_path="demo_topic_evolution.png"
):
    """
    Demo 1: Topic Evolution Timeline

    Shows how topics evolve over time during the conversation.
    """
    print("📈 Creating Topic Evolution Timeline Demo...")

    # Create dataframe
    df = pd.DataFrame(doc_topics)
    df["speaker_name"] = df["speaker"].map(lambda x: speaker_map.get(x, x))

    # Create time windows (every 10 seconds)
    df["time_window"] = (df["time"] // 10).astype(int)

    # Calculate topic frequency per window
    topic_evolution = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        window = row["time_window"]
        topic = row["dominant_topic"]
        topic_evolution[window][topic] += 1

    # Convert to DataFrame
    evolution_df = pd.DataFrame(topic_evolution).T.fillna(0)

    # Create visualization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Topic evolution lines
    for topic_id in evolution_df.columns:
        ax1.plot(
            evolution_df.index,
            evolution_df[topic_id],
            marker="o",
            linewidth=2,
            markersize=6,
            label=f"Topic {topic_id}",
        )

    ax1.set_title("Topic Evolution Over Time", fontsize=14, fontweight="bold")
    ax1.set_xlabel("Time Window (10s intervals)")
    ax1.set_ylabel("Topic Frequency")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Speaker contribution over time
    speaker_evolution = (
        df.groupby(["time_window", "speaker_name"]).size().unstack(fill_value=0)
    )
    speaker_evolution.plot(kind="bar", ax=ax2, width=0.8)
    ax2.set_title("Speaker Contribution Over Time", fontsize=14, fontweight="bold")
    ax2.set_xlabel("Time Window")
    ax2.set_ylabel("Number of Contributions")
    ax2.legend(title="Speaker")
    ax2.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Topic Evolution Timeline saved to: {output_path}")
    return output_path


def demo_topic_similarity_network(lda_topics, output_path="demo_topic_network.png"):
    """
    Demo 2: Topic Similarity Network

    Shows relationships between topics based on word overlap.
    """
    print("🕸️ Creating Topic Similarity Network Demo...")

    # Calculate topic similarities
    topic_vectors = []
    for topic in lda_topics:
        # Create topic vector from word weights
        vector = np.array(topic["weights"])
        topic_vectors.append(vector)

    if len(topic_vectors) < 2:
        print("⚠️ Need at least 2 topics for similarity analysis")
        return None

    similarity_matrix = cosine_similarity(topic_vectors)

    # Create network visualization
    fig, ax = plt.subplots(figsize=(10, 8))

    # Position topics in a circle
    n_topics = len(lda_topics)
    angles = np.linspace(0, 2 * np.pi, n_topics, endpoint=False)
    positions = {i: (np.cos(angle), np.sin(angle)) for i, angle in enumerate(angles)}

    # Draw edges (similarity connections)
    for i in range(n_topics):
        for j in range(i + 1, n_topics):
            similarity = similarity_matrix[i][j]
            if similarity > 0.1:  # Threshold for visibility
                pos1 = positions[i]
                pos2 = positions[j]
                ax.plot(
                    [pos1[0], pos2[0]],
                    [pos1[1], pos2[1]],
                    alpha=similarity,
                    linewidth=similarity * 5,
                    color="gray",
                    zorder=1,
                )

    # Draw topic nodes
    for i, topic in enumerate(lda_topics):
        pos = positions[i]
        # Node size based on average word weight
        size = np.mean(topic["weights"]) * 2000

        ax.scatter(pos[0], pos[1], s=size, alpha=0.7, color=plt.cm.Set3(i), zorder=2)

        # Add topic labels
        ax.annotate(
            f"T{i}",
            (pos[0], pos[1]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=12,
            fontweight="bold",
        )

        # Add topic words
        words = ", ".join(topic["words"][:3])
        ax.text(
            pos[0] * 1.4,
            pos[1] * 1.4,
            words,
            ha="center",
            va="center",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect("equal")
    ax.set_title(
        "Topic Similarity Network\n(Edge thickness = similarity)",
        fontsize=14,
        fontweight="bold",
    )
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Topic Similarity Network saved to: {output_path}")
    return output_path


def demo_speaker_topic_engagement(
    lda_topics, doc_topics, speaker_map, output_path="demo_speaker_engagement.png"
):
    """
    Demo 3: Speaker-Topic Engagement Heatmap

    Shows how engaged each speaker is with different topics.
    """
    print("🔥 Creating Speaker-Topic Engagement Demo...")

    # Create dataframe
    df = pd.DataFrame(doc_topics)
    df["speaker_name"] = df["speaker"].map(lambda x: speaker_map.get(x, x))

    # Calculate engagement metrics
    speaker_topic_data = defaultdict(lambda: defaultdict(list))

    for _, row in df.iterrows():
        speaker = row["speaker_name"]
        topic = row["dominant_topic"]
        confidence = row["confidence"]
        speaker_topic_data[speaker][topic].append(confidence)

    # Create engagement matrix
    speakers = list(speaker_topic_data.keys())
    topics = list(range(max(df["dominant_topic"]) + 1))

    engagement_matrix = np.zeros((len(speakers), len(topics)))
    frequency_matrix = np.zeros((len(speakers), len(topics)))

    for i, speaker in enumerate(speakers):
        for j, topic in enumerate(topics):
            if topic in speaker_topic_data[speaker]:
                confidences = speaker_topic_data[speaker][topic]
                engagement_matrix[i, j] = np.mean(confidences)
                frequency_matrix[i, j] = len(confidences)

    # Create visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

    # Engagement Heatmap
    sns.heatmap(
        engagement_matrix,
        annot=True,
        fmt=".2f",
        cmap="Blues",
        xticklabels=[f"T{i}" for i in topics],
        yticklabels=speakers,
        ax=ax1,
    )
    ax1.set_title(
        "Speaker-Topic Engagement (Confidence)", fontsize=12, fontweight="bold"
    )
    ax1.set_xlabel("Topic ID")
    ax1.set_ylabel("Speaker")

    # Frequency Heatmap
    sns.heatmap(
        frequency_matrix,
        annot=True,
        fmt=".0f",
        cmap="Reds",
        xticklabels=[f"T{i}" for i in topics],
        yticklabels=speakers,
        ax=ax2,
    )
    ax2.set_title("Speaker-Topic Frequency (Count)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Topic ID")
    ax2.set_ylabel("Speaker")

    # Speaker Contribution Distribution
    speaker_contributions = df["speaker_name"].value_counts()
    ax3.bar(
        range(len(speaker_contributions)),
        speaker_contributions.values,
        color=plt.cm.Set3(range(len(speaker_contributions))),
    )
    ax3.set_title("Speaker Contribution Distribution", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Speaker")
    ax3.set_ylabel("Number of Contributions")
    ax3.set_xticks(range(len(speaker_contributions)))
    ax3.set_xticklabels(speaker_contributions.index, rotation=45)

    # Topic Distribution
    topic_distribution = df["dominant_topic"].value_counts().sort_index()
    ax4.bar(
        range(len(topic_distribution)),
        topic_distribution.values,
        color=plt.cm.Set3(range(len(topic_distribution))),
    )
    ax4.set_title("Topic Distribution", fontsize=12, fontweight="bold")
    ax4.set_xlabel("Topic ID")
    ax4.set_ylabel("Frequency")
    ax4.set_xticks(range(len(topic_distribution)))
    ax4.set_xticklabels([f"T{i}" for i in topic_distribution.index])

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Speaker-Topic Engagement saved to: {output_path}")
    return output_path


def demo_topic_coherence_analysis(
    lda_topics, doc_topics, output_path="demo_topic_coherence.png"
):
    """
    Demo 4: Topic Coherence Analysis

    Analyzes topic quality using multiple metrics.
    """
    print("📊 Creating Topic Coherence Analysis Demo...")

    # Create dataframe
    df = pd.DataFrame(doc_topics)

    # Calculate coherence metrics
    coherence_metrics = []

    for topic in lda_topics:
        topic_id = topic["topic_id"]
        words = topic["words"]
        weights = topic["weights"]

        # Calculate metrics
        avg_weight = np.mean(weights)
        weight_variance = np.var(weights)
        word_diversity = len(set(words))

        # Topic frequency in documents
        topic_freq = (df["dominant_topic"] == topic_id).sum()

        # Average confidence when this topic is dominant
        topic_confidence = df[df["dominant_topic"] == topic_id]["confidence"].mean()

        coherence_metrics.append(
            {
                "topic_id": topic_id,
                "avg_weight": avg_weight,
                "weight_variance": weight_variance,
                "word_diversity": word_diversity,
                "frequency": topic_freq,
                "avg_confidence": topic_confidence,
                "top_words": ", ".join(words[:5]),
            }
        )

    metrics_df = pd.DataFrame(coherence_metrics)

    # Create visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

    # Topic Quality Radar Chart
    categories = ["Avg Weight", "Confidence", "Frequency", "Diversity"]
    values = [
        metrics_df["avg_weight"].values,
        metrics_df["avg_confidence"].values,
        metrics_df["frequency"].values / metrics_df["frequency"].max(),  # Normalize
        metrics_df["word_diversity"].values
        / metrics_df["word_diversity"].max(),  # Normalize
    ]

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    values = [v.tolist() + [v[0]] for v in values]  # Close the plot
    angles += angles[:1]

    ax1 = plt.subplot(2, 2, 1, projection="polar")
    for i, topic_id in enumerate(metrics_df["topic_id"]):
        ax1.plot(
            angles, values[i], "o-", linewidth=2, label=f"Topic {topic_id}", alpha=0.7
        )
        ax1.fill(angles, values[i], alpha=0.1)

    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(categories)
    ax1.set_title("Topic Quality Radar Chart", fontsize=12, fontweight="bold")
    ax1.legend(bbox_to_anchor=(1.3, 1.0))

    # Topic Weight Distribution
    ax2 = plt.subplot(2, 2, 2)
    for topic in lda_topics:
        topic_id = topic["topic_id"]
        weights = topic["weights"]
        ax2.hist(weights, alpha=0.7, label=f"Topic {topic_id}", bins=10)

    ax2.set_xlabel("Word Weight")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Topic Word Weight Distribution", fontsize=12, fontweight="bold")
    ax2.legend()

    # Topic Confidence vs Frequency
    ax3 = plt.subplot(2, 2, 3)
    scatter = ax3.scatter(
        metrics_df["frequency"],
        metrics_df["avg_confidence"],
        s=metrics_df["avg_weight"] * 1000,
        alpha=0.7,
        c=metrics_df["topic_id"],
        cmap="viridis",
    )

    for i, row in metrics_df.iterrows():
        ax3.annotate(
            f"T{row['topic_id']}",
            (row["frequency"], row["avg_confidence"]),
            xytext=(5, 5),
            textcoords="offset points",
        )

    ax3.set_xlabel("Topic Frequency")
    ax3.set_ylabel("Average Confidence")
    ax3.set_title("Topic Confidence vs Frequency", fontsize=12, fontweight="bold")

    # Topic Coherence Summary
    ax4 = plt.subplot(2, 2, 4)
    metrics_df["coherence_score"] = (
        metrics_df["avg_confidence"] * 0.4
        + metrics_df["avg_weight"] * 0.3
        + (metrics_df["frequency"] / metrics_df["frequency"].max()) * 0.3
    )

    bars = ax4.bar(
        range(len(metrics_df)),
        metrics_df["coherence_score"],
        color=plt.cm.viridis(metrics_df["topic_id"] / len(metrics_df)),
    )

    ax4.set_xlabel("Topic ID")
    ax4.set_ylabel("Coherence Score")
    ax4.set_title("Topic Coherence Summary", fontsize=12, fontweight="bold")
    ax4.set_xticks(range(len(metrics_df)))
    ax4.set_xticklabels([f"T{i}" for i in metrics_df["topic_id"]])

    # Add value labels on bars
    for bar, score in zip(bars, metrics_df["coherence_score"], strict=False):
        height = bar.get_height()
        ax4.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 0.01,
            f"{score:.2f}",
            ha="center",
            va="bottom",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Topic Coherence Analysis saved to: {output_path}")
    return output_path


def demo_interactive_explorer(
    lda_topics, doc_topics, speaker_map, output_path="demo_interactive_explorer.html"
):
    """
    Demo 5: Interactive Topic Explorer

    Creates an interactive HTML visualization.
    """
    print("🎮 Creating Interactive Topic Explorer Demo...")

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        # Create dataframe
        df = pd.DataFrame(doc_topics)
        df["speaker_name"] = df["speaker"].map(lambda x: speaker_map.get(x, x))

        # Create interactive visualization
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Topic Word Distribution",
                "Speaker-Topic Network",
                "Topic Timeline",
                "Topic Similarity Matrix",
            ),
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}],
                [{"type": "scatter"}, {"type": "heatmap"}],
            ],
        )

        # 1. Topic Word Distribution
        for topic in lda_topics:
            topic_id = topic["topic_id"]
            words = topic["words"][:8]
            weights = topic["weights"][:8]

            # Create word positions in a circle
            angles = np.linspace(0, 2 * np.pi, len(words), endpoint=False)
            x = np.cos(angles) * weights
            y = np.sin(angles) * weights

            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers+text",
                    text=words,
                    textposition="middle center",
                    name=f"Topic {topic_id}",
                    marker=dict(size=weights * 50, opacity=0.7),
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

        # 2. Speaker-Topic Network
        speakers = df["speaker_name"].unique()
        for speaker in speakers:
            speaker_topics = df[df["speaker_name"] == speaker][
                "dominant_topic"
            ].value_counts()

            fig.add_trace(
                go.Scatter(
                    x=[f"T{t}" for t in speaker_topics.index],
                    y=speaker_topics.values,
                    mode="markers+lines",
                    name=speaker,
                    marker=dict(size=10),
                    line=dict(width=2),
                ),
                row=1,
                col=2,
            )

        # 3. Topic Timeline
        time_data = df.groupby("time")["dominant_topic"].first().reset_index()

        fig.add_trace(
            go.Scatter(
                x=time_data["time"],
                y=time_data["dominant_topic"],
                mode="markers+lines",
                name="Topic Timeline",
                marker=dict(size=8),
                line=dict(width=2),
            ),
            row=2,
            col=1,
        )

        # 4. Topic Similarity Matrix
        topic_vectors = []
        for topic in lda_topics:
            vector = np.array(topic["weights"])
            topic_vectors.append(vector)

        if len(topic_vectors) >= 2:
            similarity_matrix = cosine_similarity(topic_vectors)

            fig.add_trace(
                go.Heatmap(
                    z=similarity_matrix,
                    x=[f"T{i}" for i in range(len(lda_topics))],
                    y=[f"T{i}" for i in range(len(lda_topics))],
                    colorscale="Blues",
                    showscale=True,
                ),
                row=2,
                col=2,
            )

        # Update layout
        fig.update_layout(
            title="Interactive Topic Explorer Demo",
            height=800,
            showlegend=True,
        )

        # Update axes labels
        fig.update_xaxes(title_text="X", row=1, col=1)
        fig.update_yaxes(title_text="Y", row=1, col=1)
        fig.update_xaxes(title_text="Topics", row=1, col=2)
        fig.update_yaxes(title_text="Frequency", row=1, col=2)
        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="Topic ID", row=2, col=1)
        fig.update_xaxes(title_text="To Topic", row=2, col=2)
        fig.update_yaxes(title_text="From Topic", row=2, col=2)

        # Save as HTML
        fig.write_html(output_path)

        print(f"✅ Interactive Topic Explorer saved to: {output_path}")
        return output_path

    except ImportError:
        print("⚠️ Plotly not available. Install with: pip install plotly")
        return None
    except Exception as e:
        print(f"⚠️ Could not create interactive visualization: {e}")
        return None


def main():
    """Run all demonstration visualizations."""
    print("🎨 Enhanced Topic Modeling Visualization Demonstrations")
    print("=" * 60)

    # Load data
    lda_topics, doc_topics, speaker_map = load_topic_data()

    if lda_topics is None:
        return

    print(
        f"📊 Loaded {len(lda_topics)} topics and {len(doc_topics)} document assignments"
    )
    print(f"👥 Speakers: {list(set(speaker_map.values()))}")
    print()

    # Create output directory
    output_dir = Path("demo_visualizations")
    output_dir.mkdir(exist_ok=True)

    # Run demonstrations
    demos = [
        ("Topic Evolution Timeline", demo_topic_evolution_timeline),
        ("Topic Similarity Network", demo_topic_similarity_network),
        ("Speaker-Topic Engagement", demo_speaker_topic_engagement),
        ("Topic Coherence Analysis", demo_topic_coherence_analysis),
        ("Interactive Topic Explorer", demo_interactive_explorer),
    ]

    results = {}

    for name, demo_func in demos:
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            if name == "Interactive Topic Explorer":
                result = demo_func(
                    lda_topics,
                    doc_topics,
                    speaker_map,
                    output_path=output_dir
                    / f"demo_{name.lower().replace(' ', '_')}.html",
                )
            else:
                result = demo_func(
                    lda_topics,
                    doc_topics,
                    speaker_map,
                    output_path=output_dir
                    / f"demo_{name.lower().replace(' ', '_')}.png",
                )
            results[name] = result
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = None

    # Summary
    print(f"\n{'='*60}")
    print("🎉 DEMONSTRATION COMPLETE")
    print(f"{'='*60}")
    print(f"\nGenerated visualizations in: {output_dir}")
    print("\nResults:")
    for name, result in results.items():
        if result:
            print(f"  ✅ {name}: {result}")
        else:
            print(f"  ❌ {name}: Failed")

    print(f"\n📁 Check the '{output_dir}' directory for all generated visualizations!")
    print("\n💡 These demonstrations show how the enhanced visualizations would work")
    print("   with the existing topic modeling data structure.")


if __name__ == "__main__":
    main()
