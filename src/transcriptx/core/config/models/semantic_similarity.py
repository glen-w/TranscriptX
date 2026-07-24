"""Pydantic schema for analysis.semantic_similarity settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_ADVANCED = {"advanced": True}


class SemanticSimilaritySettingsModel(BaseModel):
    """Canonical field definitions for semantic_similarity configuration."""

    model_config = ConfigDict(protected_namespaces=())

    enabled: bool = Field(
        default=True,
        description="Enable semantic similarity (default semantic path).",
    )
    mode: Literal["basic", "advanced"] = Field(
        default="basic",
        description=(
            "Selects the semantic similarity strategy: `basic` (fast, embeddings only) "
            "or `advanced` (uses sentiment/emotion/acts integration when available; "
            "may degrade to basic if integrations are missing)."
        ),
    )
    model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence-transformers model id used for embeddings.",
    )
    batch_size: int = Field(
        default=64,
        ge=1,
        description="Transformer batch size for embedding unique texts.",
        json_schema_extra=_ADVANCED,
    )
    min_text_length_words: int = Field(
        default=3,
        ge=1,
        description="Minimum word count for a segment to enter the pipeline.",
        json_schema_extra=_ADVANCED,
    )
    self_similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum cosine similarity for two segments by the same speaker to be "
            "flagged as a self-repetition (0.0–1.0; higher = stricter)."
        ),
    )
    cross_speaker_similarity_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum cosine similarity for two segments by different speakers to be "
            "flagged as a cross-speaker echo or paraphrase."
        ),
    )
    self_time_window_seconds: float = Field(
        default=300.0,
        ge=0.0,
        description="Self-repetition time window (seconds).",
    )
    cross_speaker_time_window_seconds: float = Field(
        default=600.0,
        ge=0.0,
        description="Cross-speaker candidate time window (seconds).",
    )
    max_candidate_pairs: int = Field(
        default=50_000,
        ge=1,
        description=(
            "Global cap on candidate pairs scored per run. When reached, the pipeline "
            "early-stops and returns partial results."
        ),
    )
    top_k_per_segment: int = Field(
        default=50,
        ge=1,
        description=(
            "Hard cap on candidate pairs generated per segment within the time window. "
            "Lower = faster, may miss matches."
        ),
    )
    timeout_seconds: float = Field(
        default=300.0,
        ge=1.0,
        description=(
            "Wall-clock budget for the pipeline. On timeout, partial results are "
            "returned with diagnostics.timeout_reached=True."
        ),
    )
    persist_embeddings: bool = Field(
        default=False,
        description=(
            "Persist embeddings to disk keyed by transcript hash + model name + segment "
            "hash; subsequent runs reuse the cache (requires a writable output/cache root)."
        ),
        json_schema_extra=_ADVANCED,
    )
    lru_size: int = Field(
        default=50_000,
        ge=0,
        description="Maximum entries in the in-memory embedding LRU cache (0 disables cache).",
        json_schema_extra=_ADVANCED,
    )
    use_lexical_prefilter: bool = Field(
        default=False,
        description=(
            "Cheap token-Jaccard filter applied before scoring; drops obviously non-similar "
            "candidates. Increases speed, risks dropping borderline paraphrases."
        ),
        json_schema_extra=_ADVANCED,
    )
    lexical_prefilter_min_jaccard: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Minimum Jaccard similarity when lexical prefilter is enabled.",
        json_schema_extra=_ADVANCED,
    )
    strict_advanced_inputs: bool = Field(
        default=False,
        description=(
            "When True, advanced mode blocks the run if sentiment/emotion/acts results are "
            "missing instead of degrading to basic."
        ),
    )
    motif_min_cluster_size: int = Field(
        default=2,
        ge=1,
        description="Minimum DBSCAN cluster members required to export a motif.",
        json_schema_extra=_ADVANCED,
    )
    cross_session_match_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description=(
            "Inclusive cosine threshold for matching motif centroids across sessions."
        ),
    )
    min_sessions_for_recurring: int = Field(
        default=2,
        ge=1,
        description="Minimum comparable sessions for a motif to be labeled recurring.",
    )
    max_motifs_per_session: int = Field(
        default=50,
        ge=1,
        description="Hard cap on exported motifs per transcript after deterministic rank.",
        json_schema_extra=_ADVANCED,
    )
    max_motifs_per_group: int = Field(
        default=40,
        ge=1,
        description="Hard cap on group motif rows / chart top-N after deterministic rank.",
        json_schema_extra=_ADVANCED,
    )
    max_centroid_bytes: int = Field(
        default=65_536,
        ge=256,
        description="Maximum serialized centroid JSON bytes per motif before partial export.",
        json_schema_extra=_ADVANCED,
    )
    cluster_eps: float = Field(
        default=0.35,
        ge=0.0,
        description="DBSCAN eps (cosine distance) for motif clustering.",
        json_schema_extra=_ADVANCED,
    )
    cluster_min_samples: int = Field(
        default=2,
        ge=1,
        description="DBSCAN min_samples for motif clustering.",
        json_schema_extra=_ADVANCED,
    )
