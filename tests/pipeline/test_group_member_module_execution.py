"""Group pipeline runs the same selected modules on each member transcript."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline import pipeline as pipeline_mod
from transcriptx.core.pipeline.target_resolver import AnalysisScope


@pytest.mark.unit
def test_group_pipeline_runs_identical_modules_on_each_member() -> None:
    """Group path must invoke the single-transcript DAG once per member path."""
    paths = ["/tmp/session_a.json", "/tmp/session_b.json", "/tmp/session_c.json"]
    modules = ["highlights", "insights", "llm_summary", "stats"]

    members = [
        SimpleNamespace(file_path=p, id=i, uuid=f"u{i}") for i, p in enumerate(paths)
    ]
    scope = AnalysisScope(
        scope_type="group",
        key="gk",
        uuid="guuid",
        display_name="G",
    )

    calls: list[dict[str, Any]] = []

    def _fake_single(**kwargs: Any) -> dict[str, Any]:
        calls.append(dict(kwargs))
        path = kwargs["transcript_path"]
        idx = paths.index(path)
        return {
            "transcript_key": f"tk{idx}",
            "run_id": f"r{idx}",
            "output_dir": f"/out/{idx}",
            "module_results": {
                m: {"payload": {"ok": True}} for m in kwargs["selected_modules"]
            },
            "modules_run": list(kwargs["selected_modules"]),
            "skipped_modules": [],
            "errors": [],
        }

    finalize = MagicMock(return_value={"status": "ok", "group": True})

    with (
        patch.object(
            pipeline_mod,
            "resolve_analysis_target",
            return_value=(scope, members),
        ),
        patch.object(pipeline_mod, "ensure_data_dirs"),
        patch.object(
            pipeline_mod,
            "_run_single_analysis_pipeline",
            side_effect=_fake_single,
        ),
        patch.object(pipeline_mod, "finalize_group_analysis", finalize),
    ):
        result = pipeline_mod.run_analysis_pipeline(
            target=SimpleNamespace(),
            selected_modules=modules,
        )

    assert result == {"status": "ok", "group": True}
    assert len(calls) == 3
    for call in calls:
        assert call["selected_modules"] == modules
        assert call["run_id_override"] is None
        assert call["output_dir_override"] is None

    finalize.assert_called_once()
    kw = finalize.call_args.kwargs
    assert kw["selected_modules"] == modules
    assert kw["resolved_paths"] == paths
    ptrs = kw["per_transcript_results"]
    assert [p.order_index for p in ptrs] == [0, 1, 2]
    assert [p.transcript_path for p in ptrs] == paths
    for ptr in ptrs:
        assert ptr.modules_run == modules
        assert set(ptr.module_results) == set(modules)


@pytest.mark.unit
def test_group_pipeline_preserves_per_member_skips_in_envelope() -> None:
    paths = ["/tmp/a.json", "/tmp/b.json"]
    modules = ["llm_summary", "highlights"]
    members = [
        SimpleNamespace(file_path=p, id=i, uuid=f"u{i}") for i, p in enumerate(paths)
    ]
    scope = AnalysisScope(
        scope_type="group",
        key="gk",
        uuid="guuid",
        display_name="G",
    )

    def _fake_single(**kwargs: Any) -> dict[str, Any]:
        path = kwargs["transcript_path"]
        if path.endswith("a.json"):
            return {
                "transcript_key": "tka",
                "run_id": "ra",
                "output_dir": "/out/a",
                "module_results": {
                    "highlights": {"payload": {"themes": []}},
                },
                "modules_run": ["highlights"],
                "skipped_modules": [
                    {"module": "llm_summary", "reason": "llm_disabled"}
                ],
                "errors": [],
            }
        return {
            "transcript_key": "tkb",
            "run_id": "rb",
            "output_dir": "/out/b",
            "module_results": {
                "highlights": {"payload": {"themes": []}},
                "llm_summary": {"payload": {"summary": "ok"}},
            },
            "modules_run": ["highlights", "llm_summary"],
            "skipped_modules": [],
            "errors": [],
        }

    finalize = MagicMock(return_value={"status": "ok"})
    with (
        patch.object(
            pipeline_mod,
            "resolve_analysis_target",
            return_value=(scope, members),
        ),
        patch.object(pipeline_mod, "ensure_data_dirs"),
        patch.object(
            pipeline_mod,
            "_run_single_analysis_pipeline",
            side_effect=_fake_single,
        ),
        patch.object(pipeline_mod, "finalize_group_analysis", finalize),
    ):
        pipeline_mod.run_analysis_pipeline(
            target=SimpleNamespace(),
            selected_modules=modules,
        )

    ptrs = finalize.call_args.kwargs["per_transcript_results"]
    assert ptrs[0].skipped_modules[0]["module"] == "llm_summary"
    assert "llm_summary" not in ptrs[0].modules_run
    assert "llm_summary" in ptrs[1].modules_run
    # Same module list was still requested for both members.
    assert finalize.call_args.kwargs["selected_modules"] == modules
