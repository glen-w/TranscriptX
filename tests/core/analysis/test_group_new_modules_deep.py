"""Deeper unit coverage for new group module aggregators and chart wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.aggregation.llm import (
    aggregate_llm_action_items_group,
    aggregate_llm_summary_blob,
    aggregate_narrative_summary_blob,
)
from transcriptx.core.analysis.aggregation.registry import build_registry
from transcriptx.core.analysis.aggregation.semantic_similarity import (
    aggregate_semantic_similarity_group,
)
from transcriptx.core.analysis.aggregation.voice import (
    aggregate_voice_fingerprint_group,
    aggregate_voice_mismatch_group,
    aggregate_voice_tension_group,
)
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.registry import (
    GROUP_AGGREGATE_CHART_FAMILIES,
    build_group_chart_registry,
)
from transcriptx.core.analysis.group_charts.generic_field_allowlists import (
    allowed_numeric_keys_for_generic_agg,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts(paths: list[str] | None = None) -> TranscriptSet:
    return TranscriptSet.create(paths or ["/x/a.json", "/x/b.json"], name="G", key="gk")


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={"/x/a.json": {"1": 7}, "/x/b.json": {"1": 7}},
        canonical_to_display={7: "Alice"},
        transcript_to_display={
            "/x/a.json": {"1": "Alice"},
            "/x/b.json": {"1": "Alice"},
        },
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


@pytest.mark.unit
def test_llm_summary_blob_none_when_payloads_missing() -> None:
    results = [
        _result("/x/a.json", "a", 0, {"llm_summary": {"payload": {}}}),
        _result("/x/b.json", "b", 1, {}, output_dir="o2"),
    ]
    assert aggregate_llm_summary_blob(results, _cmap(), _ts()) is None


@pytest.mark.unit
def test_narrative_summary_blob_preserves_order_and_provenance() -> None:
    results = [
        _result(
            "/x/b.json",
            "b",
            1,
            {
                "narrative_summary": {
                    "payload": {
                        "narrative": "Second",
                        "provenance": {"source_module": "summary"},
                    }
                }
            },
            output_dir="o2",
        ),
        _result(
            "/x/a.json",
            "a",
            0,
            {
                "narrative_summary": {
                    "payload": {
                        "narrative": "First",
                        "provenance": {"source_module": "summary"},
                    }
                }
            },
        ),
    ]
    out = aggregate_narrative_summary_blob(results, _cmap(), _ts())
    assert out is not None
    narratives = out["blob_payload"]["summaries"]
    assert [row["narrative"] for row in narratives] == ["First", "Second"]
    assert narratives[0]["provenance"]["source_module"] == "summary"


@pytest.mark.unit
def test_llm_action_items_ignores_non_dict_items_and_counts_status() -> None:
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {
                "llm_action_items": {
                    "payload": {
                        "schema_id": "transcriptx.llm_action_items.v1",
                        "module_version": "2",
                        "items": [
                            "bad",
                            {
                                "record_type": "action_item",
                                "text": "Do A",
                                "owner": None,
                                "deadline": None,
                                "status": "open",
                                "quote": None,
                                "confidence": 0.1,
                            },
                            {
                                "record_type": "action_item",
                                "text": "Do B",
                                "owner": "Alice",
                                "deadline": None,
                                "status": "done",
                                "quote": "do b",
                                "confidence": 0.8,
                            },
                        ],
                    }
                }
            },
        )
    ]
    out = aggregate_llm_action_items_group(results, _cmap(), _ts())
    assert out is not None
    assert out["session_rows"][0]["item_count"] == 2
    assert out["session_rows"][0]["status_open"] == 1
    assert out["session_rows"][0]["status_done"] == 1
    assert len(out["content_rows"]) == 2


@pytest.mark.unit
def test_semantic_similarity_computes_totals_from_repetition_lists() -> None:
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {
                "semantic_similarity": {
                    "payload": {
                        "speaker_repetitions": {
                            "Alice": [
                                {
                                    "segment1": {"speaker": "Alice", "text": "a"},
                                    "segment2": {"speaker": "Alice", "text": "b"},
                                    "similarity": 0.8,
                                }
                            ]
                        },
                        "cross_speaker_repetitions": [
                            {
                                "segment1": {"speaker": "Alice", "text": "x"},
                                "segment2": {"speaker": "Bob", "text": "y"},
                                "similarity": 0.7,
                                "type": "cross",
                            }
                        ],
                    }
                }
            },
        )
    ]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    assert out["session_rows"][0]["total_repetitions"] == 2
    assert out["session_rows"][0]["semantic_module"] == "semantic_similarity"
    assert len(out["content_rows"]) == 2
    assert "aggregation_note" in out


@pytest.mark.unit
def test_voice_aggregators_return_none_without_payloads() -> None:
    empty = [_result("/x/a.json", "a", 0, {})]
    assert aggregate_voice_mismatch_group(empty, _cmap(), _ts()) is None
    assert aggregate_voice_tension_group(empty, _cmap(), _ts()) is None
    assert aggregate_voice_fingerprint_group(empty, _cmap(), _ts()) is None


@pytest.mark.unit
def test_voice_fingerprint_handles_malformed_baseline() -> None:
    out = aggregate_voice_fingerprint_group(
        [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "voice_fingerprint": {
                        "payload": {
                            "summary": {"speakers": 1},
                            "fingerprints": {
                                "Alice": {
                                    "n_segments": 1,
                                    "baseline": "not-a-dict",
                                }
                            },
                            "drift_moments": {"Alice": "bad"},
                        }
                    }
                },
            )
        ],
        _cmap(),
        _ts(),
    )
    assert out is not None
    assert out["speaker_rows"][0]["rms_db_median"] is None
    assert out["content_rows"] == []


@pytest.mark.unit
def test_new_agg_ids_registered_uniquely_in_aggregation_registry() -> None:
    expected = {
        "llm_summary",
        "narrative_summary",
        "llm_speaker_summary",
        "llm_action_items",
        "insights",
        "semantic_similarity",
        "voice_mismatch",
        "voice_tension",
        "voice_fingerprint",
    }
    ids = [entry.agg_id for entry in build_registry()]
    assert len(ids) == len(set(ids))
    assert expected <= set(ids)


@pytest.mark.unit
def test_new_numeric_aggs_have_chart_generators_and_allowlists() -> None:
    from transcriptx.core.analysis.group_charts.semantic_similarity_charts import (
        SemanticSimilarityGroupChartGenerator,
    )

    reg = build_group_chart_registry()
    for agg_id in (
        "llm_action_items",
        "insights",
        "voice_mismatch",
        "voice_tension",
        "voice_fingerprint",
    ):
        assert agg_id in reg
        assert GROUP_AGGREGATE_CHART_FAMILIES[agg_id] == ("session_bars",)
        allow = allowed_numeric_keys_for_generic_agg(agg_id)
        assert allow is not None and len(allow) > 0
        gen = reg[agg_id]
        assert isinstance(gen, GenericNumericGroupChartGenerator)
        assert gen.allowed_numeric_keys == allow

    # B14: semantic_similarity uses a composite generator + motif_prevalence family
    assert "semantic_similarity" in reg
    assert GROUP_AGGREGATE_CHART_FAMILIES["semantic_similarity"] == (
        "session_bars",
        "motif_prevalence",
    )
    assert isinstance(reg["semantic_similarity"], SemanticSimilarityGroupChartGenerator)
    allow = allowed_numeric_keys_for_generic_agg("semantic_similarity")
    assert allow is not None and "motif_count" in allow


@pytest.mark.unit
def test_generic_chart_generator_respects_new_allowlists() -> None:
    gen = build_group_chart_registry()["llm_action_items"]
    assert not gen.can_generate({"session_rows": []})
    assert not gen.can_generate(
        {"session_rows": [{"transcript_id": "t", "order_index": 0, "ignored": 9}]}
    )
    assert gen.can_generate(
        {"session_rows": [{"transcript_id": "t", "order_index": 0, "item_count": 3}]}
    )


@pytest.mark.unit
def test_blob_aggs_are_omitted_from_chart_registry() -> None:
    reg = build_group_chart_registry()
    for agg_id in (
        "llm_summary",
        "narrative_summary",
        "llm_speaker_summary",
        "summary",
    ):
        assert agg_id not in reg


@pytest.mark.unit
def test_llm_action_items_generic_chart_writes_artifact(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    from transcriptx.core.analysis.group_charts.context import GroupChartContext

    gen = build_group_chart_registry()["llm_action_items"]
    root = tmp_path / "group_run"
    root.mkdir()
    ctx = GroupChartContext(
        group_run_root=root,
        group_run_id="run1",
        agg_id="llm_action_items",
        transcript_set=_ts(["/x/a.json"]),
        group_uuid="gu1",
    )
    paths = gen.generate(
        ctx,
        {
            "session_rows": [
                {"transcript_id": "a", "order_index": 0, "item_count": 2},
                {"transcript_id": "b", "order_index": 1, "item_count": 5},
            ]
        },
    )
    assert paths
    assert any(p.suffix.lower() in {".png", ".html"} for p in paths)
