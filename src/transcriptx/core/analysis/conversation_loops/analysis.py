"""
Conversation Loop Detection Module for TranscriptX.

This module detects 3-turn conversation loops in transcripts where:
1. Speaker A makes a turn (question or directive)
2. Speaker B replies (any type)
3. Speaker A responds again (any type)

It provides comprehensive analysis of conversation patterns and speaker interactions.
"""

import numpy as np
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List

import networkx as nx

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.acts import classify_utterance
from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    save_global_data,
    save_speaker_data,
)
from transcriptx.core.analysis.sentiment import score_sentiment
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    NetworkGraphSpec,
    ScatterSeries,
    ScatterSpec,
)



@dataclass
class ConversationLoop:
    """
    Represents a 3-turn conversation loop.

    This dataclass captures all relevant information about a conversation loop,
    including the speakers, their acts, timestamps, and sentiment scores.
    """

    loop_id: int
    speaker_a: str
    speaker_b: str
    turn_1_index: int
    turn_2_index: int
    turn_3_index: int
    turn_1_text: str
    turn_2_text: str
    turn_3_text: str
    turn_1_act: str
    turn_2_act: str
    turn_3_act: str
    turn_1_timestamp: float
    turn_2_timestamp: float
    turn_3_timestamp: float
    turn_1_sentiment: float
    turn_2_sentiment: float
    turn_3_sentiment: float
    gap_1_2: float  # Gap between turn 1 and 2
    gap_2_3: float  # Gap between turn 2 and 3


