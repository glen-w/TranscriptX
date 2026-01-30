"""
Tag Extraction Module for TranscriptX.

This module extracts semantic tags from the early seconds of audio/transcript,
identifying content types like "idea", "reflection", "meeting", "todo", "question".

Key Features:
- Early segment analysis (first 30-60 seconds)
- Keyword pattern matching
- Dialogue act classification integration
- Confidence scoring
"""

from typing import Any, Dict, List, Optional
import re
from collections import Counter

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Tag definitions with patterns
TAG_PATTERNS = {
    "idea": [
        r"\b(i have an?|i've got an?|here's an?|what if|maybe we could|we could|we should try|let's try|how about)\b",
        r"\b(idea|concept|proposal|suggestion|brainstorm)\b",
        r"\b(think about|consider|imagine if|suppose we)\b",
    ],
    "reflection": [
        r"\b(i'm thinking|i'm reflecting|let me think|looking back|in retrospect|thinking about)\b",
        r"\b(reflect|reflection|personal note|note to self|reminder to myself|voice memo)\b",
        r"\b(what i learned|what i realized|my thoughts on|my take on)\b",
    ],
    "meeting": [
        r"\b(agenda|minutes|action items?|action item|let's discuss|meeting|presentation)\b",
        r"\b(status update|quarterly|weekly|daily standup|standup|sprint|retrospective)\b",
        r"\b(review|debrief|sync|check-in|huddle)\b",
    ],
    "todo": [
        r"\b(i need to|i should|i must|i have to|remind me|don't forget|action item)\b",
        r"\b(follow up|follow-up|next steps?|to do|todo|task|reminder)\b",
        r"\b(make sure|remember to|don't forget to|need to remember)\b",
    ],
    "question": [
        r"\b(what|why|how|when|where|who|which|can|could|should|would)\s+\w+.*\?",
        r".*\?$",  # Ends with question mark
        r"\b(do you|did you|are you|is it|will it|would it)\b",
    ],
}

# Default analysis window (seconds) - kept for backward compatibility
DEFAULT_EARLY_WINDOW_SECONDS = 60
DEFAULT_EARLY_SEGMENTS = 10


