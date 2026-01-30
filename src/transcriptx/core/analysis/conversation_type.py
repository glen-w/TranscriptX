"""
Conversation Type Detection Module for TranscriptX.

This module provides functionality to automatically detect the type of conversation
based on speaker count and transcript content analysis. It classifies conversations
as: conversation (2-3 people), meeting (4+ people), or voice note (1 person).

Key Features:
- Hybrid detection using speaker count + transcript content analysis
- Keyword-based content analysis
- Structure pattern detection
- Confidence scoring
"""

from typing import Any, Dict, List, Optional
from collections import Counter

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Conversation type constants
CONVERSATION_TYPE_CONVERSATION = "conversation"
CONVERSATION_TYPE_MEETING = "meeting"
CONVERSATION_TYPE_VOICE_NOTE = "voice_note"

# Content indicators for different conversation types
MEETING_KEYWORDS = [
    "agenda",
    "minutes",
    "action items",
    "action item",
    "let's discuss",
    "meeting",
    "presentation",
    "slide",
    "present",
    "review",
    "status update",
    "quarterly",
    "weekly",
    "daily standup",
    "standup",
    "sprint",
    "retrospective",
]

VOICE_NOTE_KEYWORDS = [
    "let me think",
    "i'm thinking",
    "i'm reflecting",
    "looking back",
    "personal note",
    "reminder to myself",
    "note to self",
    "voice memo",
]

CONVERSATION_KEYWORDS = [
    "chat",
    "talk",
    "discuss",
    "conversation",
    "catch up",
    "check in",
]

# Question words for question density analysis
QUESTION_WORDS = [
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "can",
    "could",
    "should",
    "would",
]


