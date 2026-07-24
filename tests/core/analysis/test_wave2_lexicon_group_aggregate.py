"""Group aggregation + chart generator tests for Wave 2 lexicon modules."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.epistemic_markers.aggregation import (
    aggregate_epistemic_markers,
)
from transcriptx.core.analysis.group_charts.epistemic_markers_group_charts import (
    EpistemicMarkersGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.politeness_group_charts import (
    PolitenessGroupChartGenerator,
)
from transcriptx.core.analysis.politeness.aggregation import aggregate_politeness
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts() -> TranscriptSet:
    return TranscriptSet.create(["/x/a.json", "/x/b.json"], name="G", key="gk")


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={"/x/a.json": {"1": 7}, "/x/b.json": {"1": 7}},
        canonical_to_display={7: "Alice"},
        transcript_to_display={
            "/x/a.json": {"1": "Alice"},
            "/x/b.json": {"1": "Alice"},
        },
    )


def _epi_payload(
    *,
    hedge: int,
    booster: int,
    hits_rate: float | None = 2.5,
) -> dict:
    total = hedge + booster
    return {
        "global_stats": {
            "total_marker_hits": total,
            "token_count": 100,
            "hits_per_100_tokens": hits_rate,
            "hedge_share": (hedge / total) if total else None,
            "booster_share": (booster / total) if total else None,
            "category_counts": {
                "epistemic_hedge": hedge,
                "approximator": 0,
                "modal_uncertainty": 0,
                "certainty_booster": booster,
            },
        },
        "speaker_stats": {
            "Alice": {
                "total_marker_hits": total,
                "token_count": 100,
                "hits_per_100_tokens": hits_rate,
                "hedge_share": (hedge / total) if total else None,
                "booster_share": (booster / total) if total else None,
            }
        },
    }


def _pol_payload(*, soft: int, bare: int) -> dict:
    total = soft + bare
    return {
        "global_stats": {
            "total_marker_hits": total,
            "token_count": 80,
            "hits_per_100_tokens": 3.0,
            "soft_request_ratio": (soft / total) if total else None,
            "category_counts": {
                "gratitude": 0,
                "apology": 0,
                "request_softener": soft,
                "polite_disagreement": 0,
                "bare_directive": bare,
                "formal_marker": 0,
            },
        },
        "speaker_stats": {
            "Alice": {
                "total_marker_hits": total,
                "token_count": 80,
                "hits_per_100_tokens": 3.0,
                "soft_request_ratio": (soft / total) if total else None,
            }
        },
    }


@pytest.mark.unit
def test_aggregate_epistemic_markers_pools_categories() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={
                "epistemic_markers": {"payload": _epi_payload(hedge=2, booster=1)}
            },
        ),
        PerTranscriptResult(
            transcript_path="/x/b.json",
            transcript_key="b",
            run_id="r2",
            order_index=1,
            output_dir="o2",
            module_results={
                "epistemic_markers": {"payload": _epi_payload(hedge=1, booster=3)}
            },
        ),
    ]
    out = aggregate_epistemic_markers(results, _cmap(), _ts())
    assert out is not None
    pooled = out["epistemic_markers_pooled"]
    assert pooled["schema_version"] == 1
    assert pooled["total_marker_hits"] == 7
    assert pooled["by_category"]["epistemic_hedge"] == 3
    assert pooled["by_category"]["certainty_booster"] == 4
    assert pooled["mean_hits_per_100_tokens"] == 2.5
    assert len(out["session_rows"]) == 2


@pytest.mark.unit
def test_aggregate_epistemic_markers_none_without_payloads() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={},
        )
    ]
    assert aggregate_epistemic_markers(results, _cmap(), _ts()) is None


@pytest.mark.unit
def test_aggregate_politeness_pools_and_soft_ratio_mean() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={"politeness": {"payload": _pol_payload(soft=3, bare=1)}},
        ),
        PerTranscriptResult(
            transcript_path="/x/b.json",
            transcript_key="b",
            run_id="r2",
            order_index=1,
            output_dir="o2",
            module_results={"politeness": {"results": _pol_payload(soft=1, bare=1)}},
        ),
    ]
    out = aggregate_politeness(results, _cmap(), _ts())
    assert out is not None
    pooled = out["politeness_pooled"]
    assert pooled["total_marker_hits"] == 6
    assert pooled["by_category"]["request_softener"] == 4
    assert pooled["by_category"]["bare_directive"] == 2
    assert pooled["mean_soft_request_ratio"] == pytest.approx(0.625)


@pytest.mark.unit
def test_epistemic_group_chart_can_generate_from_pooled() -> None:
    gen = EpistemicMarkersGroupChartGenerator()
    assert gen.can_generate(
        {"epistemic_markers_pooled": {"by_category": {"epistemic_hedge": 2}}}
    )
    assert not gen.can_generate({"epistemic_markers_pooled": {"by_category": {}}})
    assert not gen.can_generate({"session_rows": [], "speaker_rows": []})


@pytest.mark.unit
def test_politeness_group_chart_can_generate_from_pooled() -> None:
    gen = PolitenessGroupChartGenerator()
    assert gen.can_generate({"politeness_pooled": {"by_category": {"gratitude": 1}}})
    assert not gen.can_generate({"politeness_pooled": {}})
