"""Edge-branch unit tests for group LLM aggregation (artifacts, malformed payloads)."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.aggregation.llm import (
    _artifact_relpath,
    _load_speaker_summary_payload,
    _status_counts,
    aggregate_llm_action_items_group,
    aggregate_llm_speaker_summary_group,
    aggregate_llm_summary_blob,
    aggregate_narrative_summary_blob,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts() -> TranscriptSet:
    return TranscriptSet.create(["/x/a.json", "/x/b.json"], name="G", key="gk")


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={"/x/a.json": {"1": 7}},
        canonical_to_display={7: "Alice"},
        transcript_to_display={"/x/a.json": {"1": "Alice"}},
    )


def _result(
    path: str,
    key: str,
    order: int,
    module_results: dict,
    output_dir: str = "o1",
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=key,
        run_id=f"r{order}",
        order_index=order,
        output_dir=output_dir,
        module_results=module_results,
    )


_ITEM = {
    "text": "Ship it",
    "owner": None,
    "deadline": None,
    "status": "open",
    "quote": None,
    "confidence": 0.9,
}


@pytest.mark.unit
class TestArtifactRelpath:
    def test_skips_non_dict_and_non_matching_artifacts(self) -> None:
        result = {
            "artifacts": [
                "not-a-dict",
                {"relative_path": "other/data.json"},
                {"relative_path": "llm_action_items/data/x_llm_action_items.md"},
                {"path": "llm_action_items/data/x_llm_action_items.json"},
            ]
        }
        rel = _artifact_relpath(result, "llm_action_items")
        assert rel == "llm_action_items/data/x_llm_action_items.json"

    def test_returns_none_without_artifacts(self) -> None:
        assert _artifact_relpath({}, "llm_action_items") is None
        assert _artifact_relpath({"artifacts": []}, "llm_action_items") is None


@pytest.mark.unit
def test_status_counts_defaults_unknown() -> None:
    counts = _status_counts([{"status": "open"}, {"status": "open"}, {}])
    assert counts == {"open": 2, "unknown": 1}


@pytest.mark.unit
def test_llm_summary_blob_none_when_payloads_missing() -> None:
    results = [
        _result("/x/a.json", "a", 0, {"llm_summary": {"payload": {}}}),
        _result("/x/b.json", "b", 1, {"other": {"payload": {"x": 1}}}),
    ]
    assert aggregate_llm_summary_blob(results, _cmap(), _ts()) is None


@pytest.mark.unit
def test_narrative_blob_skips_members_without_payload() -> None:
    results = [
        _result("/x/a.json", "a", 0, {"narrative_summary": {"payload": {}}}),
        _result(
            "/x/b.json",
            "b",
            1,
            {"narrative_summary": {"payload": {"narrative": "Story"}}},
        ),
    ]
    out = aggregate_narrative_summary_blob(results, _cmap(), _ts())
    assert out is not None
    summaries = out["blob_payload"]["summaries"]
    assert len(summaries) == 1
    assert summaries[0]["narrative"] == "Story"


@pytest.mark.unit
def test_speaker_summary_group_skips_members_without_payload() -> None:
    results = [
        _result("/x/a.json", "a", 0, {"llm_speaker_summary": {"payload": {}}}),
    ]
    assert aggregate_llm_speaker_summary_group(results, _cmap(), _ts()) is None


@pytest.mark.unit
def test_action_items_group_skips_members_without_payload() -> None:
    results = [
        _result("/x/a.json", "a", 0, {"llm_action_items": {"payload": {}}}),
    ]
    assert aggregate_llm_action_items_group(results, _cmap(), _ts()) is None


@pytest.mark.unit
def test_speaker_artifact_missing_file_yields_empty_payload(tmp_path) -> None:
    result = _result("/x/a.json", "a", 0, {}, output_dir=str(tmp_path))
    payload = _load_speaker_summary_payload(result, "Alice", "llm_speaker_summary")
    assert payload == {}


@pytest.mark.unit
class TestActionItemsGroupEdges:
    def test_items_not_a_list_is_skipped(self) -> None:
        results = [
            _result(
                "/x/a.json",
                "a",
                0,
                {"llm_action_items": {"payload": {"items": "nope"}}},
            )
        ]
        assert aggregate_llm_action_items_group(results, _cmap(), _ts()) is None

    def test_non_dict_items_filtered_and_relpath_wired(self) -> None:
        results = [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "llm_action_items": {
                        "payload": {"items": [_ITEM, "junk"]},
                        "artifacts": [
                            {
                                "relative_path": (
                                    "llm_action_items/data/a_llm_action_items.json"
                                )
                            }
                        ],
                    }
                },
            )
        ]
        out = aggregate_llm_action_items_group(results, _cmap(), _ts())
        assert out is not None
        assert out["session_rows"][0]["item_count"] == 1
        assert out["session_rows"][0]["status_open"] == 1
        rows = out["content_rows"]
        assert len(rows) == 1
        assert rows[0]["source_artifact_relpath"] == (
            "llm_action_items/data/a_llm_action_items.json"
        )
        assert rows[0]["source_run_relpath"] == "o1"

    def test_session_with_items_but_all_invalid_yields_none_rows(self) -> None:
        results = [
            _result(
                "/x/a.json",
                "a",
                0,
                {"llm_action_items": {"payload": {"items": ["junk", 42]}}},
            )
        ]
        # Session row exists but no dict items were collected -> aggregator None.
        assert aggregate_llm_action_items_group(results, _cmap(), _ts()) is None


@pytest.mark.unit
class TestSpeakerSummaryGroupEdges:
    def test_speakers_not_a_list_is_skipped(self) -> None:
        results = [
            _result(
                "/x/a.json",
                "a",
                0,
                {"llm_speaker_summary": {"payload": {"speakers": {"bad": True}}}},
            )
        ]
        assert aggregate_llm_speaker_summary_group(results, _cmap(), _ts()) is None

    def test_non_dict_and_unnamed_entries_skipped(self) -> None:
        results = [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "llm_speaker_summary": {
                        "payload": {
                            "speakers": [
                                "junk",
                                {"speaker": "", "status": "success"},
                                {"speaker": "Alice", "status": "success"},
                            ]
                        }
                    }
                },
                output_dir="",
            )
        ]
        out = aggregate_llm_speaker_summary_group(results, _cmap(), _ts())
        assert out is not None
        assert out["session_rows"][0]["speaker_count"] == 3
        assert out["session_rows"][0]["success_count"] == 2
        assert len(out["speaker_rows"]) == 1
        row = out["speaker_rows"][0]
        assert row["display_name"] == "Alice"
        # Empty output_dir means no artifact payload could be loaded.
        assert row["summary"] == ""

    def test_summary_loaded_from_speaker_artifact(self, tmp_path) -> None:
        base_dir = tmp_path / "llm_speaker_summary" / "data" / "speakers"
        base_dir.mkdir(parents=True)
        (base_dir / "a_Alice_llm_speaker_summary.json").write_text(
            json.dumps({"summary": "Alice speaks"}), encoding="utf-8"
        )
        results = [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "llm_speaker_summary": {
                        "payload": {
                            "speakers": [{"speaker": "Alice", "status": "success"}]
                        }
                    }
                },
                output_dir=str(tmp_path),
            )
        ]
        out = aggregate_llm_speaker_summary_group(results, _cmap(), _ts())
        assert out is not None
        assert out["speaker_rows"][0]["summary"] == "Alice speaks"

    def test_corrupt_speaker_artifact_yields_empty_summary(self, tmp_path) -> None:
        base_dir = tmp_path / "llm_speaker_summary" / "data" / "speakers"
        base_dir.mkdir(parents=True)
        (base_dir / "a_Alice_llm_speaker_summary.json").write_text(
            "{corrupt", encoding="utf-8"
        )
        result = _result("/x/a.json", "a", 0, {}, output_dir=str(tmp_path))
        payload = _load_speaker_summary_payload(result, "Alice", "llm_speaker_summary")
        assert payload == {}

    def test_non_dict_speaker_artifact_yields_empty_payload(self, tmp_path) -> None:
        base_dir = tmp_path / "llm_speaker_summary" / "data" / "speakers"
        base_dir.mkdir(parents=True)
        (base_dir / "a_Alice_llm_speaker_summary.json").write_text(
            json.dumps(["not", "a", "dict"]), encoding="utf-8"
        )
        result = _result("/x/a.json", "a", 0, {}, output_dir=str(tmp_path))
        payload = _load_speaker_summary_payload(result, "Alice", "llm_speaker_summary")
        assert payload == {}
