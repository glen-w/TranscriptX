"""Structural ownership and defaults parity for all Pydantic config pilots."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from transcriptx.core.config.pydantic_bridge import PYDANTIC_REGISTRY_PILOTS
from transcriptx.core.utils.config.analysis import AnalysisConfig

# Structural ownership tests live in test_registry_ownership.py (canonical).

_ANALYSIS_PARTIAL_PREFIX = "analysis_"


@pytest.mark.parametrize(
    "spec",
    [s for s in PYDANTIC_REGISTRY_PILOTS if s.dataclass_type is not None],
    ids=lambda s: s.pilot_id,
)
def test_dataclass_pilot_defaults_match(spec) -> None:
    assert spec.model().model_dump() == asdict(spec.dataclass_type())


@pytest.mark.parametrize(
    "spec",
    [
        s
        for s in PYDANTIC_REGISTRY_PILOTS
        if s.pilot_id.startswith(_ANALYSIS_PARTIAL_PREFIX)
    ],
    ids=lambda s: s.pilot_id,
)
def test_partial_analysis_pilot_defaults_match(spec) -> None:
    inst = AnalysisConfig()
    expected = {name: getattr(inst, name) for name in spec.model.model_fields}
    assert spec.model().model_dump() == expected


@pytest.mark.parametrize(
    "pilot_id,payload_attr",
    [
        ("quality_filtering_profiles", "quality_filtering_profiles"),
        ("semantic_similarity_profiles", "semantic_similarity_profiles"),
        ("quick_analysis_settings", "quick_analysis_settings"),
        ("full_analysis_settings", "full_analysis_settings"),
    ],
)
def test_dict_profile_pilot_defaults_match(pilot_id: str, payload_attr: str) -> None:
    spec = next(s for s in PYDANTIC_REGISTRY_PILOTS if s.pilot_id == pilot_id)
    runtime = getattr(AnalysisConfig(), payload_attr)
    assert spec.model().model_dump() == runtime
