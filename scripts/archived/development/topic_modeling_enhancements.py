#!/usr/bin/env python3
"""
Enhanced Topic Modeling Visualizations for TranscriptX

This file demonstrates 5 additional visualizations that would significantly
improve the topic modeling analysis capabilities.
"""

import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns
from plotly.subplots import make_subplots
from sklearn.metrics.pairwise import cosine_similarity

# Configure matplotlib
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


class EnhancedTopicVisualizations:
    """
    Enhanced topic modeling visualizations for TranscriptX.

    This class provides 5 additional visualizations:
    1. Topic Evolution Timeline
    2. Topic Similarity Network
    3. Speaker-Topic Engagement Heatmap
    4. Topic Coherence Analysis
    5. Interactive Topic Explorer
    """

    def __init__(
        self,
        lda_topics: list[dict],
        nmf_topics: list[dict],
        doc_topics: list[dict],
        speaker_map: dict[str, str] = None,
    ):
        """
        Initialize with topic modeling results.

        Args:
            lda_topics: LDA topic results
            nmf_topics: NMF topic results
            doc_topics: Document-topic assignments
            speaker_map: Speaker ID to name mapping
        """
        self.lda_topics = lda_topics
        self.nmf_topics = nmf_topics
        self.doc_topics = doc_topics
        self.speaker_map = speaker_map or {}

        # Process data
        self._process_data()

    def _process_data(self):
        """Process and prepare data for visualizations."""
        # Create time-based dataframe
        self.df = pd.DataFrame(self.doc_topics)
        self.df["speaker_name"] = self.df["speaker"].map(
            lambda x: self.speaker_map.get(x, x),
        )

        # Extract topic words and weights
        self.lda_topic_words = {t["topic_id"]: t["words"] for t in self.lda_topics}
        self.nmf_topic_words = {t["topic_id"]: t["words"] for t in self.nmf_topics}

        # Calculate topic similarities
        self._calculate_topic_similarities()

    def _calculate_topic_similarities(self):
        """Calculate topic similarity matrices."""
        # For LDA topics
        lda_vectors = []
        for topic in self.lda_topics:
            # Create topic vector from word weights
            vector = np.array(topic["weights"])
            lda_vectors.append(vector)

        if lda_vectors:
            self.lda_similarity = cosine_similarity(lda_vectors)
        else:
            self.lda_similarity = np.array([])

    def create_topic_evolution_timeline(
        self, output_path: str, window_size: int = 5
    ) -> str:
        """
        Visualization 1: Topic Evolution Timeline

        Shows how topics evolve over time using a sliding window approach.
        This helps identify when topics emerge, peak, and fade during the conversation.

        Args:
            output_path: Path to save the visualization
            window_size: Number of consecutive segments to group together

        Returns:
            Path to saved visualization
        """
        print("📈 Creating Topic Evolution Timeline...")

        # Create time windows
        self.df["time_window"] = (self.df["time"] // (window_size * 10)).astype(int)

        # Calculate topic prevalence in each window
        topic_evolution = defaultdict(lambda: defaultdict(int))

        for _, row in self.df.iterrows():
            window = row["time_window"]
            dominant_topic = row["dominant_topic"]
            topic_evolution[window][dominant_topic] += 1

        # Convert to DataFrame
        evolution_df = pd.DataFrame(topic_evolution).T.fillna(0)
        evolution_df.index.name = "Time Window"

        # Create visualization
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # LDA Evolution
        lda_evolution = evolution_df.copy()
        lda_evolution.plot(kind="line", marker="o", ax=ax1, linewidth=2, markersize=6)
        ax1.set_title("LDA Topic Evolution Over Time", fontsize=14, fontweight="bold")
        ax1.set_xlabel("Time Window")
        ax1.set_ylabel("Topic Frequency")
        ax1.legend(title="Topic ID", bbox_to_anchor=(1.05, 1), loc="upper left")
        ax1.grid(True, alpha=0.3)

        # Add topic labels
        for topic_id in evolution_df.columns:
            if topic_id in self.lda_topic_words:
                topic_label = (
                    f"Topic {topic_id}: {', '.join(self.lda_topic_words[topic_id][:3])}"
                )
                ax1.text(
                    0.02,
                    0.98 - topic_id * 0.15,
                    topic_label,
                    transform=ax1.transAxes,
                    fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                )

        # Topic Transition Heatmap
        topic_transitions = self._calculate_topic_transitions()
        if topic_transitions is not None:
            sns.heatmap(topic_transitions, annot=True, fmt=".2f", cmap="YlOrRd", ax=ax2)
            ax2.set_title(
                "Topic Transition Probabilities", fontsize=14, fontweight="bold"
            )
            ax2.set_xlabel("To Topic")
            ax2.set_ylabel("From Topic")

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"✅ Topic Evolution Timeline saved to: {output_path}")
        return output_path

    def _calculate_topic_transitions(self) -> np.ndarray:
        """Calculate transition probabilities between topics."""
        if len(self.df) < 2:
            return None

        # Get topic sequence
        topic_sequence = self.df["dominant_topic"].values

        # Count transitions
        n_topics = max(topic_sequence) + 1
        transition_matrix = np.zeros((n_topics, n_topics))

        for i in range(len(topic_sequence) - 1):
            from_topic = topic_sequence[i]
            to_topic = topic_sequence[i + 1]
            transition_matrix[from_topic][to_topic] += 1

        # Normalize to probabilities
        row_sums = transition_matrix.sum(axis=1)
        transition_matrix = np.divide(
            transition_matrix,
            row_sums[:, np.newaxis],
            where=row_sums[:, np.newaxis] != 0,
        )

        return transition_matrix

    def create_topic_similarity_network(self, output_path: str) -> str:
        """
        Visualization 2: Topic Similarity Network

        Creates a network visualization showing relationships between topics
        based on their word overlap and semantic similarity.

        Args:
            output_path: Path to save the visualization

        Returns:
            Path to saved visualization
        """
        print("🕸️ Creating Topic Similarity Network...")

        if len(self.lda_similarity) == 0:
            print("⚠️ No topic similarity data available")
            return None

        # Create network data
        nodes = []
        edges = []

        for i, topic in enumerate(self.lda_topics):
            nodes.append(
                {
                    "id": i,
                    "label": f"Topic {i}",
                    "words": ", ".join(topic["words"][:5]),
                    "size": sum(
                        topic["weights"][:5]
                    ),  # Node size based on top word weights
                }
            )

        # Create edges based on similarity
        for i in range(len(self.lda_topics)):
            for j in range(i + 1, len(self.lda_topics)):
                similarity = self.lda_similarity[i][j]
                if similarity > 0.3:  # Threshold for edge creation
                    edges.append(
                        {
                            "source": i,
                            "target": j,
                            "weight": similarity,
                        }
                    )

        # Create visualization using matplotlib
        fig, ax = plt.subplots(figsize=(12, 10))

        # Position nodes in a circle
        n_nodes = len(nodes)
        angles = np.linspace(0, 2 * np.pi, n_nodes, endpoint=False)
        positions = {
            i: (np.cos(angle), np.sin(angle)) for i, angle in enumerate(angles)
        }

        # Draw edges
        for edge in edges:
            source_pos = positions[edge["source"]]
            target_pos = positions[edge["target"]]
            weight = edge["weight"]

            ax.plot(
                [source_pos[0], target_pos[0]],
                [source_pos[1], target_pos[1]],
                alpha=weight,
                linewidth=weight * 3,
                color="gray",
                zorder=1,
            )

        # Draw nodes
        for node in nodes:
            pos = positions[node["id"]]
            size = node["size"] * 1000  # Scale for visibility

            ax.scatter(
                pos[0],
                pos[1],
                s=size,
                alpha=0.7,
                color=plt.cm.Set3(node["id"]),
                zorder=2,
            )

            # Add labels
            ax.annotate(
                f"T{node['id']}",
                (pos[0], pos[1]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=10,
                fontweight="bold",
            )

        # Add topic word labels
        for i, node in enumerate(nodes):
            pos = positions[node["id"]]
            ax.text(
                pos[0] * 1.3,
                pos[1] * 1.3,
                node["words"],
                ha="center",
                va="center",
                fontsize=8,
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

    def create_speaker_topic_engagement_heatmap(self, output_path: str) -> str:
        """
        Visualization 3: Speaker-Topic Engagement Heatmap

        Shows how engaged each speaker is with different topics,
        including both contribution frequency and topic confidence.

        Args:
            output_path: Path to save the visualization

        Returns:
            Path to saved visualization
        """
        print("🔥 Creating Speaker-Topic Engagement Heatmap...")

        # Calculate speaker-topic engagement metrics
        speaker_topic_data = defaultdict(lambda: defaultdict(list))

        for _, row in self.df.iterrows():
            speaker = row["speaker_name"]
            topic = row["dominant_topic"]
            confidence = row["confidence"]

            speaker_topic_data[speaker][topic].append(confidence)

        # Create engagement matrix
        speakers = list(speaker_topic_data.keys())
        topics = list(range(max(self.df["dominant_topic"]) + 1))

        engagement_matrix = np.zeros((len(speakers), len(topics)))
        frequency_matrix = np.zeros((len(speakers), len(topics)))

        for i, speaker in enumerate(speakers):
            for j, topic in enumerate(topics):
                if topic in speaker_topic_data[speaker]:
                    confidences = speaker_topic_data[speaker][topic]
                    engagement_matrix[i, j] = np.mean(confidences)
                    frequency_matrix[i, j] = len(confidences)

        # Create visualization
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

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
        speaker_contributions = self.df["speaker_name"].value_counts()
        ax3.bar(
            range(len(speaker_contributions)),
            speaker_contributions.values,
            color=plt.cm.Set3(range(len(speaker_contributions))),
        )
        ax3.set_title(
            "Speaker Contribution Distribution", fontsize=12, fontweight="bold"
        )
        ax3.set_xlabel("Speaker")
        ax3.set_ylabel("Number of Contributions")
        ax3.set_xticks(range(len(speaker_contributions)))
        ax3.set_xticklabels(speaker_contributions.index, rotation=45)

        # Topic Distribution
        topic_distribution = self.df["dominant_topic"].value_counts().sort_index()
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

        print(f"✅ Speaker-Topic Engagement Heatmap saved to: {output_path}")
        return output_path

    def create_topic_coherence_analysis(self, output_path: str) -> str:
        """
        Visualization 4: Topic Coherence Analysis

        Analyzes topic quality using coherence metrics and provides
        insights into topic interpretability and distinctness.

        Args:
            output_path: Path to save the visualization

        Returns:
            Path to saved visualization
        """
        print("📊 Creating Topic Coherence Analysis...")

        # Calculate topic coherence metrics
        coherence_metrics = []

        for topic in self.lda_topics:
            topic_id = topic["topic_id"]
            words = topic["words"]
            weights = topic["weights"]

            # Calculate metrics
            avg_weight = np.mean(weights)
            weight_variance = np.var(weights)
            word_diversity = len(set(words))

            # Topic frequency in documents
            topic_freq = (self.df["dominant_topic"] == topic_id).sum()

            # Average confidence when this topic is dominant
            topic_confidence = self.df[self.df["dominant_topic"] == topic_id][
                "confidence"
            ].mean()

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
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

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
                angles,
                values[i],
                "o-",
                linewidth=2,
                label=f"Topic {topic_id}",
                alpha=0.7,
            )
            ax1.fill(angles, values[i], alpha=0.1)

        ax1.set_xticks(angles[:-1])
        ax1.set_xticklabels(categories)
        ax1.set_title("Topic Quality Radar Chart", fontsize=12, fontweight="bold")
        ax1.legend(bbox_to_anchor=(1.3, 1.0))

        # Topic Weight Distribution
        ax2 = plt.subplot(2, 2, 2)
        for topic in self.lda_topics:
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

    def create_interactive_topic_explorer(self, output_path: str) -> str:
        """
        Visualization 5: Interactive Topic Explorer

        Creates an interactive HTML visualization that allows users to
        explore topics, speakers, and their relationships dynamically.

        Args:
            output_path: Path to save the HTML visualization

        Returns:
            Path to saved HTML file
        """
        print("🎮 Creating Interactive Topic Explorer...")

        try:
            # Create interactive visualization using Plotly
            fig = make_subplots(
                rows=2,
                cols=2,
                subplot_titles=(
                    "Topic Word Clouds",
                    "Speaker-Topic Network",
                    "Topic Timeline",
                    "Topic Similarity Matrix",
                ),
                specs=[
                    [{"type": "scatter"}, {"type": "scatter"}],
                    [{"type": "scatter"}, {"type": "heatmap"}],
                ],
            )

            # 1. Topic Word Clouds (simplified as scatter plot)
            for topic in self.lda_topics:
                topic_id = topic["topic_id"]
                words = topic["words"][:10]
                weights = topic["weights"][:10]

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
            speakers = self.df["speaker_name"].unique()
            for i, speaker in enumerate(speakers):
                speaker_topics = self.df[self.df["speaker_name"] == speaker][
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
            time_data = self.df.groupby("time")["dominant_topic"].first().reset_index()

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
            if len(self.lda_similarity) > 0:
                fig.add_trace(
                    go.Heatmap(
                        z=self.lda_similarity,
                        x=[f"T{i}" for i in range(len(self.lda_topics))],
                        y=[f"T{i}" for i in range(len(self.lda_topics))],
                        colorscale="Blues",
                        showscale=True,
                    ),
                    row=2,
                    col=2,
                )

            # Update layout
            fig.update_layout(
                title="Interactive Topic Explorer",
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

        except Exception as e:
            print(f"⚠️ Could not create interactive visualization: {e}")
            return None


def create_all_enhanced_visualizations(
    lda_topics_path: str,
    nmf_topics_path: str,
    doc_topics_path: str,
    speaker_map_path: str = None,
    output_dir: str = "enhanced_topic_visualizations",
) -> dict[str, str]:
    """
    Create all 5 enhanced topic modeling visualizations.

    Args:
        lda_topics_path: Path to LDA topics JSON file
        nmf_topics_path: Path to NMF topics JSON file
        doc_topics_path: Path to document topics JSON file
        speaker_map_path: Path to speaker map JSON file (optional)
        output_dir: Directory to save visualizations

    Returns:
        Dictionary mapping visualization names to output paths
    """
    # Load data
    with open(lda_topics_path) as f:
        lda_topics = json.load(f)

    with open(nmf_topics_path) as f:
        nmf_topics = json.load(f)

    with open(doc_topics_path) as f:
        doc_topics = json.load(f)

    speaker_map = {}
    if speaker_map_path and Path(speaker_map_path).exists():
        with open(speaker_map_path) as f:
            speaker_map = json.load(f)

    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)

    # Initialize visualizer
    visualizer = EnhancedTopicVisualizations(
        lda_topics, nmf_topics, doc_topics, speaker_map
    )

    # Create all visualizations
    outputs = {}

    outputs["topic_evolution"] = visualizer.create_topic_evolution_timeline(
        f"{output_dir}/topic_evolution_timeline.png",
    )

    outputs["topic_network"] = visualizer.create_topic_similarity_network(
        f"{output_dir}/topic_similarity_network.png",
    )

    outputs["speaker_engagement"] = visualizer.create_speaker_topic_engagement_heatmap(
        f"{output_dir}/speaker_topic_engagement.png",
    )

    outputs["topic_coherence"] = visualizer.create_topic_coherence_analysis(
        f"{output_dir}/topic_coherence_analysis.png",
    )

    outputs["interactive_explorer"] = visualizer.create_interactive_topic_explorer(
        f"{output_dir}/interactive_topic_explorer.html",
    )

    return outputs


if __name__ == "__main__":
    # Example usage with the generated data
    example_dir = "example_transcript/topic_modeling/data/global"

    outputs = create_all_enhanced_visualizations(
        lda_topics_path=f"{example_dir}/example_transcript_lda_topics.json",
        nmf_topics_path=f"{example_dir}/example_transcript_nmf_topics.json",
        doc_topics_path=f"{example_dir}/example_transcript_lda_document_topics.json",
        speaker_map_path="example_transcript/example_transcript_speaker_map.json",
        output_dir="enhanced_visualizations",
    )

    print("\n🎉 Enhanced Topic Modeling Visualizations Created!")
    print("\nGenerated visualizations:")
    for name, path in outputs.items():
        if path:
            print(f"  ✅ {name}: {path}")
        else:
            print(f"  ❌ {name}: Failed to create")
