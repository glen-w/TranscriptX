"""Direct unit coverage for group_member_runs.json writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.group_analysis_runner import (
    _write_group_member_runs_json,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


@pytest.mark.unit
def test_write_group_member_runs_json_schema_and_order(tmp_path: Path) -> None:
    run_dir = tmp_path / "group_run"
    run_dir.mkdir()
    results = [
        PerTranscriptResult(
            transcript_path="/a.json",
            transcript_key="a",
            run_id="r-a",
            order_index=0,
            output_dir="/out/a",
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path="/b.json",
            transcript_key="b",
            run_id="r-b",
            order_index=1,
            output_dir="/out/b",
            module_results={},
        ),
    ]
    _write_group_member_runs_json(run_dir, results)
    payload = json.loads(
        (run_dir / "group_member_runs.json").read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == 1
    assert [m["order_index"] for m in payload["members"]] == [0, 1]
    assert payload["members"][0]["transcript_path"] == "/a.json"
    assert payload["members"][1]["output_dir"] == "/out/b"
    assert payload["members"][1]["run_id"] == "r-b"
