"""Tests for block registry."""

from __future__ import annotations

import pytest

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.registry import (
    DuplicateBlockError,
    clear_registry_for_tests,
    get_block,
    list_blocks,
    register_block,
    validate_block_id,
)
from transcriptx.web.blocks.specs import BlockPrereq, BlockSpec


def _noop_render(ctx, placement) -> None:
    del ctx, placement


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry_for_tests()
    yield
    clear_registry_for_tests()


def test_register_builtin_blocks_loads_catalog() -> None:
    register_builtin_blocks()
    ids = {spec.id for spec in list_blocks()}
    assert "run_health" in ids
    assert "highlights" in ids
    assert "llm_summary_block" in ids
    assert "llm_action_items_block" in ids
    assert "llm_custom_qa_block" in ids
    assert "lexical_diversity_block" in ids
    assert "module_metrics" in ids
    assert "chart_gallery" in ids
    assert "data_artifact_preview" in ids
    assert len(ids) >= 14


def test_duplicate_block_id_raises() -> None:
    spec = BlockSpec(
        id="test_block",
        title="Test",
        group="Test",
        description="Test block",
        render=_noop_render,
    )
    register_block(spec)
    with pytest.raises(DuplicateBlockError):
        register_block(spec)


def test_validate_block_id_unknown() -> None:
    register_builtin_blocks()
    with pytest.raises(ValueError, match="Unknown block_id"):
        validate_block_id("not_a_real_block")


def test_get_block_returns_spec() -> None:
    register_builtin_blocks()
    spec = get_block("artifact_metrics")
    assert spec is not None
    assert spec.prerequisites == BlockPrereq.RUN_SCOPED
