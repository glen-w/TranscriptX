"""Pydantic schema for analysis.semantic_similarity_profiles."""

from pydantic import BaseModel, Field


class SemanticSimilarityProfileFastModel(BaseModel):
    self_similarity_threshold: float = Field(default=0.78)
    cross_speaker_similarity_threshold: float = Field(default=0.68)
    top_k_per_segment: int = Field(default=20)
    max_candidate_pairs: int = Field(default=15000)
    timeout_seconds: float = Field(default=120.0)
    use_lexical_prefilter: bool = Field(default=True)
    lexical_prefilter_min_jaccard: float = Field(default=0.1)
    mode: str = Field(default="basic")


class SemanticSimilarityProfileBalancedModel(BaseModel):
    self_similarity_threshold: float = Field(default=0.72)
    cross_speaker_similarity_threshold: float = Field(default=0.62)
    top_k_per_segment: int = Field(default=50)
    max_candidate_pairs: int = Field(default=50000)
    timeout_seconds: float = Field(default=300.0)
    use_lexical_prefilter: bool = Field(default=True)
    lexical_prefilter_min_jaccard: float = Field(default=0.05)


class SemanticSimilarityProfileDeepModel(BaseModel):
    mode: str = Field(default="advanced")
    self_similarity_threshold: float = Field(default=0.65)
    cross_speaker_similarity_threshold: float = Field(default=0.55)
    top_k_per_segment: int = Field(default=120)
    max_candidate_pairs: int = Field(default=150000)
    timeout_seconds: float = Field(default=900.0)
    use_lexical_prefilter: bool = Field(default=False)


class SemanticSimilarityProfilesSettingsModel(BaseModel):
    fast: SemanticSimilarityProfileFastModel = Field(
        default_factory=SemanticSimilarityProfileFastModel
    )
    balanced: SemanticSimilarityProfileBalancedModel = Field(
        default_factory=SemanticSimilarityProfileBalancedModel
    )
    deep: SemanticSimilarityProfileDeepModel = Field(
        default_factory=SemanticSimilarityProfileDeepModel
    )
