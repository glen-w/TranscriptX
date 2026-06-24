"""Tests for module_metrics block."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from transcriptx.web.blocks.context import BlockContext, BlockServices
from transcriptx.web.blocks.implementations.overview import render_module_metrics
from transcriptx.web.blocks.loader import ArtifactContentLoader
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.models.artifact import Artifact


def _artifact(module: str, rel: str) -> Artifact:
    return Artifact(
        id=f"{module}_json",
        module=module,
        kind="data_json",
        scope=None,
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path=rel,
        mime="application/json",
        bytes=100,
        mtime="",
        tags=[],
    )


def test_module_metrics_empty_without_selection() -> None:
    import streamlit as st

    st.session_state.pop("analysis_module", None)
    ctx = BlockContext(
        run_root=Path("/tmp/run"),
        subject_type="transcript",
        subject_id="sess",
        run_id="run",
        session_name="sess",
        artifacts=(),
        run_results=None,
        services=BlockServices(content_loader=None),
        layout_profile_id="default",
    )
    render_module_metrics(
        ctx, BlockPlacement(placement_id="test", block_id="module_metrics")
    )
    # No exception; block shows caption when no module selected.


@patch("transcriptx.web.blocks.implementations.overview.st")
@patch("transcriptx.web.blocks.implementations.overview.SummaryService")
def test_module_metrics_wires_summary_service(
    mock_summary: MagicMock,
    mock_st: MagicMock,
) -> None:
    mock_st.session_state = {"analysis_module": "sentiment"}
    mock_summary.extract_analysis_summary.return_value = {
        "has_data": True,
        "key_metrics": {"polarity": 0.8},
        "highlights": ["Strong positive tone"],
    }
    run_root = Path("/tmp/run")
    artifacts = (_artifact("sentiment", "sentiment/data/global/_sentiment.json"),)
    loader = ArtifactContentLoader(run_root, artifacts)
    loader.load_first_module_json = MagicMock(return_value={"score": 1})  # type: ignore[method-assign]
    ctx = BlockContext(
        run_root=run_root,
        subject_type="transcript",
        subject_id="sess",
        run_id="run",
        session_name="sess",
        artifacts=artifacts,
        run_results=None,
        services=BlockServices(content_loader=loader),
        layout_profile_id="default",
    )
    render_module_metrics(
        ctx, BlockPlacement(placement_id="test", block_id="module_metrics")
    )
    mock_summary.extract_analysis_summary.assert_called_once_with(
        "sentiment", {"score": 1}
    )