class ConversationLoopDetector:
    """
    Detects 3-turn conversation loops in transcript segments.

    This class implements the logic to identify conversation loops where
    Speaker A asks a question or makes a directive, Speaker B responds,
    and Speaker A responds again.
    """

    def __init__(
        self, max_intermediate_turns: int = 2, exclude_monologues: bool = True
    ):
        """
        Initialize the conversation loop detector.

        Args:
            max_intermediate_turns: Maximum number of intermediate turns allowed between loop turns
            exclude_monologues: Whether to exclude loops where Speaker A repeats themselves
        """
        self.max_intermediate_turns = max_intermediate_turns
        self.exclude_monologues = exclude_monologues

    def detect_loops(
        self, segments: list[dict], speaker_map: dict[str, str] = None
    ) -> list[ConversationLoop]:
        """
        Detect all 3-turn conversation loops in the transcript.

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)

        Returns:
            List of ConversationLoop objects representing detected loops
        """
        import warnings

        if speaker_map is not None:
            warnings.warn(
                "speaker_map parameter is deprecated. Speaker identification now uses "
                "speaker_db_id from segments directly.",
                DeprecationWarning,
                stacklevel=2,
            )
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
            SpeakerInfo,
        )

        def resolve_speaker(segment: dict, all_segments: list[dict]):
            info = extract_speaker_info(segment)
            if info is None and speaker_map:
                speaker_key = segment.get("speaker")
                mapped = speaker_map.get(speaker_key) if speaker_key else None
                if mapped:
                    info = SpeakerInfo(
                        grouping_key=speaker_key, display_name=mapped, db_id=None
                    )
                    return info, mapped
                return None, None

            if info is None:
                return None, None

            display_name = get_speaker_display_name(
                info.grouping_key, [segment], all_segments
            )
            if not is_named_speaker(display_name) and speaker_map:
                speaker_key = segment.get("speaker")
                mapped = speaker_map.get(speaker_key) if speaker_key else None
                if mapped:
                    return info, mapped
            return info, display_name

        loops = []
        loop_id = 0

        # Sort segments by start time
        sorted_segments = sorted(segments, key=lambda x: x.get("start", 0))

        # Process each potential starting turn
        for i in range(len(sorted_segments) - 2):
            turn_1 = sorted_segments[i]
            speaker_1_info, speaker_1 = resolve_speaker(turn_1, sorted_segments)
            if speaker_1_info is None:
                continue

            if not is_named_speaker(speaker_1):
                continue

            # Check if turn 1 is a question or directive
            turn_1_text = turn_1.get("text", "")
            turn_1_act = classify_utterance(turn_1_text)

            if turn_1_act not in ["question", "suggestion"]:
                continue

            # Look for turn 2 (response from different speaker)
            for j in range(
                i + 1,
                min(i + 1 + self.max_intermediate_turns + 1, len(sorted_segments) - 1),
            ):
                turn_2 = sorted_segments[j]
                speaker_2_info, speaker_2 = resolve_speaker(turn_2, sorted_segments)
                if speaker_2_info is None:
                    continue

                if not is_named_speaker(speaker_2):
                    continue

                # Turn 2 must be from a different speaker (check by grouping_key to handle same names)
                if speaker_2_info.grouping_key == speaker_1_info.grouping_key:
                    continue

                turn_2_text = turn_2.get("text", "")
                turn_2_act = classify_utterance(turn_2_text)

                # Look for turn 3 (response from original speaker)
                for k in range(
                    j + 1,
                    min(j + 1 + self.max_intermediate_turns + 1, len(sorted_segments)),
                ):
                    turn_3 = sorted_segments[k]
                    speaker_3_info, speaker_3 = resolve_speaker(turn_3, sorted_segments)
                    if speaker_3_info is None:
                        continue

                    if not is_named_speaker(speaker_3):
                        continue

                    # Turn 3 must be from the original speaker (Speaker A) - check by grouping_key
                    if speaker_3_info.grouping_key != speaker_1_info.grouping_key:
                        continue

                    turn_3_text = turn_3.get("text", "")
                    turn_3_act = classify_utterance(turn_3_text)

                    # Check for monologue exclusion
                    if self.exclude_monologues:
                        # Simple check: if turn 1 and turn 3 are very similar, exclude
                        if self._is_monologue(turn_1_text, turn_3_text):
                            continue

                    # Calculate gaps and sentiment scores
                    gap_1_2 = turn_2.get("start", 0) - turn_1.get("end", 0)
                    gap_2_3 = turn_3.get("start", 0) - turn_2.get("end", 0)

                    # Handle both dict and float returns (for mocking compatibility)
                    sentiment_1 = score_sentiment(turn_1_text)
                    sentiment_2 = score_sentiment(turn_2_text)
                    sentiment_3 = score_sentiment(turn_3_text)
                    turn_1_sentiment = (
                        sentiment_1["compound"]
                        if isinstance(sentiment_1, dict)
                        else float(sentiment_1)
                    )
                    turn_2_sentiment = (
                        sentiment_2["compound"]
                        if isinstance(sentiment_2, dict)
                        else float(sentiment_2)
                    )
                    turn_3_sentiment = (
                        sentiment_3["compound"]
                        if isinstance(sentiment_3, dict)
                        else float(sentiment_3)
                    )

                    # Create conversation loop
                    loop = ConversationLoop(
                        loop_id=loop_id,
                        speaker_a=speaker_1,
                        speaker_b=speaker_2,
                        turn_1_index=i,
                        turn_2_index=j,
                        turn_3_index=k,
                        turn_1_text=turn_1_text,
                        turn_2_text=turn_2_text,
                        turn_3_text=turn_3_text,
                        turn_1_act=turn_1_act,
                        turn_2_act=turn_2_act,
                        turn_3_act=turn_3_act,
                        turn_1_timestamp=turn_1.get("start", 0),
                        turn_2_timestamp=turn_2.get("start", 0),
                        turn_3_timestamp=turn_3.get("start", 0),
                        turn_1_sentiment=turn_1_sentiment,
                        turn_2_sentiment=turn_2_sentiment,
                        turn_3_sentiment=turn_3_sentiment,
                        gap_1_2=gap_1_2,
                        gap_2_3=gap_2_3,
                    )

                    loops.append(loop)
                    loop_id += 1

                    # Only take the first valid turn 3 for this turn 1/turn 2 pair
                    break

        return loops

    def _is_monologue(self, text1: str, text3: str) -> bool:
        """
        Check if two texts are too similar (indicating a monologue).

        Args:
            text1: First text
            text3: Third text

        Returns:
            True if texts are too similar (monologue)
        """
        # Simple similarity check: if more than 70% of words are the same
        words1 = set(text1.lower().split())
        words3 = set(text3.lower().split())

        if not words1 or not words3:
            return False

        intersection = words1.intersection(words3)
        union = words1.union(words3)

        similarity = len(intersection) / len(union)
        return similarity > 0.7


