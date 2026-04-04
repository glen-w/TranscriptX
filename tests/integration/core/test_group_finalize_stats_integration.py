"""
Integration: ``finalize_group_analysis`` with real transcripts and stats aggregation.
"""

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

pytestmark = pytest.mark.heavy


def _stats_module_result(words: int, segments: int) -> dict:
    return {
        "stats": {
            "payload": {
                "speaker_stats": [
                    (12.0, "Alice", words, segments, 0.05, 0.0),
                    (8.0, "Bob", max(words // 2, 1), max(segments // 2, 1), 0.02, 0.0),
                ],
                "sentiment_summary": {
                    "Alice": {
                        "compound": 0.0,
                        "pos": 0.33,
                        "neu": 0.34,
                        "neg": 0.33,
                    },
                    "Bob": {
                        "compound": 0.0,
                        "pos": 0.33,
                        "neu": 0.34,
                        "neg": 0.33,
                    },
                },
            }
        }
    }


@pytest.mark.integration_core
def test_finalize_group_analysis_stats_writes_rows_and_aggregation(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")

    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    if not fixture.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    t1 = tmp_path / "one.json"
    t2 = tmp_path / "two.json"
    shutil.copy(fixture, t1)
    shutil.copy(fixture, t2)

    groups_root = tmp_path / "groups"
    groups_root.mkdir(parents=True, exist_ok=True)

    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(groups_root)

    scope = AnalysisScope(
        scope_type="group",
        uuid="test-group-uuid",
        key="test-group-key",
        display_name="Integration Group",
    )
    p1, p2 = str(t1), str(t2)
    members = [
        FileTranscriptMember(
            file_path=p1, file_name=t1.name, id=101, uuid="member-uuid-1"
        ),
        FileTranscriptMember(
            file_path=p2, file_name=t2.name, id=102, uuid="member-uuid-2"
        ),
    ]

    per_results = [
        PerTranscriptResult(
            transcript_path=p1,
            transcript_key="one",
            run_id="run-a",
            order_index=0,
            output_dir="out/a",
            module_results=_stats_module_result(10, 2),
        ),
        PerTranscriptResult(
            transcript_path=p2,
            transcript_key="two",
            run_id="run-b",
            order_index=1,
            output_dir="out/b",
            module_results=_stats_module_result(20, 4),
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

    assert result["status"] == "completed"
    assert "stats" in result["aggregations"]
    stats_out = result["aggregations"]["stats"]
    assert stats_out.get("output_type") == "rows"
    pooled = stats_out.get("stats_pooled")
    assert isinstance(pooled, dict)
    # Per session: Alice + Bob words = n + max(n//2,1); 10+5=15 and 20+10=30 -> 45
    assert pooled.get("total_words") == 45

    run_dir = Path(result["group_output_dir"])
    session_json = run_dir / "stats" / "session_rows.json"
    assert session_json.exists()
    sessions = json.loads(session_json.read_text(encoding="utf-8"))
    assert len(sessions) == 2
    assert {s["order_index"] for s in sessions} == {0, 1}

    warn_path = run_dir / "aggregation_warnings.json"
    assert warn_path.exists()


@pytest.mark.integration_core
def test_group_finalize_scaling_sanity_multiple_members(tmp_path: Path) -> None:
    """Scaling sanity: multiple members complete with coherent stats artifacts."""
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "mini_transcript.json"
    if not fixture.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    member_paths = []
    for idx in range(6):
        dst = tmp_path / f"member_{idx}.json"
        shutil.copy(fixture, dst)
        member_paths.append(dst)

    groups_root = tmp_path / "groups"
    groups_root.mkdir(parents=True, exist_ok=True)
    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(groups_root)

    scope = AnalysisScope(
        scope_type="group",
        uuid="scale-group-uuid",
        key="scale-group-key",
        display_name="Scale Group",
    )
    members = [
        FileTranscriptMember(
            file_path=str(path), file_name=path.name, id=1000 + i, uuid=f"member-{i}"
        )
        for i, path in enumerate(member_paths)
    ]
    per_results = [
        PerTranscriptResult(
            transcript_path=str(path),
            transcript_key=f"member-{i}",
            run_id=f"run-{i}",
            order_index=i,
            output_dir=f"out/{i}",
            module_results=_stats_module_result(words=10 + i, segments=2 + (i % 3)),
        )
        for i, path in enumerate(member_paths)
    ]

    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=[str(path) for path in member_paths],
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=["stats"],
        config=cfg,
    )
    assert result["status"] == "completed"
    run_dir = Path(result["group_output_dir"])
    session_rows = json.loads((run_dir / "stats" / "session_rows.json").read_text())
    assert len(session_rows) == 6
    assert sorted(row["order_index"] for row in session_rows) == list(range(6))
