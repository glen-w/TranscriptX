"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class SemanticSimilarityConfig:
    """Tunable settings for semantic_similarity. Defaults owned by SemanticSimilaritySettingsModel."""

    enabled: bool = field(init=False, repr=True)
    mode: str = field(init=False, repr=True)
    model_name: str = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    min_text_length_words: int = field(init=False, repr=True)
    self_similarity_threshold: float = field(init=False, repr=True)
    cross_speaker_similarity_threshold: float = field(init=False, repr=True)
    self_time_window_seconds: float = field(init=False, repr=True)
    cross_speaker_time_window_seconds: float = field(init=False, repr=True)
    max_candidate_pairs: int = field(init=False, repr=True)
    top_k_per_segment: int = field(init=False, repr=True)
    timeout_seconds: float = field(init=False, repr=True)
    persist_embeddings: bool = field(init=False, repr=True)
    lru_size: int = field(init=False, repr=True)
    use_lexical_prefilter: bool = field(init=False, repr=True)
    lexical_prefilter_min_jaccard: float = field(init=False, repr=True)
    strict_advanced_inputs: bool = field(init=False, repr=True)
    motif_min_cluster_size: int = field(init=False, repr=True)
    cross_session_match_threshold: float = field(init=False, repr=True)
    min_sessions_for_recurring: int = field(init=False, repr=True)
    max_motifs_per_session: int = field(init=False, repr=True)
    max_motifs_per_group: int = field(init=False, repr=True)
    max_centroid_bytes: int = field(init=False, repr=True)
    cluster_eps: float = field(init=False, repr=True)
    cluster_min_samples: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.semantic_similarity import (
            SemanticSimilaritySettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, SemanticSimilaritySettingsModel())
