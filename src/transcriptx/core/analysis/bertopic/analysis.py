"""
BERTopic analysis module.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.lazy_imports import optional_import
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.nlp_utils import (
    has_meaningful_content,
    preprocess_for_topic_modeling,
)
from transcriptx.core.viz.specs import BarCategoricalSpec, HeatmapMatrixSpec

from transcriptx.core.analysis.topic_modeling.utils import prepare_text_data

from .utils import build_doc_topic_data, build_topic_objects


class BERTopicAnalysis(AnalysisModule):
    """
    Topic modeling analysis module using BERTopic.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "bertopic"
        self.logger = get_logger()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] | None = None
    ) -> Dict[str, Any]:
        """
        Perform BERTopic analysis on transcript segments (pure logic, no I/O).
        """
        texts, speaker_labels, time_labels, segment_indices = prepare_text_data(
            segments, return_indices=True
        )

        if not texts:
            total_segments = len(segments)
            meaningful_count = sum(
                1
                for seg in segments
                if has_meaningful_content(
                    seg.get("text", "").strip(),
                    preprocessing_func=preprocess_for_topic_modeling,
                )
            )
            return {
                "error": "No valid text data found for BERTopic",
                "message": (
                    "BERTopic failed - insufficient data after preprocessing. "
                    f"Total segments: {total_segments}, segments with meaningful "
                    f"content: {meaningful_count}"
                ),
                "topics": [],
                "doc_topic_data": [],
                "meta": {
                    "total_segments": total_segments,
                    "meaningful_segments_after_preprocessing": meaningful_count,
                    "reason": (
                        "All segments were filtered out during preprocessing "
                        "(likely too short or contain only stopwords/tics after "
                        "content word filtering)"
                    ),
                },
            }

        if len(texts) < 3:
            return {
                "error": (
                    "Need at least 3 text segments for BERTopic analysis, "
                    f"but only {len(texts)} segment(s) found after preprocessing"
                ),
                "topics": [],
                "doc_topic_data": [],
                "meta": {"texts_count": len(texts)},
            }

        try:
            bertopic_module = optional_import(
                "bertopic", "BERTopic topic modeling", "bertopic", auto_install=True
            )
        except ImportError as exc:
            raise ImportError(
                f"{exc} If install fails on your platform, try upgrading pip and "
                "installing build tools."
            ) from exc

        config = get_config()
        bertopic_cfg = getattr(config.analysis, "bertopic", None)

        model_kwargs: Dict[str, Any] = {}
        if bertopic_cfg:
            if getattr(bertopic_cfg, "embedding_model", None):
                model_kwargs["embedding_model"] = bertopic_cfg.embedding_model
            if getattr(bertopic_cfg, "min_topic_size", None):
                model_kwargs["min_topic_size"] = bertopic_cfg.min_topic_size
            nr_topics = getattr(bertopic_cfg, "nr_topics", None)
            if isinstance(nr_topics, str):
                if nr_topics.isdigit():
                    model_kwargs["nr_topics"] = int(nr_topics)
                elif nr_topics:
                    model_kwargs["nr_topics"] = nr_topics
            elif isinstance(nr_topics, int):
                model_kwargs["nr_topics"] = nr_topics
            if getattr(bertopic_cfg, "top_n_words", None):
                model_kwargs["top_n_words"] = bertopic_cfg.top_n_words
            if getattr(bertopic_cfg, "calculate_probabilities", None):
                model_kwargs["calculate_probabilities"] = True

        BERTopic = bertopic_module.BERTopic
        model = BERTopic(**model_kwargs)
        topic_assignments, topic_probs = model.fit_transform(texts)

        doc_extra_fields = [
            {"segment_index": int(segment_index)} for segment_index in segment_indices
        ]
        topics = build_topic_objects(
            model,
            top_n_words=(
                getattr(bertopic_cfg, "top_n_words", 10) if bertopic_cfg else 10
            ),
            label_words=getattr(bertopic_cfg, "label_words", 3) if bertopic_cfg else 3,
            include_outlier=any(int(t) == -1 for t in topic_assignments),
        )
        doc_topic_data, meta = build_doc_topic_data(
            topic_assignments=topic_assignments,
            topic_probs=topic_probs,
            texts=texts,
            speaker_labels=speaker_labels,
            time_labels=time_labels,
            doc_extra_fields=doc_extra_fields,
        )

        meta.setdefault("texts_count", len(texts))
        return {
            "topics": topics,
            "doc_topic_data": doc_topic_data,
            "meta": meta,
            "error": None,
        }

    def _save_results(self, results: Dict[str, Any], output_service) -> None:
        """
        Save results using OutputService.
        """
        if results.get("error"):
            error_payload = {
                "error": results.get("error"),
                "message": results.get("message"),
                "meta": results.get("meta", {}),
            }
            output_service.save_data(
                error_payload, "bertopic_error", format_type="json"
            )
            return

        topics = results.get("topics", [])
        doc_topic_data = results.get("doc_topic_data", [])
        meta = results.get("meta", {})

        output_service.save_data(topics, "bertopic_topics", format_type="json")
        output_service.save_data(
            doc_topic_data, "bertopic_doc_topics", format_type="json"
        )
        if meta:
            output_service.save_data(meta, "bertopic_meta", format_type="json")

        try:
            self._create_charts(topics, doc_topic_data, output_service)
        except Exception as exc:
            self.logger.warning(f"[BERTopic] Could not create charts: {exc}")

    def _create_charts(
        self,
        topics: List[Dict[str, Any]],
        doc_topic_data: List[Dict[str, Any]],
        output_service,
    ) -> None:
        topics_filtered = [
            topic for topic in topics if int(topic.get("topic_id", -1)) != -1
        ]
        if not topics_filtered:
            return

        config = get_config()
        bertopic_cfg = getattr(config.analysis, "bertopic", None)
        top_n_words = getattr(bertopic_cfg, "top_n_words", 10) if bertopic_cfg else 10

        first_words = topics_filtered[0].get("words") or []
        if not first_words:
            return
        top_n_words = min(top_n_words, len(first_words))
        word_labels = list(first_words[:top_n_words])

        topic_word_matrix: List[List[float]] = []
        y_labels: List[str] = []
        for topic in topics_filtered:
            words = topic.get("words") or []
            weights = topic.get("weights") or []
            weight_map = {w: float(v) for w, v in zip(words, weights, strict=False)}
            topic_word_matrix.append([weight_map.get(w, 0.0) for w in word_labels])
            label = topic.get("label") or f"Topic {topic.get('topic_id')}"
            y_labels.append(f"T{int(topic.get('topic_id', 0))}: {label}")

        heatmap_spec = HeatmapMatrixSpec(
            viz_id="bertopic.topic_word_heatmap.global",
            module="bertopic",
            name="bertopic_topic_word_heatmap",
            scope="global",
            chart_intent="heatmap_matrix",
            title="BERTopic Topic-Word Heatmap",
            x_label="Words",
            y_label="Topics",
            z=topic_word_matrix,
            x_labels=word_labels,
            y_labels=y_labels,
        )
        output_service.save_chart(heatmap_spec, chart_type="heatmap")

        counts = Counter(
            int(row.get("dominant_topic", -1))
            for row in doc_topic_data
            if int(row.get("dominant_topic", -1)) != -1
        )
        total = sum(counts.values())
        if total <= 0:
            return
        topic_labels = {
            int(topic.get("topic_id")): topic.get(
                "label", f"Topic {topic.get('topic_id')}"
            )
            for topic in topics_filtered
        }
        categories = []
        values = []
        for topic_id, count in counts.most_common():
            categories.append(topic_labels.get(topic_id, f"Topic {topic_id}"))
            values.append(count / total if total else 0.0)

        bar_spec = BarCategoricalSpec(
            viz_id="bertopic.topic_prevalence.global",
            module="bertopic",
            name="bertopic_topic_prevalence",
            scope="global",
            chart_intent="bar_categorical",
            title="BERTopic Topic Prevalence",
            x_label="Topics",
            y_label="Share",
            categories=categories,
            values=values,
        )
        output_service.save_chart(bar_spec, chart_type="bar")
