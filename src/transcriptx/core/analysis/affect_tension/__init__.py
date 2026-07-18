"""
Affect–tension analysis: combines emotion and sentiment to detect mismatches,
entropy, volatility, and derived indices (polite tension, suppressed conflict,
tone–affect delta).
"""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.affect_tension.metrics import (
    affect_mismatch_posneg,
    affect_trust_neutral,
    emotion_entropy,
    emotion_volatility_proxy,
    trust_like_score,
    compute_derived_indices,
)
from transcriptx.core.analysis.emotion_family.consumer_contracts import (
    CONTEXTUAL_EMOTION_FOR_AFFECT_TENSION,
    evaluate_optional_producer,
    merge_contextual_projection,
)
from transcriptx.core.analysis.emotion_family.generational_store import (
    scores_by_segment_from_rows,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import (
    get_logger,
    log_analysis_start,
    log_analysis_complete,
)
from transcriptx.utils.text_utils import is_named_speaker

logger = get_logger()

AFFECT_TENSION_VERSION = "1.0.0"


def _contextual_scores_index(
    contextual_emotion_data: Dict[str, Any] | None,
    *,
    producer_module_dir: Any | None = None,
) -> tuple[dict[str, dict[str, float]], str | None]:
    """
    Load score vectors from validated canonical store authority only.

    Never falls back to unvalidated disk rows or in-memory write buffers.
    Returns (scores_by_segment, disable_reason).
    """
    if not isinstance(contextual_emotion_data, dict):
        return {}, "canonical_unavailable"
    generation_id = str(contextual_emotion_data.get("artifact_generation_id") or "")
    if not producer_module_dir or not generation_id:
        return {}, "canonical_unavailable"
    try:
        from transcriptx.core.analysis.emotion_family.generational_store import (
            validate_generation_integrity,
        )

        rows, manifest = validate_generation_integrity(
            producer_module_dir, generation_id
        )
        expected_module = contextual_emotion_data.get("module_id")
        if expected_module and manifest.get("module_id") != expected_module:
            return {}, "canonical_integrity_failed"
        expected_schema = contextual_emotion_data.get("schema_version")
        if expected_schema and manifest.get("schema_version") != expected_schema:
            return {}, "canonical_integrity_failed"
        expected_semantics = contextual_emotion_data.get("semantics_version")
        if (
            expected_semantics
            and manifest.get("semantics_version") != expected_semantics
        ):
            return {}, "canonical_integrity_failed"
        return scores_by_segment_from_rows(rows), None
    except Exception as exc:
        logger.warning(
            "affect_tension: canonical integrity failed for %s: %s",
            generation_id,
            exc,
        )
        return {}, "canonical_integrity_failed"


def _segment_eligible_for_contextual_metrics(seg: Dict[str, Any]) -> bool:
    """
    Abstained segments are ineligible.
    Neutral is eligible only when analytical_outcome is scored neutral.
    Labeled requires a non-empty primary/label.
    """
    if seg.get("context_emotion_source") != "contextual_emotion":
        return False
    outcome = seg.get("contextual_emotion_analytical_outcome")
    if outcome == "abstained":
        return False
    if outcome == "neutral":
        return True
    if outcome == "labeled":
        primary = seg.get("context_emotion_primary") or seg.get(
            "contextual_emotion_label"
        )
        return bool(primary)
    return False


def _producer_selected(
    *,
    selected_modules: list[str] | None,
    explicit: bool | None,
    artifact: Dict[str, Any] | None,
) -> bool:
    if explicit is not None:
        return bool(explicit)
    if isinstance(selected_modules, (list, tuple, set)):
        return "contextual_emotion" in selected_modules
    return artifact is not None


class AffectTensionAnalysis(AnalysisModule):
    """
    Combines emotion and sentiment to compute mismatch flags, emotion entropy,
    volatility proxy, and derived indices. Hard-depends on emotion and sentiment;
    optionally consumes contextual_emotion when the producer contract is satisfied
    (registry optional_dependencies). Classifier-derived metrics are nullable when
    contextual evidence is absent.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "affect_tension"

    def get_dependencies(self) -> List[str]:
        # Hard deps only; contextual_emotion is optional via registry planner.
        return ["emotion", "sentiment"]

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        contextual_emotion_data: Dict[str, Any] | None = None,
        *,
        contextual_module_dir: Any | None = None,
        contextual_selected: bool | None = None,
        selected_modules: list[str] | None = None,
    ) -> Dict[str, Any]:
        """Pure logic: compute per-segment metrics and derived indices."""
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        selected = _producer_selected(
            selected_modules=selected_modules,
            explicit=contextual_selected,
            artifact=contextual_emotion_data,
        )
        contextual_eval = evaluate_optional_producer(
            CONTEXTUAL_EMOTION_FOR_AFFECT_TENSION,
            selected=selected,
            artifact=contextual_emotion_data,
        )
        contextual_allowed = contextual_eval.satisfied
        scores_by_sid: dict[str, dict[str, float]] = {}
        canonical_disable_reason: str | None = None
        if contextual_allowed:
            merge_contextual_projection(segments, contextual_emotion_data)
            scores_by_sid, canonical_disable_reason = _contextual_scores_index(
                contextual_emotion_data,
                producer_module_dir=contextual_module_dir,
            )

        cfg = get_config().analysis
        at_cfg = getattr(cfg, "affect_tension", None)
        if at_cfg is None:
            mismatch_compound = -0.1
            trust_like_th = 0.3
            pos_emotion_th = 0.3
            weights = {
                "weight_posneg_mismatch": 0.4,
                "weight_trust_neutral": 0.3,
                "weight_entropy": 0.15,
                "weight_volatility": 0.15,
            }
        else:
            mismatch_compound = getattr(at_cfg, "mismatch_compound_threshold", -0.1)
            trust_like_th = getattr(at_cfg, "trust_like_threshold", 0.3)
            pos_emotion_th = getattr(at_cfg, "pos_emotion_threshold", 0.3)
            weights = {
                "weight_posneg_mismatch": getattr(
                    at_cfg, "weight_posneg_mismatch", 0.4
                ),
                "weight_trust_neutral": getattr(at_cfg, "weight_trust_neutral", 0.3),
                "weight_entropy": getattr(at_cfg, "weight_entropy", 0.15),
                "weight_volatility": getattr(at_cfg, "weight_volatility", 0.15),
            }
        thresholds = {
            "mismatch_compound_threshold": mismatch_compound,
            "trust_like_threshold": trust_like_th,
            "pos_emotion_threshold": pos_emotion_th,
        }

        primary_labels = []
        for seg in segments:
            if contextual_allowed and _segment_eligible_for_contextual_metrics(seg):
                primary_labels.append(seg.get("context_emotion_primary") or "")
            else:
                primary_labels.append("")
        speaker_segment_indexes: Dict[str, List[int]] = {}
        excluded_count = 0
        contextual_branch_segments = 0
        skipped_metrics_reasons: Dict[str, int] = {}

        for idx, seg in enumerate(segments):
            compound = seg.get("sentiment_compound_norm")
            if compound is None:
                compound = seg.get("sentiment", {}).get("compound", 0.0)

            scores: Dict[str, float] | None = None
            metric_reason: str | None = None
            if not contextual_allowed:
                metric_reason = contextual_eval.reason or "contextual_not_available"
            elif not _segment_eligible_for_contextual_metrics(seg):
                outcome = seg.get("contextual_emotion_analytical_outcome")
                if outcome == "abstained":
                    metric_reason = "abstained_ineligible"
                elif seg.get("context_emotion_source") != "contextual_emotion":
                    metric_reason = "missing_contextual_provenance"
                else:
                    metric_reason = "ineligible_outcome"
            else:
                sid = str(seg.get("id") or seg.get("segment_id") or "")
                scores = scores_by_sid.get(sid)
                if not scores:
                    metric_reason = (
                        canonical_disable_reason or "canonical_scores_unavailable"
                    )
                else:
                    contextual_branch_segments += 1

            if scores is None:
                seg["affect_mismatch_posneg"] = None
                seg["affect_trust_neutral"] = None
                seg["emotion_entropy"] = None
                seg["emotion_volatility_proxy"] = None
                seg["affect_contextual_metrics_status"] = "skipped"
                seg["affect_contextual_metrics_reason"] = metric_reason
                skipped_metrics_reasons[metric_reason or "unknown"] = (
                    skipped_metrics_reasons.get(metric_reason or "unknown", 0) + 1
                )
            else:
                trust = trust_like_score(scores)
                seg["affect_mismatch_posneg"] = affect_mismatch_posneg(
                    compound, scores, pos_emotion_th, mismatch_compound
                )
                tn = affect_trust_neutral(compound, trust, trust_like_th)
                seg["affect_trust_neutral"] = tn
                ent = emotion_entropy(scores)
                seg["emotion_entropy"] = ent
                vol = emotion_volatility_proxy(idx, primary_labels, 5)
                seg["emotion_volatility_proxy"] = vol
                seg["affect_contextual_metrics_status"] = "computed"
                seg["affect_contextual_metrics_reason"] = None

            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                excluded_count += 1
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )
            if not speaker or not is_named_speaker(speaker):
                excluded_count += 1
                continue
            speaker_segment_indexes.setdefault(speaker, []).append(idx)

        # Derived indices only use segments that have computed contextual metrics;
        # compute_derived_indices still reads scores from segments — attach a
        # temporary private key for eligible segments only.
        for seg in segments:
            if seg.get("affect_contextual_metrics_status") == "computed":
                sid = str(seg.get("id") or seg.get("segment_id") or "")
                seg["_affect_scores"] = scores_by_sid.get(sid) or {}
            else:
                seg["_affect_scores"] = None

        derived = compute_derived_indices(
            segments,
            speaker_segment_indexes,
            thresholds,
            weights,
            scores_key="_affect_scores",
        )

        for seg in segments:
            seg.pop("_affect_scores", None)

        metadata = {
            "version": AFFECT_TENSION_VERSION,
            "params": {
                "thresholds": thresholds,
                "weights": weights,
            },
            "excluded_unnamed_segments": excluded_count,
            "segments_analyzed": len(segments),
            "named_speakers": list(speaker_segment_indexes.keys()),
            "emotion_branches": {
                "contextual_emotion_segments": contextual_branch_segments,
                "contextual_contract": {
                    "satisfied": contextual_eval.satisfied,
                    "reason": contextual_eval.reason,
                    "details": contextual_eval.details,
                },
                "skipped_metrics_reasons": skipped_metrics_reasons,
                "note": (
                    "Classifier scores used only when the contextual_emotion "
                    "producer contract is satisfied, provenance is "
                    "context_emotion_source='contextual_emotion', the segment is "
                    "eligible (abstained excluded; neutral requires scored "
                    "neutral), and canonical score vectors are available. "
                    "Missing evidence yields null metrics with explicit reasons. "
                    "Lexical NRC is a separate branch and is not blended."
                ),
            },
        }

        return {
            "segments": segments,
            "derived_indices": derived,
            "metadata": metadata,
        }

    def _save_results(
        self,
        results: Dict[str, Any],
        output_service: Any,
    ) -> None:
        base_name = output_service.base_name
        metadata = results.get("metadata", {})
        payload = {
            "metadata": metadata,
            "derived_indices": results.get("derived_indices", {}),
        }
        output_service.save_data(
            payload,
            f"{base_name}_affect_tension",
            format_type="json",
        )
        segments = results.get("segments", [])
        if segments:
            rows = []
            for i, seg in enumerate(segments):
                rows.append(
                    {
                        "index": i,
                        "start": seg.get("start"),
                        "text": (seg.get("text") or "")[:200],
                        "affect_mismatch_posneg": seg.get("affect_mismatch_posneg"),
                        "affect_trust_neutral": seg.get("affect_trust_neutral"),
                        "emotion_entropy": seg.get("emotion_entropy"),
                        "emotion_volatility_proxy": seg.get("emotion_volatility_proxy"),
                        "context_emotion_primary": seg.get("context_emotion_primary"),
                        "affect_contextual_metrics_status": seg.get(
                            "affect_contextual_metrics_status"
                        ),
                        "affect_contextual_metrics_reason": seg.get(
                            "affect_contextual_metrics_reason"
                        ),
                        "sentiment_compound_norm": seg.get("sentiment_compound_norm"),
                    }
                )
            output_service.save_data(
                rows,
                f"{base_name}_affect_tension_segments",
                format_type="csv",
            )

        try:
            from transcriptx.core.analysis.affect_tension.output import (
                build_derived_indices_charts,
                build_dynamics_timeseries_charts,
                build_tension_summary_heatmap,
            )
        except Exception as e:
            logger.warning("affect_tension charts: failed to import helpers: %s", e)
            return

        derived_indices = results.get("derived_indices", {})
        chart_specs = []
        try:
            chart_specs.extend(
                build_derived_indices_charts(derived_indices, segments, base_name)
            )
        except Exception as e:
            logger.warning("affect_tension charts: failed to build bar specs: %s", e)
        try:
            chart_specs.extend(build_dynamics_timeseries_charts(segments, base_name))
        except Exception as e:
            logger.warning(
                "affect_tension charts: failed to build timeseries specs: %s", e
            )
        try:
            heatmap = build_tension_summary_heatmap(
                derived_indices, segments, base_name
            )
            if heatmap:
                chart_specs.append(heatmap)
        except Exception as e:
            logger.warning("affect_tension charts: failed to build heatmap spec: %s", e)

        for spec in chart_specs:
            try:
                output_service.save_chart(spec)
            except Exception as e:
                logger.warning("affect_tension charts: failed to save chart: %s", e)

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        from transcriptx.core.utils.module_result import (
            build_module_result,
            now_iso,
        )
        from transcriptx.core.output.output_service import create_output_service

        started_at = now_iso()
        try:
            log_analysis_start(self.module_name, context.transcript_path)
            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            segments = context.get_segments()
            if not segments:
                payload = {
                    "metadata": {
                        "version": AFFECT_TENSION_VERSION,
                        "skipped": "no_segments",
                    },
                    "derived_indices": {"global": {}, "by_speaker": {}},
                }
                output_service.save_data(
                    payload,
                    f"{output_service.base_name}_affect_tension",
                    format_type="json",
                )
                context.store_analysis_result(self.module_name, payload)
                log_analysis_complete(self.module_name, context.transcript_path)
                return build_module_result(
                    module_name=self.module_name,
                    status="success",
                    started_at=started_at,
                    finished_at=now_iso(),
                    artifacts=output_service.get_artifacts(),
                    payload_type="analysis_results",
                    payload=payload,
                )
            contextual_result = context.get_analysis_result("contextual_emotion")
            contextual_module_dir = None
            if isinstance(contextual_result, dict):
                try:
                    from transcriptx.core.output.output_service import (
                        create_output_service,
                    )

                    ctx_os = create_output_service(
                        context.transcript_path,
                        "contextual_emotion",
                        output_dir=context.get_transcript_dir(),
                        run_id=context.get_run_id(),
                        runtime_flags=context.get_runtime_flags(),
                    )
                    structure = ctx_os.get_output_structure()
                    contextual_module_dir = getattr(structure, "module_dir", None)
                    if contextual_module_dir is None and isinstance(structure, dict):
                        contextual_module_dir = structure.get("module_dir")
                except Exception as exc:
                    logger.debug(
                        "affect_tension: could not resolve contextual module_dir: %s",
                        exc,
                    )
            results = self.analyze(
                segments,
                contextual_emotion_data=(
                    contextual_result if isinstance(contextual_result, dict) else None
                ),
                contextual_module_dir=contextual_module_dir,
                selected_modules=(
                    context.get_computed_value("selected_modules")
                    if isinstance(context.get_computed_value("selected_modules"), list)
                    else None
                ),
            )
            self._save_results(results, output_service)
            context.store_analysis_result(self.module_name, results)
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=output_service.get_artifacts(),
                payload_type="analysis_results",
                payload=results,
            )
        except Exception as e:
            logger.exception("affect_tension failed: %s", e)
            from transcriptx.core.utils.module_result import (
                build_module_result,
                now_iso,
            )

            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=now_iso(),
                error=str(e),
            )
