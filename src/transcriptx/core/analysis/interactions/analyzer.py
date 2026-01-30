"""Interaction detection and analysis logic."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.utils.notifications import notify_user


class SpeakerInteractionAnalyzer:
    """
    Analyzes speaker interactions in transcript segments.

    This class provides comprehensive analysis of speaker interactions including
    interruption detection, response tracking, and pattern analysis. It uses
    configurable thresholds to identify different types of interactions.
    """

    def __init__(
        self,
        overlap_threshold: float = 0.5,
        min_gap: float = 0.1,
        min_segment_length: float = 0.5,
        response_threshold: float = 2.0,
        include_responses: bool = True,
        include_overlaps: bool = True,
    ):
        """
        Initialize the speaker interaction analyzer with configurable parameters.

        Args:
            overlap_threshold: Maximum gap (seconds) to consider as interruption
            min_gap: Minimum gap (seconds) to consider as interruption
            min_segment_length: Minimum segment length (seconds) to consider
            response_threshold: Maximum gap (seconds) to consider as response
            include_responses: Whether to detect response interactions
            include_overlaps: Whether to detect overlap interruptions
        """
        self.overlap_threshold = overlap_threshold
        self.min_gap = min_gap
        self.min_segment_length = min_segment_length
        self.response_threshold = response_threshold
        self.include_responses = include_responses
        self.include_overlaps = include_overlaps

    def detect_interactions(self, segments: list[dict]) -> list[InteractionEvent]:
        """
        Detect all types of speaker interactions in transcript segments.

        This method analyzes consecutive segments to identify interruptions and responses.
        It uses configurable thresholds to distinguish between different interaction types.

        Args:
            segments: List of transcript segments with speaker, start, end, text

        Returns:
            List of InteractionEvent objects representing detected interactions
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        interactions = []

        # Remove segment limit: always process all segments
        # Sort segments by start time to ensure chronological analysis
        sorted_segments = sorted(segments, key=lambda x: x.get("start", 0))
        notify_user(
            f"🔍 Analyzing {len(sorted_segments)} segments for interactions...",
            technical=False,
            section="interactions",
        )

        # Analyze consecutive segment pairs for interactions
        for i in range(len(sorted_segments) - 1):
            # Progress indicator for large transcripts
            if i % 1000 == 0 and i > 0:
                notify_user(
                    f"   Processed {i}/{len(sorted_segments)} segments...",
                    technical=True,
                    section="interactions",
                )

            current_seg = sorted_segments[i]
            next_seg = sorted_segments[i + 1]

            # Skip segments that are too short (likely noise)
            current_duration = current_seg.get("end", 0) - current_seg.get("start", 0)
            next_duration = next_seg.get("end", 0) - next_seg.get("start", 0)

            if (
                current_duration < self.min_segment_length
                or next_duration < self.min_segment_length
            ):
                continue

            current_info = extract_speaker_info(current_seg)
            next_info = extract_speaker_info(next_seg)
            if current_info is None or next_info is None:
                continue

            # Use grouping_key to compare (handles same-name speakers)
            if current_info.grouping_key == next_info.grouping_key:
                continue

            current_speaker = get_speaker_display_name(
                current_info.grouping_key, [current_seg], sorted_segments
            )
            next_speaker = get_speaker_display_name(
                next_info.grouping_key, [next_seg], sorted_segments
            )

            # Extract timing information
            current_start = current_seg.get("start", 0)
            current_end = current_seg.get("end", 0)
            next_start = next_seg.get("start", 0)
            next_end = next_seg.get("end", 0)

            # Calculate gap and overlap between segments
            gap = next_start - current_end
            overlap = (
                min(current_end, next_end) - next_start if next_start < current_end else 0
            )

            # Detect interruption types based on overlap and gap thresholds
            if self.include_overlaps and overlap > 0 and overlap >= self.min_gap:
                # Overlap interruption: speaker B starts while speaker A is still talking
                interactions.append(
                    InteractionEvent(
                        timestamp=next_start,
                        speaker_a=current_speaker,  # Current speaker is interrupted
                        speaker_b=next_speaker,  # Next speaker is the interrupter
                        interaction_type="interruption_overlap",
                        speaker_a_text=current_seg.get("text", ""),
                        speaker_b_text=next_seg.get("text", ""),
                        gap_before=0,
                        overlap=overlap,
                        speaker_a_start=current_start,
                        speaker_a_end=current_end,
                        speaker_b_start=next_start,
                        speaker_b_end=next_end,
                    )
                )
            elif self.include_overlaps and gap > 0 and gap <= self.overlap_threshold:
                # Gap interruption: speaker B starts very quickly after speaker A
                interactions.append(
                    InteractionEvent(
                        timestamp=next_start,
                        speaker_a=current_speaker,  # Current speaker is interrupted
                        speaker_b=next_speaker,  # Next speaker is the interrupter
                        interaction_type="interruption_gap",
                        speaker_a_text=current_seg.get("text", ""),
                        speaker_b_text=next_seg.get("text", ""),
                        gap_before=gap,
                        overlap=0,
                        speaker_a_start=current_start,
                        speaker_a_end=current_end,
                        speaker_b_start=next_start,
                        speaker_b_end=next_end,
                    )
                )

            # Detect responses: when speaker B responds to speaker A within threshold
            if self.include_responses and gap > 0 and gap <= self.response_threshold:
                interactions.append(
                    InteractionEvent(
                        timestamp=next_start,
                        speaker_a=current_speaker,
                        speaker_b=next_speaker,
                        interaction_type="response",
                        speaker_a_text=current_seg.get("text", ""),
                        speaker_b_text=next_seg.get("text", ""),
                        gap_before=gap,
                        overlap=0,
                        speaker_a_start=current_start,
                        speaker_a_end=current_end,
                        speaker_b_start=next_start,
                        speaker_b_end=next_end,
                    )
                )

        notify_user(f"✅ Found {len(interactions)} interactions", technical=False)
        return interactions

    def analyze_interactions(
        self, interactions: list[InteractionEvent], speaker_map: dict[str, str] = None
    ) -> dict[str, Any]:
        """
        Analyze interaction patterns and generate comprehensive statistics.

        This method processes detected interactions to calculate various metrics
        including interruption counts, response patterns, and speaker dominance scores.

        Args:
            interactions: List of InteractionEvent objects
            speaker_map: Mapping from speaker IDs to names (deprecated, kept for backward compatibility, not used)

        Returns:
            Dictionary containing comprehensive analysis results
        """
        import warnings

        if speaker_map is not None:
            warnings.warn(
                "speaker_map parameter is deprecated. Speaker names come from InteractionEvent objects.",
                DeprecationWarning,
                stacklevel=2,
            )
        from transcriptx.utils.text_utils import is_named_speaker

        # Initialize counters for different interaction types
        interruption_initiated = defaultdict(int)
        interruption_received = defaultdict(int)
        responses_initiated = defaultdict(int)
        responses_received = defaultdict(int)
        interaction_matrix = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        # Process each interaction to build statistics
        for event in interactions:
            # Event already contains display names from detect_interactions
            speaker_a = event.speaker_a
            speaker_b = event.speaker_b

            # Skip interactions involving unnamed speakers
            if (
                not speaker_a
                or not speaker_b
                or not is_named_speaker(speaker_a)
                or not is_named_speaker(speaker_b)
            ):
                continue

            # Categorize and count interactions
            if event.interaction_type.startswith("interruption"):
                interruption_initiated[speaker_a] += 1
                interruption_received[speaker_b] += 1
                interaction_matrix[speaker_a][speaker_b]["interruptions"] += 1
            elif event.interaction_type == "response":
                responses_initiated[speaker_a] += 1
                responses_received[speaker_b] += 1
                interaction_matrix[speaker_a][speaker_b]["responses"] += 1

        # Calculate net balances for each speaker
        all_speakers = (
            set(interruption_initiated.keys())
            | set(interruption_received.keys())
            | set(responses_initiated.keys())
            | set(responses_received.keys())
        )

        net_interruption_balance = {}
        net_response_balance = {}
        total_interactions = {}

        for speaker in all_speakers:
            net_interruption_balance[speaker] = (
                interruption_initiated[speaker] - interruption_received[speaker]
            )
            net_response_balance[speaker] = (
                responses_initiated[speaker] - responses_received[speaker]
            )
            total_interactions[speaker] = (
                interruption_initiated[speaker]
                + interruption_received[speaker]
                + responses_initiated[speaker]
                + responses_received[speaker]
            )

        # Calculate dominance scores (positive = dominant, negative = submissive)
        dominance_scores = {}
        for speaker in all_speakers:
            total_initiated = (
                interruption_initiated[speaker] + responses_initiated[speaker]
            )
            total_received = (
                interruption_received[speaker] + responses_received[speaker]
            )
            total = total_initiated + total_received
            if total > 0:
                dominance_scores[speaker] = (total_initiated - total_received) / total
            else:
                dominance_scores[speaker] = 0

        return {
            "interruption_initiated": dict(interruption_initiated),
            "interruption_received": dict(interruption_received),
            "responses_initiated": dict(responses_initiated),
            "responses_received": dict(responses_received),
            "net_interruption_balance": net_interruption_balance,
            "net_response_balance": net_response_balance,
            "total_interactions": total_interactions,
            "dominance_scores": dominance_scores,
            "interaction_matrix": {
                k: {k2: dict(v2) for k2, v2 in v.items()}
                for k, v in interaction_matrix.items()
            },
            "total_interactions_count": len(interactions),
            "unique_speakers": len(all_speakers),
            "interaction_types": Counter(
                event.interaction_type for event in interactions
            ),
        }
