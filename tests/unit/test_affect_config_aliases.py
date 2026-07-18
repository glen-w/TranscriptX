"""Config alias conflict and nested emotion-family settings tests."""

from __future__ import annotations

import pytest

from transcriptx.core.config.models.analysis_emotion_family import (
    ContextualEmotionSettingsModel,
    EmotionFamilyAliasConflictError,
    EmotionLexicalSettingsModel,
    FineGrainedEmotionSettingsModel,
    validate_emotion_family_aliases,
)
from transcriptx.core.utils.config.analysis import (
    AnalysisConfig,
    ContextualEmotionConfig,
    EmotionLexicalConfig,
    FineGrainedEmotionConfig,
)


@pytest.mark.unit
def test_nested_emotion_family_configs_hydrate_defaults():
    lexical = EmotionLexicalConfig()
    contextual = ContextualEmotionConfig()
    fine = FineGrainedEmotionConfig()
    assert (
        lexical.low_coverage_threshold
        == EmotionLexicalSettingsModel().low_coverage_threshold
    )
    assert contextual.profile_id == ContextualEmotionSettingsModel().profile_id
    assert fine.profile_id == FineGrainedEmotionSettingsModel().profile_id
    analysis = AnalysisConfig()
    assert analysis.contextual_emotion.profile_id == contextual.profile_id
    assert analysis.fine_grained_emotion.batch_size == fine.batch_size


@pytest.mark.unit
def test_alias_conflict_fails_when_both_explicit_and_disagree():
    with pytest.raises(EmotionFamilyAliasConflictError):
        validate_emotion_family_aliases(
            legacy_emotion_model_name="some-other/model",
            contextual_profile_id="contextual_hartmann_distilroberta_v1",
            legacy_explicitly_set=True,
            nested_explicitly_set=True,
        )


@pytest.mark.unit
def test_alias_accepts_when_only_one_side_set():
    validate_emotion_family_aliases(
        legacy_emotion_model_name="some-other/model",
        contextual_profile_id="contextual_hartmann_distilroberta_v1",
        legacy_explicitly_set=True,
        nested_explicitly_set=False,
    )


@pytest.mark.unit
def test_alias_accepts_equivalent_strings():
    validate_emotion_family_aliases(
        legacy_emotion_model_name="contextual_hartmann_distilroberta_v1",
        contextual_profile_id="contextual_hartmann_distilroberta_v1",
        legacy_explicitly_set=True,
        nested_explicitly_set=True,
    )
