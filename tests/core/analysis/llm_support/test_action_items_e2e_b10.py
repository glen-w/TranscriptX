"""End-to-end acceptance: parse → ground → dedupe → render → group → export."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.aggregation.llm import aggregate_llm_action_items_group
from transcriptx.core.analysis.llm_support.action_items_contract import (
    LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION,
    LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
    LLM_ACTION_ITEMS_SCHEMA_ID,
    RECORD_TYPE_LABELS,
    finalize_action_items,
)
from transcriptx.core.analysis.llm_support.action_items_render import (
    render_action_items_markdown,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.export.summary_bodies import action_items_markdown


@pytest.mark.unit
def test_b10_e2e_committed_counts_stable_across_layers(monkeypatch) -> None:
    transcript = (
        "Alice: We decided on Postgres. "
        "Bob: I will send the report by Friday. "
        "Carol: Should we hire a contractor?"
    )
    raw = json.dumps(
        {
            "items": [
                {
                    "record_type": "decision",
                    "text": "We decided on Postgres",
                    "owner": None,
                    "deadline": None,
                    "status": "open",
                    "quote": "We decided on Postgres",
                    "confidence": 0.9,
                },
                {
                    "record_type": "action_item",
                    "text": "send the report by Friday",
                    "owner": "Bob",
                    "deadline": "Friday",
                    "status": "open",
                    "quote": "I will send the report by Friday.",
                    "confidence": 0.95,
                },
                {
                    "record_type": "open_question",
                    "text": "Should we hire a contractor?",
                    "owner": None,
                    "deadline": None,
                    "status": "open",
                    "quote": "Should we hire a contractor?",
                    "confidence": 0.8,
                },
                {
                    "record_type": "action_item",
                    "text": "Invented task",
                    "owner": None,
                    "deadline": None,
                    "status": "open",
                    "quote": "Not in transcript",
                    "confidence": 0.5,
                },
            ]
        }
    )
    items, diagnostics = finalize_action_items(raw, transcript)
    assert diagnostics["items_committed"] == 3
    assert diagnostics["counts_by_type"] == {
        "decision": 1,
        "commitment": 0,
        "action_item": 1,
        "proposal": 0,
        "open_question": 1,
    }
    type_ids = [item["record_type"] for item in items]
    assert type_ids == ["decision", "action_item", "open_question"]

    payload = {
        "schema_id": LLM_ACTION_ITEMS_SCHEMA_ID,
        "module_version": "2",
        "render_contract_id": LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
        "module": "llm_action_items",
        "items": items,
        "diagnostics": diagnostics,
        "input_coverage": {},
        "provenance": {
            "prompt_version": "5",
            "model": "e2e",
            "render_contract_id": LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
        },
    }
    md = render_action_items_markdown(payload)
    assert f"## {RECORD_TYPE_LABELS['decision']}" in md
    assert f"## {RECORD_TYPE_LABELS['action_item']}" in md
    assert f"## {RECORD_TYPE_LABELS['open_question']}" in md
    assert LLM_ACTION_ITEMS_RENDER_CONTRACT_ID in md

    export_md = action_items_markdown(payload)
    assert RECORD_TYPE_LABELS["decision"] in export_md
    assert RECORD_TYPE_LABELS["action_item"] in export_md
    assert RECORD_TYPE_LABELS["open_question"] in export_md

    from transcriptx.core.utils.config.main import TranscriptXConfig

    cfg = TranscriptXConfig()
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.llm.get_config",
        lambda: cfg,
    )
    result = PerTranscriptResult(
        transcript_path="/x/a.json",
        transcript_key="a",
        run_id="r0",
        order_index=0,
        output_dir="o1",
        module_results={"llm_action_items": {"payload": payload}},
    )
    group = aggregate_llm_action_items_group(
        [result],
        CanonicalSpeakerMap(
            transcript_to_speakers={"/x/a.json": {}},
            canonical_to_display={},
            transcript_to_display={"/x/a.json": {}},
        ),
        TranscriptSet.create(["/x/a.json"], name="G", key="gk"),
    )
    assert group is not None
    assert group["schema_version"] == LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION
    assert group["session_rows"][0]["item_count"] == 3
    assert group["session_rows"][0]["count_decision"] == 1
    assert group["session_rows"][0]["count_action_item"] == 1
    assert group["session_rows"][0]["count_open_question"] == 1
    assert {row["record_type"] for row in group["content_rows"]} == set(type_ids)
    assert len(group["content_rows"]) == diagnostics["items_committed"]
