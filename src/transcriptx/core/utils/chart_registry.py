"""Chart registry for TranscriptX overview selection and matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Literal

import fnmatch
import re


Cardinality = Literal["single", "multi", "speaker_set", "paired_static_dynamic"]


@dataclass(frozen=True)
class ChartDefinition:
    viz_id: str
    label: str
    rank_default: int
    kind: str
    module: str
    scope: Literal["global", "speaker"]
    cardinality: Cardinality
    prefer_formats: List[str] = field(default_factory=lambda: ["html", "png"])
    match: "ChartMatcher" = field(default_factory=lambda: ChartMatcher())
    description: Optional[str] = None
    family_id: Optional[str] = None
    variant: Optional[str] = None


@dataclass(frozen=True)
class ChartMatcher:
    by_viz_id: Optional[str] = None
    by_artifact_key_prefix: Optional[str] = None
    by_chart_slug_regex: Optional[str] = None
    by_filename_glob: Optional[List[str]] = None

    def matches(self, artifact, chart_def: ChartDefinition) -> bool:
        artifact_kind = getattr(artifact, "kind", None)
        if artifact_kind and chart_def.kind:
            if not _kind_matches(artifact_kind, chart_def.kind):
                return False

        artifact_viz_id = _artifact_meta_value(artifact, "viz_id")
        if artifact_viz_id and self.by_viz_id:
            return artifact_viz_id == self.by_viz_id

        artifact_module = getattr(artifact, "module", None)
        artifact_scope = getattr(artifact, "scope", None)
        if artifact_module == chart_def.module and artifact_scope == chart_def.scope:
            if self.by_chart_slug_regex:
                if re.search(
                    self.by_chart_slug_regex, artifact.rel_path, re.IGNORECASE
                ):
                    return True

        if self.by_artifact_key_prefix:
            if artifact.rel_path.startswith(self.by_artifact_key_prefix):
                return True

        if self.by_filename_glob:
            for pattern in self.by_filename_glob:
                if fnmatch.fnmatch(artifact.rel_path, pattern):
                    return True

        return False


def _kind_matches(artifact_kind: str, chart_kind: str) -> bool:
    if chart_kind in {"chart", "map", "wordcloud"}:
        return artifact_kind.startswith("chart")
    return artifact_kind.startswith(chart_kind)


def _artifact_meta_value(artifact, key: str) -> Optional[str]:
    meta = getattr(artifact, "meta", None)
    if isinstance(meta, dict):
        return meta.get(key)
    return None


def get_artifact_format(artifact) -> Optional[str]:
    meta_format = _artifact_meta_value(artifact, "format")
    if meta_format:
        return str(meta_format).lower()
    suffix = Path(artifact.rel_path).suffix.lower().lstrip(".")
    return suffix or None


def select_preferred_artifacts(artifacts: List, chart_def: ChartDefinition) -> List:
    if not artifacts:
        return []

    def _pick_best(candidates: List) -> Optional[object]:
        if not candidates:
            return None
        for preferred in chart_def.prefer_formats:
            for candidate in candidates:
                if get_artifact_format(candidate) == preferred:
                    return candidate
        return candidates[0]

    if chart_def.cardinality == "single":
        best = _pick_best(artifacts)
        return [best] if best else []

    if chart_def.cardinality == "paired_static_dynamic":
        selected: List = []
        for preferred in chart_def.prefer_formats:
            match = next(
                (a for a in artifacts if get_artifact_format(a) == preferred), None
            )
            if match:
                selected.append(match)
        return selected or artifacts[:1]

    if chart_def.cardinality == "speaker_set":
        by_speaker: Dict[str, List] = {}
        for artifact in artifacts:
            speaker = getattr(artifact, "speaker", None) or "unknown"
            by_speaker.setdefault(speaker, []).append(artifact)
        selected = []
        for speaker_key in sorted(by_speaker.keys()):
            best = _pick_best(by_speaker[speaker_key])
            if best:
                selected.append(best)
        return selected

    return artifacts


DEFAULT_OVERVIEW_VIZ_IDS: List[str] = [
    "sentiment.multi_speaker_sentiment.global",
    "emotion.radar.global",
    "interactions.network.global",
    "interactions.dominance.global",
    "interactions.heatmap.global",
    "momentum.momentum.global",
    "interactions.timeline.global",
    "acts.acts_temporal_all.global",
    "acts.acts_temporal.speaker",
    "conversation_loops.loop_timeline.global",
    "temporal_dynamics.temporal_dashboard.global",
    "temporal_dynamics.temporal_dashboard_speaking_rate.global",
    "understandability.readability_indices.global",
    "wordcloud.wordcloud.global.basic",
]


CHART_DEFINITIONS: List[ChartDefinition] = [
    # Sentiment
    ChartDefinition(
        viz_id="sentiment.multi_speaker_sentiment.global",
        label="Multispeaker Sentiment Over Time",
        rank_default=10,
        kind="chart",
        module="sentiment",
        scope="global",
        cardinality="paired_static_dynamic",
        match=ChartMatcher(
            by_viz_id="sentiment.multi_speaker_sentiment.global",
            by_artifact_key_prefix="sentiment/charts/",
            by_chart_slug_regex=r"multi_speaker_sentiment",
        ),
    ),
    ChartDefinition(
        viz_id="sentiment.rolling_sentiment.speaker",
        label="Rolling Sentiment (Per Speaker)",
        rank_default=20,
        kind="chart",
        module="sentiment",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="sentiment.rolling_sentiment.speaker",
            by_artifact_key_prefix="sentiment/charts/",
            by_chart_slug_regex=r"rolling_sentiment",
        ),
    ),
    # Emotion
    ChartDefinition(
        viz_id="emotion.radar.global",
        label="Emotion Radar - All Speakers",
        rank_default=30,
        kind="chart",
        module="emotion",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="emotion.radar.global",
            by_artifact_key_prefix="emotion/charts/",
            by_chart_slug_regex=r"emotion_all_radar",
        ),
    ),
    ChartDefinition(
        viz_id="emotion.radar.speaker",
        label="Emotion Radar (Per Speaker)",
        rank_default=40,
        kind="chart",
        module="emotion",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="emotion.radar.speaker",
            by_artifact_key_prefix="emotion/charts/",
            by_chart_slug_regex=r"/radar\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="emotion.radar_polar.global",
        label="Emotion Radar (Polar) – Global",
        rank_default=42,
        kind="chart",
        module="emotion",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="emotion.radar_polar.global",
            by_artifact_key_prefix="emotion/charts/",
            by_chart_slug_regex=r"radar_polar",
        ),
    ),
    ChartDefinition(
        viz_id="emotion.radar_polar.speaker",
        label="Emotion Radar (Polar) – Per Speaker",
        rank_default=43,
        kind="chart",
        module="emotion",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="emotion.radar_polar.speaker",
            by_artifact_key_prefix="emotion/charts/speakers/",
            by_chart_slug_regex=r"radar_polar",
        ),
    ),
    # NER
    ChartDefinition(
        viz_id="ner.entity_types.global",
        label="Entity Types - Global",
        rank_default=50,
        kind="chart",
        module="ner",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="ner.entity_types.global",
            by_artifact_key_prefix="ner/charts/",
            by_chart_slug_regex=r"ner-types-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="ner.entity_types.speaker",
        label="Entity Types (Per Speaker)",
        rank_default=60,
        kind="chart",
        module="ner",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="ner.entity_types.speaker",
            by_artifact_key_prefix="ner/charts/",
            by_chart_slug_regex=r"ner-types",
        ),
    ),
    ChartDefinition(
        viz_id="ner.locations.global",
        label="Locations Map - Global",
        rank_default=70,
        kind="map",
        module="ner",
        scope="global",
        cardinality="paired_static_dynamic",
        prefer_formats=["html", "png"],
        match=ChartMatcher(
            by_viz_id="ner.locations.global",
            by_artifact_key_prefix="ner/charts/",
            by_chart_slug_regex=r"locations-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="ner.locations.speaker",
        label="Locations Map (Per Speaker)",
        rank_default=80,
        kind="map",
        module="ner",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["html", "png"],
        match=ChartMatcher(
            by_viz_id="ner.locations.speaker",
            by_artifact_key_prefix="ner/charts/",
            by_chart_slug_regex=r"locations-[^/]+",
        ),
    ),
    # Interactions
    ChartDefinition(
        viz_id="interactions.timeline.global",
        label="Speaker Interaction Timeline",
        rank_default=90,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.timeline.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"/timeline\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.timeline.speaker",
        label="Speaker Interaction Timeline (Per Speaker)",
        rank_default=100,
        kind="chart",
        module="interactions",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="interactions.timeline.speaker",
            by_artifact_key_prefix="interactions/charts/speakers/",
            by_chart_slug_regex=r"/timeline\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.network.global",
        label="Speaker Interaction Network",
        rank_default=110,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.network.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"/network\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.heatmap.global",
        label="Speaker Interaction Matrices",
        rank_default=120,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.heatmap.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"/heatmap\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.dominance.global",
        label="Dominance Analysis",
        rank_default=130,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.dominance.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"/dominance\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.network_graph.global",
        label="Speaker Interaction Network (Graph)",
        rank_default=132,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.network_graph.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"network_graph",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.heatmap_interruptions.global",
        label="Interruption Matrix",
        rank_default=133,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.heatmap_interruptions.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"heatmap_interruptions",
        ),
    ),
    ChartDefinition(
        viz_id="interactions.heatmap_responses.global",
        label="Response Matrix",
        rank_default=134,
        kind="chart",
        module="interactions",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="interactions.heatmap_responses.global",
            by_artifact_key_prefix="interactions/charts/",
            by_chart_slug_regex=r"heatmap_responses",
        ),
    ),
    # Momentum
    ChartDefinition(
        viz_id="momentum.momentum.global",
        label="Momentum Over Time",
        rank_default=140,
        kind="chart",
        module="momentum",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="momentum.momentum.global",
            by_artifact_key_prefix="momentum/charts/",
            by_chart_slug_regex=r"momentum",
        ),
    ),
    # Temporal dynamics
    ChartDefinition(
        viz_id="temporal_dynamics.engagement_timeseries.global",
        label="Engagement Timeseries",
        rank_default=150,
        kind="chart",
        module="temporal_dynamics",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="temporal_dynamics.engagement_timeseries.global",
            by_artifact_key_prefix="temporal_dynamics/charts/",
            by_chart_slug_regex=r"engagement_timeseries",
        ),
    ),
    ChartDefinition(
        viz_id="temporal_dynamics.speaking_rate_timeseries.global",
        label="Speaking Rate Timeseries",
        rank_default=160,
        kind="chart",
        module="temporal_dynamics",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="temporal_dynamics.speaking_rate_timeseries.global",
            by_artifact_key_prefix="temporal_dynamics/charts/",
            by_chart_slug_regex=r"speaking_rate_timeseries",
        ),
    ),
    ChartDefinition(
        viz_id="temporal_dynamics.sentiment_timeseries.global",
        label="Sentiment Timeseries",
        rank_default=170,
        kind="chart",
        module="temporal_dynamics",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="temporal_dynamics.sentiment_timeseries.global",
            by_artifact_key_prefix="temporal_dynamics/charts/",
            by_chart_slug_regex=r"sentiment_timeseries",
        ),
    ),
    ChartDefinition(
        viz_id="temporal_dynamics.phase_detection.global",
        label="Phase Detection Timeline",
        rank_default=180,
        kind="chart",
        module="temporal_dynamics",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="temporal_dynamics.phase_detection.global",
            by_artifact_key_prefix="temporal_dynamics/charts/",
            by_chart_slug_regex=r"phase_detection",
        ),
    ),
    ChartDefinition(
        viz_id="temporal_dynamics.temporal_dashboard.global",
        label="Temporal Dynamics Dashboard (Turn Frequency & Segments)",
        rank_default=190,
        kind="chart",
        module="temporal_dynamics",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="temporal_dynamics.temporal_dashboard.global",
            by_artifact_key_prefix="temporal_dynamics/charts/",
            by_chart_slug_regex=r"temporal_dashboard\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="temporal_dynamics.temporal_dashboard_speaking_rate.global",
        label="Temporal Dynamics – Speaking Rate",
        rank_default=192,
        kind="chart",
        module="temporal_dynamics",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="temporal_dynamics.temporal_dashboard_speaking_rate.global",
            by_artifact_key_prefix="temporal_dynamics/charts/",
            by_chart_slug_regex=r"temporal_dashboard_speaking_rate",
        ),
    ),
    # Q&A analysis
    ChartDefinition(
        viz_id="qa_analysis.qa_timeline.global",
        label="Q&A Timeline",
        rank_default=200,
        kind="chart",
        module="qa_analysis",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="qa_analysis.qa_timeline.global",
            by_artifact_key_prefix="qa_analysis/charts/",
            by_chart_slug_regex=r"qa_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="qa_analysis.response_quality.global",
        label="Response Quality Distribution",
        rank_default=210,
        kind="chart",
        module="qa_analysis",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="qa_analysis.response_quality.global",
            by_artifact_key_prefix="qa_analysis/charts/",
            by_chart_slug_regex=r"response_quality",
        ),
    ),
    ChartDefinition(
        viz_id="qa_analysis.question_type_breakdown.global",
        label="Question Type Breakdown",
        rank_default=220,
        kind="chart",
        module="qa_analysis",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="qa_analysis.question_type_breakdown.global",
            by_artifact_key_prefix="qa_analysis/charts/",
            by_chart_slug_regex=r"question_type_breakdown",
        ),
    ),
    ChartDefinition(
        viz_id="qa_analysis.response_time_analysis.global",
        label="Response Time Analysis",
        rank_default=230,
        kind="chart",
        module="qa_analysis",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="qa_analysis.response_time_analysis.global",
            by_artifact_key_prefix="qa_analysis/charts/",
            by_chart_slug_regex=r"response_time_analysis",
        ),
    ),
    # Tics
    ChartDefinition(
        viz_id="tics.tics.speaker",
        label="Verbal Tics (Per Speaker)",
        rank_default=240,
        kind="chart",
        module="tics",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="tics.tics.speaker",
            by_artifact_key_prefix="tics/charts/",
            by_chart_slug_regex=r"/tics\\.(png|html)$",
        ),
    ),
    # Entity sentiment
    ChartDefinition(
        viz_id="entity_sentiment.sentiment_heatmap.global",
        label="Entity Sentiment Heatmap",
        rank_default=250,
        kind="chart",
        module="entity_sentiment",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="entity_sentiment.sentiment_heatmap.global",
            by_artifact_key_prefix="entity_sentiment/charts/",
            by_chart_slug_regex=r"sentiment_heatmap",
        ),
    ),
    ChartDefinition(
        viz_id="entity_sentiment.entity_type_analysis.global",
        label="Entity Sentiment by Type",
        rank_default=260,
        kind="chart",
        module="entity_sentiment",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="entity_sentiment.entity_type_analysis.global",
            by_artifact_key_prefix="entity_sentiment/charts/",
            by_chart_slug_regex=r"entity_type_analysis",
        ),
    ),
    ChartDefinition(
        viz_id="entity_sentiment.entity_mentions.speaker",
        label="Entity Mentions (Per Speaker)",
        rank_default=270,
        kind="chart",
        module="entity_sentiment",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="entity_sentiment.entity_mentions.speaker",
            by_artifact_key_prefix="entity_sentiment/charts/",
            by_chart_slug_regex=r"entity_mentions",
        ),
    ),
    # Contagion
    ChartDefinition(
        viz_id="contagion.contagion_matrix.global",
        label="Emotional Contagion Matrix",
        rank_default=280,
        kind="chart",
        module="contagion",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="contagion.contagion_matrix.global",
            by_artifact_key_prefix="contagion/charts/",
            by_chart_slug_regex=r"contagion_matrix",
        ),
    ),
    # Dynamics
    ChartDefinition(
        viz_id="echoes.echo_heatmap.global",
        label="Echo Network Heatmap",
        rank_default=290,
        kind="chart",
        module="echoes",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="echoes.echo_heatmap.global",
            by_artifact_key_prefix="echoes/charts/",
            by_chart_slug_regex=r"echo_heatmap",
        ),
    ),
    ChartDefinition(
        viz_id="echoes.echo_timeline.global",
        label="Echo Timeline",
        rank_default=300,
        kind="chart",
        module="echoes",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="echoes.echo_timeline.global",
            by_artifact_key_prefix="echoes/charts/",
            by_chart_slug_regex=r"echo_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="pauses.pauses_hist.global",
        label="Pause Duration Histogram",
        rank_default=310,
        kind="chart",
        module="pauses",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="pauses.pauses_hist.global",
            by_artifact_key_prefix="pauses/charts/",
            by_chart_slug_regex=r"pauses_hist",
        ),
    ),
    ChartDefinition(
        viz_id="pauses.pauses_timeline.global",
        label="Pause Timeline",
        rank_default=320,
        kind="chart",
        module="pauses",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="pauses.pauses_timeline.global",
            by_artifact_key_prefix="pauses/charts/",
            by_chart_slug_regex=r"pauses_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="moments.moments_timeline.global",
        label="Moments Timeline",
        rank_default=330,
        kind="chart",
        module="moments",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="moments.moments_timeline.global",
            by_artifact_key_prefix="moments/charts/",
            by_chart_slug_regex=r"moments_timeline",
        ),
    ),
    # Semantic similarity
    ChartDefinition(
        viz_id="semantic_similarity.speaker_repetition_frequency.global",
        label="Speaker Repetition Frequency",
        rank_default=340,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.speaker_repetition_frequency.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"speaker_repetition_frequency",
        ),
    ),
    ChartDefinition(
        viz_id="semantic_similarity.agreement_breakdown.global",
        label="Cross-Speaker Interaction Types",
        rank_default=350,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.agreement_breakdown.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"agreement_disagreement_breakdown",
        ),
    ),
    ChartDefinition(
        viz_id="semantic_similarity.similarity_distribution.global",
        label="Similarity Distribution",
        rank_default=360,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.similarity_distribution.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"similarity_distribution",
        ),
    ),
    ChartDefinition(
        viz_id="semantic_similarity.speaker_repetitions.global",
        label="Repetitions by Speaker",
        rank_default=370,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.speaker_repetitions.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"speaker_repetitions",
        ),
    ),
    ChartDefinition(
        viz_id="semantic_similarity.classification.global",
        label="Repetition Classification",
        rank_default=380,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.classification.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"classification",
        ),
    ),
    ChartDefinition(
        viz_id="semantic_similarity.speaker_similarity.global",
        label="Average Similarity by Speaker",
        rank_default=382,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.speaker_similarity.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"speaker_similarity",
        ),
    ),
    ChartDefinition(
        viz_id="semantic_similarity.agreement_disagreement_breakdown.global",
        label="Agreement/Disagreement Breakdown",
        rank_default=384,
        kind="chart",
        module="semantic_similarity",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="semantic_similarity.agreement_disagreement_breakdown.global",
            by_artifact_key_prefix="semantic_similarity/charts/",
            by_chart_slug_regex=r"agreement_disagreement_breakdown",
        ),
    ),
    # Topic modeling
    ChartDefinition(
        viz_id="topic_modeling.diagnostic_plots.global",
        label="Topic Modeling Diagnostics",
        rank_default=390,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.diagnostic_plots.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"diagnostic_plots",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.discourse_analysis.global",
        label="Discourse Analysis",
        rank_default=400,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.discourse_analysis.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"discourse_analysis",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.lda_topic_word_heatmap.global",
        label="LDA Topic-Word Heatmap",
        rank_default=410,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.lda_topic_word_heatmap.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"enhanced_lda_topic_word_heatmap",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.nmf_topic_word_heatmap.global",
        label="NMF Topic-Word Heatmap",
        rank_default=420,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.nmf_topic_word_heatmap.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"enhanced_nmf_topic_word_heatmap",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.topic_evolution_timeline.global",
        label="Topic Evolution Timeline",
        rank_default=430,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.topic_evolution_timeline.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"topic_evolution_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.speaker_topic_engagement_heatmap.global",
        label="Speaker-Topic Engagement Heatmap",
        rank_default=440,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.speaker_topic_engagement_heatmap.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"speaker_topic_engagement_heatmap",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.expected_topic_proportions.global",
        label="Expected Topic Proportions",
        rank_default=450,
        kind="chart",
        module="topic_modeling",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="topic_modeling.expected_topic_proportions.global",
            by_artifact_key_prefix="topic_modeling/charts/",
            by_chart_slug_regex=r"expected_topic_proportions",
        ),
    ),
    ChartDefinition(
        viz_id="topic_modeling.topic_bar.speaker",
        label="Topic Distribution (Per Speaker)",
        rank_default=460,
        kind="chart",
        module="topic_modeling",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="topic_modeling.topic_bar.speaker",
            by_artifact_key_prefix="topic_modeling/charts/speakers/",
            by_chart_slug_regex=r"topic_bar",
        ),
    ),
    # Acts
    ChartDefinition(
        viz_id="acts.acts_pie.speaker",
        label="Dialogue Acts - Pie (Per Speaker)",
        rank_default=470,
        kind="chart",
        module="acts",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="acts.acts_pie.speaker",
            by_artifact_key_prefix="acts/charts/speakers/",
            by_chart_slug_regex=r"acts_pie",
        ),
    ),
    ChartDefinition(
        viz_id="acts.acts_bar.speaker",
        label="Dialogue Acts - Bar (Per Speaker)",
        rank_default=480,
        kind="chart",
        module="acts",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="acts.acts_bar.speaker",
            by_artifact_key_prefix="acts/charts/speakers/",
            by_chart_slug_regex=r"acts_bar",
        ),
    ),
    ChartDefinition(
        viz_id="acts.global_acts_pie.global",
        label="Dialogue Acts - Global Pie",
        rank_default=490,
        kind="chart",
        module="acts",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="acts.global_acts_pie.global",
            by_artifact_key_prefix="acts/charts/",
            by_chart_slug_regex=r"global_acts_pie",
        ),
    ),
    ChartDefinition(
        viz_id="acts.global_acts_bar.global",
        label="Dialogue Acts - Global Bar",
        rank_default=500,
        kind="chart",
        module="acts",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="acts.global_acts_bar.global",
            by_artifact_key_prefix="acts/charts/",
            by_chart_slug_regex=r"global_acts_bar",
        ),
    ),
    ChartDefinition(
        viz_id="acts.acts_temporal_all.global",
        label="Dialogue Acts Over Time - All Speakers",
        rank_default=510,
        kind="chart",
        module="acts",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="acts.acts_temporal_all.global",
            by_artifact_key_prefix="acts/charts/",
            by_chart_slug_regex=r"acts_temporal_all",
        ),
    ),
    ChartDefinition(
        viz_id="acts.acts_temporal.speaker",
        label="Dialogue Acts Over Time (Per Speaker)",
        rank_default=520,
        kind="chart",
        module="acts",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="acts.acts_temporal.speaker",
            by_artifact_key_prefix="acts/charts/speakers/",
            by_chart_slug_regex=r"acts_temporal",
        ),
    ),
    # Conversation loops
    ChartDefinition(
        viz_id="conversation_loops.loop_network.global",
        label="Conversation Loop Network",
        rank_default=530,
        kind="chart",
        module="conversation_loops",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="conversation_loops.loop_network.global",
            by_artifact_key_prefix="conversation_loops/charts/",
            by_chart_slug_regex=r"loop_network",
        ),
    ),
    ChartDefinition(
        viz_id="conversation_loops.loop_timeline.global",
        label="Conversation Loop Timeline",
        rank_default=540,
        kind="chart",
        module="conversation_loops",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="conversation_loops.loop_timeline.global",
            by_artifact_key_prefix="conversation_loops/charts/",
            by_chart_slug_regex=r"loop_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="conversation_loops.act_patterns.global",
        label="Conversation Loop Act Patterns",
        rank_default=550,
        kind="chart",
        module="conversation_loops",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="conversation_loops.act_patterns.global",
            by_artifact_key_prefix="conversation_loops/charts/",
            by_chart_slug_regex=r"act_patterns",
        ),
    ),
    # Voice & prosody (voice_charts_core, prosody_dashboard, voice_contours, etc.)
    ChartDefinition(
        viz_id="voice.pauses_distribution.global",
        label="Pauses Distribution (Voice) – Global",
        rank_default=552,
        kind="chart",
        module="voice",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice.pauses_distribution.global",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"pauses_distribution",
        ),
    ),
    ChartDefinition(
        viz_id="voice.pauses_distribution.speaker",
        label="Pauses Distribution (Voice) – Per Speaker",
        rank_default=553,
        kind="chart",
        module="voice",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="voice.pauses_distribution.speaker",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"pauses_distribution",
        ),
    ),
    ChartDefinition(
        viz_id="voice.pauses_timeline.global",
        label="Pauses Timeline (Voice)",
        rank_default=554,
        kind="chart",
        module="voice",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice.pauses_timeline.global",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"pauses_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="voice.hesitation_map.global",
        label="Hesitation Map",
        rank_default=555,
        kind="chart",
        module="voice",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice.hesitation_map.global",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"hesitation_map",
        ),
    ),
    ChartDefinition(
        viz_id="voice.burstiness.speaker",
        label="Burstiness (Per Speaker)",
        rank_default=556,
        kind="chart",
        module="voice",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="voice.burstiness.speaker",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"burstiness",
        ),
    ),
    ChartDefinition(
        viz_id="voice.rhythm_compare.global",
        label="Rhythm Comparison",
        rank_default=557,
        kind="chart",
        module="voice",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice.rhythm_compare.global",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"rhythm_compare",
        ),
    ),
    ChartDefinition(
        viz_id="voice.rhythm_scatter.global",
        label="Rhythm Scatter",
        rank_default=558,
        kind="chart",
        module="voice",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice.rhythm_scatter.global",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"rhythm_scatter",
        ),
    ),
    ChartDefinition(
        viz_id="voice.f0_contours.speaker",
        label="F0 Contours (Per Speaker)",
        rank_default=559,
        kind="chart",
        module="voice",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="voice.f0_contours.speaker",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"f0_contours",
        ),
    ),
    ChartDefinition(
        viz_id="voice.f0_slope_distribution.global",
        label="F0 Slope Distribution",
        rank_default=560,
        kind="chart",
        module="voice",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice.f0_slope_distribution.global",
            by_artifact_key_prefix="voice",
            by_chart_slug_regex=r"f0_slope_distribution",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.profile_distribution.speaker",
        label="Prosody Profile Distribution (Per Speaker)",
        rank_default=561,
        kind="chart",
        module="prosody_dashboard",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.profile_distribution.speaker",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"profile_distribution",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.profile_corr.speaker",
        label="Prosody Profile Correlation (Per Speaker)",
        rank_default=562,
        kind="chart",
        module="prosody_dashboard",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.profile_corr.speaker",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"profile_corr",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.timeline.global",
        label="Prosody Timeline",
        rank_default=563,
        kind="chart",
        module="prosody_dashboard",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.timeline.global",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"timeline",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.compare_speakers.global",
        label="Prosody Compare Speakers",
        rank_default=564,
        kind="chart",
        module="prosody_dashboard",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.compare_speakers.global",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"compare_speakers",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.fingerprint_scatter.global",
        label="Prosody Fingerprint Scatter",
        rank_default=565,
        kind="chart",
        module="prosody_dashboard",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.fingerprint_scatter.global",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"fingerprint_scatter",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.egemaps_distribution.speaker",
        label="Prosody eGeMAPS Distribution (Per Speaker)",
        rank_default=566,
        kind="chart",
        module="prosody_dashboard",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.egemaps_distribution.speaker",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"egemaps_distribution",
        ),
    ),
    ChartDefinition(
        viz_id="prosody_dashboard.quality_scatter.global",
        label="Prosody Quality Scatter",
        rank_default=567,
        kind="chart",
        module="prosody_dashboard",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="prosody_dashboard.quality_scatter.global",
            by_artifact_key_prefix="prosody_dashboard",
            by_chart_slug_regex=r"quality_scatter",
        ),
    ),
    ChartDefinition(
        viz_id="voice_tension.tension_curve.global",
        label="Voice Tension Curve",
        rank_default=568,
        kind="chart",
        module="voice_tension",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice_tension.tension_curve.global",
            by_artifact_key_prefix="voice_tension",
            by_chart_slug_regex=r"tension_curve",
        ),
    ),
    ChartDefinition(
        viz_id="voice_mismatch.sentiment_vs_arousal.global",
        label="Sentiment vs Arousal (Mismatch)",
        rank_default=569,
        kind="chart",
        module="voice_mismatch",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice_mismatch.sentiment_vs_arousal.global",
            by_artifact_key_prefix="voice_mismatch",
            by_chart_slug_regex=r"sentiment_vs_arousal",
        ),
    ),
    ChartDefinition(
        viz_id="voice_mismatch.mismatch_timeline.global",
        label="Voice Mismatch Timeline",
        rank_default=570,
        kind="chart",
        module="voice_mismatch",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="voice_mismatch.mismatch_timeline.global",
            by_artifact_key_prefix="voice_mismatch",
            by_chart_slug_regex=r"mismatch_timeline",
        ),
    ),
    ChartDefinition(
        viz_id="voice_fingerprint.drift_timeline.speaker",
        label="Voice Drift Timeline (Per Speaker)",
        rank_default=571,
        kind="chart",
        module="voice_fingerprint",
        scope="speaker",
        cardinality="speaker_set",
        match=ChartMatcher(
            by_viz_id="voice_fingerprint.drift_timeline.speaker",
            by_artifact_key_prefix="voice_fingerprint",
            by_chart_slug_regex=r"drift_timeline",
        ),
    ),
    # Understandability
    ChartDefinition(
        viz_id="understandability.flesch_reading_ease.global",
        label="Flesch Reading Ease (Per Speaker)",
        rank_default=560,
        kind="chart",
        module="understandability",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="understandability.flesch_reading_ease.global",
            by_artifact_key_prefix="understandability/charts/",
            by_chart_slug_regex=r"flesch-reading-ease-bars",
        ),
    ),
    ChartDefinition(
        viz_id="understandability.readability_indices.global",
        label="Readability Indices (Per Speaker)",
        rank_default=570,
        kind="chart",
        module="understandability",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="understandability.readability_indices.global",
            by_artifact_key_prefix="understandability/charts/",
            by_chart_slug_regex=r"readability-indices-bars",
        ),
    ),
    ChartDefinition(
        viz_id="understandability.structure_bars.global",
        label="Structural Features (Per Speaker)",
        rank_default=580,
        kind="chart",
        module="understandability",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="understandability.structure_bars.global",
            by_artifact_key_prefix="understandability/charts/",
            by_chart_slug_regex=r"structure-bars",
        ),
    ),
    ChartDefinition(
        viz_id="understandability.word_count_bars.global",
        label="Word Count (Per Speaker)",
        rank_default=590,
        kind="chart",
        module="understandability",
        scope="global",
        cardinality="single",
        match=ChartMatcher(
            by_viz_id="understandability.word_count_bars.global",
            by_artifact_key_prefix="understandability/charts/",
            by_chart_slug_regex=r"word-count-bars",
        ),
    ),
    # Wordclouds (explicit variants, with family support)
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.basic",
        label="Wordcloud (Per Speaker)",
        rank_default=600,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="basic",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.basic",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"/wordcloud\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.basic",
        label="Wordcloud - All Speakers",
        rank_default=610,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="basic",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.basic",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"_wordcloud\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.bigrams",
        label="Wordcloud Bigrams (Per Speaker)",
        rank_default=620,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="bigrams",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.bigrams",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"wordcloud-bigrams",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.bigrams",
        label="Wordcloud Bigrams - All Speakers",
        rank_default=630,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="bigrams",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.bigrams",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"wordcloud-bigrams-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.tfidf",
        label="Wordcloud TF-IDF (Per Speaker)",
        rank_default=640,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="tfidf",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.tfidf",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"/tfidf\\.(png|html)$",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.tfidf",
        label="Wordcloud TF-IDF - All Speakers",
        rank_default=650,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="tfidf",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.tfidf",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"tfidf-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.tfidf_bigrams",
        label="Wordcloud TF-IDF Bigrams (Per Speaker)",
        rank_default=660,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="tfidf_bigrams",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.tfidf_bigrams",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"tfidf-bigrams",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.tfidf_bigrams",
        label="Wordcloud TF-IDF Bigrams - All Speakers",
        rank_default=670,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="tfidf_bigrams",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.tfidf_bigrams",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"tfidf-bigrams-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.tics",
        label="Wordcloud Tics (Per Speaker)",
        rank_default=680,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="tics",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.tics",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"wordcloud-tics",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.noun",
        label="Wordcloud Nouns (Per Speaker)",
        rank_default=690,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="noun",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.noun",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"wordcloud-noun",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.noun",
        label="Wordcloud Nouns - All Speakers",
        rank_default=700,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="noun",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.noun",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"wordcloud-noun-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.verb",
        label="Wordcloud Verbs (Per Speaker)",
        rank_default=710,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="verb",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.verb",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"wordcloud-verb",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.verb",
        label="Wordcloud Verbs - All Speakers",
        rank_default=720,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="verb",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.verb",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"wordcloud-verb-ALL",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.speaker.adj",
        label="Wordcloud Adjectives (Per Speaker)",
        rank_default=730,
        kind="wordcloud",
        module="wordclouds",
        scope="speaker",
        cardinality="speaker_set",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.speaker",
        variant="adj",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.speaker.adj",
            by_artifact_key_prefix="wordclouds/charts/speakers/",
            by_chart_slug_regex=r"wordcloud-adj",
        ),
    ),
    ChartDefinition(
        viz_id="wordcloud.wordcloud.global.adj",
        label="Wordcloud Adjectives - All Speakers",
        rank_default=740,
        kind="wordcloud",
        module="wordclouds",
        scope="global",
        cardinality="single",
        prefer_formats=["png"],
        family_id="wordcloud.wordcloud.global",
        variant="adj",
        match=ChartMatcher(
            by_viz_id="wordcloud.wordcloud.global.adj",
            by_artifact_key_prefix="wordclouds/charts/",
            by_chart_slug_regex=r"wordcloud-adj-ALL",
        ),
    ),
]


_REGISTRY_BY_ID: Dict[str, ChartDefinition] = {c.viz_id: c for c in CHART_DEFINITIONS}


def get_chart_registry() -> Dict[str, ChartDefinition]:
    return dict(_REGISTRY_BY_ID)


def get_chart_definition(viz_id: str) -> Optional[ChartDefinition]:
    return _REGISTRY_BY_ID.get(viz_id)


def iter_chart_definitions() -> Iterable[ChartDefinition]:
    return CHART_DEFINITIONS


def get_default_overview_charts() -> List[str]:
    return list(DEFAULT_OVERVIEW_VIZ_IDS)
