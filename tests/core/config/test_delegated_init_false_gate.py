"""Gate: delegated dataclass fields use init=False and hydrate coverage."""

from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest

from transcriptx.core.utils.config.analysis import (
    CorrectionsConfig,
    CorrectionsLlmConfig,
    HighlightsColdOpen,
    HighlightsConfig,
    HighlightsConflict,
    HighlightsCounts,
    HighlightsMergeAdjacent,
    HighlightsOutput,
    HighlightsSections,
    HighlightsThresholds,
    HighlightsWeights,
    LLMActionItemsConfig,
    LLMSpeakerSummaryConfig,
    LLMSummaryConfig,
    PausesConfig,
    SummaryCommitments,
    SummaryConfig,
    SummaryCounts,
    SummarySections,
    VoiceConfig,
    EchoesConfig,
    MomentumConfig,
    MomentsConfig,
    AffectTensionConfig,
    ActsConfig,
    TopicModelingConfig,
    SpeakerExemplarsConfig,
    BERTopicConfig,
    SemanticSimilarityConfig,
    VectorizationConfig,
    TagExtractionConfig,
    QAAnalysisConfig,
    TemporalDynamicsConfig,
    AnalysisConfig,
)
from transcriptx.core.utils.config.system import (
    AudioPreprocessingConfig,
    LLMConfig,
    LoggingConfig,
)
from transcriptx.core.utils.config.workflow import (
    DashboardConfig,
    GroupAnalysisConfig,
    InputConfig,
    MetadataConfig,
    OutputConfig,
    SpeakerGateConfig,
    WorkflowConfig,
)

# Root delegated dataclasses: require __post_init__ hydrate.
_ROOT_DELEGATED = (
    PausesConfig,
    VoiceConfig,
    CorrectionsConfig,
    CorrectionsLlmConfig,
    SummaryConfig,
    HighlightsConfig,
    LLMSummaryConfig,
    LLMSpeakerSummaryConfig,
    LLMActionItemsConfig,
    EchoesConfig,
    MomentumConfig,
    MomentsConfig,
    AffectTensionConfig,
    ActsConfig,
    TopicModelingConfig,
    SpeakerExemplarsConfig,
    BERTopicConfig,
    SemanticSimilarityConfig,
    VectorizationConfig,
    TagExtractionConfig,
    QAAnalysisConfig,
    TemporalDynamicsConfig,
    LLMConfig,
    LoggingConfig,
    AudioPreprocessingConfig,
    WorkflowConfig,
    SpeakerGateConfig,
    InputConfig,
    OutputConfig,
    GroupAnalysisConfig,
    MetadataConfig,
    DashboardConfig,
)

# Nested children: init=False only; coverage transitive via parent dump.
_NESTED_CHILDREN = (
    HighlightsCounts,
    HighlightsThresholds,
    HighlightsWeights,
    HighlightsSections,
    HighlightsOutput,
    HighlightsMergeAdjacent,
    HighlightsConflict,
    HighlightsColdOpen,
    SummaryCounts,
    SummarySections,
    SummaryCommitments,
)


def _assert_all_fields_init_false(cls: type) -> None:
    assert is_dataclass(cls)
    for f in fields(cls):
        assert f.init is False, f"{cls.__name__}.{f.name} must be init=False"


@pytest.mark.parametrize("cls", _ROOT_DELEGATED, ids=lambda c: c.__name__)
def test_root_delegated_fields_init_false_and_post_init(cls: type) -> None:
    _assert_all_fields_init_false(cls)
    assert hasattr(cls, "__post_init__"), f"{cls.__name__} needs __post_init__ hydrate"
    # Construction without kwargs must succeed (hydrate runs).
    inst = cls()
    for f in fields(cls):
        assert hasattr(inst, f.name)


@pytest.mark.parametrize("cls", _NESTED_CHILDREN, ids=lambda c: c.__name__)
def test_nested_child_fields_init_false_no_own_post_init_required(cls: type) -> None:
    _assert_all_fields_init_false(cls)
    # Children are reconstructed by parent; direct Cls() is not the runtime path.


def test_mapping_store_attrs_init_false_on_analysis_config() -> None:
    for name in (
        "quality_filtering_profiles",
        "semantic_similarity_profiles",
        "quick_analysis_settings",
        "full_analysis_settings",
    ):
        f = next(x for x in fields(AnalysisConfig) if x.name == name)
        assert f.init is False
    # Construction hydrates stores
    ac = AnalysisConfig()
    assert isinstance(ac.quality_filtering_profiles, dict)
    assert ac.quick_analysis_settings