class ConversationLoopsAnalysis(AnalysisModule):
    """
    Conversation loop detection and analysis module.

    This module detects 3-turn conversation loops and provides comprehensive
    analysis of conversation patterns.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the conversation loops analysis module."""
        super().__init__(config)
        self.module_name = "conversation_loops"
        self.max_intermediate_turns = self.config.get("max_intermediate_turns", 2)
        self.exclude_monologues = self.config.get("exclude_monologues", True)

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform conversation loop analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing conversation loop analysis results
        """
        # Initialize detector
        detector = ConversationLoopDetector(
            max_intermediate_turns=self.max_intermediate_turns,
            exclude_monologues=self.exclude_monologues,
        )

        # Detect loops
        loops = detector.detect_loops(segments, speaker_map)

        # Analyze loop patterns
        analysis_results = analyze_loop_patterns(loops, speaker_map or {})

        # Add loops to results
        analysis_results["loops"] = loops
        analysis_results["conversation_loops"] = loops  # Alias for compatibility

        # Add summary/statistics aliases for compatibility
        analysis_results["summary"] = {
            "total_loops": analysis_results.get("total_loops", 0),
            "unique_speaker_pairs": analysis_results.get("unique_speaker_pairs", 0),
            "speaker_pair_counts": analysis_results.get("speaker_pair_counts", {}),
            "act_patterns": analysis_results.get("act_patterns", {}),
            "gap_statistics": analysis_results.get("gap_statistics", {}),
            "sentiment_statistics": analysis_results.get("sentiment_statistics", {}),
        }
        analysis_results["statistics"] = analysis_results["summary"]  # Alias

        return analysis_results

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        loops = results.get("loops", [])
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()

        # Save loop data
        csv_rows = []
        for loop in loops:
            row = {
                "loop_id": loop.loop_id,
                "speaker_a": loop.speaker_a,
                "speaker_b": loop.speaker_b,
                "turn_1_index": loop.turn_1_index,
                "turn_2_index": loop.turn_2_index,
                "turn_3_index": loop.turn_3_index,
                "turn_1_text": (
                    loop.turn_1_text[:100] + "..."
                    if len(loop.turn_1_text) > 100
                    else loop.turn_1_text
                ),
                "turn_2_text": (
                    loop.turn_2_text[:100] + "..."
                    if len(loop.turn_2_text) > 100
                    else loop.turn_2_text
                ),
                "turn_3_text": (
                    loop.turn_3_text[:100] + "..."
                    if len(loop.turn_3_text) > 100
                    else loop.turn_3_text
                ),
                "turn_1_act": loop.turn_1_act,
                "turn_2_act": loop.turn_2_act,
                "turn_3_act": loop.turn_3_act,
                "turn_1_timestamp": loop.turn_1_timestamp,
                "turn_2_timestamp": loop.turn_2_timestamp,
                "turn_3_timestamp": loop.turn_3_timestamp,
                "turn_1_sentiment": loop.turn_1_sentiment,
                "turn_2_sentiment": loop.turn_2_sentiment,
                "turn_3_sentiment": loop.turn_3_sentiment,
                "gap_1_2": loop.gap_1_2,
                "gap_2_3": loop.gap_2_3,
            }
            csv_rows.append(row)

        # Save data
        output_service.save_data(csv_rows, "conversation_loops", format_type="csv")
        output_service.save_data(results, "conversation_loops", format_type="json")

        # Generate visualizations using existing functions
        if loops:
            self._create_loop_network(
                results, output_structure, base_name, output_service
            )
            self._create_loop_timeline(
                loops, None, output_structure, base_name, output_service
            )
            self._create_loop_act_analysis(
                loops, output_structure, base_name, output_service
            )

        # Create comprehensive summary
        self._create_analysis_summary(
            results, output_structure, base_name, output_service
        )

    def _create_loop_network(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create loop network visualization."""
        # Use existing create_loop_network function
        from transcriptx.core.analysis.conversation_loops import create_loop_network

        create_loop_network(
            analysis_results, output_structure, base_name, output_service=output_service
        )

    def _create_loop_timeline(
        self,
        loops: List[ConversationLoop],
        speaker_map: Dict[str, str] = None,
        output_structure=None,
        base_name: str = None,
        output_service: "OutputService" = None,
    ) -> None:
        """Create loop timeline visualization."""
        from transcriptx.core.analysis.conversation_loops import create_loop_timeline

        if output_structure is None and output_service is not None:
            output_structure = output_service.get_output_structure()
        if base_name is None and output_service is not None:
            base_name = output_service.base_name
        create_loop_timeline(
            loops,
            speaker_map,
            output_structure,
            base_name,
            output_service=output_service,
        )

    def _create_loop_act_analysis(
        self,
        loops: List[ConversationLoop],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create loop act analysis visualization."""
        from transcriptx.core.analysis.conversation_loops import (
            create_loop_act_analysis,
        )

        create_loop_act_analysis(
            loops, output_structure, base_name, output_service=output_service
        )

    def _create_analysis_summary(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create analysis summary."""
        from transcriptx.core.analysis.conversation_loops import create_analysis_summary

        create_analysis_summary(analysis_results, output_structure, base_name)

        # Also save summary using OutputService
        global_stats = {
            "total_loops": analysis_results.get("total_loops", 0),
            "unique_speaker_pairs": analysis_results.get("unique_speaker_pairs", 0),
        }
        output_service.save_summary(global_stats, {}, analysis_metadata={})


def analyze_conversation_loops(
    segments: list[dict],
    base_name: str,
    transcript_dir: str,
    **kwargs,
) -> dict[str, Any]:
    """
    Analyze conversation loops in transcript segments and generate comprehensive outputs.

    Args:
        segments: List of transcript segments
        base_name: Base name for output files
        transcript_dir: Directory to save outputs
        **kwargs: Additional arguments for ConversationLoopDetector

    Returns:
        Dictionary containing analysis results
    """

    # Create standardized output structure
    output_structure = create_standard_output_structure(
        transcript_dir, "conversation_loops"
    )

    # Initialize detector
    max_intermediate_turns = kwargs.get("max_intermediate_turns", 2)
    exclude_monologues = kwargs.get("exclude_monologues", True)

    detector = ConversationLoopDetector(
        max_intermediate_turns=max_intermediate_turns,
        exclude_monologues=exclude_monologues,
    )

    # Detect loops (speaker_map not used, detector uses extract_speaker_info)
    loops = detector.detect_loops(segments, None)

    # Analyze loop patterns (speaker_map not used, loops already have speaker names)
    analysis_results = analyze_loop_patterns(loops, None)

    # Save loop data (speaker_map not used, loops already have speaker names)
    save_loop_data(loops, None, output_structure, base_name)

    # Generate visualizations
    if loops:
        create_loop_network(analysis_results, output_structure, base_name)
        create_loop_timeline(loops, None, output_structure, base_name)
        create_loop_act_analysis(loops, output_structure, base_name)

    # Create comprehensive summary
    create_analysis_summary(analysis_results, output_structure, base_name)

    return analysis_results


def analyze_loop_patterns(
    loops: list[ConversationLoop], speaker_map: dict[str, str] = None
) -> dict[str, Any]:
    """
    Analyze patterns in detected conversation loops.

    Args:
        loops: List of ConversationLoop objects
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)

    Returns:
        Dictionary containing pattern analysis results
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker names come from ConversationLoop objects.",
            DeprecationWarning,
            stacklevel=2,
        )
    # Initialize counters
    speaker_pair_counts = defaultdict(int)
    act_patterns = defaultdict(int)
    gap_stats = defaultdict(list)
    sentiment_stats = defaultdict(list)

    # Process each loop
    for loop in loops:
        # Speaker pair analysis
        pair_key = f"{loop.speaker_a} ↔ {loop.speaker_b}"
        speaker_pair_counts[pair_key] += 1

        # Act pattern analysis
        act_pattern = f"{loop.turn_1_act} → {loop.turn_2_act} → {loop.turn_3_act}"
        act_patterns[act_pattern] += 1

        # Gap analysis
        gap_stats["gap_1_2"].append(loop.gap_1_2)
        gap_stats["gap_2_3"].append(loop.gap_2_3)

        # Sentiment analysis
        sentiment_stats["turn_1"].append(loop.turn_1_sentiment)
        sentiment_stats["turn_2"].append(loop.turn_2_sentiment)
        sentiment_stats["turn_3"].append(loop.turn_3_sentiment)

    # Calculate statistics
    analysis_results = {
        "total_loops": len(loops),
        "unique_speaker_pairs": len(speaker_pair_counts),
        "speaker_pair_counts": dict(speaker_pair_counts),
        "act_patterns": dict(act_patterns),
        "gap_statistics": {
            "gap_1_2": {
                "mean": np.mean(gap_stats["gap_1_2"]) if gap_stats["gap_1_2"] else 0,
                "std": np.std(gap_stats["gap_1_2"]) if gap_stats["gap_1_2"] else 0,
                "min": min(gap_stats["gap_1_2"]) if gap_stats["gap_1_2"] else 0,
                "max": max(gap_stats["gap_1_2"]) if gap_stats["gap_1_2"] else 0,
            },
            "gap_2_3": {
                "mean": np.mean(gap_stats["gap_2_3"]) if gap_stats["gap_2_3"] else 0,
                "std": np.std(gap_stats["gap_2_3"]) if gap_stats["gap_2_3"] else 0,
                "min": min(gap_stats["gap_2_3"]) if gap_stats["gap_2_3"] else 0,
                "max": max(gap_stats["gap_2_3"]) if gap_stats["gap_2_3"] else 0,
            },
        },
        "sentiment_statistics": {
            "turn_1": {
                "mean": (
                    np.mean(sentiment_stats["turn_1"])
                    if sentiment_stats["turn_1"]
                    else 0
                ),
                "std": (
                    np.std(sentiment_stats["turn_1"])
                    if sentiment_stats["turn_1"]
                    else 0
                ),
            },
            "turn_2": {
                "mean": (
                    np.mean(sentiment_stats["turn_2"])
                    if sentiment_stats["turn_2"]
                    else 0
                ),
                "std": (
                    np.std(sentiment_stats["turn_2"])
                    if sentiment_stats["turn_2"]
                    else 0
                ),
            },
            "turn_3": {
                "mean": (
                    np.mean(sentiment_stats["turn_3"])
                    if sentiment_stats["turn_3"]
                    else 0
                ),
                "std": (
                    np.std(sentiment_stats["turn_3"])
                    if sentiment_stats["turn_3"]
                    else 0
                ),
            },
        },
    }

    return analysis_results


def save_loop_data(
    loops: list[ConversationLoop],
    speaker_map: dict[str, str] = None,
    output_structure=None,
    base_name: str = None,
):
    """
    Save conversation loop data to standardized locations.

    Args:
        loops: List of ConversationLoop objects
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker names come from ConversationLoop objects.",
            DeprecationWarning,
            stacklevel=2,
        )
    # Prepare CSV data
    csv_rows = []
    for loop in loops:
        row = {
            "loop_id": loop.loop_id,
            "speaker_a": loop.speaker_a,
            "speaker_b": loop.speaker_b,
            "turn_1_index": loop.turn_1_index,
            "turn_2_index": loop.turn_2_index,
            "turn_3_index": loop.turn_3_index,
            "turn_1_text": (
                loop.turn_1_text[:100] + "..."
                if len(loop.turn_1_text) > 100
                else loop.turn_1_text
            ),
            "turn_2_text": (
                loop.turn_2_text[:100] + "..."
                if len(loop.turn_2_text) > 100
                else loop.turn_2_text
            ),
            "turn_3_text": (
                loop.turn_3_text[:100] + "..."
                if len(loop.turn_3_text) > 100
                else loop.turn_3_text
            ),
            "turn_1_act": loop.turn_1_act,
            "turn_2_act": loop.turn_2_act,
            "turn_3_act": loop.turn_3_act,
            "turn_1_timestamp": loop.turn_1_timestamp,
            "turn_2_timestamp": loop.turn_2_timestamp,
            "turn_3_timestamp": loop.turn_3_timestamp,
            "turn_1_sentiment": loop.turn_1_sentiment,
            "turn_2_sentiment": loop.turn_2_sentiment,
            "turn_3_sentiment": loop.turn_3_sentiment,
            "gap_1_2": loop.gap_1_2,
            "gap_2_3": loop.gap_2_3,
        }
        csv_rows.append(row)

    # Save global data
    save_global_data(csv_rows, output_structure, base_name, "conversation_loops", "csv")
    save_global_data(
        {"loops": [loop.__dict__ for loop in loops]},
        output_structure,
        base_name,
        "conversation_loops",
        "json",
    )

    # Create per-speaker breakdown
    speaker_loop_data = defaultdict(list)
    for loop in loops:
        # Add to both speakers' data
        for speaker in [loop.speaker_a, loop.speaker_b]:
            if not is_named_speaker(speaker):
                continue

            speaker_loop_data[speaker].append(
                {
                    "loop_id": loop.loop_id,
                    "other_speaker": (
                        loop.speaker_b if speaker == loop.speaker_a else loop.speaker_a
                    ),
                    "turn_1_act": loop.turn_1_act,
                    "turn_2_act": loop.turn_2_act,
                    "turn_3_act": loop.turn_3_act,
                    "turn_1_sentiment": loop.turn_1_sentiment,
                    "turn_2_sentiment": loop.turn_2_sentiment,
                    "turn_3_sentiment": loop.turn_3_sentiment,
                    "gap_1_2": loop.gap_1_2,
                    "gap_2_3": loop.gap_2_3,
                }
            )

    # Save per-speaker data
    for speaker, data in speaker_loop_data.items():
        save_speaker_data(
            data, output_structure, base_name, speaker, "conversation_loops", "csv"
        )
        save_speaker_data(
            {"loops": data},
            output_structure,
            base_name,
            speaker,
            "conversation_loops",
            "json",
        )


