"""Tests for build_report_payload (report.v1) and report payload structure."""

from __future__ import annotations

import json
from pathlib import Path


from transcriptx.core.analysis.stats.report_input_resolver import (
    REPORT_CONTRIBUTION_FULL_SECTION,
    REPORT_CONTRIBUTION_MENTION_ONLY,
    REPORT_CONTRIBUTION_OMITTED,
)
from transcriptx.core.analysis.stats.stats_report import build_report_payload


class DummyContext:
    def __init__(self, base_name: str, transcript_dir: Path, results: dict) -> None:
        self._base_name = base_name
        self._dir = str(transcript_dir)
        self._results = results

    def get_analysis_result(self, module_id: str) -> object | None:
        return self._results.get(module_id)

    def get_base_name(self) -> str:
        return self._base_name

    def get_transcript_dir(self) -> str:
        return self._dir

    def get_run_id(self) -> str:
        return "run_123"

    def get_transcript_key(self) -> str:
        return "transcript_key_abc"


def _make_segments() -> list[dict]:
    return [
        {
            "speaker": "Alice",
            "speaker_db_id": 1,
            "text": "Hello world",
            "start": 0.0,
            "end": 3.0,
        },
        {
            "speaker": "Bob",
            "speaker_db_id": 2,
            "text": "How are you",
            "start": 3.0,
            "end": 6.0,
        },
    ]


def _make_stats_results() -> dict:
    return {
        "speaker_stats": [
            (120.0, "Alice", 600, 10, 0.02, 60.0),
            (60.0, "Bob", 300, 5, 0.01, 60.0),
        ],
        "sentiment_summary": {
            "Alice": {"compound": 0.1, "pos": 0.2, "neu": 0.7, "neg": 0.1},
            "Bob": {"compound": -0.1, "pos": 0.1, "neu": 0.8, "neg": 0.1},
        },
    }


def test_build_report_payload_schema_version_report_v1(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": [],
                "modules_run": [],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    assert payload["meta"]["schema_version"] == "report.v1"


def test_build_report_payload_modules_have_status_and_contribution(
    tmp_path: Path,
) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment"],
                "modules_run": ["sentiment"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    (tmp_path / "sentiment" / "data" / "global").mkdir(parents=True)
    (
        tmp_path / "sentiment" / "data" / "global" / "sample_sentiment_summary.json"
    ).write_text(json.dumps({"mean_compound": 0.25}))
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    mods = payload["modules"]
    assert "sentiment" in mods
    assert mods["sentiment"]["module_status"] == "succeeded"
    assert (
        mods["sentiment"]["report_contribution_status"]
        == REPORT_CONTRIBUTION_FULL_SECTION
    )
    assert "section_payload" in mods["sentiment"]
    assert mods["sentiment"]["section_payload"]["mean_compound"] == 0.25


def test_build_report_payload_report_summary_index_structure(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment"],
                "modules_run": ["sentiment"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    (tmp_path / "sentiment" / "data" / "global").mkdir(parents=True)
    (
        tmp_path / "sentiment" / "data" / "global" / "sample_sentiment_summary.json"
    ).write_text(json.dumps({"mean_compound": 0.0}))
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    index = payload.get("report_summary_index", [])
    assert isinstance(index, list)
    sentiment_entry = next(
        (e for e in index if "sentiment" in e.get("source_modules", [])), None
    )
    assert sentiment_entry is not None
    assert "section_name" in sentiment_entry
    assert "descriptor" in sentiment_entry
    assert sentiment_entry["source_modules"] == ["sentiment"]


def test_build_report_payload_no_outputs_index(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": [],
                "modules_run": [],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    assert "outputs_index" not in payload


def test_build_report_payload_warnings_key_present(tmp_path: Path) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment"],
                "modules_run": ["sentiment"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    # No sentiment file -> sentiment omitted; payload still has warnings list (may merge resolver warnings when path exists but fails contract)
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    assert "warnings" in payload
    assert isinstance(payload["warnings"], list)
    assert (
        payload["modules"]["sentiment"]["report_contribution_status"]
        == REPORT_CONTRIBUTION_OMITTED
    )


def test_build_report_payload_resolver_warnings_merged_when_contract_fails(
    tmp_path: Path,
) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment"],
                "modules_run": ["sentiment"],
                "modules_skipped": [],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    (tmp_path / "sentiment" / "data" / "global").mkdir(parents=True)
    # File exists but fails contract (null required key) -> resolver adds warning
    (
        tmp_path / "sentiment" / "data" / "global" / "sample_sentiment_summary.json"
    ).write_text(json.dumps({"mean_compound": None}))
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    warnings = payload.get("warnings", [])
    assert any("sentiment" in w for w in warnings)
    assert (
        payload["modules"]["sentiment"]["report_contribution_status"]
        == REPORT_CONTRIBUTION_MENTION_ONLY
    )


def test_build_report_payload_omitted_and_mention_only_preserved(
    tmp_path: Path,
) -> None:
    (tmp_path / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "r1",
                "transcript_key": "tk",
                "modules_enabled": ["sentiment", "tics", "contagion"],
                "modules_run": ["sentiment", "tics"],
                "modules_skipped": [
                    {"module": "contagion", "reason": "missing emotion"}
                ],
                "modules_failed": [],
                "errors": [],
            }
        )
    )
    (tmp_path / "sentiment" / "data" / "global").mkdir(parents=True)
    (
        tmp_path / "sentiment" / "data" / "global" / "sample_sentiment_summary.json"
    ).write_text(json.dumps({"mean_compound": 0.1}))
    (tmp_path / "tics" / "data" / "global").mkdir(parents=True)
    (tmp_path / "tics" / "data" / "global" / "sample_tics_summary.json").write_text(
        ""
    )  # zero-byte -> mention_only
    context = DummyContext("sample", tmp_path, {})
    payload = build_report_payload(
        context,
        _make_segments(),
        _make_stats_results(),
        module_data={},
        run_dir=str(tmp_path),
    )
    mods = payload["modules"]
    assert (
        mods["sentiment"]["report_contribution_status"]
        == REPORT_CONTRIBUTION_FULL_SECTION
    )
    assert (
        mods["tics"]["report_contribution_status"] == REPORT_CONTRIBUTION_MENTION_ONLY
    )
    assert (
        mods["contagion"]["report_contribution_status"] == REPORT_CONTRIBUTION_OMITTED
    )
    assert mods["contagion"]["module_status"] == "skipped"
