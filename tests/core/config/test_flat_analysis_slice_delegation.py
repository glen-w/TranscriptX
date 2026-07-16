"""Flat AnalysisConfig pilot-slice delegation tests."""

from __future__ import annotations

import pytest

from transcriptx.core.config.pydantic_bridge import PYDANTIC_REGISTRY_PILOTS
from transcriptx.core.utils.config.analysis import AnalysisConfig

from .delegation_test_utils import (
    assert_normalized_defaults_parity,
    assert_ownership_invariant_unchanged,
    without_transcriptx_env,
)

_SLICES = (
    "analysis_sentiment",
    "analysis_ner",
    "analysis_wordcloud",
    "analysis_interaction",
    "analysis_entity",
    "analysis_legacy_semantic",
)


def _spec(pilot_id: str):
    return next(s for s in PYDANTIC_REGISTRY_PILOTS if s.pilot_id == pilot_id)


@pytest.mark.parametrize("pilot_id", _SLICES)
def test_slice_defaults_match_model(pilot_id: str) -> None:
    assert_ownership_invariant_unchanged()
    spec = _spec(pilot_id)
    with without_transcriptx_env():
        inst = AnalysisConfig()
        actual = {name: getattr(inst, name) for name in spec.model.model_fields}
    assert_normalized_defaults_parity(actual, spec.model().model_dump())


@pytest.mark.parametrize("pilot_id", _SLICES)
def test_delegated_slice_kwargs_raise(pilot_id: str) -> None:
    spec = _spec(pilot_id)
    field_name = next(iter(spec.model.model_fields))
    with pytest.raises(TypeError):
        AnalysisConfig(**{field_name: object()})


def test_runtime_only_use_dag_pipeline_kwargs_still_work() -> None:
    cfg = AnalysisConfig(use_dag_pipeline=False)
    assert cfg.use_dag_pipeline is False
    assert cfg.sentiment_window_size == 10


def test_previously_delegated_slices_untouched_when_passing_runtime_kwarg() -> None:
    cfg = AnalysisConfig(use_dag_pipeline=False)
    assert cfg.ner_labels  # hydrated
    assert cfg.wordcloud_max_words == 100