def create_loop_network(
    analysis_results: dict[str, Any],
    output_structure,
    base_name: str,
    output_service=None,
):
    """
    Create network plot of speaker pairs and their loop counts.

    Args:
        analysis_results: Analysis results dictionary
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    speaker_pair_counts = analysis_results["speaker_pair_counts"]
    if not speaker_pair_counts:
        return

    # Build deterministic node/edge lists
    speakers: set[str] = set()
    edges: list[dict[str, Any]] = []
    for pair, count in speaker_pair_counts.items():
        speaker_names = pair.split(" ↔ ")
        if len(speaker_names) == 2:
            source, target = speaker_names
            speakers.update([source, target])
            edges.append({"source": source, "target": target, "weight": count})

    if not speakers or not edges:
        return

    nodes_sorted = sorted(speakers)
    edges_sorted = sorted(edges, key=lambda item: (item["source"], item["target"]))

    # Create network graph (deterministic ordering)
    G = nx.Graph()
    for node in nodes_sorted:
        G.add_node(node)
    for edge in edges_sorted:
        G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1))

    if G.number_of_edges() == 0:
        return

    # Compute deterministic positions once and store in spec
    pos = nx.spring_layout(G, k=1, iterations=50, seed=42)
    node_positions = {
        node: (float(pos[node][0]), float(pos[node][1]))
        for node in nodes_sorted
        if node in pos
    }

    nodes_spec = [
        {
            "id": node,
            "label": node,
            "size": G.degree(node) * 10 + 20,
            "color": "lightblue",
        }
        for node in nodes_sorted
    ]
    edges_spec = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "weight": edge.get("weight", 1),
            "label": str(edge.get("weight", 1)),
        }
        for edge in edges_sorted
    ]

    # Save global chart
    if output_service:
        spec = NetworkGraphSpec(
            viz_id="conversation_loops.loop_network.global",
            module="conversation_loops",
            name="loop_network",
            scope="global",
            chart_intent="network_graph",
            title=f"Conversation Loop Network - {base_name}",
            nodes=nodes_spec,
            edges=edges_spec,
            node_positions=node_positions,
        )
        output_service.save_chart(spec, chart_type="network")


def create_loop_timeline(
    loops: list[ConversationLoop],
    speaker_map: dict[str, str] = None,
    output_structure=None,
    base_name: str = None,
    output_service=None,
):
    """
    Create timeline plot of conversation loops.

    Args:
        loops: List of ConversationLoop objects
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility, not used)
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    import warnings

    if speaker_map is not None:
        warnings.warn(
            "speaker_map parameter is deprecated. Speaker names come from ConversationLoop objects.",
            DeprecationWarning,
            stacklevel=2,
        )
    if not loops:
        return

    # Save global chart
    if output_service:
        series_list: list[ScatterSeries] = []
        for loop in loops:
            loop_label = f"Loop {loop.loop_id}"
            x_vals = [
                loop.turn_1_timestamp / 60.0,
                loop.turn_2_timestamp / 60.0,
                loop.turn_3_timestamp / 60.0,
            ]
            y_vals = [loop_label, loop_label, loop_label]
            text_vals = [
                f"{loop.speaker_a}: {loop.turn_1_act}",
                f"{loop.speaker_b}: {loop.turn_2_act}",
                f"{loop.speaker_a}: {loop.turn_3_act}",
            ]
            series_list.append(
                ScatterSeries(
                    name=loop_label,
                    x=x_vals,
                    y=y_vals,
                    text=text_vals,
                    marker={"color": ["red", "blue", "green"], "size": [100, 100, 100]},
                )
            )

        spec = ScatterSpec(
            viz_id="conversation_loops.loop_timeline.global",
            module="conversation_loops",
            name="loop_timeline",
            scope="global",
            chart_intent="scatter_events",
            title=f"Conversation Loop Timeline - {base_name}",
            x_label="Time (minutes)",
            y_label="Loop ID",
            mode="markers",
            series=series_list,
            y_is_categorical=True,
        )
        output_service.save_chart(spec, chart_type="timeline")


