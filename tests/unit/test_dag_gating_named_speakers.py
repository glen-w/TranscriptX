"""Unit tests for DAG named-speaker gating merge (file-only vs DB resolver)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from transcriptx.core.pipeline.dag_pipeline_run import gating_named_speaker_count


@pytest.mark.unit
def test_gating_uses_max_of_resolver_and_segment_keys() -> None:
    ctx = SimpleNamespace(runtime_flags={"named_speaker_keys": {"a", "b", "c"}})
    with patch(
        "transcriptx.core.pipeline.dag_pipeline_run.named_speaker_count_for_path",
        return_value=1,
    ):
        assert gating_named_speaker_count("/x/y.json", ctx) == 3


@pytest.mark.unit
def test_gating_segment_keys_boost_zero_resolver() -> None:
    ctx = SimpleNamespace(runtime_flags={"named_speaker_keys": {1, 2}})
    with patch(
        "transcriptx.core.pipeline.dag_pipeline_run.named_speaker_count_for_path",
        return_value=0,
    ):
        assert gating_named_speaker_count("/x/y.json", ctx) == 2


@pytest.mark.unit
def test_gating_resolver_only_when_no_context_or_empty_keys() -> None:
    with patch(
        "transcriptx.core.pipeline.dag_pipeline_run.named_speaker_count_for_path",
        return_value=4,
    ):
        assert gating_named_speaker_count("/x/y.json", None) == 4
    ctx = SimpleNamespace(runtime_flags={"named_speaker_keys": set()})
    with patch(
        "transcriptx.core.pipeline.dag_pipeline_run.named_speaker_count_for_path",
        return_value=4,
    ):
        assert gating_named_speaker_count("/x/y.json", ctx) == 4
