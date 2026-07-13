"""Integration: finalize with aggregation disabled uses real GroupOutputService I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.group_analysis_runner import finalize_group_analysis
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.target_resolver import (
    AnalysisScope,
    FileTranscriptMember,
)
from transcriptx.core.utils.config import TranscriptXConfig


@pytest.mark.integration_core
def test_finalize_disabled_writes_real_scaffold_artifacts(tmp_path: Path) -> None:
    groups_root = tmp_path / "groups"
    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = False
    cfg.group_analysis.output_dir = str(groups_root)
    cfg.group_analysis.scaffold_by_session = True
    cfg.group_analysis.scaffold_by_speaker = False
    cfg.group_analysis.scaffold_comparisons = True

    scope = AnalysisScope(
        scope_type="group",
        uuid="disabled-scaffold",
        key="disabled-key",
        display_name="Disabled Scaffold",
    )
    p1 = str(tmp_path / "one.json")
    p2 = str(tmp_path / "two.json")
    Path(p1).write_text("{}", encoding="utf-8")
    Path(p2).write_text("{}", encoding="utf-8")
    members = [
        FileTranscriptMember(file_path=p1, file_name="one.json", id=1, uuid="u1"),
        FileTranscriptMember(file_path=p2, file_name="two.json", id=2, uuid="u2"),
    ]
    per_results = [
        PerTranscriptResult(
            transcript_path=p1,
            transcript_key="one",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={},
            modules_run=["stats"],
        ),
        PerTranscriptResult(
            transcript_path=p2,
            transcript_key="two",
            run_id="r2",
            order_index=1,
            output_dir="out/b",
            module_results={},
            modules_run=["stats"],
        ),
    ]

    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=[p1, p2],
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=["stats"],
        config=cfg,
    )

    out = Path(result["group_output_dir"])
    assert out.is_dir()
    assert (out / "combined").is_dir()
    assert (out / "by_session").is_dir()
    assert not (out / "by_speaker").exists()
    assert (out / "comparisons").is_dir()
    assert (out / "summary.txt").exists()
    assert "Aggregation disabled" in (out / "summary.txt").read_text(encoding="utf-8")
    assert (out / "group_run_metadata.json").exists()
    assert (out / "group_manifest.json").exists()
    assert (out / "group_member_runs.json").exists()
    assert (out / "run_results.json").exists()
    assert (out / "manifest.json").exists()

    member_runs = json.loads(
        (out / "group_member_runs.json").read_text(encoding="utf-8")
    )
    assert [m["order_index"] for m in member_runs["members"]] == [0, 1]
    meta = json.loads((out / "group_run_metadata.json").read_text(encoding="utf-8"))
    assert meta["member_transcript_ids"] == [1, 2]
    assert result["status"] == "completed"
    assert "disabled" in (result.get("warning") or "").lower()
