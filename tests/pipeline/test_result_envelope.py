"""Tests for per-transcript result envelope."""

from __future__ import annotations

import json

from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


def test_per_transcript_result_to_dict_is_serializable() -> None:
    result = PerTranscriptResult(
        transcript_path="/tmp/sample.json",
        transcript_key="key-1",
        run_id="run-1",
        order_index=0,
        output_dir="/tmp/run",
        module_results={"sentiment": {"status": "success"}},
    )
    payload = result.to_dict()
    assert payload["transcript_key"] == "key-1"
    json.dumps(payload)
