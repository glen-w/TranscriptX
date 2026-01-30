"""Speaker interactions analysis package."""

from transcriptx.core.analysis.interactions.analysis import InteractionsAnalysis
from transcriptx.core.analysis.interactions.analyzer import SpeakerInteractionAnalyzer
from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.output import (
    analyze_interactions,
    create_analysis_summary,
    save_interaction_events,
    save_interaction_matrix_data,
    save_speaker_summary_data,
)
from transcriptx.core.analysis.interactions.visualization import (
    create_combined_timeline,
    create_dominance_analysis,
    create_interaction_heatmap,
    create_interaction_network,
    create_speaker_timeline_charts,
)

__all__ = [
    "InteractionsAnalysis",
    "SpeakerInteractionAnalyzer",
    "InteractionEvent",
    "analyze_interactions",
    "save_interaction_events",
    "save_speaker_summary_data",
    "save_interaction_matrix_data",
    "create_combined_timeline",
    "create_interaction_network",
    "create_interaction_heatmap",
    "create_dominance_analysis",
    "create_speaker_timeline_charts",
    "create_analysis_summary",
]
