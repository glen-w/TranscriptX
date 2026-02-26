"""Topic modeling module."""

from __future__ import annotations

import json
import os
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from collections import defaultdict

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.utils.nlp_utils import (
    has_meaningful_content,
    preprocess_for_topic_modeling,
)
from transcriptx.utils.text_utils import is_named_speaker


# --- Robust JSON serialization for numpy types ---
def _to_serializable(obj):
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_to_serializable(v) for v in obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _safe_numpy_array(data, dtype=np.float64):
    """Safely convert data to numpy array with proper error handling."""
    try:
        if isinstance(data, (list, tuple)):
            # Convert each element to float to ensure compatibility
            cleaned_data = []
            for item in data:
                try:
                    cleaned_data.append(float(item))
                except (ValueError, TypeError):
                    cleaned_data.append(0.0)
            return np.array(cleaned_data, dtype=dtype)
        if isinstance(data, np.ndarray):
            return data.astype(dtype)
        return np.array([float(data)], dtype=dtype)
    except Exception as e:
        print(f"[TOPICS] Warning: Could not convert data to numpy array: {e}")
        return np.array([0.0], dtype=dtype)


def _get_segments(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("segments", [])
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"Error reading segments from {path}: {e}")
        return []


def _notify_user(msg: str, technical: bool = False, section: str = None) -> None:
    print(f"[{section or 'TOPICS'}] {msg}")


