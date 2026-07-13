"""Tests for llm_action_items analysis module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.llm_action_items import (
    LLM_ACTION_ITEMS_MODULE_VERSION,
    LLM_ACTION_ITEMS_PROMPT_VERSION,
    LLM_ACTION_ITEMS_SCHEMA_ID,
    LLMActionItemsAnalysis,
)
from transcriptx.core.analysis.llm_common import (
    dedupe_action_items,
    ground_action_items,
    parse_action_items_json,
    render_action_items_markdown,
)
from transcriptx.core.analysis.llm_module_errors import ModuleEmptyInputError
from transcriptx.core.analysis.llm_summary_effort import LLMSummaryRuntime
from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.core.utils.config.main import TranscriptXConfig


def _mini_segments() -> list[dict]:
    return [
        {
            "speaker": "Alice",
            "text": "I will send the report by Friday.",
            "start": 0.0,
            "end": 1.0,
        },
        {"speaker": "Bob", "text": "That is done.", "start": 1.0, "end": 2.0},
    ]


def _valid_items_json() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "text": "Send the report",
                    "owner": "Alice",
                    "deadline": "Friday",
                    "status": "open",
                    "quote": "I will send the report by Friday.",
                    "confidence": 0.9,
                },
                {
                    "text": "Completed prior task",
                    "owner": None,
                    "deadline": None,
                    "status": "done",
                    "quote": "That is done.",
                    "confidence": 0.8,
                },
            ]
        }
    )


@pytest.mark.unit
def test_parse_action_items_json_success() -> None:
    items = parse_action_items_json(_valid_items_json())
    assert len(items) == 2
    assert items[0]["status"] == "open"


@pytest.mark.unit
def test_parse_action_items_rejects_invalid_status() -> None:
    payload = json.dumps(
        {
            "items": [
                {
                    "text": "x",
                    "owner": None,
                    "deadline": None,
                    "status": "pending",
                    "quote": None,
                    "confidence": 0.5,
                }
            ]
        }
    )
    with pytest.raises(LLMResponseError, match="status"):
        parse_action_items_json(payload)


@pytest.mark.unit
def test_ground_action_items_drops_fabricated_quote() -> None:
    items = parse_action_items_json(
        json.dumps(
            {
                "items": [
                    {
                        "text": "I will send the report by Friday",
                        "owner": "Alice",
                        "deadline": None,
                        "status": "open",
                        "quote": "Totally fabricated quote.",
                        "confidence": 0.9,
                    }
                ]
            }
        )
    )
    transcript = "Alice: I will send the report by Friday."
    grounded, diagnostics = ground_action_items(items, transcript)
    assert len(grounded) == 1
    assert grounded[0]["quote"] is None
    assert diagnostics["quotes_nulled"] == 1


@pytest.mark.unit
def test_dedupe_action_items_keeps_higher_confidence() -> None:
    items = [
        {
            "text": "Send report",
            "owner": "Alice",
            "deadline": None,
            "status": "open",
            "quote": "send report",
            "confidence": 0.5,
        },
        {
            "text": "Send report",
            "owner": "Alice",
            "deadline": None,
            "status": "open",
            "quote": "send report",
            "confidence": 0.9,
        },
    ]
    deduped = dedupe_action_items(items)
    assert len(deduped) == 1
    assert deduped[0]["confidence"] == 0.9


@pytest.mark.unit
def test_render_action_items_markdown_escapes() -> None:
    payload = {
        "items": [
            {
                "text": "Fix [bug] _now_",
                "owner": None,
                "deadline": None,
                "status": "open",
                "quote": None,
                "confidence": 0.7,
            }
        ],
        "provenance": {"prompt_version": "1", "model": "test"},
    }
    md = render_action_items_markdown(payload)
    assert "\\[bug\\]" in md


@pytest.mark.unit
def test_llm_action_items_success(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_base_name.return_value = "mini"
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = _valid_items_json()
    runtime = LLMSummaryRuntime(
        effort="high",
        profile_name="high",
        model="qwen3:8b",
        max_input_chars=256_000,
        request_timeout=1800.0,
        max_output_tokens=8192,
    )

    with (
        patch(
            "transcriptx.core.analysis.llm_action_items.get_config", return_value=cfg
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.resolve_llm_summary_runtime",
            return_value=runtime,
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.build_llm_summary_ollama_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.write_llm_artifacts",
            return_value=("a.json", "a.md"),
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.create_output_service"
        ) as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value.module_dir = tmp_path
        mock_os.return_value.get_artifacts.return_value = []
        result = LLMActionItemsAnalysis().run_from_context(context)

    assert result["status"] == "success"
    payload = result["payload"]
    assert payload["schema_id"] == LLM_ACTION_ITEMS_SCHEMA_ID
    assert payload["module_version"] == LLM_ACTION_ITEMS_MODULE_VERSION
    assert payload["provenance"]["prompt_version"] == LLM_ACTION_ITEMS_PROMPT_VERSION
    assert payload["provenance"]["cache_key"]
    context.store_analysis_result.assert_called_once()


@pytest.mark.unit
def test_llm_action_items_empty_transcript(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = [{"speaker": "Alice", "text": "   "}]

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    with patch(
        "transcriptx.core.analysis.llm_action_items.get_config", return_value=cfg
    ):
        with pytest.raises(ModuleEmptyInputError):
            LLMActionItemsAnalysis().run_from_context(context)


@pytest.mark.unit
def test_llm_action_items_empty_items_success(tmp_path) -> None:
    context = MagicMock()
    context.transcript_path = str(tmp_path / "t.json")
    context.get_segments.return_value = _mini_segments()
    context.get_base_name.return_value = "mini"
    context.get_transcript_dir.return_value = str(tmp_path / "out")
    context.get_run_id.return_value = "run-1"
    context.get_runtime_flags.return_value = {}

    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    mock_client = MagicMock()
    mock_client.model = "qwen3:8b"
    mock_client.generate.return_value = '{"items": []}'
    runtime = LLMSummaryRuntime(
        effort="high",
        profile_name="high",
        model="qwen3:8b",
        max_input_chars=256_000,
        request_timeout=1800.0,
        max_output_tokens=8192,
    )

    with (
        patch(
            "transcriptx.core.analysis.llm_action_items.get_config", return_value=cfg
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.resolve_llm_summary_runtime",
            return_value=runtime,
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.build_llm_summary_ollama_client",
            return_value=mock_client,
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.write_llm_artifacts",
            return_value=("a.json", "a.md"),
        ),
        patch(
            "transcriptx.core.analysis.llm_action_items.create_output_service"
        ) as mock_os,
    ):
        mock_os.return_value.get_output_structure.return_value.module_dir = tmp_path
        mock_os.return_value.get_artifacts.return_value = []
        result = LLMActionItemsAnalysis().run_from_context(context)

    assert result["status"] == "success"
    assert result["payload"]["items"] == []
