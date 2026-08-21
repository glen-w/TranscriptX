"""
Integration: finalize_group_analysis writes artifacts for new group modules.
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

pytestmark = [pytest.mark.integration_core, pytest.mark.unit]


def _member_payloads(order: int) -> dict:
    return {
        "llm_summary": {
            "payload": {
                "summary": f"Summary {order}",
                "provenance": {"module": "llm_summary"},
            }
        },
        "llm_action_items": {
            "payload": {
                "schema_id": "transcriptx.llm_action_items.v1",
                "items": [
                    {
                        "record_type": "action_item",
                        "text": f"Action {order}",
                        "owner": "Alice",
                        "deadline": None,
                        "status": "open",
                        "quote": f"action {order}",
                        "confidence": 0.7 + order * 0.05,
                    }
                ],
            }
        },
        "insights": {
            "payload": {
                "key_themes": [
                    {"phrase": f"theme-{order}", "score": {"total": float(order + 1)}}
                ],
                "recurring_ideas": [],
                "notable_moments": [],
            }
        },
        "semantic_similarity": {
            "payload": {
                "total_repetitions": order + 1,
                "unique_patterns": 1,
                "mode": "fast",
                "speaker_repetitions": {},
                "cross_speaker_repetitions": [],
            }
        },
        "voice_mismatch": {
            "payload": {
                "summary": {"moments_count": 1},
                "moments": [
                    {
                        "start_s": 1.0,
                        "end_s": 2.0,
                        "speaker": "Alice",
                        "text": "fine",
                        "mismatch_score": 0.5 + order * 0.1,
                    }
                ],
            }
        },
    }


@pytest.mark.integration_core
def test_finalize_group_analysis_new_modules_write_blobs_rows_and_charts(
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
        uuid="new-modules-group",
        key="new-modules-key",
        display_name="New Modules Group",
    )
    p1, p2 = str(t1), str(t2)
    members = [
        FileTranscriptMember(
            file_path=p1, file_name=t1.name, id=201, uuid="member-uuid-a"
        ),
        FileTranscriptMember(
            file_path=p2, file_name=t2.name, id=202, uuid="member-uuid-b"
        ),
    ]
    selected = [
        "llm_summary",
        "llm_action_items",
        "insights",
        "semantic_similarity",
        "voice_mismatch",
    ]
    per_results = [
        PerTranscriptResult(
            transcript_path=p1,
            transcript_key="one",
            run_id="run-a",
            order_index=0,
            output_dir="out/a",
            module_results=_member_payloads(0),
        ),
        PerTranscriptResult(
            transcript_path=p2,
            transcript_key="two",
            run_id="run-b",
            order_index=1,
            output_dir="out/b",
            module_results=_member_payloads(1),
        ),
    ]

    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=[p1, p2],
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=selected,
        config=cfg,
    )

    assert result["status"] == "completed"
    aggs = result["aggregations"]
    assert aggs["llm_summary"]["output_type"] == "blob"
    assert aggs["llm_action_items"]["output_type"] == "rows"
    assert aggs["insights"]["output_type"] == "rows"
    assert aggs["semantic_similarity"]["output_type"] == "rows"
    assert aggs["voice_mismatch"]["output_type"] == "rows"

    run_dir = Path(result["group_output_dir"])

    blob_path = run_dir / "llm_summary" / "llm_summary.json"
    assert blob_path.exists()
    blob = json.loads(blob_path.read_text(encoding="utf-8"))
    assert len(blob["summaries"]) == 2
    assert blob["summaries"][0]["summary"] == "Summary 0"

    action_rows = json.loads(
        (run_dir / "llm_action_items" / "action_item_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(action_rows) == 2
    assert {row["text"] for row in action_rows} == {"Action 0", "Action 1"}

    insight_sessions = json.loads(
        (run_dir / "insights" / "session_rows.json").read_text(encoding="utf-8")
    )
    assert len(insight_sessions) == 2
    assert insight_sessions[0]["theme_count"] == 1

    semantic_sessions = json.loads(
        (run_dir / "semantic_similarity" / "session_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert [row["total_repetitions"] for row in semantic_sessions] == [1, 2]

    mismatch_content = json.loads(
        (run_dir / "voice_mismatch" / "mismatch_moment_rows.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(mismatch_content) == 2

    warnings = json.loads(
        (run_dir / "aggregation_warnings.json").read_text(encoding="utf-8")
    )
    assert isinstance(warnings, list)
    schema_failures = [
        w
        for w in warnings
        if isinstance(w, dict) and w.get("code") == "SCHEMA_VALIDATION_FAILED"
    ]
    assert not schema_failures, schema_failures
