"""Tests for block availability."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.blocks.availability import check_block_availability
from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.context import build_block_context
from transcriptx.web.blocks.registry import clear_registry_for_tests, get_block
from transcriptx.web.models.artifact import Artifact


def _artifact(module: str, rel_path: str) -> Artifact:
    return Artifact(
        id=rel_path,
        kind="data_json",
        module=module,
        scope=None,
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path=rel_path,
        bytes=1,
        mtime="",
        mime="application/json",
        tags=[],
    )


def test_run_scoped_block_unavailable_without_run() -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    spec = get_block("highlights")
    assert spec is not None
    ctx = build_block_context(
        run_root=None,
        subject_type=None,
        subject_id=None,
        run_id=None,
        session_name=None,
        artifacts=(),
        run_results=None,
        layout_profile_id="default",
    )
    result = check_block_availability(spec, ctx)
    assert not result.available
    assert "run" in (result.reason or "").lower()


def test_highlights_unavailable_without_artifact() -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    spec = get_block("highlights")
    assert spec is not None
    ctx = build_block_context(
        run_root=Path("/tmp/run"),
        subject_type="transcript",
        subject_id="slug",
        run_id="run1",
        session_name="slug/run1",
        artifacts=(),
        run_results=None,
        layout_profile_id="default",
    )
    result = check_block_availability(spec, ctx)
    assert not result.available
    assert result.reason


def test_highlights_available_with_artifact() -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    spec = get_block("highlights")
    assert spec is not None
    art = _artifact("highlights", "highlights/out/_highlights.json")
    ctx = build_block_context(
        run_root=Path("/tmp/run"),
        subject_type="transcript",
        subject_id="slug",
        run_id="run1",
        session_name="slug/run1",
        artifacts=(art,),
        run_results=None,
        layout_profile_id="default",
    )
    result = check_block_availability(spec, ctx)
    assert result.available


def test_llm_summary_placement_narrows_module_deps() -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    spec = get_block("llm_summary_block")
    assert spec is not None
    art = _artifact(
        "narrative_summary", "narrative_summary/out/_narrative_summary.json"
    )
    ctx = build_block_context(
        run_root=Path("/tmp/run"),
        subject_type="transcript",
        subject_id="slug",
        run_id="run1",
        session_name="slug/run1",
        artifacts=(art,),
        run_results=None,
        layout_profile_id="default",
    )
    available_for_narrative = check_block_availability(
        spec,
        ctx,
        placement_params={
            "module": "narrative_summary",
            "artifact_stem": "_narrative_summary",
        },
    )
    assert available_for_narrative.available
    unavailable_for_llm = check_block_availability(
        spec,
        ctx,
        placement_params={"module": "llm_summary", "artifact_stem": "_llm_summary"},
    )
    assert not unavailable_for_llm.available


def test_action_items_unavailable_uses_failure_guidance_not_rerun_hint() -> None:
    clear_registry_for_tests()
    register_builtin_blocks()
    spec = get_block("llm_action_items_block")
    assert spec is not None
    run_results = {
        "schema_version": 2,
        "modules_enabled": ["llm_action_items"],
        "modules_run": [],
        "modules_failed": ["llm_action_items"],
        "modules_skipped": [],
        "module_outcomes": [
            {
                "module_id": "llm_action_items",
                "execution_status": "failed",
                "error_code": "llm_invalid_response",
                "error_message": (
                    "Action items output is not valid JSON: Unterminated string "
                    "starting at: line 760 column 13 (char 26531)"
                ),
            }
        ],
    }
    ctx = build_block_context(
        run_root=Path("/tmp/run"),
        subject_type="transcript",
        subject_id="slug",
        run_id="run1",
        session_name="slug/run1",
        artifacts=(),
        run_results=run_results,
        layout_profile_id="default",
    )
    result = check_block_availability(spec, ctx)
    assert not result.available
    reason = result.reason or ""
    assert "failed for this run" in reason
    assert "same settings will usually fail" in reason.lower()
    assert "Run the required analysis modules" not in reason
