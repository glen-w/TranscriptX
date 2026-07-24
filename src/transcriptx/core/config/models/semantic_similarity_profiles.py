"""Pydantic schema for analysis.semantic_similarity_profiles."""

from pydantic import BaseModel, Field


class SemanticSimilarityV2ProfilesSettingsModelFastV2Model(BaseModel):
    self_similarity_threshold: float = Field(default=0.78)
    cross_speaker_similarity_threshold: float = Field(default=0.68)
    top_k_per_segment: int = Field(default=20)
    max_candidate_pairs: int = Field(default=15000)
    timeout_seconds: float = Field(default=120.0)
    use_lexical_prefilter: bool = Field(default=True)
    lexical_prefilter_min_jaccard: float = Field(default=0.1)
    mode: str = Field(default="basic")


class SemanticSimilarityV2ProfilesSettingsModelBalancedV2Model(BaseModel):
    self_similarity_threshold: float = Field(default=0.72)
    cross_speaker_similarity_threshold: float = Field(default=0.62)
    top_k_per_segment: int = Field(default=50)
    max_candidate_pairs: int = Field(default=50000)
    timeout_seconds: float = Field(default=300.0)
    use_lexical_prefilter: bool = Field(default=True)
    lexical_prefilter_min_jaccard: float = Field(default=0.05)


class SemanticSimilarityV2ProfilesSettingsModelDeepV2Model(BaseModel):
    mode: str = Field(default="advanced")
    self_similarity_threshold: float = Field(default=0.65)
    cross_speaker_similarity_threshold: float = Field(default=0.55)
    top_k_per_segment: int = Field(default=120)
    max_candidate_pairs: int = Field(default=150000)
    timeout_seconds: float = Field(default=900.0)
    use_lexical_prefilter: bool = Field(default=False)


class SemanticSimilarityV2ProfilesSettingsModel(BaseModel):
    fast_v2: SemanticSimilarityV2ProfilesSettingsModelFastV2Model = Field(
        default_factory=SemanticSimilarityV2ProfilesSettingsModelFastV2Model
    )
    balanced_v2: SemanticSimilarityV2ProfilesSettingsModelBalancedV2Model = Field(
        default_factory=SemanticSimilarityV2ProfilesSettingsModelBalancedV2Model
    )
    deep_v2: SemanticSimilarityV2ProfilesSettingsModelDeepV2Model = Field(
        default_factory=SemanticSimilarityV2ProfilesSettingsModelDeepV2Model
    )
