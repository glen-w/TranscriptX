"""Unit tests for pydantic_model_to_field_metadata converter."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from transcriptx.core.config.models.semantic_similarity_v2 import (
    SemanticSimilarityV2SettingsModel,
)
from transcriptx.core.config.pydantic_registry import pydantic_model_to_field_metadata


class _SampleModel(BaseModel):
    mode: Literal["basic", "advanced"] = "basic"
    batch_size: int = Field(default=32, ge=1, description="Batch size.", json_schema_extra={"advanced": True})
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


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