def create_loop_act_analysis(
    loops: list[ConversationLoop], output_structure, base_name: str, output_service=None
):
    """
    Create analysis of act patterns in conversation loops.

    Args:
        loops: List of ConversationLoop objects
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    if not loops:
        return

    # Count act patterns
    act_patterns = Counter()
    for loop in loops:
        pattern = f"{loop.turn_1_act} → {loop.turn_2_act} → {loop.turn_3_act}"
        act_patterns[pattern] += 1

    # Save global chart
    if output_service:
        ordered_patterns = sorted(
            act_patterns.items(), key=lambda item: item[1], reverse=True
        )
        patterns = [pattern for pattern, _ in ordered_patterns]
        counts = [count for _, count in ordered_patterns]
        spec = BarCategoricalSpec(
            viz_id="conversation_loops.act_patterns.global",
            module="conversation_loops",
            name="act_patterns",
            scope="global",
            chart_intent="bar_categorical",
            title=f"Conversation Loop Act Patterns - {base_name}",
            x_label="Act Pattern",
            y_label="Count",
            categories=patterns,
            values=counts,
        )
        output_service.save_chart(spec, chart_type="bar")


def create_analysis_summary(
    analysis_results: dict[str, Any], output_structure, base_name: str
):
    """
    Create comprehensive analysis summary.

    Args:
        analysis_results: Analysis results dictionary
        output_structure: OutputStructure object
        base_name: Base name for files
    """
    # Create summary statistics
    summary = {
        "total_loops": analysis_results["total_loops"],
        "unique_speaker_pairs": analysis_results["unique_speaker_pairs"],
        "top_speaker_pairs": sorted(
            analysis_results["speaker_pair_counts"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10],
        "top_act_patterns": sorted(
            analysis_results["act_patterns"].items(), key=lambda x: x[1], reverse=True
        )[:10],
        "gap_statistics": analysis_results["gap_statistics"],
        "sentiment_statistics": analysis_results["sentiment_statistics"],
    }

    # Save summary
    save_global_data(summary, output_structure, base_name, "summary", "json")

    # Create text summary
    summary_text = f"""Conversation Loop Analysis Summary: {base_name}
{'=' * 60}

