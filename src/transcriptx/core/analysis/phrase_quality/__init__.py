"""Shared phrase quality analysis for themes and content phrases."""

from __future__ import annotations

from transcriptx.core.analysis.phrase_quality.analyser import (
    PHRASE_QUALITY_VERSION,
    analyse_phrase,
    annotations_from_surfaces,
)
from transcriptx.core.analysis.phrase_quality.policies import (
    content_phrase_policy,
    highlight_label_policy,
    theme_label_policy,
)
from transcriptx.core.analysis.phrase_quality.resources import (
    ThemePhraseResources,
    load_theme_phrase_resources,
    resource_fingerprint,
)
from transcriptx.core.analysis.phrase_quality.scoring import (
    adjust_theme_score,
    theme_sort_key,
)
from transcriptx.core.analysis.phrase_quality.types import (
    PhraseFeatures,
    PhraseQualityResult,
    PolicyDecision,
    TokenAnnotation,
)

__all__ = [
    "PHRASE_QUALITY_VERSION",
    "PhraseFeatures",
    "PhraseQualityResult",
    "PolicyDecision",
    "ThemePhraseResources",
    "TokenAnnotation",
    "analyse_phrase",
    "annotations_from_surfaces",
    "adjust_theme_score",
    "content_phrase_policy",
    "highlight_label_policy",
    "load_theme_phrase_resources",
    "resource_fingerprint",
    "theme_label_policy",
    "theme_sort_key",
]
