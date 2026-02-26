"""
Question-Answer Analysis Module for TranscriptX.

This module identifies question-answer pairs in conversations and evaluates
response quality, including:
- Question detection and classification
- Answer matching
- Response quality assessment
- Unanswered question detection
- Question chain identification
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.viz_ids import (
    VIZ_QA_TIMELINE,
    VIZ_QA_RESPONSE_QUALITY,
    VIZ_QA_QUESTION_TYPE_BREAKDOWN,
    VIZ_QA_RESPONSE_TIME_ANALYSIS,
)
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import BarCategoricalSpec, LineTimeSeriesSpec

logger = get_logger()


class QAAnalysis(AnalysisModule):
    """
    Question-Answer analysis module.

    This module identifies questions in conversations, matches them to answers,
    and evaluates the quality of responses.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Q&A analysis module."""
        super().__init__(config)
        self.module_name = "qa_analysis"

        # Get config from profile
        from transcriptx.core.utils.config import get_config

        profile_config = get_config().analysis.qa_analysis

        # Use config values, with fallback to provided config or defaults
        self.response_time_threshold = self.config.get(
            "response_time_threshold", profile_config.response_time_threshold
        )
        self.quality_weights = self.config.get(
            "quality_weights",
            {
                "directness": profile_config.weight_directness,
                "completeness": profile_config.weight_completeness,
                "relevance": profile_config.weight_relevance,
                "length": profile_config.weight_length,
            },
        )

        # Store thresholds from config
        self.min_match_threshold = profile_config.min_match_threshold
        self.good_match_threshold = profile_config.good_match_threshold
        self.high_match_threshold = profile_config.high_match_threshold
        self.min_answer_length = profile_config.min_answer_length
        self.optimal_answer_length = profile_config.optimal_answer_length
        self.max_answer_length = profile_config.max_answer_length

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        acts_data: Optional[Dict[str, Any]] = None,
        semantic_similarity_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform Q&A analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping
            acts_data: Optional dialogue act classification results
            semantic_similarity_data: Optional semantic similarity results

        Returns:
            Dictionary containing Q&A analysis results
        """
        if not segments:
            return {
                "qa_pairs": [],
                "unanswered_questions": [],
                "question_chains": [],
                "statistics": {
                    "total_questions": 0,
                    "answered": 0,
                    "unanswered": 0,
                    "avg_response_time": 0.0,
                    "avg_quality_score": 0.0,
                },
                "error": "No segments provided",
            }

        # Detect questions
        questions = self._detect_questions(segments, speaker_map, acts_data)

        if not questions:
            return {
                "qa_pairs": [],
                "unanswered_questions": [],
                "question_chains": [],
                "statistics": {
                    "total_questions": 0,
                    "answered": 0,
                    "unanswered": 0,
                    "avg_response_time": 0.0,
                    "avg_quality_score": 0.0,
                },
            }

        # Match questions to answers
        qa_pairs = self._match_questions_to_answers(
            questions, segments, speaker_map, semantic_similarity_data
        )

        # Identify unanswered questions
        answered_question_indices = {
            pair["question"]["index"] for pair in qa_pairs if pair.get("matched", False)
        }
        unanswered_questions = [
            q for i, q in enumerate(questions) if i not in answered_question_indices
        ]

        # Detect question chains
        question_chains = self._detect_question_chains(qa_pairs, questions)

        # Calculate statistics
        statistics = self._calculate_statistics(qa_pairs, unanswered_questions)

        return {
            "qa_pairs": qa_pairs,
            "unanswered_questions": unanswered_questions,
            "question_chains": question_chains,
            "statistics": statistics,
        }

    def _resolve_speaker_for_segment(
        self,
        segment: Dict[str, Any],
        all_segments: List[Dict[str, Any]],
        speaker_map: Optional[Dict[str, str]],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve speaker display name and ID, using speaker_map as fallback."""
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        speaker_info = extract_speaker_info(segment)
        if speaker_info is not None:
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [segment], all_segments
            )
            if speaker and is_named_speaker(speaker):
                speaker_id = segment.get("speaker", speaker_info.grouping_key)
                return speaker, str(speaker_id)

        speaker_id = segment.get("speaker") or segment.get("original_speaker_id")
        if speaker_map and speaker_id in speaker_map:
            return speaker_map[speaker_id], str(speaker_id)

        return None, None

    def _detect_questions(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        acts_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Detect and classify questions in segments."""
        questions = []

        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            speaker, speaker_id = self._resolve_speaker_for_segment(
                seg, segments, speaker_map
            )
            if not speaker or not speaker_id:
                continue

            # Check if segment is a question
            is_question = False

            # First, check if acts module classified it as a question
            if acts_data or "dialogue_act" in seg or "act_type" in seg:
                act_type = seg.get("dialogue_act") or seg.get("act_type")
                if act_type == "question":
                    is_question = True

            # Fallback: pattern-based detection
            if not is_question:
                is_question = self._is_question_by_pattern(text)

            if is_question:
                question_type = self._classify_question_type(text)
                question_word = self._extract_question_word(text)

                questions.append(
                    {
                        "index": i,
                        "speaker": speaker,
                        "speaker_id": speaker_id,
                        "text": text,
                        "timestamp": seg.get("start", 0),
                        "type": question_type,
                        "question_word": question_word,
                        "segment": seg,
                    }
                )

        return questions

    def _is_question_by_pattern(self, text: str) -> bool:
        """Check if text is a question using pattern matching."""
        text_lower = text.lower().strip()

        # Ends with question mark
        if text_lower.endswith("?"):
            return True

        # Starts with question words
        question_starters = [
            r"^(what|why|how|when|where|who|which|can|could|should|would|will|do|does|did|is|are|was|were)\s+",
            r"^(any idea|do you know|could you tell me|would you mind|is there|are there)\s+",
        ]

        for pattern in question_starters:
            if re.match(pattern, text_lower):
                return True

        return False

    def _classify_question_type(self, text: str) -> str:
        """Classify question type."""
        text_lower = text.lower().strip()

        # Open-ended questions
        open_ended_words = ["what", "why", "how", "when", "where", "who", "which"]
        if any(text_lower.startswith(word) for word in open_ended_words):
            return "open_ended"

        # Closed questions (yes/no)
        closed_patterns = [
            r"^(can|could|should|would|will|do|does|did|is|are|was|were|have|has|had)\s+",
            r"^(is there|are there|do you|did you|are you|is it|will it)\s+",
        ]
        for pattern in closed_patterns:
            if re.match(pattern, text_lower):
                return "closed"

        # Clarification requests
        clarification_patterns = [
            r"\b(what do you mean|so you mean|just to clarify|to be clear|can you explain)\b",
            r"\b(can you repeat|say that again|pardon|excuse me)\b",
        ]
        for pattern in clarification_patterns:
            if re.search(pattern, text_lower):
                return "clarification"

        # Rhetorical questions (often don't have question marks or are statements)
        rhetorical_indicators = ["right", "isn't it", "don't you", "won't you"]
        if any(indicator in text_lower for indicator in rhetorical_indicators):
            return "rhetorical"

        # Default to open-ended if we can't determine
        return "open_ended"

    def _extract_question_word(self, text: str) -> Optional[str]:
        """Extract the main question word from text."""
        text_lower = text.lower().strip()
        question_words = ["what", "why", "how", "when", "where", "who", "which"]

        for word in question_words:
            if text_lower.startswith(word):
                return word

        return None

    def _match_questions_to_answers(
        self,
        questions: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str],
        semantic_similarity_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Match questions to their answers."""
        qa_pairs = []

        for question in questions:
            question_index = question["index"]
            question_speaker = question["speaker_id"]
            question_timestamp = question["timestamp"]

            # Find potential answers (subsequent segments from different speakers)
            best_match = None
            best_score = 0.0

            for i in range(question_index + 1, len(segments)):
                answer_seg = segments[i]
                answer_speaker_id = answer_seg.get("speaker", "UNKNOWN")
                answer_timestamp = answer_seg.get("start", 0)
                answer_text = answer_seg.get("text", "")

                # Skip if same speaker
                if answer_speaker_id == question_speaker:
                    continue

                # Check temporal proximity
                response_time = answer_timestamp - question_timestamp
                if response_time > self.response_time_threshold:
                    break  # Too far away, stop searching

                if response_time < 0:
                    continue  # Answer before question (shouldn't happen)

                # Calculate match score
                match_score = self._calculate_match_score(
                    question, answer_seg, response_time, semantic_similarity_data
                )

                if match_score > best_score:
                    best_score = match_score
                    best_match = {
                        "segment": answer_seg,
                        "index": i,
                        "response_time": response_time,
                        "match_score": match_score,
                    }

            # Create QA pair
            if best_match and best_score > self.min_match_threshold:
                answer_seg = best_match["segment"]
                answer_speaker, answer_speaker_id = self._resolve_speaker_for_segment(
                    answer_seg, segments, speaker_map
                )
                if not answer_speaker or not answer_speaker_id:
                    continue

                # Assess response quality
                quality = self._assess_response_quality(
                    question, answer_seg, semantic_similarity_data
                )

                qa_pairs.append(
                    {
                        "question": {
                            "speaker": question["speaker"],
                            "text": question["text"],
                            "timestamp": question["timestamp"],
                            "type": question["type"],
                            "question_word": question["question_word"],
                            "index": question_index,
                        },
                        "answer": {
                            "speaker": answer_speaker,
                            "text": answer_seg.get("text", ""),
                            "timestamp": answer_seg.get("start", 0),
                            "response_time": best_match["response_time"],
                            "index": best_match["index"],
                        },
                        "quality": quality,
                        "matched": True,
                        "match_score": best_score,
                    }
                )
            else:
                # Unmatched question
                qa_pairs.append(
                    {
                        "question": {
                            "speaker": question["speaker"],
                            "text": question["text"],
                            "timestamp": question["timestamp"],
                            "type": question["type"],
                            "question_word": question["question_word"],
                            "index": question_index,
                        },
                        "answer": None,
                        "quality": None,
                        "matched": False,
                        "match_score": 0.0,
                    }
                )

        return qa_pairs

    def _calculate_match_score(
        self,
        question: Dict[str, Any],
        answer_seg: Dict[str, Any],
        response_time: float,
        semantic_similarity_data: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate how well an answer segment matches a question."""
        score = 0.0

        # Temporal proximity score (closer is better)
        time_score = max(0, 1.0 - (response_time / self.response_time_threshold))
        score += 0.4 * time_score

        # Semantic similarity (if available)
        if semantic_similarity_data:
            # Try to get similarity score if available
            # This is a placeholder - would need actual similarity calculation
            similarity_score = 0.5  # Default
            score += 0.3 * similarity_score
        else:
            # Keyword overlap as fallback
            question_words = set(question["text"].lower().split())
            answer_words = set(answer_seg.get("text", "").lower().split())
            overlap = len(question_words & answer_words) / max(len(question_words), 1)
            score += 0.3 * overlap

        # Speaker change (different speaker is better)
        if question["speaker_id"] != answer_seg.get("speaker", "UNKNOWN"):
            score += 0.3

        return min(score, 1.0)

    def _assess_response_quality(
        self,
        question: Dict[str, Any],
        answer_seg: Dict[str, Any],
        semantic_similarity_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """Assess the quality of a response to a question."""
        question_text = question["text"].lower()
        answer_text = answer_seg.get("text", "").lower()

        # Directness: Does the answer directly address the question?
        directness = self._calculate_directness(
            question_text, answer_text, question.get("question_word")
        )

        # Completeness: Is the question fully answered?
        completeness = self._calculate_completeness(
            question_text, answer_text, question.get("type")
        )

        # Relevance: Semantic relevance between question and answer
        if semantic_similarity_data:
            relevance = 0.7  # Placeholder - would use actual similarity
        else:
            relevance = self._calculate_relevance(question_text, answer_text)

        # Length appropriateness
        length_score = self._calculate_length_score(question_text, answer_text)

        # Overall quality score
        overall = (
            self.quality_weights["directness"] * directness
            + self.quality_weights["completeness"] * completeness
            + self.quality_weights["relevance"] * relevance
            + self.quality_weights["length"] * length_score
        )

        return {
            "directness": round(directness, 3),
            "completeness": round(completeness, 3),
            "relevance": round(relevance, 3),
            "length_score": round(length_score, 3),
            "overall": round(overall, 3),
        }

    def _calculate_directness(
        self, question_text: str, answer_text: str, question_word: Optional[str]
    ) -> float:
        """Calculate how directly the answer addresses the question."""
        if not question_word:
            return 0.5  # Default if we can't determine question word

        # Check if answer contains relevant keywords based on question word
        question_words_set = set(question_text.split())
        answer_words_set = set(answer_text.split())

        # Remove common stop words
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
        }
        question_words_set -= stop_words
        answer_words_set -= stop_words

        # Calculate overlap
        overlap = len(question_words_set & answer_words_set)
        max_words = max(len(question_words_set), 1)

        directness = min(overlap / max_words, 1.0)

        # Boost for specific question word patterns
        if question_word == "what" and any(
            word in answer_text for word in ["is", "are", "was", "were"]
        ):
            directness = min(directness + 0.2, 1.0)
        elif question_word == "when" and any(
            word in answer_text for word in ["at", "on", "in", "time", "date"]
        ):
            directness = min(directness + 0.2, 1.0)
        elif question_word == "where" and any(
            word in answer_text for word in ["at", "in", "location", "place"]
        ):
            directness = min(directness + 0.2, 1.0)
        elif question_word == "who" and any(
            word in answer_text for word in ["person", "people", "name"]
        ):
            directness = min(directness + 0.2, 1.0)

        return directness

    def _calculate_completeness(
        self, question_text: str, answer_text: str, question_type: str
    ) -> float:
        """Calculate how completely the question is answered."""
        # For closed questions, check for yes/no indicators
        if question_type == "closed":
            yes_no_indicators = [
                "yes",
                "no",
                "yeah",
                "nope",
                "yep",
                "nay",
                "sure",
                "absolutely",
                "definitely",
                "not",
            ]
            if any(indicator in answer_text for indicator in yes_no_indicators):
                return 0.9

        # For open-ended questions, check answer length and detail
        if question_type == "open_ended":
            answer_length = len(answer_text.split())
            # Answers with 5+ words are likely more complete
            if answer_length >= 5:
                return min(0.7 + (answer_length / 50.0), 1.0)
            elif answer_length >= 2:
                return 0.5
            else:
                return 0.3

        # Default completeness
        answer_length = len(answer_text.split())
        if answer_length >= 3:
            return 0.7
        elif answer_length >= 1:
            return 0.5
        else:
            return 0.3

    def _calculate_relevance(self, question_text: str, answer_text: str) -> float:
        """Calculate semantic relevance between question and answer."""
        # Simple keyword-based relevance
        question_words = set(question_text.split())
        answer_words = set(answer_text.split())

        # Remove stop words
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "what",
            "why",
            "how",
            "when",
            "where",
            "who",
            "which",
        }
        question_words -= stop_words
        answer_words -= stop_words

        if not question_words:
            return 0.5

        # Calculate Jaccard similarity
        intersection = len(question_words & answer_words)
        union = len(question_words | answer_words)

        if union == 0:
            return 0.0

        relevance = intersection / union
        return min(relevance, 1.0)

    def _calculate_length_score(self, question_text: str, answer_text: str) -> float:
        """Calculate length appropriateness score."""
        question_length = len(question_text.split())
        answer_length = len(answer_text.split())

        # Ideal answer length is 2-5x question length
        if question_length == 0:
            return 0.5

        ratio = answer_length / question_length

        if 2.0 <= ratio <= 5.0:
            return 1.0
        elif 1.0 <= ratio < 2.0:
            return 0.8
        elif 5.0 < ratio <= 10.0:
            return 0.7
        elif ratio > 10.0:
            return 0.4  # Too long, might be rambling
        else:
            return 0.3  # Too short, dismissive

    def _detect_question_chains(
        self, qa_pairs: List[Dict[str, Any]], questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect chains of follow-up questions."""
        chains = []
        current_chain = []

        for i, pair in enumerate(qa_pairs):
            if not pair.get("matched", False):
                continue

            question = pair["question"]
            answer = pair["answer"]

            # Check if next question is a follow-up (same topic, within short time)
            if i + 1 < len(qa_pairs):
                next_pair = qa_pairs[i + 1]
                if next_pair.get("matched", False):
                    next_question = next_pair["question"]
                    time_gap = next_question["timestamp"] - answer["timestamp"]

                    # Follow-up if within 5 seconds and potentially related
                    if time_gap < 5.0:
                        if not current_chain:
                            current_chain = [pair]
                        current_chain.append(next_pair)
                    else:
                        if len(current_chain) > 1:
                            chains.append(
                                {
                                    "chain_length": len(current_chain),
                                    "questions": [p["question"] for p in current_chain],
                                    "start_time": current_chain[0]["question"][
                                        "timestamp"
                                    ],
                                    "end_time": current_chain[-1]["answer"][
                                        "timestamp"
                                    ],
                                }
                            )
                        current_chain = []

        # Add final chain if exists
        if len(current_chain) > 1:
            chains.append(
                {
                    "chain_length": len(current_chain),
                    "questions": [p["question"] for p in current_chain],
                    "start_time": current_chain[0]["question"]["timestamp"],
                    "end_time": current_chain[-1]["answer"]["timestamp"],
                }
            )

        return chains

    def _calculate_statistics(
        self, qa_pairs: List[Dict[str, Any]], unanswered_questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate Q&A statistics."""
        total_questions = len(qa_pairs)
        answered = sum(1 for pair in qa_pairs if pair.get("matched", False))
        unanswered = len(unanswered_questions)

        # Calculate average response time
        response_times = [
            pair["answer"]["response_time"]
            for pair in qa_pairs
            if pair.get("matched", False) and pair.get("answer")
        ]
        avg_response_time = np.mean(response_times) if response_times else 0.0

        # Calculate average quality score
        quality_scores = [
            pair["quality"]["overall"]
            for pair in qa_pairs
            if pair.get("matched", False) and pair.get("quality")
        ]
        avg_quality_score = np.mean(quality_scores) if quality_scores else 0.0

        return {
            "total_questions": total_questions,
            "answered": answered,
            "unanswered": unanswered,
            "answer_rate": (
                round(answered / total_questions, 3) if total_questions > 0 else 0.0
            ),
            "avg_response_time": round(avg_response_time, 2),
            "avg_quality_score": round(avg_quality_score, 3),
        }

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """
        Run Q&A analysis using PipelineContext (can access cached results).

        Args:
            context: PipelineContext containing transcript data and cached results

        Returns:
            Dictionary containing analysis results and metadata
        """
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_start,
                log_analysis_complete,
                log_analysis_error,
            )

            log_analysis_start(self.module_name, context.transcript_path)

            # Extract data from context
            segments = context.get_segments()
            speaker_map = context.get_speaker_map()

            # Get acts results (required dependency)
            acts_result = context.get_analysis_result("acts")
            if not acts_result:
                # Try to get from segments directly
                if not any(
                    seg.get("dialogue_act") == "question"
                    or seg.get("act_type") == "question"
                    for seg in segments
                ):
                    logger.warning(
                        "No acts data found. Q&A analysis may be less accurate."
                    )

            # Get semantic similarity results (optional)
            semantic_similarity_result = context.get_analysis_result(
                "semantic_similarity"
            ) or context.get_analysis_result("semantic_similarity_advanced")

            # Enrich segments with acts data if available
            if acts_result:
                segments_with_acts = acts_result.get("segments_with_acts", [])
                if segments_with_acts:
                    acts_map = {seg.get("start", 0): seg for seg in segments_with_acts}
                    for seg in segments:
                        seg_start = seg.get("start", 0)
                        if seg_start in acts_map:
                            acts_seg = acts_map[seg_start]
                            seg["dialogue_act"] = acts_seg.get("dialogue_act")
                            seg["act_type"] = acts_seg.get("act_type")

            # Perform analysis
            results = self.analyze(
                segments,
                speaker_map,
                acts_data=acts_result,
                semantic_similarity_data=semantic_similarity_result,
            )

            # Create output service and save results
            from transcriptx.core.output.output_service import create_output_service

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)

            # Store result in context for reuse by other modules
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

        except Exception as e:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(e))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(e),
                "results": {},
            }

    def save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """Save Q&A analysis results."""
        self._save_results(results, output_service)

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """Save results using OutputService (new interface)."""
        # Save main results as JSON
        output_service.save_data(results, "qa_analysis", format_type="json")

        # Save QA pairs as CSV
        if results.get("qa_pairs"):
            csv_rows = []
            for pair in results["qa_pairs"]:
                row = {
                    "question_speaker": pair["question"]["speaker"],
                    "question_text": pair["question"]["text"],
                    "question_timestamp": pair["question"]["timestamp"],
                    "question_type": pair["question"]["type"],
                    "answer_speaker": (
                        pair.get("answer", {}).get("speaker")
                        if pair.get("answer")
                        else None
                    ),
                    "answer_text": (
                        pair.get("answer", {}).get("text")
                        if pair.get("answer")
                        else None
                    ),
                    "answer_timestamp": (
                        pair.get("answer", {}).get("timestamp")
                        if pair.get("answer")
                        else None
                    ),
                    "response_time": (
                        pair.get("answer", {}).get("response_time")
                        if pair.get("answer")
                        else None
                    ),
                    "matched": pair.get("matched", False),
                    "quality_overall": (
                        pair.get("quality", {}).get("overall")
                        if pair.get("quality")
                        else None
                    ),
                    "quality_directness": (
                        pair.get("quality", {}).get("directness")
                        if pair.get("quality")
                        else None
                    ),
                    "quality_completeness": (
                        pair.get("quality", {}).get("completeness")
                        if pair.get("quality")
                        else None
                    ),
                    "quality_relevance": (
                        pair.get("quality", {}).get("relevance")
                        if pair.get("quality")
                        else None
                    ),
                }
                csv_rows.append(row)
            output_service.save_data(csv_rows, "qa_pairs", format_type="csv")

        # Save unanswered questions
        if results.get("unanswered_questions"):
            output_service.save_data(
                results["unanswered_questions"],
                "unanswered_questions",
                format_type="json",
            )

        # Generate visualizations
        self._generate_visualizations(results, output_service)

        # Save summary
        global_stats = results.get("statistics", {})
        output_service.save_summary(global_stats, {}, analysis_metadata={})

    def _generate_visualizations(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """Generate Q&A analysis visualizations."""
        try:
            qa_pairs = results.get("qa_pairs", [])
            if not qa_pairs:
                return

            # Create QA timeline
            self._create_qa_timeline(qa_pairs, output_service)

            # Create response quality distribution
            self._create_quality_distribution(qa_pairs, output_service)

            # Create question type breakdown
            self._create_question_type_breakdown(qa_pairs, output_service)

            # Create response time analysis
            self._create_response_time_analysis(qa_pairs, output_service)

        except Exception as e:
            logger.warning(f"Failed to generate visualizations: {e}")

    def _create_qa_timeline(
        self, qa_pairs: List[Dict[str, Any]], output_service: "OutputService"
    ) -> None:
        """Create question-answer timeline visualization."""
        matched_pairs = [p for p in qa_pairs if p.get("matched", False)]

        question_times = [p["question"]["timestamp"] for p in qa_pairs]
        answer_times = [
            p["answer"]["timestamp"] for p in matched_pairs if p.get("answer")
        ]
        q_disp, x_label = time_axis_display(question_times)
        a_disp = time_axis_display(answer_times)[0] if answer_times else []
        spec = LineTimeSeriesSpec(
            viz_id=VIZ_QA_TIMELINE,
            module=self.module_name,
            name="qa_timeline",
            scope="global",
            chart_intent="line_timeseries",
            title="Question-Answer Timeline",
            x_label=x_label,
            y_label="Event",
            markers=True,
            series=[
                {"name": "Questions", "x": q_disp, "y": [1] * len(question_times)},
                {"name": "Answers", "x": a_disp, "y": [0.5] * len(answer_times)},
            ],
        )
        output_service.save_chart(spec)

    def _create_quality_distribution(
        self, qa_pairs: List[Dict[str, Any]], output_service: "OutputService"
    ) -> None:
        """Create response quality distribution chart."""
        matched_pairs = [
            p for p in qa_pairs if p.get("matched", False) and p.get("quality")
        ]
        if not matched_pairs:
            return

        quality_scores = [p["quality"]["overall"] for p in matched_pairs]

        counts, bin_edges = np.histogram(quality_scores, bins=20)
        categories = [
            f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}" for i in range(len(counts))
        ]
        spec = BarCategoricalSpec(
            viz_id=VIZ_QA_RESPONSE_QUALITY,
            module=self.module_name,
            name="response_quality",
            scope="global",
            chart_intent="bar_categorical",
            title="Response Quality Distribution",
            x_label="Quality Score",
            y_label="Frequency",
            categories=categories,
            values=counts.tolist(),
        )
        output_service.save_chart(spec)

    def _create_question_type_breakdown(
        self, qa_pairs: List[Dict[str, Any]], output_service: "OutputService"
    ) -> None:
        """Create question type breakdown chart."""
        question_types = [p["question"]["type"] for p in qa_pairs]
        type_counts = defaultdict(int)
        for qtype in question_types:
            type_counts[qtype] += 1

        if not type_counts:
            return

        types = list(type_counts.keys())
        counts = list(type_counts.values())
        spec = BarCategoricalSpec(
            viz_id=VIZ_QA_QUESTION_TYPE_BREAKDOWN,
            module=self.module_name,
            name="question_type_breakdown",
            scope="global",
            chart_intent="bar_categorical",
            title="Question Type Breakdown",
            x_label="Question Type",
            y_label="Count",
            categories=types,
            values=counts,
        )
        output_service.save_chart(spec)

    def _create_response_time_analysis(
        self, qa_pairs: List[Dict[str, Any]], output_service: "OutputService"
    ) -> None:
        """Create response time analysis chart."""
        matched_pairs = [
            p for p in qa_pairs if p.get("matched", False) and p.get("answer")
        ]
        if not matched_pairs:
            return

        response_times = [p["answer"]["response_time"] for p in matched_pairs]
        counts, bin_edges = np.histogram(response_times, bins=20)
        max_rt = max(response_times)
        if max_rt > 3600.0:
            edges_display = bin_edges / 3600.0
            x_label = "Response Time (hours)"
        else:
            edges_display = bin_edges / 60.0
            x_label = "Response Time (minutes)"
        categories = [
            f"{edges_display[i]:.2f}-{edges_display[i + 1]:.2f}"
            for i in range(len(counts))
        ]
        spec = BarCategoricalSpec(
            viz_id=VIZ_QA_RESPONSE_TIME_ANALYSIS,
            module=self.module_name,
            name="response_time_analysis",
            scope="global",
            chart_intent="bar_categorical",
            title="Response Time Distribution",
            x_label=x_label,
            y_label="Frequency",
            categories=categories,
            values=counts.tolist(),
        )
        output_service.save_chart(spec)
