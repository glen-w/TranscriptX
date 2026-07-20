"""
BERTopic analysis module.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.bertopic.deps import (
    EXTRA_NAME,
    embedding_model_policy_check,
    verify_bertopic_import,
)
from transcriptx.core.analysis.bertopic.eligibility import (
    evaluate_bertopic_eligibility,
)
from transcriptx.core.analysis.bertopic.runtime import (
    build_model_kwargs,
    build_provenance,
)
from transcriptx.core.utils.native_threads import limited_native_threads
from transcriptx.core.analysis.bertopic.schema import (
    SCHEMA_VERSION,
    attach_schema_version,
)
from transcriptx.core.analysis.topic_modeling.utils import prepare_text_data
from transcriptx.core.pipeline.contracts import ErrorKind
from transcriptx.core.pipeline.optional_dep_outcomes import (
    build_optional_dep_blocked_result,
    install_hint_for_extra,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.module_result import (
    build_module_result,
    capture_exception,
    now_iso,
)
from transcriptx.core.utils.nlp_utils import (
    has_meaningful_content,
    preprocess_for_topic_modeling,
)
from transcriptx.core.viz.specs import BarCategoricalSpec, HeatmapMatrixSpec

from .utils import build_doc_topic_data, build_topic_objects


class BERTopicAnalysis(AnalysisModule):
    """Topic modeling analysis module using BERTopic."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "bertopic"
        self.logger = get_logger()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] | None = None
    ) -> Dict[str, Any]:
        """
        Perform BERTopic analysis on transcript segments (pure logic, no I/O).

        Documents are ordered by segment_index ascending (from prepare_text_data).
        Duplicate texts are retained as separate documents (no pre-fit dedup).
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
                "meta": attach_schema_version(
                    {
                        "total_segments": total_segments,
                        "meaningful_segments_after_preprocessing": meaningful_count,
                        "reason": (
                            "All segments were filtered out during preprocessing "
                            "(likely too short or contain only stopwords/tics after "
                            "content word filtering)"
                        ),
                        "fit_scope": "transcript",
                    }
                ),
            }

        eligibility = evaluate_bertopic_eligibility(texts)
        if not eligibility.eligible:
            return {
                "error": (
                    "Need at least 3 text segments for BERTopic analysis, "
                    f"but only {eligibility.documents_count} segment(s) found "
                    "after preprocessing"
                    if eligibility.reason == "insufficient_documents"
                    else f"BERTopic eligibility failed: {eligibility.reason}"
                ),
                "topics": [],
                "doc_topic_data": [],
                "meta": attach_schema_version(
                    {
                        "texts_count": eligibility.documents_count,
                        "total_chars": eligibility.total_chars,
                        "reason": eligibility.reason,
                        "fit_scope": "transcript",
                    }
                ),
            }

        bertopic_module, dep_reason = verify_bertopic_import(auto_install=False)
        if bertopic_module is None:
            return {
                "error": dep_reason or f"missing_extra:{EXTRA_NAME}",
                "topics": [],
                "doc_topic_data": [],
                "meta": attach_schema_version(
                    {
                        "reason": dep_reason,
                        "fit_scope": "transcript",
                        "blocked": True,
                    }
                ),
            }

        config = get_config()
        bertopic_cfg = getattr(config.analysis, "bertopic", None)
        embedding_model = (
            getattr(bertopic_cfg, "embedding_model", None) if bertopic_cfg else None
        )
        policy_reason = embedding_model_policy_check(str(embedding_model or ""))
        if policy_reason:
            return {
                "error": policy_reason,
                "topics": [],
                "doc_topic_data": [],
                "meta": attach_schema_version(
                    {
                        "reason": policy_reason,
                        "fit_scope": "transcript",
                        "blocked": True,
                    }
                ),
            }

        model_kwargs = build_model_kwargs(bertopic_cfg)
        started = time.perf_counter()
        try:
            BERTopic = bertopic_module.BERTopic
            with limited_native_threads(1):
                model = BERTopic(**model_kwargs)
                topic_assignments, topic_probs = model.fit_transform(texts)
        except ImportError as exc:
            return {
                "error": f"broken_extra:{EXTRA_NAME}",
                "message": str(exc),
                "topics": [],
                "doc_topic_data": [],
                "meta": attach_schema_version(
                    {
                        "reason": f"broken_extra:{EXTRA_NAME}",
                        "fit_scope": "transcript",
                        "blocked": True,
                    }
                ),
            }
        except Exception as exc:
            # Tiny corpora can collapse to zero non-outlier samples during
            # BERTopic auto-reduce (HDBSCAN/sklearn). Soft-fail like eligibility.
            msg = str(exc)
            soft = (
                "0 sample" in msg
                or "minimum of 1 is required" in msg
                or "n_samples=0" in msg
            )
            if soft:
                return {
                    "error": "insufficient_data_after_fit",
                    "message": msg,
                    "topics": [],
                    "doc_topic_data": [],
                    "meta": attach_schema_version(
                        {
                            "texts_count": len(texts),
                            "reason": "insufficient_data_after_fit",
                            "fit_scope": "transcript",
                            "fit_error": msg,
                        }
                    ),
                }
            raise

        duration = time.perf_counter() - started
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
        meta["fit_scope"] = "transcript"
        meta["schema_version"] = SCHEMA_VERSION
        package_version: Optional[str] = None
        try:
            import importlib.metadata as im

            package_version = im.version("bertopic")
        except Exception:
            package_version = None
        meta["provenance"] = build_provenance(
            embedding_model=embedding_model,
            fit_scope="transcript",
            duration_seconds=duration,
            package_version=package_version,
        )
        return {
            "topics": topics,
            "doc_topic_data": doc_topic_data,
            "meta": meta,
            "error": None,
        }

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        """Run with optional-extra blocked outcomes (no auto-install)."""
        from transcriptx.core.output.output_service import create_output_service
        from transcriptx.core.utils.logger import (
            log_analysis_complete,
            log_analysis_error,
            log_analysis_start,
        )

        started_at = now_iso()
        start_time = time.time()
        try:
            log_analysis_start(self.module_name, context.transcript_path)
            segments = context.get_segments()
            if not self.validate_input(segments):
                raise ValueError(f"Invalid input segments for {self.module_name}")

            results = self.analyze(segments)
            meta = results.get("meta") or {}
            reason = meta.get("reason") or results.get("error")
            if meta.get("blocked") and isinstance(reason, str):
                error_kind = (
                    ErrorKind.CONFIG
                    if reason.startswith("config:")
                    or reason.startswith("model_unavailable:")
                    else ErrorKind.DEPENDENCY
                )
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_optional_dep_blocked_result(
                    module_name=self.module_name,
                    reason=reason,
                    error_kind=error_kind,
                    started_at=started_at,
                    finished_at=now_iso(),
                    install_hint=install_hint_for_extra(EXTRA_NAME),
                    extra_metrics={"fit_scope": "transcript"},
                )

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)
            context.store_analysis_result(self.module_name, results)
            log_analysis_complete(self.module_name, context.transcript_path)
            finished_at = now_iso()
            duration_seconds = time.time() - start_time
            output_structure = output_service.get_output_structure()
            if hasattr(output_structure, "module_dir"):
                output_directory = str(output_structure.module_dir)
            elif isinstance(output_structure, dict):
                output_directory = str(output_structure.get("module_dir", ""))
            else:
                output_directory = ""
            module_result = build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=output_service.get_artifacts(),
                metrics={
                    "duration_seconds": duration_seconds,
                    "output_directory": output_directory,
                    "all_outlier": bool(meta.get("all_outlier")),
                    "schema_version": SCHEMA_VERSION,
                },
                payload_type="analysis_results",
                payload=results,
            )
            module_result["output_directory"] = output_directory
            return module_result
        except Exception as e:
            log_analysis_error(self.module_name, context.transcript_path, str(e))
            if isinstance(e, ValueError):
                raise
            finished_at = now_iso()
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=[],
                metrics={
                    "duration_seconds": time.time() - start_time,
                    "error_kind": ErrorKind.INTERNAL.value,
                },
                payload_type="analysis_results",
                payload={},
                error=capture_exception(e),
            )

    def _save_results(self, results: Dict[str, Any], output_service) -> None:
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
        # Fail-closed: emit no chart specification when only outliers / empty.
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
