"""Integration: finalize_group_analysis dependency and skip semantics."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from transcriptx.core.pipeline.group_analysis_runner import finalize_group_analysis
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.target_resolver import (
    AnalysisScope,
    FileTranscriptMember,
)
from transcriptx.core.utils.config import TranscriptXConfig


def _scope_and_members(tmp_path: Path):
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    if not fixture.exists():
        pytest.skip("fixtures/mini_transcript.json not found")
    t1 = tmp_path / "one.json"
    t2 = tmp_path / "two.json"
    shutil.copy(fixture, t1)
    shutil.copy(fixture, t2)
    p1, p2 = str(t1), str(t2)
    scope = AnalysisScope(
        scope_type="group",
        uuid="deps-group",
        key="deps-group",
        display_name="Deps Group",
    )
    members = [
        FileTranscriptMember(file_path=p1, file_name=t1.name, id=1, uuid="m1"),
        FileTranscriptMember(file_path=p2, file_name=t2.name, id=2, uuid="m2"),
    ]
    return scope, members, [p1, p2]


@pytest.mark.integration_core
def test_finalize_missing_dep_writes_warning_and_skips_child(
    tmp_path: Path,
) -> None:
    scope, members, paths = _scope_and_members(tmp_path)
    groups_root = tmp_path / "groups"
    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(groups_root)

    per_results = [
        PerTranscriptResult(
            transcript_path=paths[0],
            transcript_key="one",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "entity_sentiment": {
                    "payload": {"global_stats": {}, "speaker_stats": {}}
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=paths[1],
            transcript_key="two",
            run_id="r2",
            order_index=1,
            output_dir="out/b",
            module_results={
                "entity_sentiment": {
                    "payload": {"global_stats": {}, "speaker_stats": {}}
                }
            },
        ),
    ]

    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=paths,
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=["entity_sentiment"],
        config=cfg,
    )
    assert result["status"] == "completed"
    assert "entity_sentiment" not in result["aggregations"]
    warnings = json.loads(
        (Path(result["group_output_dir"]) / "aggregation_warnings.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(
        w.get("code") == "MISSING_DEP"
        and w.get("aggregation_key") == "entity_sentiment"
        and "ner" in (w.get("missing_deps") or [])
        for w in warnings
    )
    assert not (Path(result["group_output_dir"]) / "entity_sentiment").exists()
