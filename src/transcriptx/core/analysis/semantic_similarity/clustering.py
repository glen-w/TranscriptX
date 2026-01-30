"""
Clustering utilities for repetition patterns.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

import numpy as np

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import log_error, log_warning


def cluster_repetitions_advanced(
    speaker_repetitions: dict[str, list],
    cross_speaker_repetitions: list[dict[str, Any]],
    log_tag: str,
) -> list[dict[str, Any]]:
    """Cluster repetitions using TF-IDF (advanced)."""
    try:
        clusters: list[dict[str, Any]] = []
        all_repetitions: list[dict[str, Any]] = []

        for reps in speaker_repetitions.values():
            all_repetitions.extend(reps)
        all_repetitions.extend(cross_speaker_repetitions)

        if not all_repetitions:
            return clusters

        texts: list[str] = []
        for rep in all_repetitions:
            if "segment1" in rep and "segment2" in rep:
                texts.append(rep["segment1"]["text"])
                texts.append(rep["segment2"]["text"])

        if len(texts) < 2:
            return clusters

        try:
            vector_config = get_config().analysis.vectorization
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import DBSCAN

            vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=vector_config.ngram_range,
                max_features=vector_config.max_features,
            )
            tfidf_matrix = vectorizer.fit_transform(texts)
            clustering = DBSCAN(eps=0.3, min_samples=2).fit(tfidf_matrix)

            cluster_groups: dict[int, list] = defaultdict(list)
            for i, label in enumerate(clustering.labels_):
                if label >= 0:
                    cluster_groups[label].append(all_repetitions[i // 2])

            for cluster_id, cluster_reps in cluster_groups.items():
                if len(cluster_reps) >= 2:
                    clusters.append(
                        {
                            "cluster_id": cluster_id,
                            "size": len(cluster_reps),
                            "repetitions": cluster_reps,
                            "average_similarity": np.mean(
                                [rep.get("similarity", 0) for rep in cluster_reps]
                            ),
                            "types": list(
                                set(rep.get("type", "") for rep in cluster_reps)
                            ),
                        }
                    )
        except Exception as exc:
            log_warning(log_tag, f"Clustering failed: {exc}")
            type_groups: dict[str, list] = defaultdict(list)
            for rep in all_repetitions:
                type_groups[rep.get("type", "unknown")].append(rep)

            for rep_type, reps in type_groups.items():
                if len(reps) >= 2:
                    clusters.append(
                        {
                            "cluster_id": f"type_{rep_type}",
                            "size": len(reps),
                            "repetitions": reps,
                            "average_similarity": np.mean(
                                [rep.get("similarity", 0) for rep in reps]
                            ),
                            "types": [rep_type],
                        }
                    )

        return clusters
    except Exception as exc:
        log_error(log_tag, f"Repetition clustering failed: {exc}", exception=exc)
        return []


def cluster_repetitions_basic(
    speaker_repetitions: dict[str, list],
    cross_speaker_repetitions: list[dict[str, Any]],
    embedding_fn: Callable[[str], np.ndarray | None],
    log_tag: str,
) -> list[dict[str, Any]]:
    """Cluster repetitions using embeddings (basic)."""
    clusters: list[dict[str, Any]] = []
    all_texts: list[str] = []
    text_to_repetition: dict[str, dict[str, Any]] = {}

    for reps in speaker_repetitions.values():
        for rep in reps:
            text1 = rep["segment1"]["text"]
            text2 = rep["segment2"]["text"]
            all_texts.extend([text1, text2])
            text_to_repetition[text1] = rep
            text_to_repetition[text2] = rep

    for rep in cross_speaker_repetitions:
        text1 = rep["segment1"]["text"]
        text2 = rep["segment2"]["text"]
        all_texts.extend([text1, text2])
        text_to_repetition[text1] = rep
        text_to_repetition[text2] = rep

    if not all_texts:
        return clusters

    embeddings: list[np.ndarray] = []
    valid_texts: list[str] = []

    for text in all_texts:
        if text not in text_to_repetition:
            continue
        emb = embedding_fn(text)
        if emb is not None:
            embeddings.append(emb.flatten())
            valid_texts.append(text)

    if len(embeddings) < 2:
        return clusters

    try:
        embeddings_array = np.array(embeddings)
        from sklearn.cluster import DBSCAN

        clustering = DBSCAN(eps=0.3, min_samples=2).fit(embeddings_array)

        cluster_groups: dict[int, list] = defaultdict(list)
        for i, label in enumerate(clustering.labels_):
            if label >= 0:
                cluster_groups[label].append(valid_texts[i])

        for cluster_id, texts in cluster_groups.items():
            if len(texts) < 2:
                continue

            cluster_repetitions = [
                text_to_repetition[text]
                for text in texts
                if text in text_to_repetition
            ]

            clusters.append(
                {
                    "cluster_id": cluster_id,
                    "size": len(texts),
                    "repetitions": cluster_repetitions,
                    "representative_text": texts[0],
                    "speakers_involved": list(
                        set(
                            [
                                rep.get("speaker", rep.get("speaker1", "Unknown"))
                                for rep in cluster_repetitions
                            ]
                        )
                    ),
                }
            )
    except Exception as exc:
        log_warning(log_tag, f"Clustering failed: {exc}")

    return clusters
