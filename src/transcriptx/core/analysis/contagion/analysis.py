"""
Emotional contagion detection analysis module.

Branch contract (frozen): lexical branch reads only nrc_emotion produced by
the `emotion` module; contextual branch reads context_emotion_* only when the
contextual_emotion optional-producer contract is satisfied AND segments carry
context_emotion_source == 'contextual_emotion'. Branches are never blended;
both may be emitted as separately named subresults when each is usable.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.emotion_family.consumer_contracts import (
    CONTEXTUAL_EMOTION_FOR_CONTAGION,
    LEXICAL_EMOTION_FOR_CONTAGION,
    OptionalProducerEvaluation,
    evaluate_optional_producer,
    merge_contextual_projection,
)
from transcriptx.core.utils.logger import get_logger

from .detection import build_emotion_timeline, detect_contagion
from .emotion_merger import merge_lexical_emotion
from .visualization import create_contagion_matrix

logger = get_logger()


def _segments_have_contextual_branch(segments: List[Dict[str, Any]]) -> bool:
    """Usable contextual signals only — abstained/empty labels are not evidence."""
    for seg in segments:
        if seg.get("context_emotion_source") != "contextual_emotion":
            continue
        outcome = seg.get("contextual_emotion_analytical_outcome")
        if outcome == "abstained":
            continue
        label = (
            seg.get("contextual_emotion_label")
            or seg.get("context_emotion_primary")
            or seg.get("context_emotion")
        )
        if label:
            return True
        if outcome in {"neutral", "labeled"}:
            return True
    return False


def _producer_selected(
    *,
    module_id: str,
    selected_modules: Optional[List[str]],
    explicit: Optional[bool],
    artifact: Optional[Dict[str, Any]],
) -> bool:
    """Resolve selection from planner metadata; never from artifact presence alone."""
    if explicit is not None:
        return bool(explicit)
    if isinstance(selected_modules, (list, tuple, set)):
        return module_id in selected_modules
    # Standalone/analyze without planner metadata: selected only when artifact given.
    return artifact is not None


def _segments_have_lexical_branch(segments: List[Dict[str, Any]]) -> bool:
    for seg in segments:
        nrc = seg.get("nrc_emotion")
        if isinstance(nrc, dict) and any(
            isinstance(v, (int, float)) and v > 0 for v in nrc.values()
        ):
            return True
    return False


def _lexical_artifact_usable(emotion_data: Optional[Dict[str, Any]]) -> bool:
    """Gate lexical artifact via the frozen producer contract."""
    if not isinstance(emotion_data, dict):
        return False
    evaluation = evaluate_optional_producer(
        LEXICAL_EMOTION_FOR_CONTAGION,
        selected=True,
        artifact=emotion_data,
    )
    return bool(evaluation.satisfied)


def _run_branch(segments: List[Dict[str, Any]], emotion_type: str) -> Dict[str, Any]:
    speaker_emotions, timeline = build_emotion_timeline(segments, emotion_type)
    contagion_events, contagion_counts, contagion_summary = detect_contagion(timeline)
    return {
        "contagion_events": contagion_events,
        "contagion_counts": contagion_counts,
        "contagion_summary": contagion_summary,
        "emotion_type": emotion_type,
        "timeline": timeline,
        "speaker_emotions": speaker_emotions,
    }


class ContagionAnalysis(AnalysisModule):
    """Emotional contagion detection module."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "contagion"

    def _resolve_branches(
        self,
        segments: List[Dict[str, Any]],
        emotion_data: Optional[Dict[str, Any]],
        contextual_emotion_data: Optional[Dict[str, Any]],
        *,
        contextual_selected: Optional[bool] = None,
        selected_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve lexical and contextual branches independently.

        Never contextual-first overwrite: each branch is evaluated on its own
        contract and may both be present in the result.
        """
        selected = _producer_selected(
            module_id="contextual_emotion",
            selected_modules=selected_modules,
            explicit=contextual_selected,
            artifact=contextual_emotion_data,
        )
        contextual_eval: OptionalProducerEvaluation = evaluate_optional_producer(
            CONTEXTUAL_EMOTION_FOR_CONTAGION,
            selected=selected,
            artifact=contextual_emotion_data,
        )

        decision: Dict[str, Any] = {
            "contextual": {
                "satisfied": contextual_eval.satisfied,
                "reason": contextual_eval.reason,
                "details": contextual_eval.details,
            },
            "lexical": {},
        }

        branches: Dict[str, Any] = {}

        if contextual_eval.satisfied:
            merged = merge_contextual_projection(segments, contextual_emotion_data)
            if _segments_have_contextual_branch(segments):
                decision["contextual"]["segments_with_projection"] = merged
                branches["contextual_emotion"] = _run_branch(
                    segments, "context_emotion"
                )
            else:
                decision["contextual"]["satisfied"] = False
                decision["contextual"]["reason"] = "dependency_not_applicable"
                decision["contextual"]["details"] = {
                    "projection_segments": merged,
                    "usable_signals": False,
                }

        if not _segments_have_lexical_branch(segments) and emotion_data:
            if _lexical_artifact_usable(emotion_data):
                source_segments = emotion_data.get("segments_with_emotion") or []
                merged = merge_lexical_emotion(segments, source_segments, logger)
                decision["lexical"]["merged_segments"] = merged
            else:
                decision["lexical"]["reason"] = "dependency_not_applicable"
                decision["lexical"]["details"] = {
                    "run_status": emotion_data.get("run_status"),
                    "usable_output": emotion_data.get("usable_output"),
                }

        if _segments_have_lexical_branch(segments):
            decision["lexical"]["satisfied"] = True
            branches["lexical_emotion"] = _run_branch(segments, "nrc_emotion")
        else:
            decision["lexical"].setdefault("satisfied", False)
            decision["lexical"].setdefault("reason", "dependency_failed")

        return {"branches": branches, "branch_decision": decision}

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        emotion_data: Dict[str, Any] = None,
        contextual_emotion_data: Dict[str, Any] = None,
        *,
        contextual_selected: Optional[bool] = None,
        selected_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        resolved = self._resolve_branches(
            segments,
            emotion_data,
            contextual_emotion_data,
            contextual_selected=contextual_selected,
            selected_modules=selected_modules,
        )
        branches = resolved["branches"]
        branch_decision = resolved["branch_decision"]

        if not branches:
            reason = "no_usable_emotion_signals"
            logger.info(
                "[CONTAGION] Skipping: no usable lexical or contextual emotion signals. "
                f"Branch decision: {branch_decision}"
            )
            return {
                "run_status": "not_applicable",
                "usable_output": False,
                "skip_reason": reason,
                "contagion_events": [],
                "contagion_counts": [],
                "contagion_summary": {
                    "total_events": 0,
                    "skip_reason": reason,
                },
                "emotion_type": None,
                "branch_decision": branch_decision,
                "timeline": [],
                "speaker_emotions": {},
                "branches": {},
                "primary_branch": None,
                "warnings": [
                    "No usable emotion signals for contagion; "
                    "run emotion and/or contextual_emotion with labeled outcomes."
                ],
            }

        # Prefer lexical as the primary top-level view for backward compat when
        # both exist; both full subresults are always under `branches`.
        primary_key = (
            "lexical_emotion" if "lexical_emotion" in branches else next(iter(branches))
        )
        primary = branches[primary_key]
        logger.debug(
            f"[CONTAGION] Branches active: {list(branches.keys())}; "
            f"primary={primary_key}"
        )

        return {
            "run_status": "complete",
            "usable_output": True,
            "contagion_events": primary["contagion_events"],
            "contagion_counts": primary["contagion_counts"],
            "contagion_summary": primary["contagion_summary"],
            "emotion_type": primary["emotion_type"],
            "branch_decision": branch_decision,
            "timeline": primary["timeline"],
            "speaker_emotions": primary["speaker_emotions"],
            "branches": branches,
            "primary_branch": primary_key,
        }

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_start,
                log_analysis_complete,
                log_analysis_error,
            )

            log_analysis_start(self.module_name, context.transcript_path)
            segments = context.get_segments()
            logger.debug(f"[CONTAGION] Loaded {len(segments)} segments from context")

            emotion_result = context.get_analysis_result("emotion")
            contextual_result = context.get_analysis_result("contextual_emotion")
            selected_modules = None
            getter = getattr(context, "get_computed_value", None)
            if callable(getter):
                selected_modules = getter("selected_modules")
            if not isinstance(selected_modules, list):
                selected_modules = None

            if emotion_result and isinstance(emotion_result, dict):
                segments_with_emotion = emotion_result.get("segments_with_emotion", [])
                sample_seg = segments_with_emotion[0] if segments_with_emotion else {}
                if segments_with_emotion and "nrc_emotion" not in sample_seg:
                    from transcriptx.core.utils._path_core import (
                        find_enriched_transcript,
                    )
                    from transcriptx.io.transcript_loader import load_transcript

                    enriched_path = find_enriched_transcript(
                        context.transcript_path, "emotion"
                    )
                    if enriched_path:
                        try:
                            enriched_data = load_transcript(enriched_path)
                            enriched_segments = None
                            if (
                                isinstance(enriched_data, dict)
                                and "segments" in enriched_data
                            ):
                                enriched_segments = enriched_data["segments"]
                            elif isinstance(enriched_data, list):
                                enriched_segments = enriched_data
                            if enriched_segments:
                                emotion_result["segments_with_emotion"] = (
                                    enriched_segments
                                )
                        except Exception as exc:
                            logger.warning(
                                f"[CONTAGION] Failed to load enriched transcript: {exc}"
                            )

            if not emotion_result:
                logger.warning(
                    "[CONTAGION] No emotion_result found in context. "
                    "Emotion analysis may not have run or completed."
                )

            results = self.analyze(
                segments,
                emotion_data=(
                    emotion_result if isinstance(emotion_result, dict) else None
                ),
                contextual_emotion_data=(
                    contextual_result if isinstance(contextual_result, dict) else None
                ),
                selected_modules=selected_modules,
            )

            from transcriptx.core.output.output_service import create_output_service

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

            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "success",
                "results": results,
                "output_directory": str(
                    output_service.get_output_structure().module_dir
                ),
            }

        except Exception as exc:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(exc),
                "results": {},
            }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        if str(results.get("run_status") or "") in {"not_applicable", "skipped"}:
            output_service.save_data(
                {
                    "run_status": results.get("run_status"),
                    "skip_reason": results.get("skip_reason"),
                    "branch_decision": results.get("branch_decision"),
                    "warnings": results.get("warnings"),
                },
                "contagion_summary",
                format_type="json",
            )
            output_service.save_summary(
                {
                    "total_contagion_events": 0,
                    "run_status": results.get("run_status"),
                    "skip_reason": results.get("skip_reason"),
                },
                {},
                analysis_metadata={},
            )
            return

        contagion_events = results.get("contagion_events") or []
        contagion_summary = results.get("contagion_summary") or {}
        output_service.get_output_structure()

        output_service.save_data(
            contagion_events, "contagion_events", format_type="json"
        )
        output_service.save_data(
            contagion_summary, "contagion_summary", format_type="json"
        )

        branches = results.get("branches") or {}
        if branches:
            output_service.save_data(branches, "contagion_branches", format_type="json")

        branch_name = (
            "contextual (contextual_emotion classifier)"
            if results.get("emotion_type") == "context_emotion"
            else "lexical (NRC vocabulary association)"
        )
        summary_text = "Emotional Contagion Analysis Results:\n\n"
        summary_text += f"Total contagion events detected: {len(contagion_events)}\n"
        summary_text += f"Primary emotion branch analyzed: {branch_name}\n"
        summary_text += f"Active branches: {', '.join(branches.keys()) or 'none'}\n\n"

        contagion_counts = results.get("contagion_counts", [])
        if contagion_events:
            summary_text += "Top contagion patterns:\n"
            if isinstance(contagion_counts, list):
                ranked = sorted(
                    (item for item in contagion_counts if isinstance(item, dict)),
                    key=lambda item: (
                        -int(item.get("count") or 0),
                        item.get("actor") or "",
                        item.get("target") or "",
                        item.get("emotion") or "",
                    ),
                )[:5]
                for item in ranked:
                    summary_text += (
                        f"• {item.get('actor')} → {item.get('target')} "
                        f"({item.get('emotion')}): {item.get('count')} times\n"
                    )
            else:
                # Legacy tuple-keyed map (tests / older in-memory shapes).
                top_patterns = Counter(contagion_counts).most_common(5)
                for (from_spk, to_spk, emo), count in top_patterns:
                    summary_text += f"• {from_spk} → {to_spk} ({emo}): {count} times\n"
        else:
            summary_text += "No significant emotional contagion patterns detected.\n"

        output_service.save_data(summary_text, "contagion_summary", format_type="txt")
        create_contagion_matrix(results, output_service)

        global_stats = {
            "total_contagion_events": len(contagion_events),
            "emotion_type": results.get("emotion_type", "unknown"),
            "primary_branch": results.get("primary_branch"),
            "active_branches": list(branches.keys()),
            "branch_decision": results.get("branch_decision", {}),
        }
        output_service.save_summary(global_stats, {}, analysis_metadata={})
