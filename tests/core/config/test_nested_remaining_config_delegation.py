"""Parametrized delegation tests for newly hydrated nested analysis subtrees."""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

import pytest

from transcriptx.core.config.pydantic_bridge import PYDANTIC_REGISTRY_PILOTS
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import AnalysisConfig
from transcriptx.core.utils.config.file_overrides import load_config_file_into

from .delegation_test_utils import (
    assert_is_dataclass_subtree,
    assert_mutable_container_independence,
    assert_normalized_defaults_parity,
    assert_ownership_invariant_unchanged,
    assert_subtree_shape_matches_pre_snapshot,
    assert_three_path_access,
    without_transcriptx_env,
)

_NEW_NESTED = (
    "echoes",
    "momentum",
    "moments",
    "topic_shift",
    "affect_tension",
    "acts",
    "topic_modeling",
    "speaker_exemplars",
    "bertopic",
    "semantic_similarity",
    "vectorization",
    "tag_extraction",
    "qa_analysis",
    "temporal_dynamics",
)

# Adapter-owned analysis targets skip raw nested setattr in load_config_file_into,
# then apply via profile adapters when target payloads exist (acts, qa_analysis,
# semantic_similarity, tag_extraction, temporal_dynamics, topic_modeling,
# vectorization).


def _spec_for_subtree(subtree: str):
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if spec.dataclass_type is None:
            continue
        if getattr(AnalysisConfig(), subtree).__class__ is spec.dataclass_type:
            return spec
    raise AssertionError(f"no pilot for subtree {subtree}")


def test_ownership_invariant_unchanged() -> None:
    assert_ownership_invariant_unchanged()


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_default_shape_matches_pre_delegation_snapshot(subtree: str) -> None:
    assert_subtree_shape_matches_pre_snapshot(subtree)


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_normalized_parity_with_pydantic_model(subtree: str) -> None:
    spec = _spec_for_subtree(subtree)
    assert_normalized_defaults_parity(
        asdict(spec.dataclass_type()), spec.model().model_dump()
    )


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_three_path_default_access(subtree: str) -> None:
    spec = _spec_for_subtree(subtree)
    field_name = next(iter(spec.model.model_fields))
    expected = spec.model().model_dump()[field_name]
    assert_three_path_access(subtree, field_name, expected)


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_kwargs_rejected_for_owned_fields(subtree: str) -> None:
    spec = _spec_for_subtree(subtree)
    field_name = next(iter(spec.model.model_fields))
    with pytest.raises(TypeError):
        spec.dataclass_type(**{field_name: object()})


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_mutable_independence(subtree: str) -> None:
    spec = _spec_for_subtree(subtree)
    assert_mutable_container_independence(spec.dataclass_type)


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_file_override_partial_merge(subtree: str, tmp_path: Path) -> None:
    spec = _spec_for_subtree(subtree)
    field_name = None
    new_value = None
    dump = spec.model().model_dump()
    for name, value in dump.items():
        if isinstance(value, bool):
            field_name, new_value = name, (not value)
            break
        if isinstance(value, int) and not isinstance(value, bool):
            field_name, new_value = name, value + 1
            break
        if isinstance(value, float):
            field_name, new_value = name, value + 1.0
            break
    if field_name is None:
        pytest.skip("no simple scalar field")
    with without_transcriptx_env():
        cfg = TranscriptXConfig()
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"analysis": {subtree: {field_name: new_value}}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(config_file))
    assert_is_dataclass_subtree(subtree)
    after = getattr(getattr(cfg.analysis, subtree), field_name)
    # Adapter-owned keys skip raw nested setattr, then apply via adapter
    # get_target_payload → apply_profile_to_config. Non-adapter nested keys
    # merge in-place. Either path must apply the scalar override.
    assert after == new_value


@pytest.mark.parametrize("subtree", _NEW_NESTED)
def test_all_fields_init_false(subtree: str) -> None:
    spec = _spec_for_subtree(subtree)
    for f in fields(spec.dataclass_type):
        assert f.init is False
