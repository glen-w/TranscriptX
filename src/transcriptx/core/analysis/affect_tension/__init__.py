"""
Affect–tension analysis: combines emotion and sentiment to detect mismatches,
entropy, volatility, and derived indices (polite tension, suppressed conflict,
tone–affect delta).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.affect_tension.metrics import (
    affect_mismatch_posneg,
    affect_trust_neutral,
    emotion_entropy,
    emotion_volatility_proxy,
    trust_like_score,
    compute_derived_indices,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_analysis_start, log_analysis_complete
from transcriptx.utils.text_utils import is_named_speaker

logger = get_logger()

AFFECT_TENSION_VERSION = "1.0.0"


class AffectTensionAnalysis(AnalysisModule):
    """
    Combines emotion and sentiment to compute mismatch flags, emotion entropy,
    volatility proxy, and derived indices (polite tension, suppressed conflict,
    institutional tone vs affect delta). Depends on emotion and sentiment.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.module_name = "affect_tension"

    def get_dependencies(self) -> List[str]:
        return ["emotion", "sentiment"]

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Pure logic: compute per-segment metrics and derived indices."""
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
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
            mismatch_compound = getattr(
                at_cfg, "mismatch_compound_threshold", -0.1
            )
            trust_like_th = getattr(at_cfg, "trust_like_threshold", 0.3)
            pos_emotion_th = getattr(at_cfg, "pos_emotion_threshold", 0.3)
            weights = {
                "weight_posneg_mismatch": getattr(
                    at_cfg, "weight_posneg_mismatch", 0.4
                ),
                "weight_trust_neutral": getattr(
                    at_cfg, "weight_trust_neutral", 0.3
                ),
                "weight_entropy": getattr(at_cfg, "weight_entropy", 0.15),
                "weight_volatility": getattr(at_cfg, "weight_volatility", 0.15),
            }
        thresholds = {
            "mismatch_compound_threshold": mismatch_compound,
            "trust_like_threshold": trust_like_th,
            "pos_emotion_threshold": pos_emotion_th,
        }

        primary_labels = [
            seg.get("context_emotion_primary") or "" for seg in segments
        ]
        speaker_segment_indexes: Dict[str, List[int]] = {}
        excluded_count = 0

        for idx, seg in enumerate(segments):
            compound = seg.get("sentiment_compound_norm")
            if compound is None:
                compound = seg.get("sentiment", {}).get("compound", 0.0)
            scores = seg.get("context_emotion_scores") or {}
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

        derived = compute_derived_indices(
            segments,
            speaker_segment_indexes,
            thresholds,
            weights,
        )

        metadata = {
            "version": AFFECT_TENSION_VERSION,
            "params": {
                "thresholds": thresholds,
                "weights": weights,
            },
            "excluded_unnamed_segments": excluded_count,
            "segments_analyzed": len(segments),
            "named_speakers": list(speaker_segment_indexes.keys()),
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
                rows.append({
                    "index": i,
                    "start": seg.get("start"),
                    "text": (seg.get("text") or "")[:200],
                    "affect_mismatch_posneg": seg.get("affect_mismatch_posneg"),
                    "affect_trust_neutral": seg.get("affect_trust_neutral"),
                    "emotion_entropy": seg.get("emotion_entropy"),
                    "emotion_volatility_proxy": seg.get("emotion_volatility_proxy"),
                    "context_emotion_primary": seg.get("context_emotion_primary"),
                    "sentiment_compound_norm": seg.get("sentiment_compound_norm"),
                })
            output_service.save_data(
                rows,
                f"{base_name}_affect_tension_segments",
                format_type="csv",
            )

        # Charts (spec build and save guarded separately)
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
            chart_specs.extend(
                build_dynamics_timeseries_charts(segments, base_name)
            )
        except Exception as e:
            logger.warning("affect_tension charts: failed to build timeseries specs: %s", e)
        try:
            heatmap = build_tension_summary_heatmap(derived_indices, segments, base_name)
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
                    "metadata": {"version": AFFECT_TENSION_VERSION, "skipped": "no_segments"},
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
            results = self.analyze(segments, context.get_speaker_map())
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
            from transcriptx.core.utils.module_result import build_module_result, now_iso
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=now_iso(),
                error=str(e),
            )
