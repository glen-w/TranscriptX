"""Topic modeling module."""

from __future__ import annotations

from typing import Any

import numpy as np
from transcriptx.core.utils.lazy_imports import lazy_module

from .utils import (
    calculate_topic_coherence,
    find_optimal_k,
    generate_topic_labels,
    _safe_numpy_array,
)


# --- Robust JSON serialization for numpy types ---
def perform_enhanced_lda_analysis(
    texts, speaker_labels, time_labels, optimal_k: int | None = None
) -> dict[str, Any]:
    """
    Perform enhanced LDA analysis with optimal k selection and topic evaluation.

    Args:
        texts: List of text documents
        speaker_labels: List of speaker labels
        time_labels: List of time labels
        optimal_k: Optional pre-determined k value

    Returns:
        Enhanced LDA results with diagnostics and topic labels
    """
    if len(texts) < 3:
        raise ValueError("Need at least 3 text segments for LDA analysis")

    mpl = lazy_module("matplotlib", "plotting", "visualization")
    sns = lazy_module("seaborn", "plotting", "visualization")
    mpl.rcdefaults()
    sns.reset_defaults()
    sns.set_theme(style="whitegrid")

    # Find optimal k if not provided
    if optimal_k is None:
        k_results = find_optimal_k(texts, algorithm="lda")
        optimal_k = k_results["optimal_k"]
        diagnostics = k_results["diagnostics"]
    else:
        diagnostics = {}

    from transcriptx.core.utils.config import get_config

    config = get_config()
    topic_config = config.analysis.topic_modeling

    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    vectorizer = CountVectorizer(
        max_features=topic_config.max_features,
        stop_words="english",
        min_df=topic_config.min_df,
        max_df=topic_config.max_df,
        ngram_range=topic_config.ngram_range,
    )
    X = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    if len(feature_names) == 0:
        raise ValueError("No features found after vectorization")

    lda = LatentDirichletAllocation(
        n_components=optimal_k,
        random_state=topic_config.random_state,
        learning_method=topic_config.learning_method,
        max_iter=topic_config.max_iter_lda,
    )
    doc_topics = lda.fit_transform(X)

    topics = []
    for topic_idx, topic in enumerate(lda.components_):
        top_words_idx = topic.argsort()[-10:][::-1]
        top_words = [feature_names[i] for i in top_words_idx]
        top_weights = [float(topic[i]) for i in top_words_idx]

        # Generate topic label
        topic_label = generate_topic_labels(top_words, top_weights)

        # Calculate topic coherence
        coherence = calculate_topic_coherence(top_words, texts, vectorizer)

        topics.append(
            {
                "topic_id": topic_idx,
                "words": top_words,
                "weights": top_weights,
                "label": topic_label,
                "coherence": coherence,
            }
        )

    doc_topic_data = []
    for i, (text, speaker, time) in enumerate(
        zip(texts, speaker_labels, time_labels, strict=False)
    ):
        topic_dist = _safe_numpy_array(doc_topics[i], dtype=np.float64)
        dominant_topic = int(np.argmax(topic_dist))
        doc_topic_data.append(
            {
                "text": text,
                "speaker": speaker,
                "time": time,
                "dominant_topic": dominant_topic,
                "topic_distribution": topic_dist.tolist(),
                "confidence": float(np.max(topic_dist)),
            }
        )

    return {
        "model": lda,
        "vectorizer": vectorizer,
        "topics": topics,
        "doc_topics": doc_topics,
        "doc_topic_data": doc_topic_data,
        "feature_names": feature_names.tolist(),
        "diagnostics": diagnostics,
        "optimal_k": optimal_k,
    }
