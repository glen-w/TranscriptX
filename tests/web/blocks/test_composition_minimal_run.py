"""Composition smoke tests using minimal_run fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.web.blocks.availability import check_block_availability
from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.context import build_block_context
from transcriptx.web.blocks.registry import clear_registry_for_tests, get_block
from transcriptx.web.services import ArtifactService

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "composition" / "minimal_run"
)


@pytest.fixture(autouse=True)
def _registry():
    clear_registry_for_tests()
    register_builtin_blocks()
    yield
    clear_registry_for_tests()


@pytest.fixture
def minimal_run(tmp_path: Path) -> Path:
    """Copy minimal_run fixture to a temp directory."""
    import shutil

    if not FIXTURE_ROOT.exists():
        pytest.skip("minimal_run fixture not present")
    dest = tmp_path / "minimal_run"
    shutil.copytree(FIXTURE_ROOT, dest)
    return dest


def test_minimal_run_lists_artifacts(minimal_run: Path) -> None:
    artifacts = ArtifactService.list_artifacts(minimal_run)
    modules = {a.module for a in artifacts}
    assert "sentiment" in modules
    assert "highlights" in modules


def test_block_availability_on_minimal_run(minimal_run: Path) -> None:
    artifacts = ArtifactService.list_artifacts(minimal_run)
    ctx = build_block_context(
        run_root=minimal_run,
        subject_type="transcript",
        subject_id="mini",
        run_id="20240101_120000",
        session_name="mini",
        artifacts=artifacts,
        run_results=json.loads((minimal_run / "run_results.json").read_text()),
        layout_profile_id="default",
    )
    highlights = get_block("highlights")
    assert highlights is not None
    result = check_block_availability(highlights, ctx)
    assert result.available
    assert result.matched_artifacts