class ConversationTypeDetector:
    """
    Detects conversation type using hybrid approach: speaker count + content analysis.

    This class analyzes transcripts to determine if they are:
    - voice_note: Single speaker
    - conversation: 2-3 speakers with casual structure
    - meeting: 4+ speakers or structured content indicating formal meeting
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the conversation type detector.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = get_logger()

    def detect_type(
        self,
        transcript_data: List[Dict[str, Any]],
        speaker_count: int,
        audio_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Detect conversation type using hybrid approach.

        Args:
            transcript_data: List of transcript segments with 'speaker' and 'text' fields
            speaker_count: Number of unique speakers
            audio_metadata: Optional audio metadata (duration, etc.)

        Returns:
            Dictionary with type, confidence, and evidence
        """
        try:
            # Step 1: Initial classification by speaker count
            speaker_based_type, speaker_confidence = self._detect_by_speaker_count(
                speaker_count
            )

            # Step 2: Content analysis
            content_analysis = self._analyze_transcript_content(transcript_data)

            # Step 3: Structure pattern analysis
            structure_score = self._analyze_structure_patterns(
                transcript_data, speaker_count
            )

            # Step 4: Combine evidence for final classification
            final_type, confidence, evidence = self._calculate_final_type(
                speaker_based_type,
                speaker_confidence,
                content_analysis,
                structure_score,
                speaker_count,
            )

            return {"type": final_type, "confidence": confidence, "evidence": evidence}

        except Exception as e:
            self.logger.error(f"Error in conversation type detection: {e}")
            # Fallback to speaker count only
            type_result, confidence = self._detect_by_speaker_count(speaker_count)
            return {
                "type": type_result,
                "confidence": confidence * 0.7,  # Lower confidence due to error
                "evidence": {
                    "speaker_count": speaker_count,
                    "error": str(e),
                    "fallback": True,
                },
            }

    def _detect_by_speaker_count(self, speaker_count: int) -> tuple[str, float]:
        """
        Initial classification based on speaker count.

        Args:
            speaker_count: Number of unique speakers

        Returns:
            Tuple of (type, confidence)
        """
        if speaker_count == 1:
            return CONVERSATION_TYPE_VOICE_NOTE, 0.95
        elif speaker_count == 2 or speaker_count == 3:
            return CONVERSATION_TYPE_CONVERSATION, 0.75
        elif speaker_count >= 4:
            return CONVERSATION_TYPE_MEETING, 0.70
        else:
            # Edge case: 0 speakers (shouldn't happen, but handle gracefully)
            return CONVERSATION_TYPE_VOICE_NOTE, 0.50

    def _analyze_transcript_content(
        self, transcript_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze transcript content for keywords and patterns.

        Args:
            transcript_data: List of transcript segments

        Returns:
            Dictionary with content analysis results
        """
        if not transcript_data:
            return {
                "meeting_indicators": 0,
                "voice_note_indicators": 0,
                "conversation_indicators": 0,
                "question_count": 0,
                "total_segments": 0,
            }

        # Combine all text
        all_text = " ".join(
            [segment.get("text", "") for segment in transcript_data]
        ).lower()

        # Count keyword matches
        meeting_indicators = sum(
            1 for keyword in MEETING_KEYWORDS if keyword in all_text
        )
        voice_note_indicators = sum(
            1 for keyword in VOICE_NOTE_KEYWORDS if keyword in all_text
        )
        conversation_indicators = sum(
            1 for keyword in CONVERSATION_KEYWORDS if keyword in all_text
        )

        # Count questions
        question_count = 0
        for segment in transcript_data:
            text = segment.get("text", "").lower().strip()
            # Check if ends with question mark
            if text.endswith("?"):
                question_count += 1
            # Check if starts with question word
            elif any(text.startswith(word + " ") for word in QUESTION_WORDS):
                question_count += 1

        return {
            "meeting_indicators": meeting_indicators,
            "voice_note_indicators": voice_note_indicators,
            "conversation_indicators": conversation_indicators,
            "question_count": question_count,
            "total_segments": len(transcript_data),
            "question_density": (
                question_count / len(transcript_data) if transcript_data else 0.0
            ),
        }

    def _analyze_structure_patterns(
        self, transcript_data: List[Dict[str, Any]], speaker_count: int
    ) -> float:
        """
        Analyze structure patterns to determine formality.

        Args:
            transcript_data: List of transcript segments
            speaker_count: Number of speakers

        Returns:
            Structure score (0.0-1.0), higher = more structured/formal
        """
        if not transcript_data or speaker_count == 0:
            return 0.5

        # Calculate turn-taking patterns
        speakers = [segment.get("speaker", "") for segment in transcript_data]
        speaker_changes = sum(
            1 for i in range(1, len(speakers)) if speakers[i] != speakers[i - 1]
        )

        # More speaker changes relative to segments = more structured
        change_ratio = (
            speaker_changes / len(transcript_data) if transcript_data else 0.0
        )

        # Calculate speaking time distribution
        speaker_durations: Counter[str] = Counter()
        for segment in transcript_data:
            speaker = segment.get("speaker", "")
            start = segment.get("start", 0.0)
            end = segment.get("end", start)
            duration = end - start
            speaker_durations[speaker] += duration

        # More even distribution = more structured (meeting-like)
        if speaker_durations:
            durations = list(speaker_durations.values())
            max_duration = max(durations)
            min_duration = min(durations)
            if max_duration > 0:
                evenness = 1.0 - (max_duration - min_duration) / max_duration
            else:
                evenness = 0.5
        else:
            evenness = 0.5

        # Combine metrics
        structure_score = change_ratio * 0.5 + evenness * 0.5

        return min(1.0, max(0.0, structure_score))

    def _calculate_final_type(
        self,
        speaker_based_type: str,
        speaker_confidence: float,
        content_analysis: Dict[str, Any],
        structure_score: float,
        speaker_count: int,
    ) -> tuple[str, float, Dict[str, Any]]:
        """
        Calculate final type by combining all evidence.

        Args:
            speaker_based_type: Initial type from speaker count
            speaker_confidence: Confidence from speaker count
            content_analysis: Content analysis results
            structure_score: Structure pattern score
            speaker_count: Number of speakers

        Returns:
            Tuple of (final_type, confidence, evidence_dict)
        """
        evidence = {
            "speaker_count": speaker_count,
            "speaker_based_type": speaker_based_type,
            "content_indicators": content_analysis,
            "structure_score": structure_score,
        }

        # Start with speaker-based classification
        final_type = speaker_based_type
        base_confidence = speaker_confidence

        # Adjust based on content indicators
        meeting_indicators = content_analysis.get("meeting_indicators", 0)
        voice_note_indicators = content_analysis.get("voice_note_indicators", 0)
        question_density = content_analysis.get("question_density", 0.0)

        # Strong content indicators can override speaker count
        if meeting_indicators >= 3 and speaker_count >= 2:
            final_type = CONVERSATION_TYPE_MEETING
            base_confidence = min(0.95, base_confidence + 0.2)
            evidence["content_override"] = "meeting_keywords"

        elif voice_note_indicators >= 2 and speaker_count == 1:
            final_type = CONVERSATION_TYPE_VOICE_NOTE
            base_confidence = min(0.95, base_confidence + 0.15)
            evidence["content_override"] = "voice_note_keywords"

        # Structure score adjustments
        if structure_score > 0.7 and speaker_count >= 3:
            # High structure + multiple speakers = likely meeting
            if final_type == CONVERSATION_TYPE_CONVERSATION:
                final_type = CONVERSATION_TYPE_MEETING
                base_confidence = min(0.90, base_confidence + 0.15)
                evidence["structure_override"] = True

        elif structure_score < 0.3 and speaker_count <= 3:
            # Low structure + few speakers = likely casual conversation
            if final_type == CONVERSATION_TYPE_MEETING:
                final_type = CONVERSATION_TYPE_CONVERSATION
                base_confidence = min(0.85, base_confidence + 0.1)
                evidence["structure_override"] = True

        # Question density: high = more interactive (conversation or meeting)
        if question_density > 0.3:
            if final_type == CONVERSATION_TYPE_VOICE_NOTE and speaker_count > 1:
                final_type = CONVERSATION_TYPE_CONVERSATION
                base_confidence = min(0.90, base_confidence + 0.1)
                evidence["question_density_override"] = True

        # Ensure confidence is reasonable
        final_confidence = min(0.95, max(0.5, base_confidence))

        return final_type, final_confidence, evidence


def detect_conversation_type(
    transcript_data: List[Dict[str, Any]],
    speaker_count: int,
    audio_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to detect conversation type.

    Args:
        transcript_data: List of transcript segments
        speaker_count: Number of unique speakers
        audio_metadata: Optional audio metadata

    Returns:
        Dictionary with type, confidence, and evidence
    """
    detector = ConversationTypeDetector()
    return detector.detect_type(transcript_data, speaker_count, audio_metadata)
