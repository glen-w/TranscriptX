#!/usr/bin/env python3
"""
Create sample PNG chart files for testing the web app.
"""


import matplotlib.pyplot as plt
import numpy as np


def create_sample_chart(filename, title, data_type="bar"):
    """Create a sample chart and save as PNG."""
    plt.figure(figsize=(10, 6))

    if data_type == "bar":
        categories = ["Category A", "Category B", "Category C", "Category D"]
        values = np.random.randint(10, 100, len(categories))
        plt.bar(categories, values, color=["#007bff", "#28a745", "#ffc107", "#dc3545"])
        plt.ylabel("Values")
    elif data_type == "line":
        x = np.linspace(0, 10, 50)
        y = np.sin(x) + np.random.normal(0, 0.1, 50)
        plt.plot(x, y, color="#007bff", linewidth=2)
        plt.xlabel("Time")
        plt.ylabel("Value")
    elif data_type == "pie":
        sizes = [30, 25, 20, 15, 10]
        labels = ["Group A", "Group B", "Group C", "Group D", "Group E"]
        colors = ["#007bff", "#28a745", "#ffc107", "#dc3545", "#6f42c1"]
        plt.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%")

    plt.title(title)
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()


def main():
    """Create sample charts for testing."""
    base_dir = "transcriptx_output/meeting1"

    # Sentiment Analysis charts
    sentiment_dir = f"{base_dir}/sentiment_analysis/charts"

    # Global sentiment charts
    global_dir = f"{sentiment_dir}/global"
    create_sample_chart(
        f"{global_dir}/overall_sentiment_distribution.png",
        "Overall Sentiment Distribution",
        "pie",
    )
    create_sample_chart(
        f"{global_dir}/sentiment_timeline.png", "Sentiment Timeline", "line"
    )
    create_sample_chart(
        f"{global_dir}/sentiment_scores.png", "Sentiment Scores by Category", "bar"
    )

    # Per-speaker sentiment charts
    per_speaker_dir = f"{sentiment_dir}/per_speaker"
    create_sample_chart(
        f"{per_speaker_dir}/speaker_sentiment_comparison.png",
        "Speaker Sentiment Comparison",
        "bar",
    )
    create_sample_chart(
        f"{per_speaker_dir}/speaker_emotion_distribution.png",
        "Speaker Emotion Distribution",
        "pie",
    )

    # Topic Modeling charts
    topic_dir = f"{base_dir}/topic_modeling/charts"

    # Global topic charts
    topic_global_dir = f"{topic_dir}/global"
    create_sample_chart(
        f"{topic_global_dir}/topic_distribution.png", "Topic Distribution", "pie"
    )
    create_sample_chart(
        f"{topic_global_dir}/topic_evolution.png", "Topic Evolution Over Time", "line"
    )

    # Per-topic charts
    per_topic_dir = f"{topic_dir}/per_topic"
    create_sample_chart(
        f"{per_topic_dir}/topic_1_keywords.png", "Topic 1: Key Terms", "bar"
    )
    create_sample_chart(
        f"{per_topic_dir}/topic_2_keywords.png", "Topic 2: Key Terms", "bar"
    )
    create_sample_chart(
        f"{per_topic_dir}/topic_3_keywords.png", "Topic 3: Key Terms", "bar"
    )

    print("Sample charts created successfully!")
    print(f"Created charts in: {base_dir}")


if __name__ == "__main__":
    main()