Total Loops Detected: {summary['total_loops']}
Unique Speaker Pairs: {summary['unique_speaker_pairs']}

Top Speaker Pairs by Loop Count:
"""

    for pair, count in summary["top_speaker_pairs"]:
        summary_text += f"  • {pair}: {count} loops\n"

    summary_text += "\nTop Act Patterns:\n"
    for pattern, count in summary["top_act_patterns"]:
        summary_text += f"  • {pattern}: {count} occurrences\n"

    summary_text += "\nGap Statistics (seconds):\n"
    gap_stats = summary["gap_statistics"]
    summary_text += f"  • Gap between turns 1-2: mean={gap_stats['gap_1_2']['mean']:.2f}s, std={gap_stats['gap_1_2']['std']:.2f}s\n"
    summary_text += f"  • Gap between turns 2-3: mean={gap_stats['gap_2_3']['mean']:.2f}s, std={gap_stats['gap_2_3']['std']:.2f}s\n"

    summary_text += "\nSentiment Statistics:\n"
    sent_stats = summary["sentiment_statistics"]
    summary_text += f"  • Turn 1: mean={sent_stats['turn_1']['mean']:.3f}, std={sent_stats['turn_1']['std']:.3f}\n"
    summary_text += f"  • Turn 2: mean={sent_stats['turn_2']['mean']:.3f}, std={sent_stats['turn_2']['std']:.3f}\n"
    summary_text += f"  • Turn 3: mean={sent_stats['turn_3']['mean']:.3f}, std={sent_stats['turn_3']['std']:.3f}\n"

    # Save text summary
    summary_file = output_structure.global_data_dir / f"{base_name}_summary.txt"
    write_text(summary_file, summary_text)
