"""
Smoke test: group analysis aggregation path.

Validates a lightweight group-oriented path with topic aggregation and
fail-closed filtering semantics.
"""

from __future__ import annotations

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


@pytest.mark.smoke
def test_group_topic_aggregation_smoke_fail_closed(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.core.pipeline.module_registry import is_extra_available

    if not is_extra_available("nlp"):
        pytest.skip("requires transcriptx[nlp] (spaCy runtime for topic preprocess)")

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "mini_transcript.json"
    if not fixture.exists():
        pytest.skip("fixtures/mini_transcript.json not found")

    t1 = tmp_path / "one.json"
    t2 = tmp_path / "two.json"
    shutil.copy(fixture, t1)
    shutil.copy(fixture, t2)

    def _fake_lda(
        texts: list[str], speakers: list[str | None], time_labels: list[float]
    ) -> dict:
        topic_count = len(texts)
        return {
            "topics": [
                {"topic_id": 0, "words": ["think", "know", "mean"]},
                {"topic_id": 1, "words": ["battery", "timeline", "risks"]},
            ],
            "doc_topics": [
                [0.9, 0.1] if i % 2 == 0 else [0.1, 0.9] for i in range(topic_count)
            ],
        }

    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.topics.perform_enhanced_lda_analysis",
        _fake_lda,
    )

    cfg = TranscriptXConfig()
    cfg.group_analysis.enabled = True
    cfg.group_analysis.output_dir = str(tmp_path / "groups")

    scope = AnalysisScope(
        scope_type="group",
        uuid="smoke-group-uuid",
        key="smoke-group-key",
        display_name="Smoke Group",
    )
    p1, p2 = str(t1), str(t2)
    members = [
        FileTranscriptMember(file_path=p1, file_name=t1.name, id=101, uuid="member-1"),
        FileTranscriptMember(file_path=p2, file_name=t2.name, id=102, uuid="member-2"),
    ]
    per_results = [
        PerTranscriptResult(
            transcript_path=p1,
            transcript_key="one",
            run_id="run-a",
            order_index=0,
            output_dir="out/a",
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path=p2,
            transcript_key="two",
            run_id="run-b",
            order_index=1,
            output_dir="out/b",
            module_results={},
        ),
    ]

    result = finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=[p1, p2],
        per_transcript_results=per_results,
        group_errors=[],
        selected_modules=["topic_modeling"],
        config=cfg,
    )

    assert result["status"] == "completed"
    assert "topic_modeling" in result.get("aggregations", {})
    topic_out = result["aggregations"]["topic_modeling"]
    pooled = topic_out.get("topic_modeling_pooled", {})
    assert pooled.get("schema_version") == 1
    assert all(int(row.get("topic_id", -1)) != 0 for row in pooled.get("topics", []))
