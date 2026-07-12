"""Unit tests for pydantic_model_to_field_metadata converter."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

from transcriptx.core.config.models.semantic_similarity_v2 import (
    SemanticSimilarityV2SettingsModel,
)
from transcriptx.core.config.pydantic_registry import pydantic_model_to_field_metadata


class _SampleModel(BaseModel):
    mode: Literal["basic", "advanced"] = "basic"
    batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size.",
        json_schema_extra={"advanced": True},
    )
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class _ModernTypingModel(BaseModel):
    optional_label: Optional[str] = None
    nullable_label: str | None = None
    tagged_count: Annotated[int, "count"] = 0
    tags: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    window: tuple[int, int] = (0, 10)
    positive: int = Field(default=1, gt=0)
    under_cap: int = Field(default=50, lt=100)


def test_literal_maps_to_choices_and_str_type() -> None:
    meta = pydantic_model_to_field_metadata(
        _SampleModel, dotpath_prefix="test.sample", category="test"
    )
    mode = meta["test.sample.mode"]
    assert mode.type is str
    assert list(mode.choices) == ["basic", "advanced"]
    assert mode.default == "basic"


def test_ge_le_map_to_min_max() -> None:
    meta = pydantic_model_to_field_metadata(
        _SampleModel, dotpath_prefix="test.sample", category="test"
    )
    batch = meta["test.sample.batch_size"]
    assert batch.min == 1
    assert batch.max is None
    threshold = meta["test.sample.threshold"]
    assert threshold.min == 0.0
    assert threshold.max == 1.0


def test_json_schema_extra_advanced_flag() -> None:
    meta = pydantic_model_to_field_metadata(
        _SampleModel, dotpath_prefix="test.sample", category="test"
    )
    assert meta["test.sample.batch_size"].advanced is True
    assert meta["test.sample.mode"].advanced is False


def test_dotpath_prefix_and_category() -> None:
    meta = pydantic_model_to_field_metadata(
        SemanticSimilarityV2SettingsModel,
        dotpath_prefix="analysis.semantic_similarity_v2",
        category="analysis",
    )
    assert "analysis.semantic_similarity_v2.enabled" in meta
    assert meta["analysis.semantic_similarity_v2.enabled"].category == "analysis"


def test_defaults_match_model_dump() -> None:
    meta = pydantic_model_to_field_metadata(
        SemanticSimilarityV2SettingsModel,
        dotpath_prefix="analysis.semantic_similarity_v2",
        category="analysis",
    )
    expected = SemanticSimilarityV2SettingsModel().model_dump()
    for name, value in expected.items():
        key = f"analysis.semantic_similarity_v2.{name}"
        assert meta[key].default == value


def test_modern_typing_annotations_resolve_to_container_types() -> None:
    meta = pydantic_model_to_field_metadata(
        _ModernTypingModel, dotpath_prefix="test.modern", category="test"
    )
    assert meta["test.modern.optional_label"].type is str
    assert meta["test.modern.nullable_label"].type is str
    assert meta["test.modern.tagged_count"].type is int
    assert meta["test.modern.tags"].type is list
    assert meta["test.modern.weights"].type is dict
    assert meta["test.modern.window"].type is tuple


def test_gt_lt_bounds_are_validation_only_not_registry_metadata() -> None:
    meta = pydantic_model_to_field_metadata(
        _ModernTypingModel, dotpath_prefix="test.modern", category="test"
    )
    assert meta["test.modern.positive"].min is None
    assert meta["test.modern.under_cap"].max is None

    with pytest.raises(ValidationError):
        _ModernTypingModel(positive=0)
    with pytest.raises(ValidationError):
        _ModernTypingModel(under_cap=100)


class _GeGtModel(BaseModel):
    bounded: int = Field(default=5, ge=1, gt=0)


def test_ge_wins_over_gt_for_registry_min() -> None:
    meta = pydantic_model_to_field_metadata(
        _GeGtModel, dotpath_prefix="test.ge_gt", category="test"
    )
    assert meta["test.ge_gt.bounded"].min == 1.0


def test_workflow_optional_nested_model_leaf_dotpaths() -> None:
    from transcriptx.core.config.models.workflow import WorkflowSettingsModel
    from transcriptx.core.config.pydantic_registry import collect_model_leaf_dotpaths

    keys = collect_model_leaf_dotpaths(
        WorkflowSettingsModel,
        dotpath_prefix="workflow",
    )
    assert "workflow.speaker_gate.threshold_value" in keys
    assert "workflow.speaker_gate.mode" in keys


@pytest.mark.parametrize(
    ("key", "expected_type", "expected_default", "min_val", "max_val"),
    [
        ("llm.model", str, None, None, None),
        ("llm.base_url", str, None, None, None),
        ("llm.max_output_tokens", int, 2048, None, None),
        ("llm.request_timeout", float, 1350.0, None, None),
    ],
)
def test_llm_registry_metadata_fields(
    key: str,
    expected_type: type,
    expected_default: object,
    min_val: float | None,
    max_val: float | None,
) -> None:
    from transcriptx.core.config.models.llm import LLMSettingsModel

    meta = pydantic_model_to_field_metadata(
        LLMSettingsModel, dotpath_prefix="llm", category="llm"
    )
    field = meta[key]
    assert field.type is expected_type
    assert field.default == expected_default
    assert field.min == min_val
    assert field.max == max_val


@pytest.mark.parametrize(
    ("key", "choices", "min_val", "field_type"),
    [
        (
            "workflow.speaker_gate.mode",
            ["ignore", "warn", "enforce"],
            None,
            str,
        ),
        (
            "workflow.speaker_gate.threshold_type",
            ["absolute", "percentage"],
            None,
            str,
        ),
        ("workflow.speaker_gate.threshold_value", None, 0.0, float),
        ("workflow.speaker_gate.exemplar_count", None, 0.0, int),
    ],
)
def test_workflow_speaker_gate_registry_metadata(
    key: str,
    choices: list[str] | None,
    min_val: float | None,
    field_type: type,
) -> None:
    from transcriptx.core.config.models.workflow import WorkflowSettingsModel

    meta = pydantic_model_to_field_metadata(
        WorkflowSettingsModel, dotpath_prefix="workflow", category="workflow"
    )
    field = meta[key]
    assert field.type is field_type
    assert field.min == min_val
    if choices is not None:
        assert list(field.choices) == choices