def _save_json(data: Any, path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json(path, _to_serializable(data), indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving JSON to {path}: {e}")


def _create_output_structure(transcript_dir: str, module_name: str) -> dict[str, Path]:
    module_dir = Path(OUTPUTS_DIR) / Path(transcript_dir).name / module_name
    data_dir = module_dir / "data"
    charts_dir = module_dir / "charts"
    global_data_dir = data_dir / "global"
    global_charts_dir = charts_dir / "global"
    speaker_data_dir = data_dir / "speakers"
    speaker_charts_dir = charts_dir / "speakers"
    for d in [global_data_dir, global_charts_dir, speaker_data_dir, speaker_charts_dir]:
        os.makedirs(d, exist_ok=True)
    return {
        "module_dir": module_dir,
        "global_data_dir": global_data_dir,
        "global_charts_dir": global_charts_dir,
        "speaker_data_dir": speaker_data_dir,
        "speaker_charts_dir": speaker_charts_dir,
    }


def prepare_text_data(
    segments: list[dict], return_indices: bool = False
) -> (
    tuple[list[str], list[str], list[float]]
    | tuple[list[str], list[str], list[float], list[int]]
):
    """
    Prepare text data for topic modeling from transcript segments.

    Uses database-driven speaker identification via extract_speaker_info().

    Args:
        segments: List of transcript segments

    Returns:
        Tuple of (texts, speaker_labels, time_labels) by default.
        If return_indices is True, also returns segment_indices for each text.
    """
    from transcriptx.core.utils.speaker_extraction import (
        extract_speaker_info,
        get_speaker_display_name,
    )

    texts, speaker_labels, time_labels, segment_indices = [], [], [], []
    for idx, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        # Check if segment has meaningful content using topic modeling preprocessing
        if not has_meaningful_content(
            text, preprocessing_func=preprocess_for_topic_modeling
        ):
            continue
        speaker_info = extract_speaker_info(seg)
        if speaker_info is None:
            continue
        display_name = get_speaker_display_name(
            speaker_info.grouping_key, [seg], segments
        )
        if not display_name:
            continue

        # Apply preprocessing to remove stopwords/tics and keep content words
        preprocessed_text = preprocess_for_topic_modeling(text)
        texts.append(preprocessed_text)
        speaker_labels.append(display_name)
        time_labels.append(seg.get("start", 0))
        if return_indices:
            segment_indices.append(idx)
    if return_indices:
        return texts, speaker_labels, time_labels, segment_indices
    return texts, speaker_labels, time_labels


def calculate_topic_coherence(
    top_words: list[str], texts: list[str], vectorizer
) -> float:
    """
    Calculate topic coherence using pointwise mutual information.

    Args:
        top_words: Top words for the topic
        texts: All text documents
        vectorizer: Fitted vectorizer for document-term matrix

    Returns:
        Coherence score (higher is better)
    """
    try:
        # Get document-term matrix
        X = vectorizer.transform(texts)
        feature_names = vectorizer.get_feature_names_out()

        # Create word-to-index mapping
        word_to_idx = {word: idx for idx, word in enumerate(feature_names)}

        # Calculate word frequencies
        word_freqs = {}
        for word in top_words:
            if word in word_to_idx:
                idx = word_to_idx[word]
                word_freqs[word] = float(X[:, idx].sum())

        if len(word_freqs) < 2:
            return 0.0

        # Calculate pairwise mutual information
        coherence_scores = []
        word_pairs = list(combinations(word_freqs.keys(), 2))

        for word1, word2 in word_pairs:
            if word1 in word_to_idx and word2 in word_to_idx:
                idx1, idx2 = word_to_idx[word1], word_to_idx[word2]

                # Co-occurrence count
                co_occurrence = (X[:, idx1].multiply(X[:, idx2]) > 0).sum()

                # Individual frequencies
                freq1 = word_freqs[word1]
                freq2 = word_freqs[word2]

                # Calculate PMI
                if co_occurrence > 0 and freq1 > 0 and freq2 > 0:
                    pmi = np.log((co_occurrence * len(texts)) / (freq1 * freq2))
                    coherence_scores.append(float(pmi))

        return float(np.mean(coherence_scores)) if coherence_scores else 0.0

    except Exception as e:
        print(f"[TOPICS] Warning: Could not calculate coherence: {e}")
        return 0.0


def find_optimal_k(
    texts: list[str],
    k_range: tuple[int, int] | None = None,
    algorithm: str = "lda",
    max_iter: int | None = None,
) -> dict[str, Any]:
    """
    Find optimal number of topics using diagnostic metrics (STM-inspired).

    Args:
        texts: List of text documents
        k_range: Range of k values to test (min, max). If None, uses config.
        algorithm: 'lda' or 'nmf'
        max_iter: Maximum number of iterations for NMF/LDA (optional, uses config if None)

    Returns:
        Dictionary with optimal k and diagnostic metrics
    """
    from transcriptx.core.utils.config import get_config

    config = get_config()
    topic_config = config.analysis.topic_modeling

    # Use config values if not provided
    if k_range is None:
        k_range = tuple(topic_config.k_range)
    if max_iter is None:
        max_iter = (
            topic_config.max_iter_lda
            if algorithm == "lda"
            else topic_config.max_iter_nmf
        )

    print(f"[TOPICS] Finding optimal k for {algorithm.upper()}...")

    if len(texts) < 10:
        print("[TOPICS] Warning: Insufficient data for optimal k selection")
        return {"optimal_k": min(3, len(texts)), "diagnostics": {}}

    from sklearn.decomposition import NMF, LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
    from sklearn.metrics import silhouette_score
    from sklearn.model_selection import train_test_split

    # Prepare vectorizer using config
    if algorithm == "lda":
        vectorizer = CountVectorizer(
            max_features=topic_config.max_features,
            stop_words="english",
            min_df=topic_config.min_df,
            max_df=topic_config.max_df,
            ngram_range=topic_config.ngram_range,
        )
    else:
        vectorizer = TfidfVectorizer(
            max_features=topic_config.max_features,
            stop_words="english",
            min_df=topic_config.min_df,
            max_df=topic_config.max_df,
            ngram_range=topic_config.ngram_range,
        )

    X = vectorizer.fit_transform(texts)

    # Check if X has the expected shape attribute
    try:
        n_features = X.shape[1] if hasattr(X, "shape") and len(X.shape) >= 2 else 0
        if n_features == 0:
            print("[TOPICS] Warning: No features found after vectorization")
            return {"optimal_k": 3, "diagnostics": {}}
    except Exception:
        print("[TOPICS] Warning: Could not access document-term matrix shape")
        return {"optimal_k": 3, "diagnostics": {}}

    # Determine k range based on data size
    max_possible_k = min(k_range[1], len(texts) // 5, X.shape[1] // 10)
    k_values = list(range(max(k_range[0], 3), max_possible_k + 1))

    if len(k_values) < 2:
        return {"optimal_k": k_values[0] if k_values else 3, "diagnostics": {}}

    diagnostics = {
        "k_values": k_values,
        "held_out_likelihood": [],
        "coherence_scores": [],
        "silhouette_scores": [],
        "residuals": [],
        "perplexity_scores": [],
    }

    # Split data for held-out likelihood
    X_train, X_test = train_test_split(
        X, test_size=topic_config.test_size, random_state=topic_config.random_state
    )

    for k in k_values:
        try:
            if algorithm == "lda":
                model = LatentDirichletAllocation(
                    n_components=k,
                    random_state=topic_config.random_state,
                    learning_method=topic_config.learning_method,
                    max_iter=max_iter,
                )
            else:
                model = NMF(
                    n_components=k,
                    random_state=topic_config.random_state,
                    alpha_H=topic_config.alpha_H,
                    max_iter=max_iter,
                    tol=topic_config.tol,
                    init="nndsvd",  # Better initialization for faster convergence
                )

            # Fit model
            doc_topics = model.fit_transform(X_train)

            # Calculate diagnostic metrics
            # 1. Held-out likelihood (log-likelihood on test set)
            test_topics = model.transform(X_test)
            if algorithm == "lda":
                log_likelihood = model.score(X_test)
            else:
                # For NMF, use reconstruction error as proxy
                X_reconstructed = test_topics @ model.components_
                log_likelihood = -np.mean((X_test.toarray() - X_reconstructed) ** 2)

            diagnostics["held_out_likelihood"].append(float(log_likelihood))

            # 2. Topic coherence
            coherence_scores = []
            for topic_idx in range(k):
                top_words_idx = model.components_[topic_idx].argsort()[-10:][::-1]
                top_words = [
                    vectorizer.get_feature_names_out()[i] for i in top_words_idx
                ]
                coherence = calculate_topic_coherence(top_words, texts, vectorizer)
                coherence_scores.append(coherence)

            avg_coherence = float(np.mean(coherence_scores))
            diagnostics["coherence_scores"].append(avg_coherence)

            # 3. Silhouette score (topic separation)
            if k > 1:
                dominant_topics = np.argmax(doc_topics, axis=1)
                silhouette = silhouette_score(doc_topics, dominant_topics)
                diagnostics["silhouette_scores"].append(float(silhouette))
            else:
                diagnostics["silhouette_scores"].append(0.0)

            # 4. Residuals (reconstruction error)
            X_reconstructed = doc_topics @ model.components_
            residuals = float(np.mean((X_train.toarray() - X_reconstructed) ** 2))
            diagnostics["residuals"].append(residuals)

            # 5. Perplexity (for LDA)
            if algorithm == "lda":
                perplexity = model.perplexity(X_train)
                diagnostics["perplexity_scores"].append(float(perplexity))
            else:
                diagnostics["perplexity_scores"].append(0.0)

        except Exception as e:
            print(f"[TOPICS] Warning: Error evaluating k={k}: {e}")
            diagnostics["held_out_likelihood"].append(0.0)
            diagnostics["coherence_scores"].append(0.0)
            diagnostics["silhouette_scores"].append(0.0)
            diagnostics["residuals"].append(float("inf"))
            diagnostics["perplexity_scores"].append(0.0)

    # Find optimal k based on diagnostic metrics
    if len(diagnostics["held_out_likelihood"]) > 0:
        # Normalize metrics for comparison
        likelihood_norm = np.array(diagnostics["held_out_likelihood"])
        coherence_norm = np.array(diagnostics["coherence_scores"])
        silhouette_norm = np.array(diagnostics["silhouette_scores"])
        residuals_norm = np.array(diagnostics["residuals"])

        # Normalize to 0-1 range
        if likelihood_norm.max() > likelihood_norm.min():
            likelihood_norm = (likelihood_norm - likelihood_norm.min()) / (
                likelihood_norm.max() - likelihood_norm.min()
            )
        if coherence_norm.max() > coherence_norm.min():
            coherence_norm = (coherence_norm - coherence_norm.min()) / (
                coherence_norm.max() - coherence_norm.min()
            )
        if silhouette_norm.max() > silhouette_norm.min():
            silhouette_norm = (silhouette_norm - silhouette_norm.min()) / (
                silhouette_norm.max() - silhouette_norm.min()
            )
        if residuals_norm.max() > residuals_norm.min():
            residuals_norm = (residuals_norm - residuals_norm.min()) / (
                residuals_norm.max() - residuals_norm.min()
            )

        # Combined score (higher is better)
        combined_scores = (
            likelihood_norm * 0.3
            + coherence_norm * 0.3
            + silhouette_norm * 0.2
            - residuals_norm * 0.2
        )

        optimal_k_idx = np.argmax(combined_scores)
        optimal_k = k_values[optimal_k_idx]

        print(f"[TOPICS] Optimal k for {algorithm.upper()}: {optimal_k}")
        print(
            f"[TOPICS] Diagnostic scores: Likelihood={diagnostics['held_out_likelihood'][optimal_k_idx]:.3f}, "
            f"Coherence={diagnostics['coherence_scores'][optimal_k_idx]:.3f}, "
            f"Silhouette={diagnostics['silhouette_scores'][optimal_k_idx]:.3f}"
        )

        return {
            "optimal_k": optimal_k,
            "diagnostics": diagnostics,
            "combined_scores": combined_scores.tolist(),
        }

    return {"optimal_k": k_values[0] if k_values else 3, "diagnostics": diagnostics}


def generate_topic_labels(top_words: list[str], weights: list[float]) -> str:
    """
    Generate narrative labels for topics based on top words.

    Args:
        top_words: Top words for the topic
        weights: Corresponding weights

    Returns:
        Narrative label for the topic
    """
    # Simple rule-based labeling
    word_str = " ".join(top_words[:3]).lower()

    # Define topic categories based on common conversation themes
    topic_patterns = {
        "project": ["project", "plan", "planning", "strategy", "goal"],
        "technical": ["technical", "technology", "system", "implementation", "code"],
        "business": ["business", "market", "customer", "revenue", "profit"],
        "team": ["team", "collaboration", "meeting", "discussion", "communication"],
        "timeline": ["timeline", "deadline", "schedule", "time", "date"],
        "budget": ["budget", "cost", "financial", "money", "expense"],
        "quality": ["quality", "testing", "review", "evaluation", "assessment"],
        "risk": ["risk", "issue", "problem", "challenge", "concern"],
    }

    for category, keywords in topic_patterns.items():
        if any(keyword in word_str for keyword in keywords):
            return f"{category.title()} Discussion"

    # Default label based on most prominent word
    if weights and top_words:
        primary_word = top_words[0]
        return f"{primary_word.title()}-Related Discussion"

    return "General Discussion"


def analyze_discourse_topics(
    doc_topic_data: list[dict], discourse_assignments: dict[int, str] | None = None
) -> dict[str, Any]:
    """
    Analyze how topics vary across different discourse contexts.

    Args:
        doc_topic_data: Document-topic assignments
        discourse_assignments: Optional discourse labels for documents

    Returns:
        Discourse-aware topic analysis
    """
    if not discourse_assignments:
        # Create simple discourse categories based on conversation flow
        discourse_assignments = {}
        for i, doc in enumerate(doc_topic_data):
            if i < len(doc_topic_data) * 0.3:
                discourse_assignments[i] = "opening"
            elif i < len(doc_topic_data) * 0.7:
                discourse_assignments[i] = "main_discussion"
            else:
                discourse_assignments[i] = "closing"

    # Analyze topic prevalence across discourses
    discourse_topic_analysis = defaultdict(lambda: defaultdict(int))
    discourse_confidence = defaultdict(lambda: defaultdict(list))

    for i, doc in enumerate(doc_topic_data):
        discourse = discourse_assignments.get(i, "unknown")
        topic = doc["dominant_topic"]
        confidence = doc["confidence"]

        discourse_topic_analysis[discourse][topic] += 1
        discourse_confidence[discourse][topic].append(confidence)

    # Calculate average confidence per discourse-topic combination
    discourse_topic_confidence = {}
    for discourse, topics in discourse_confidence.items():
        discourse_topic_confidence[discourse] = {
            topic: np.mean(confidences) for topic, confidences in topics.items()
        }

    return {
        "discourse_assignments": discourse_assignments,
        "topic_prevalence": dict(discourse_topic_analysis),
        "topic_confidence": discourse_topic_confidence,
        "discourse_summary": {
            discourse: {
                "total_segments": sum(
                    len(confidences) for confidences in topics.values()
                ),
                "topic_diversity": len(topics),
                "avg_confidence": np.mean(
                    [np.mean(confidences) for confidences in topics.values()]
                ),
            }
            for discourse, topics in discourse_confidence.items()
        },
    }


def _is_named_speaker(speaker):
    return is_named_speaker(speaker)
