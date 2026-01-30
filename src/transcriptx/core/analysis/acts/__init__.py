"""Dialogue act analysis package."""

from transcriptx.core.analysis.acts.analysis import ActsAnalysis
from transcriptx.core.analysis.acts.classification import (
    classify_utterance,
    classify_with_both_methods,
    ml_classify_utterance,
    reset_ml_classifier,
)
from transcriptx.core.analysis.acts.confidence import (
    adjust_confidence_for_context,
    calculate_act_confidence,
)
from transcriptx.core.analysis.acts.config import (
    ACT_TYPE_DEFINITIONS,
    ActClassificationConfig,
    ClassificationMethod,
    ContextWindowType,
    get_act_config,
    get_all_act_types,
    update_act_config,
)
from transcriptx.core.analysis.acts.output import tag_acts
from transcriptx.core.analysis.acts.rules import (
    CUE_PHRASES,
    enhanced_fallback_classification,
    rules_classify_utterance,
)

ACT_TYPES = get_all_act_types()

__all__ = [
    "ActsAnalysis",
    "ACT_TYPES",
    "ACT_TYPE_DEFINITIONS",
    "ActClassificationConfig",
    "ClassificationMethod",
    "ContextWindowType",
    "get_act_config",
    "get_all_act_types",
    "update_act_config",
    "classify_utterance",
    "classify_with_both_methods",
    "ml_classify_utterance",
    "reset_ml_classifier",
    "rules_classify_utterance",
    "enhanced_fallback_classification",
    "adjust_confidence_for_context",
    "calculate_act_confidence",
    "tag_acts",
    "CUE_PHRASES",
]