class TagExtractor(AnalysisModule):
    """
    Extracts semantic tags from early segments of transcripts.

    This class analyzes the first 30-60 seconds (or first 5-10 segments) of a
    transcript to identify content types and extract relevant tags.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the tag extractor.

        Args:
            config: Optional configuration dictionary
                - early_window_seconds: Time window to analyze (default: from profile)
                - early_segments: Number of segments to analyze (default: from profile)
                - min_confidence: Minimum confidence for tag inclusion (default: from profile)
        """
        super().__init__(config)
        self.module_name = "tag_extraction"

        # Get config from profile
        from transcriptx.core.utils.config import get_config

        profile_config = get_config().analysis.tag_extraction

        # Use config values, with fallback to provided config or defaults
        self.early_window_seconds = self.config.get(
            "early_window_seconds", profile_config.early_window_seconds
        )
        self.early_segments = self.config.get(
            "early_segments", profile_config.early_segments
        )
        self.min_confidence = self.config.get(
            "min_confidence", profile_config.min_confidence
        )
        self.logger = get_logger()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform tag extraction analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used for tag extraction)

        Returns:
            Dictionary containing tag extraction results
        """
        # Extract tags using existing method
        return self.extract_tags(segments)

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        # Save tag extraction results
        output_service.save_data(results, "tag_extraction", format_type="json")

        # Save summary
        tags = results.get("tags", [])
        tag_details = results.get("tag_details", {})
        global_stats = {
            "total_tags": len(tags),
            "tags": tags,
        }
        output_service.save_summary(global_stats, {}, analysis_metadata=tag_details)

    def extract_tags(
        self,
        transcript_data: List[Dict[str, Any]],
        early_segments: Optional[List[Dict[str, Any]]] = None,
        audio_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract tags from early segments of transcript.

        Args:
            transcript_data: Full list of transcript segments
            early_segments: Optional pre-filtered early segments (if None, will extract)
            audio_metadata: Optional audio metadata (duration, etc.)

        Returns:
            Dictionary with tags, tag_details, and analysis metadata
        """
        try:
            # Extract early segments if not provided
            if early_segments is None:
                early_segments = self._extract_early_segments(
                    transcript_data, audio_metadata
                )

            if not early_segments:
                return {
                    "tags": [],
                    "tag_details": {},
                    "early_segments_analyzed": 0,
                    "analysis_window_seconds": 0.0,
                    "message": "No early segments found",
                }

            # Analyze early content
            content_analysis = self._analyze_early_content(early_segments)

            # Detect tag patterns
            tag_results = self._detect_tag_patterns(
                content_analysis["combined_text"],
                first_word=content_analysis.get("first_word"),
            )

            # Classify dialogue acts for additional context
            dialogue_acts = self._classify_dialogue_acts(early_segments)

            # Combine evidence and calculate final tags
            final_tags, tag_details = self._calculate_final_tags(
                tag_results, dialogue_acts, content_analysis
            )

            # Calculate analysis window
            analysis_window = self._calculate_analysis_window(early_segments)

            return {
                "tags": final_tags,
                "tag_details": tag_details,
                "early_segments_analyzed": len(early_segments),
                "analysis_window_seconds": analysis_window,
                "content_analysis": content_analysis,
            }

        except Exception as e:
            self.logger.error(f"Error in tag extraction: {e}")
            return {
                "tags": [],
                "tag_details": {},
                "early_segments_analyzed": 0,
                "analysis_window_seconds": 0.0,
                "error": str(e),
            }

    def _extract_early_segments(
        self,
        transcript_data: List[Dict[str, Any]],
        audio_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract early segments based on time window or segment count.

        Args:
            transcript_data: Full transcript segments
            audio_metadata: Optional audio metadata

        Returns:
            List of early segments
        """
        if not transcript_data:
            return []

        # Strategy 1: Extract by time window
        if audio_metadata and "duration" in audio_metadata:
            early_segments = []
            for segment in transcript_data:
                start = segment.get("start", 0.0)
                if start <= self.early_window_seconds:
                    early_segments.append(segment)
                else:
                    break
            if early_segments:
                return early_segments

        # Strategy 2: Extract by segment count (fallback)
        return transcript_data[: self.early_segments]

    def _analyze_early_content(
        self, early_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze early content for patterns and statistics.

        Args:
            early_segments: List of early transcript segments

        Returns:
            Dictionary with content analysis results
        """
        if not early_segments:
            return {
                "combined_text": "",
                "word_count": 0,
                "segment_count": 0,
                "question_count": 0,
                "question_density": 0.0,
                "first_word": None,
                "first_text": "",
            }

        # Get first segment text for first word analysis
        first_text = early_segments[0].get("text", "").strip()
        first_word = None
        if first_text:
            # Extract first word, removing punctuation
            first_token = first_text.split()[0] if first_text.split() else ""
            if first_token:
                # Remove trailing punctuation (comma, colon, semicolon, period)
                first_word = first_token.rstrip(",:;.").lower()

        # Combine all text
        texts = [segment.get("text", "") for segment in early_segments]
        combined_text = " ".join(texts).lower()

        # Count words
        words = combined_text.split()
        word_count = len(words)

        # Count questions
        question_count = 0
        for text in texts:
            text_lower = text.lower().strip()
            if text_lower.endswith("?"):
                question_count += 1
            elif any(
                text_lower.startswith(word + " ")
                for word in ["what", "why", "how", "when", "where", "who", "which"]
            ):
                question_count += 1

        question_density = (
            question_count / len(early_segments) if early_segments else 0.0
        )

        return {
            "combined_text": combined_text,
            "word_count": word_count,
            "segment_count": len(early_segments),
            "question_count": question_count,
            "question_density": question_density,
            "first_word": first_word,
            "first_text": first_text,
        }

    def _detect_tag_patterns(
        self, text: str, first_word: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect tag patterns in text.

        Args:
            text: Combined text from early segments
            first_word: First word of the transcript (for direct tag matching)

        Returns:
            Dictionary mapping tag names to detection results
        """
        tag_results = {}

        for tag_name, patterns in TAG_PATTERNS.items():
            matches = []
            match_count = 0
            indicators = []

            # Check if first word directly matches the tag name
            if first_word and first_word == tag_name.lower():
                match_count += 1
                matches.append(first_word)
                indicators.append("first_word_match")
                # High confidence for direct first word match
                base_confidence = 0.95
            else:
                # Use pattern matching
                for pattern in patterns:
                    pattern_matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in pattern_matches:
                        matches.append(match.group())
                        match_count += 1

                # Calculate confidence based on match count and pattern coverage
                if match_count > 0:
                    # Base confidence from match count
                    base_confidence = min(0.9, 0.5 + (match_count * 0.1))

                    # Boost confidence if multiple patterns match
                    if match_count >= 2:
                        base_confidence = min(0.95, base_confidence + 0.1)
                else:
                    base_confidence = 0.0

            if match_count > 0:
                if "first_word_match" not in indicators:
                    indicators.append("keyword_match")

                tag_results[tag_name] = {
                    "confidence": base_confidence,
                    "match_count": match_count,
                    "matches": matches[:5],  # Limit to first 5 matches
                    "indicators": indicators,
                }
            else:
                tag_results[tag_name] = {
                    "confidence": 0.0,
                    "match_count": 0,
                    "matches": [],
                    "indicators": [],
                }

        return tag_results

    def _classify_dialogue_acts(
        self, early_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Classify dialogue acts for early segments.

        Args:
            early_segments: List of early transcript segments

        Returns:
            Dictionary with dialogue act analysis
        """
        # Lazy import to avoid circular dependency
        from transcriptx.core.analysis.acts import classify_utterance

        if not early_segments:
            return {"act_types": {}, "question_acts": 0, "suggestion_acts": 0}

        act_types: Counter[str] = Counter()
        question_acts = 0
        suggestion_acts = 0

        for segment in early_segments:
            text = segment.get("text", "")
            if not text.strip():
                continue

            try:
                act_result = classify_utterance(text)
                act_type = act_result.get("act_type", "statement")
                act_types[act_type] += 1

                if act_type == "question":
                    question_acts += 1
                elif act_type == "suggestion":
                    suggestion_acts += 1
            except Exception as e:
                # If classification fails, continue
                self.logger.debug(
                    f"Dialogue act classification failed for segment: {e}"
                )
                continue

        return {
            "act_types": dict(act_types),
            "question_acts": question_acts,
            "suggestion_acts": suggestion_acts,
            "total_classified": len(early_segments),
        }

    def _calculate_final_tags(
        self,
        tag_results: Dict[str, Dict[str, Any]],
        dialogue_acts: Dict[str, Any],
        content_analysis: Dict[str, Any],
    ) -> tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Calculate final tags by combining all evidence.

        Args:
            tag_results: Pattern detection results
            dialogue_acts: Dialogue act classification results
            content_analysis: Content analysis results

        Returns:
            Tuple of (final_tags_list, tag_details_dict)
        """
        final_tags = []
        tag_details = {}

        # Process each potential tag
        for tag_name, tag_data in tag_results.items():
            confidence = tag_data.get("confidence", 0.0)
            indicators = tag_data.get("indicators", []).copy()

            # Adjust confidence based on dialogue acts
            if tag_name == "question":
                question_acts = dialogue_acts.get("question_acts", 0)
                question_density = content_analysis.get("question_density", 0.0)

                if question_acts > 0:
                    confidence = max(confidence, 0.7)
                    indicators.append("dialogue_act")

                if question_density > 0.3:
                    confidence = min(0.95, confidence + 0.15)
                    indicators.append("high_question_density")

            elif tag_name == "idea" or tag_name == "todo":
                suggestion_acts = dialogue_acts.get("suggestion_acts", 0)
                if suggestion_acts > 0:
                    confidence = min(0.95, confidence + 0.1)
                    indicators.append("dialogue_act")

            # Include tag if confidence meets threshold
            if confidence >= self.min_confidence:
                final_tags.append(tag_name)
                tag_details[tag_name] = {
                    "confidence": round(confidence, 2),
                    "indicators": indicators,
                    "match_count": tag_data.get("match_count", 0),
                }

        # Sort tags by confidence (highest first)
        final_tags.sort(key=lambda t: tag_details[t]["confidence"], reverse=True)

        return final_tags, tag_details

    def _calculate_analysis_window(self, early_segments: List[Dict[str, Any]]) -> float:
        """
        Calculate the time window covered by early segments.

        Args:
            early_segments: List of early segments

        Returns:
            Time window in seconds
        """
        if not early_segments:
            return 0.0

        # Get last segment's end time
        last_segment = early_segments[-1]
        end_time = last_segment.get("end", last_segment.get("start", 0.0))

        # Get first segment's start time
        first_segment = early_segments[0]
        start_time = first_segment.get("start", 0.0)

        return float(max(0.0, end_time - start_time))


def extract_tags(
    transcript_data: List[Dict[str, Any]],
    early_segments: Optional[List[Dict[str, Any]]] = None,
    audio_metadata: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to extract tags from transcript.

    Args:
        transcript_data: List of transcript segments
        early_segments: Optional pre-filtered early segments
        audio_metadata: Optional audio metadata
        config: Optional configuration

    Returns:
        Dictionary with tags, tag_details, and analysis metadata
    """
    extractor = TagExtractor(config)
    return extractor.extract_tags(transcript_data, early_segments, audio_metadata)
