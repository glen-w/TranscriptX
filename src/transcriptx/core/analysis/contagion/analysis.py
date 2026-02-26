"""
Emotional contagion detection analysis module.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.logger import get_logger

from .detection import build_emotion_timeline, detect_contagion
from .emotion_merger import merge_emotion_data
from .emotion_reconstruction import reconstruct_emotion_data
from .visualization import create_contagion_matrix


logger = get_logger()


class ContagionAnalysis(AnalysisModule):
    """Emotional contagion detection module."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "contagion"

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        emotion_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        emotion_type = None
        emotion_found = False

        def check_emotion_data(segments_to_check, log_prefix=""):
            context_emotion_count = 0
            nrc_emotion_count = 0
            nrc_emotion_with_values = 0

            for seg in segments_to_check:
                if "context_emotion" in seg:
                    context_emotion_count += 1
                    if seg["context_emotion"]:
                        logger.debug(
                            f"{log_prefix}Found context_emotion in segment: {seg.get('start', 'unknown')}"
                        )
                        return "context_emotion", True

                if "nrc_emotion" in seg:
                    nrc_emotion_count += 1
                    nrc_data = seg.get("nrc_emotion", {})
                    if isinstance(nrc_data, dict) and nrc_data:
                        if any(v > 0 for v in nrc_data.values()):
                            nrc_emotion_with_values += 1
                            logger.debug(
                                f"{log_prefix}Found nrc_emotion with values > 0 in segment: {seg.get('start', 'unknown')}"
                            )
                            return "nrc_emotion", True
                        logger.debug(
                            f"{log_prefix}nrc_emotion dict exists but all values are 0 in segment: {seg.get('start', 'unknown')}"
                        )
                    elif nrc_data:
                        logger.debug(
                            f"{log_prefix}nrc_emotion exists but is not a dict in segment: {seg.get('start', 'unknown')}, type: {type(nrc_data)}"
                        )

            if log_prefix:
                logger.debug(
                    f"{log_prefix}No emotion data found. "
                    f"Segments checked: {len(segments_to_check)}, "
                    f"context_emotion fields: {context_emotion_count}, "
                    f"nrc_emotion fields: {nrc_emotion_count}, "
                    f"nrc_emotion with values>0: {nrc_emotion_with_values}"
                )

            return None, False

        emotion_type, emotion_found = check_emotion_data(
            segments, "[CONTAGION] Initial check: "
        )

        if not emotion_found:
            if emotion_data and isinstance(emotion_data, dict):
                segments_with_emotion = emotion_data.get("segments_with_emotion", [])
                logger.debug(
                    f"[CONTAGION] emotion_data provided. segments_with_emotion count: {len(segments_with_emotion) if segments_with_emotion else 0}"
                )

                if segments_with_emotion:
                    emotion_type_check, emotion_found_check = check_emotion_data(
                        segments_with_emotion,
                        "[CONTAGION] Checking segments_with_emotion: ",
                    )
                    if emotion_found_check:
                        logger.debug(
                            f"[CONTAGION] Using segments_with_emotion directly, emotion_type: {emotion_type_check}"
                        )
                        segments = segments_with_emotion
                        emotion_type = emotion_type_check
                        emotion_found = True
                    else:
                        logger.debug(
                            "[CONTAGION] segments_with_emotion don't have emotion data embedded, attempting to merge..."
                        )
                        segments, emotion_type, emotion_found = merge_emotion_data(
                            segments, segments_with_emotion, logger
                        )

                        if emotion_found:
                            emotion_type, emotion_found = check_emotion_data(
                                segments, "[CONTAGION] After merge: "
                            )

                if not emotion_found and isinstance(emotion_data, dict):
                    logger.debug(
                        "[CONTAGION] Attempting to reconstruct emotion data from contextual_examples..."
                    )
                    segments, emotion_type, emotion_found = reconstruct_emotion_data(
                        segments, emotion_data, logger
                    )
                    if emotion_found:
                        emotion_type, emotion_found = check_emotion_data(
                            segments, "[CONTAGION] After reconstruction: "
                        )
                else:
                    logger.debug(
                        "[CONTAGION] emotion_data provided but segments_with_emotion is empty or missing"
                    )
            else:
                logger.debug(
                    f"[CONTAGION] No emotion_data provided or not a dict. emotion_data type: {type(emotion_data)}"
                )

            if not emotion_found:
                error_details = []
                error_details.append("No emotion data found in segments.")

                if emotion_data:
                    error_details.append(f"emotion_data type: {type(emotion_data)}")
                    if isinstance(emotion_data, dict):
                        error_details.append(
                            f"emotion_data keys: {list(emotion_data.keys())}"
                        )
                        segments_with_emotion = emotion_data.get(
                            "segments_with_emotion", []
                        )
                        error_details.append(
                            f"segments_with_emotion count: {len(segments_with_emotion)}"
                        )
                        if segments_with_emotion:
                            sample_seg = segments_with_emotion[0]
                            error_details.append(
                                f"Sample segment keys: {list(sample_seg.keys())}"
                            )
                            if "context_emotion" in sample_seg:
                                error_details.append(
                                    f"context_emotion value: {sample_seg.get('context_emotion')}"
                                )
                            if "nrc_emotion" in sample_seg:
                                nrc_val = sample_seg.get("nrc_emotion")
                                error_details.append(
                                    f"nrc_emotion type: {type(nrc_val)}, value: {nrc_val}"
                                )
                else:
                    error_details.append("emotion_data is None or not provided")

                error_details.append("Please run emotion analysis first.")
                error_msg = " ".join(error_details)
                logger.error(f"[CONTAGION] {error_msg}")
                raise ValueError(error_msg)

        speaker_emotions, timeline = build_emotion_timeline(segments, emotion_type)
        contagion_events, contagion_counts, contagion_summary = detect_contagion(
            timeline
        )

        return {
            "contagion_events": contagion_events,
            "contagion_counts": contagion_counts,
            "contagion_summary": contagion_summary,
            "emotion_type": emotion_type,
            "timeline": timeline,
            "speaker_emotions": speaker_emotions,
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
            speaker_map = context.get_speaker_map()
            logger.debug(f"[CONTAGION] Loaded {len(segments)} segments from context")

            emotion_result = context.get_analysis_result("emotion")

            if emotion_result and isinstance(emotion_result, dict):
                segments_with_emotion = emotion_result.get("segments_with_emotion", [])
                if segments_with_emotion:
                    sample_seg = (
                        segments_with_emotion[0] if segments_with_emotion else {}
                    )
                    if (
                        "context_emotion" not in sample_seg
                        and "nrc_emotion" not in sample_seg
                    ):
                        from transcriptx.core.utils.path_utils import (
                            find_enriched_transcript,
                        )
                        from transcriptx.io.transcript_loader import load_transcript

                        enriched_path = find_enriched_transcript(
                            context.transcript_path, "emotion"
                        )
                        if enriched_path:
                            logger.debug(
                                f"[CONTAGION] Loading enriched transcript from: {enriched_path}"
                            )
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
                                    logger.debug(
                                        "[CONTAGION] Loaded "
                                        f"{len(enriched_segments)} segments from enriched transcript"
                                    )
                                    emotion_result["segments_with_emotion"] = (
                                        enriched_segments
                                    )
                            except Exception as exc:
                                logger.warning(
                                    f"[CONTAGION] Failed to load enriched transcript: {exc}"
                                )

            if emotion_result:
                logger.debug(
                    f"[CONTAGION] Found emotion_result in context. Type: {type(emotion_result)}"
                )
                if isinstance(emotion_result, dict):
                    logger.debug(
                        f"[CONTAGION] emotion_result keys: {list(emotion_result.keys())}"
                    )
                    segments_with_emotion = emotion_result.get(
                        "segments_with_emotion", []
                    )
                    logger.debug(
                        f"[CONTAGION] segments_with_emotion count: {len(segments_with_emotion)}"
                    )

                    if segments_with_emotion:
                        sample_seg = (
                            segments_with_emotion[0] if segments_with_emotion else {}
                        )
                        logger.debug(
                            "[CONTAGION] Sample segment_with_emotion keys: "
                            f"{list(sample_seg.keys())}"
                        )
                        if "context_emotion" in sample_seg:
                            logger.debug(
                                "[CONTAGION] Sample has context_emotion: "
                                f"{sample_seg.get('context_emotion')}"
                            )
                        if "nrc_emotion" in sample_seg:
                            nrc_val = sample_seg.get("nrc_emotion")
                            logger.debug(
                                "[CONTAGION] Sample has nrc_emotion: "
                                f"type={type(nrc_val)}, value={nrc_val}"
                            )

                        logger.debug(
                            "[CONTAGION] Will attempt to use segments_with_emotion in analyze()"
                        )
                else:
                    logger.warning(
                        f"[CONTAGION] emotion_result is not a dict: {type(emotion_result)}"
                    )
            else:
                logger.warning(
                    "[CONTAGION] No emotion_result found in context. Emotion analysis may not have run or completed."
                )

            results = self.analyze(segments, speaker_map, emotion_data=emotion_result)

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
        contagion_events = results["contagion_events"]
        contagion_summary = results["contagion_summary"]
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()

        output_service.save_data(
            contagion_events, "contagion_events", format_type="json"
        )
        output_service.save_data(
            contagion_summary, "contagion_summary", format_type="json"
        )

        summary_text = "Emotional Contagion Analysis Results:\n\n"
        summary_text += f"Total contagion events detected: {len(contagion_events)}\n"
        summary_text += (
            f"Emotion type analyzed: {results.get('emotion_type', 'unknown')}\n\n"
        )

        contagion_counts = results.get("contagion_counts", {})
        if contagion_events:
            summary_text += "Top contagion patterns:\n"
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
        }
        output_service.save_summary(global_stats, {}, analysis_metadata={})
