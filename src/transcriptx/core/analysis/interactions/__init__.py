"""Speaker interactions analysis package."""

from transcriptx.core.analysis.interactions.analysis import InteractionsAnalysis
from transcriptx.core.analysis.interactions.analyzer import SpeakerInteractionAnalyzer
from transcriptx.core.analysis.interactions.equity import (
    compute_equity,
    nearest_rank_p90,
)
from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.output import (
    analyze_interactions,
    create_analysis_summary,
    save_interaction_events,
    save_interaction_matrix_data,
    save_speaker_summary_data,
)
from transcriptx.core.analysis.interactions.roles import (
    INTERACTIONS_SEMANTICS_VERSION,
    interruption_balance_index,
    resolve_interaction_roles,
)
from transcriptx.core.analysis.interactions.serialize import (
    serialize_equity,
    serialize_interactions_summary,
)
from transcriptx.core.analysis.interactions.visualization import (
    create_combined_timeline,
    create_dominance_analysis,
    create_equity_floor_chart,
    create_equity_summary_chart,
    create_interaction_heatmap,
    create_interaction_network,
    create_speaker_timeline_charts,
)

__all__ = [
    "INTERACTIONS_SEMANTICS_VERSION",
    "InteractionsAnalysis",
    "SpeakerInteractionAnalyzer",
    "InteractionEvent",
    "analyze_interactions",
    "compute_equity",
    "create_analysis_summary",
    "create_combined_timeline",
    "create_dominance_analysis",
    "create_equity_floor_chart",
    "create_equity_summary_chart",
    "create_interaction_heatmap",
    "create_interaction_network",
    "create_speaker_timeline_charts",
    "interruption_balance_index",
    "nearest_rank_p90",
    "resolve_interaction_roles",
    "save_interaction_events",
    "save_interaction_matrix_data",
    "save_speaker_summary_data",
    "serialize_equity",
    "serialize_interactions_summary",
]
