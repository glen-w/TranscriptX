"""Tests for group aggregate chart generation."""

from __future__ import annotations

from pathlib import Path
import pytest

from transcriptx.core.analysis.acts.config import get_all_act_types
from transcriptx.core.analysis.group_charts.acts import (
    ActsGroupChartGenerator,
    reconstruct_act_counters,
)
from transcriptx.core.analysis.group_charts.pauses_charts import (
    PausesGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.prosody_charts import (
    ProsodyGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.contagion_pooled_charts import (
    ContagionPooledGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.highlights_moments import (
    HighlightsGroupChartGenerator,
    MomentsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.interactions_charts import (
    InteractionsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.emotion_charts import (
    EmotionGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.entity_sentiment_pooled_charts import (
    EntitySentimentPooledGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.ner_pooled_charts import (
    NerPooledGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.tics_group_charts import (
    TicsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.topic_modeling_group_charts import (
    TopicModelingGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.bertopic_group_charts import (
    BertopicGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.sentiment_charts import (
    SentimentGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.stats_charts import StatsGroupChartGenerator
from transcriptx.core.analysis.group_charts.registry import (
    GROUP_AGGREGATE_CHART_FAMILIES,
    GROUP_CHART_REGISTRY,
)
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils.chart_registry import DEFAULT_GROUP_OVERVIEW_VIZ_IDS
from transcriptx.core.analysis.group_charts.runner import run_group_aggregate_charts
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.io import save_json, save_transcript


def test_reconstruct_act_counters_sums_sessions_and_merges_speakers() -> None:
    act_types = get_all_act_types()
    if not act_types:
        pytest.skip("no act types configured")
    a0, a1 = act_types[0], act_types[1] if len(act_types) > 1 else act_types[0]

    session_rows = [
        {"transcript_id": 1, "order_index": 0, "run_relpath": "r0", a0: 3, a1: 1},
        {"transcript_id": 2, "order_index": 1, "run_relpath": "r1", a0: 2, a1: 4},
    ]
    speaker_rows = [
        {
            "canonical_speaker_id": 10,
            "display_name": "Alice Example",
            a0: 2,
            a1: 1,
        },
        {
            "canonical_speaker_id": 10,
            "display_name": "Alice Example",
            a0: 1,
            a1: 2,
        },
    ]
    g, per = reconstruct_act_counters(session_rows, speaker_rows)
    assert g[a0] == 5
    assert g[a1] == 5 or (a0 == a1 and g[a0] == 5)
    alice = per.get("Alice Example")
    assert alice is not None
    assert alice[a0] == 3
    assert alice[a1] == 3 or (a0 == a1)


def test_acts_can_generate_false_when_empty() -> None:
    gen = ActsGroupChartGenerator()
    assert not gen.can_generate({"session_rows": [], "speaker_rows": []})
    assert not gen.can_generate(
        {"session_rows": [{"transcript_id": 1, "order_index": 0}], "speaker_rows": []}
    )


def _patch_output_dirs(monkeypatch: pytest.MonkeyPatch, outputs_root: Path) -> None:
    import transcriptx.core.utils.output_standards as output_standards_module
    import transcriptx.core.utils.paths as paths_module

    monkeypatch.setattr(paths_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(paths_module, "GROUP_OUTPUTS_DIR", str(outputs_root / "groups"))
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))


def test_run_group_aggregate_charts_acts_manifest_and_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    act_types = get_all_act_types()
    if not act_types:
        pytest.skip("no act types configured")
    a0 = act_types[0]

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "x",
                a0: 5,
            }
        ],
        "speaker_rows": [
            {
                "canonical_speaker_id": 1,
                "display_name": "Alice Example",
                a0: 5,
            }
        ],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="acts",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    assert res.skipped_reason is None
    assert res.emitted_paths, "expected chart files"
    assert all(p.exists() for p in res.emitted_paths)

    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["acts"],
    )
    charts = [
        a
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert charts, "manifest should list charts"
    for art in charts:
        if art.get("module") == "acts":
            tags = art.get("tags") or []
            assert "group_aggregate" in tags


def test_run_group_aggregate_charts_exception_sets_chart_failed_skip_reason(
    tmp_path: Path,
) -> None:
    """Generator exceptions surface as GROUP_CHART_FAILED + skipped_reason chart_failed."""

    class _BoomGen:
        agg_id = "stats"

        def can_generate(self, outcome: dict) -> bool:
            return True

        def generate(self, ctx, outcome: dict):
            raise RuntimeError("boom")

    group_run = tmp_path / "gr"
    group_run.mkdir(parents=True, exist_ok=True)
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "total_words": 10,
                "total_segments": 2,
                "total_duration": 1.0,
            }
        ],
        "speaker_rows": [],
    }
    res = run_group_aggregate_charts(
        agg_id="stats",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        registry={"stats": _BoomGen()},
    )
    assert res.skipped_reason == "chart_failed"
    assert res.warnings and res.warnings[0].get("code") == "GROUP_CHART_FAILED"


def test_registry_omits_misleading_generic_agg_ids() -> None:
    for aid in (
        "temporal_dynamics",
        "insight_eligibility",
        "voice_contours",
        "transcript_output",
    ):
        assert aid not in GROUP_CHART_REGISTRY
    assert isinstance(GROUP_CHART_REGISTRY["ner"], NerPooledGroupChartGenerator)
    assert isinstance(
        GROUP_CHART_REGISTRY["entity_sentiment"],
        EntitySentimentPooledGroupChartGenerator,
    )
    assert isinstance(
        GROUP_CHART_REGISTRY["topic_modeling"], TopicModelingGroupChartGenerator
    )
    assert isinstance(GROUP_CHART_REGISTRY["bertopic"], BertopicGroupChartGenerator)
    assert "highlights" in GROUP_CHART_REGISTRY
    assert "moments" in GROUP_CHART_REGISTRY


def test_registry_phase4_dedicated_generators() -> None:
    assert isinstance(GROUP_CHART_REGISTRY["pauses"], PausesGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["prosody"], ProsodyGroupChartGenerator)


def test_contagion_registered_with_dedicated_pooled_generator() -> None:
    assert isinstance(
        GROUP_CHART_REGISTRY["contagion"], ContagionPooledGroupChartGenerator
    )
    assert "pooled_single_view" in GROUP_AGGREGATE_CHART_FAMILIES["contagion"]


def test_group_chart_registry_matches_family_map_keys() -> None:
    assert set(GROUP_CHART_REGISTRY) == set(GROUP_AGGREGATE_CHART_FAMILIES)


def test_group_chart_registry_expected_generator_types() -> None:
    assert isinstance(GROUP_CHART_REGISTRY["acts"], ActsGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["stats"], StatsGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["sentiment"], SentimentGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["highlights"], HighlightsGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["moments"], MomentsGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["prosody"], ProsodyGroupChartGenerator)
    assert isinstance(GROUP_CHART_REGISTRY["pauses"], PausesGroupChartGenerator)

    assert isinstance(GROUP_CHART_REGISTRY["emotion"], EmotionGroupChartGenerator)
    assert isinstance(
        GROUP_CHART_REGISTRY["interactions"], InteractionsGroupChartGenerator
    )
    assert isinstance(
        GROUP_CHART_REGISTRY["contagion"], ContagionPooledGroupChartGenerator
    )
    assert isinstance(GROUP_CHART_REGISTRY["bertopic"], BertopicGroupChartGenerator)

    generic_agg_ids = (
        "understandability",
        "lexical_diversity",
        "simplified_transcript",
        "momentum",
        "affect_tension",
        "qa_analysis",
        "echoes",
        "conversation_loops",
    )
    for aid in generic_agg_ids:
        assert isinstance(
            GROUP_CHART_REGISTRY[aid], GenericNumericGroupChartGenerator
        ), aid

    assert isinstance(GROUP_CHART_REGISTRY["tics"], TicsGroupChartGenerator)


def test_ner_pooled_can_generate_requires_ner_pooled_payload() -> None:
    gen = NerPooledGroupChartGenerator()
    assert not gen.can_generate(
        {"session_rows": [{"order_index": 0}], "speaker_rows": []}
    )
    assert gen.can_generate(
        {
            "session_rows": [{"order_index": 0}],
            "speaker_rows": [],
            "ner_pooled": {"entity_type_counts": {"PER": 2}, "top_entities": []},
        }
    )


def test_interactions_pooled_can_generate_requires_payload() -> None:
    gen = InteractionsGroupChartGenerator()
    assert not gen.can_generate(
        {
            "session_rows": [],
            "speaker_rows": [],
            "interactions_pooled": {"schema_version": 1, "speakers": []},
        }
    )
    assert gen.can_generate(
        {
            "session_rows": [{"order_index": 0, "total_interactions": 1}],
            "speaker_rows": [],
            "interactions_pooled": {
                "schema_version": 1,
                "speakers": [
                    {
                        "canonical_speaker_id": 1,
                        "display_name": "A",
                        "interruptions_initiated": 2,
                        "interruptions_received": 0,
                        "responses_initiated": 0,
                        "responses_received": 0,
                    }
                ],
            },
        }
    )


def test_entity_sentiment_pooled_can_generate_requires_payload() -> None:
    gen = EntitySentimentPooledGroupChartGenerator()
    assert not gen.can_generate({"session_rows": [], "speaker_rows": []})
    assert gen.can_generate(
        {
            "session_rows": [],
            "speaker_rows": [],
            "entity_sentiment_pooled": {
                "entities": [{"entity": "x", "entity_type": "ORG", "mentions": 1}]
            },
        }
    )


def test_momentum_group_charts_respect_field_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "r0",
                "stall_zone_count": 2,
                "noise_metric": 99.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="momentum",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["momentum"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert any(v == "group.momentum.session.stall_zone_count" for v in vids)
    assert not any("noise_metric" in str(v) for v in vids)


def test_conversation_loops_group_charts_respect_numeric_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "r0",
                "total_loops": 3,
                "unique_speaker_pairs": 2,
                "speaker_pair_counts": {"A|B": 5},
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "r1",
                "total_loops": 1,
                "unique_speaker_pairs": 1,
                "speaker_pair_counts": {"C|D": 9},
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="conversation_loops",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    assert res.skipped_reason is None
    assert res.emitted_paths
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["conversation_loops"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    loop_viz = [v for v in vids if v and str(v).startswith("group.conversation_loops.")]
    assert set(loop_viz) == {
        "group.conversation_loops.session.total_loops",
        "group.conversation_loops.session.unique_speaker_pairs",
    }


def test_prosody_group_charts_skip_raw_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "r0",
                "prosody.f0_mean_hz": 120.0,
                "raw": {"noise_metric": 99.0},
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="prosody",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["prosody"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert "group.prosody.session.prosody_f0_mean_hz" in vids
    assert not any("noise_metric" in str(v) for v in vids)


def test_run_group_aggregate_charts_pauses_temporal_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    p1 = tmp_path / "m1" / "pauses" / "data" / "global"
    p2 = tmp_path / "m2" / "pauses" / "data" / "global"
    p1.mkdir(parents=True, exist_ok=True)
    p2.mkdir(parents=True, exist_ok=True)

    ev = {
        "event_id": "e1",
        "kind": "long_pause",
        "time_start": 120.0,
        "time_end": 125.0,
        "speaker": "Alice Example",
        "segment_start_idx": 0,
        "segment_end_idx": 0,
        "severity": 1.0,
    }
    save_json([ev], str(p1 / "pauses.events.json"))
    save_json(
        [
            {
                **ev,
                "event_id": "e2",
                "time_start": 30.0,
                "time_end": 32.0,
            }
        ],
        str(p2 / "pauses.events.json"),
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "mean_pause": 1.2,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "mean_pause": 2.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t2), str(t1)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={},
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="pauses",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=list(reversed(members)),
    )
    assert res.skipped_reason is None
    assert res.emitted_paths

    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["pauses"],
    )
    titles = [str(a.get("title") or "") for a in manifest["artifacts"]]
    assert any("cross-session overlay" in t.lower() for t in titles), titles
    assert any("session-relative minutes" in t.lower() for t in titles), titles
    metas = [a.get("meta") or {} for a in manifest["artifacts"]]
    vids = [m.get("viz_id") for m in metas if isinstance(m, dict)]
    assert "group.pauses.temporal_overlay.global" in vids


def test_run_group_aggregate_charts_highlights_content_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    outcome = {
        "session_rows": [
            {"transcript_id": 1, "order_index": 0, "session_label": "Meet1"},
            {"transcript_id": 2, "order_index": 1, "session_label": "Meet2"},
        ],
        "speaker_rows": [],
        "content_rows": [
            {"order_index": 0, "score": 0.9},
            {"order_index": 0, "score": 0.7},
            {"order_index": 1, "score": 0.5},
        ],
        "content_rows_name": "highlight_rows",
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json", "/tmp/b.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="highlights",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    assert res.skipped_reason is None
    assert res.emitted_paths
    assert all(p.exists() for p in res.emitted_paths)


def test_run_group_aggregate_charts_acts_temporal_overlay_with_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    m1 = tmp_path / "m1" / "acts" / "data" / "global"
    m2 = tmp_path / "m2" / "acts" / "data" / "global"
    m1.mkdir(parents=True, exist_ok=True)
    m2.mkdir(parents=True, exist_ok=True)

    act_types = get_all_act_types()
    if not act_types:
        pytest.skip("no act types configured")
    a0 = act_types[0]

    save_transcript(
        [
            {"start": 10.0, "speaker": "Alice Example", "dialogue_act": a0},
            {"start": 130.0, "speaker": "Alice Example", "dialogue_act": a0},
        ],
        str(m1 / "meet_a_with_acts.json"),
    )
    save_transcript(
        [
            {"start": 5.0, "speaker": "Alice Example", "dialogue_act": a0},
        ],
        str(m2 / "meet_b_with_acts.json"),
    )

    outcome = {
        "session_rows": [
            {"transcript_id": 1, "order_index": 0, "run_relpath": "m1", a0: 2},
            {"transcript_id": 2, "order_index": 1, "run_relpath": "m2", a0: 1},
        ],
        "speaker_rows": [
            {
                "canonical_speaker_id": 1,
                "display_name": "Alice Example",
                a0: 3,
            }
        ],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={},
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="acts",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
    )
    assert res.skipped_reason is None
    assert res.emitted_paths

    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["acts"],
    )
    titles = [str(a.get("title") or "") for a in manifest["artifacts"]]
    assert any("cross-session overlay" in t for t in titles), titles
    metas = [a.get("meta") or {} for a in manifest["artifacts"]]
    vids = [m.get("viz_id") for m in metas if isinstance(m, dict)]
    assert "group.acts.temporal_overlay.global" in vids


def test_run_group_aggregate_charts_sentiment_temporal_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    s1 = tmp_path / "m1" / "sentiment" / "data" / "global"
    s2 = tmp_path / "m2" / "sentiment" / "data" / "global"
    s1.mkdir(parents=True, exist_ok=True)
    s2.mkdir(parents=True, exist_ok=True)

    save_transcript(
        [
            {"start": 10.0, "sentiment": {"compound": 0.4}},
            {"start": 70.0, "sentiment": {"compound": -0.1}},
        ],
        str(s1 / "meet_a_with_sentiment.json"),
    )
    save_transcript(
        [
            {"start": 5.0, "sentiment": {"compound": 0.2}},
        ],
        str(s2 / "meet_b_with_sentiment.json"),
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "compound_mean": 0.3,
                "pos_mean": 0.2,
                "neu_mean": 0.5,
                "neg_mean": 0.1,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "compound_mean": 0.1,
                "pos_mean": 0.1,
                "neu_mean": 0.7,
                "neg_mean": 0.1,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={},
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="sentiment",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
    )
    assert res.skipped_reason is None
    assert res.emitted_paths

    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["sentiment"],
    )
    titles = [str(a.get("title") or "") for a in manifest["artifacts"]]
    assert any("cross-session overlay" in t.lower() for t in titles), titles
    assert any("session-relative minutes" in t.lower() for t in titles), titles


def test_emotion_group_charts_zero_fills_absent_emotions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "r0",
                "global_emotions": {"joy": 0.5, "anger": 0.1},
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "r1",
                "global_emotions": {"anger": 0.2},
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json", "/tmp/b.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="emotion",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["emotion"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert "group.emotion.session.joy" in vids
    joy_art = next(
        a
        for a in manifest["artifacts"]
        if (a.get("meta") or {}).get("viz_id") == "group.emotion.session.joy"
    )
    assert joy_art.get("title")


def test_emotion_group_charts_canonical_order_in_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    # sadness appears before joy lexically in data keys, but charts follow CANONICAL_EMOTION_LABELS.
    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "r0",
                "global_emotions": {"sadness": 0.3, "joy": 0.1},
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    run_group_aggregate_charts(
        agg_id="emotion",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["emotion"],
    )
    emotion_session_vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
        and str((a.get("meta") or {}).get("viz_id", "")).startswith(
            "group.emotion.session."
        )
    ]
    assert "group.emotion.session.joy" in emotion_session_vids
    assert "group.emotion.session.sadness" in emotion_session_vids
    assert {"joy", "sadness"} == {str(v).split(".")[-1] for v in emotion_session_vids}


def test_emotion_group_charts_skips_all_zero_series(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "r0",
                "global_emotions": {"joy": 0.0},
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "r1",
                "global_emotions": {"joy": 0.0},
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=["/tmp/a.json", "/tmp/b.json"],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    run_group_aggregate_charts(
        agg_id="emotion",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
    )
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["emotion"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert not any(v == "group.emotion.session.joy" for v in vids)


def test_registry_emotion_is_dedicated_not_generic() -> None:
    assert isinstance(GROUP_CHART_REGISTRY["emotion"], EmotionGroupChartGenerator)
    assert not isinstance(
        GROUP_CHART_REGISTRY["emotion"], GenericNumericGroupChartGenerator
    )


def test_emotion_group_charts_noop_when_no_canonical_keys() -> None:
    gen = EmotionGroupChartGenerator()
    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "global_emotions": {"Joy": 0.5, "happiness": 0.2},
            },
        ],
        "speaker_rows": [],
    }
    assert not gen.can_generate(outcome)


def test_run_group_aggregate_charts_emotion_temporal_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    e1 = tmp_path / "m1" / "emotion" / "data" / "global"
    e2 = tmp_path / "m2" / "emotion" / "data" / "global"
    e1.mkdir(parents=True, exist_ok=True)
    e2.mkdir(parents=True, exist_ok=True)

    save_transcript(
        [
            {
                "start": 10.0,
                "context_emotion_primary": "joy",
                "context_emotion_scores": {"joy": 0.8, "sadness": 0.1},
            },
            {
                "start": 40.0,
                "context_emotion_primary": "joy",
                "context_emotion_scores": {"joy": 0.5},
            },
        ],
        str(e1 / "meet_a_with_emotion.json"),
    )
    save_transcript(
        [
            {
                "start": 5.0,
                "context_emotion_primary": "joy",
                "context_emotion_scores": {"joy": 0.3},
            },
            {
                "start": 25.0,
                "context_emotion_primary": "joy",
                "context_emotion_scores": {"joy": 0.6},
            },
        ],
        str(e2 / "meet_b_with_emotion.json"),
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "global_emotions": {"joy": 0.5},
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "global_emotions": {"joy": 0.4},
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={},
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="emotion",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["emotion"],
    )
    titles = [str(a.get("title") or "") for a in manifest["artifacts"]]
    assert any("cross-session overlay" in t.lower() for t in titles), titles
    assert any("session-relative minutes" in t.lower() for t in titles), titles
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if isinstance(a.get("meta"), dict)
    ]
    assert "group.emotion.temporal_overlay.global" in vids


def test_run_group_aggregate_charts_prosody_temporal_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    g1 = tmp_path / "m1" / "prosody_dashboard" / "data" / "global"
    g2 = tmp_path / "m2" / "prosody_dashboard" / "data" / "global"
    g1.mkdir(parents=True, exist_ok=True)
    g2.mkdir(parents=True, exist_ok=True)

    save_json(
        {
            "schema_version": 1,
            "y_field": "rms_db",
            "segments": [
                {"start": 10.0, "rms_db": -20.0},
                {"start": 40.0, "rms_db": -18.0},
            ],
        },
        str(g1 / "meet_a_prosody_overlay_segments.v1.json"),
    )
    save_json(
        {
            "schema_version": 1,
            "y_field": "rms_db",
            "segments": [
                {"start": 5.0, "rms_db": -22.0},
                {"start": 25.0, "rms_db": -19.0},
            ],
        },
        str(g2 / "meet_b_prosody_overlay_segments.v1.json"),
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "prosody.f0_mean_hz": 120.0,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "prosody.f0_mean_hz": 130.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={},
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={},
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="prosody",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["prosody"],
    )
    titles = [str(a.get("title") or "") for a in manifest["artifacts"]]
    assert any("cross-session overlay" in t.lower() for t in titles), titles
    assert any("session-relative minutes" in t.lower() for t in titles), titles
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if isinstance(a.get("meta"), dict)
    ]
    assert "group.prosody.temporal_overlay.global" in vids


def test_prosody_temporal_overlay_skipped_without_per_transcript_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    g1 = tmp_path / "m1" / "prosody_dashboard" / "data" / "global"
    g2 = tmp_path / "m2" / "prosody_dashboard" / "data" / "global"
    g1.mkdir(parents=True, exist_ok=True)
    g2.mkdir(parents=True, exist_ok=True)

    save_json(
        {
            "schema_version": 1,
            "y_field": "rms_db",
            "segments": [
                {"start": 10.0, "rms_db": -20.0},
                {"start": 40.0, "rms_db": -18.0},
            ],
        },
        str(g1 / "meet_a_prosody_overlay_segments.v1.json"),
    )
    save_json(
        {
            "schema_version": 1,
            "y_field": "rms_db",
            "segments": [
                {"start": 5.0, "rms_db": -22.0},
                {"start": 25.0, "rms_db": -19.0},
            ],
        },
        str(g2 / "meet_b_prosody_overlay_segments.v1.json"),
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "prosody.f0_mean_hz": 120.0,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "prosody.f0_mean_hz": 130.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    res = run_group_aggregate_charts(
        agg_id="prosody",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=None,
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["prosody"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if isinstance(a.get("meta"), dict)
    ]
    assert "group.prosody.temporal_overlay.global" not in vids


def test_stats_cross_session_skipped_without_canonical_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "speaker_count": 1,
                "total_words": 50,
                "total_segments": 5,
                "total_duration": 60.0,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "speaker_count": 1,
                "total_words": 80,
                "total_segments": 8,
                "total_duration": 90.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    tuple_a = (60.0, "Alice", 50, 5, 0.01, 0.0)
    tuple_b = (90.0, "Alice", 80, 8, 0.02, 0.0)
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [tuple_a],
                        "sentiment_summary": {},
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [tuple_b],
                        "sentiment_summary": {},
                    }
                }
            },
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="stats",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
        canonical_speaker_map=None,
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["stats"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert not any(v and "cross_session_speaker" in str(v) for v in vids), vids


def test_default_group_overview_excludes_sentiment_cross_session() -> None:
    for vid in DEFAULT_GROUP_OVERVIEW_VIZ_IDS:
        assert "cross_session_speaker" not in vid


def test_sentiment_cross_session_speaker_charts_with_canonical_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={str(t1): {"0": 42}, str(t2): {"0": 42}},
        transcript_to_display={str(t1): {"0": "Alice"}, str(t2): {"0": "Alice"}},
        canonical_to_display={42: "Alice"},
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "compound_mean": 0.1,
                "pos_mean": 0.2,
                "neu_mean": 0.5,
                "neg_mean": 0.2,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "compound_mean": 0.2,
                "pos_mean": 0.2,
                "neu_mean": 0.5,
                "neg_mean": 0.1,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={
                "sentiment": {
                    "payload": {
                        "speaker_stats": {
                            "Alice": {
                                "count": 2,
                                "compound_mean": 0.4,
                                "pos_mean": 0.2,
                                "neu_mean": 0.5,
                                "neg_mean": 0.1,
                            }
                        },
                        "global_stats": {"count": 2, "compound_mean": 0.4},
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={
                "sentiment": {
                    "payload": {
                        "speaker_stats": {
                            "Alice": {
                                "count": 1,
                                "compound_mean": -0.1,
                                "pos_mean": 0.1,
                                "neu_mean": 0.6,
                                "neg_mean": 0.2,
                            }
                        },
                        "global_stats": {"count": 1, "compound_mean": -0.1},
                    }
                }
            },
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="sentiment",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
        canonical_speaker_map=cmap,
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["sentiment"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert "group.sentiment.cross_session_speaker.speaker_42" in vids


def test_sentiment_cross_session_skipped_when_only_one_session_has_speaker_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={str(t1): {"0": 42}, str(t2): {"0": 42}},
        transcript_to_display={str(t1): {"0": "Alice"}, str(t2): {"0": "Alice"}},
        canonical_to_display={42: "Alice"},
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "compound_mean": 0.1,
                "pos_mean": 0.2,
                "neu_mean": 0.5,
                "neg_mean": 0.2,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "compound_mean": 0.2,
                "pos_mean": 0.2,
                "neu_mean": 0.5,
                "neg_mean": 0.1,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={
                "sentiment": {
                    "payload": {
                        "speaker_stats": {
                            "Alice": {
                                "count": 2,
                                "compound_mean": 0.4,
                                "pos_mean": 0.2,
                                "neu_mean": 0.5,
                                "neg_mean": 0.1,
                            }
                        },
                        "global_stats": {"count": 2, "compound_mean": 0.4},
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={
                "sentiment": {
                    "payload": {
                        "speaker_stats": {},
                        "global_stats": {"count": 0, "compound_mean": 0.0},
                    }
                }
            },
        ),
    ]
    run_group_aggregate_charts(
        agg_id="sentiment",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
        canonical_speaker_map=cmap,
    )
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["sentiment"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert not any(
        v and "cross_session_speaker" in str(v) for v in vids
    ), "need ≥2 sessions with speaker_stats points"


def test_stats_cross_session_speaker_charts_with_canonical_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={str(t1): {"0": 42}, str(t2): {"0": 42}},
        transcript_to_display={str(t1): {"0": "Alice"}, str(t2): {"0": "Alice"}},
        canonical_to_display={42: "Alice"},
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "speaker_count": 1,
                "total_words": 50,
                "total_segments": 5,
                "total_duration": 60.0,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "speaker_count": 1,
                "total_words": 80,
                "total_segments": 8,
                "total_duration": 90.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    tuple_a = (60.0, "Alice", 50, 5, 0.01, 0.0)
    tuple_b = (90.0, "Alice", 80, 8, 0.02, 0.0)
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [tuple_a],
                        "sentiment_summary": {},
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [tuple_b],
                        "sentiment_summary": {},
                    }
                }
            },
        ),
    ]
    res = run_group_aggregate_charts(
        agg_id="stats",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
        canonical_speaker_map=cmap,
    )
    assert res.skipped_reason is None
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["stats"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert "group.stats.cross_session_speaker.speaker_42" in vids
    assert "group.stats.cross_session_speaker.segment_count.speaker_42" in vids
    titles = [str(a.get("title") or "") for a in manifest["artifacts"]]
    assert any("segment count across sessions" in t.lower() for t in titles), titles


def test_stats_cross_session_skipped_when_only_one_session_has_word_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("matplotlib")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _patch_output_dirs(monkeypatch, outputs_root)

    group_run = outputs_root / "groups" / "guuid" / "run1"
    group_run.mkdir(parents=True, exist_ok=True)

    t1 = tmp_path / "meet_a.json"
    t2 = tmp_path / "meet_b.json"
    t1.write_text("[]", encoding="utf-8")
    t2.write_text("[]", encoding="utf-8")

    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={str(t1): {"0": 42}, str(t2): {"0": 42}},
        transcript_to_display={str(t1): {"0": "Alice"}, str(t2): {"0": "Alice"}},
        canonical_to_display={42: "Alice"},
    )

    outcome = {
        "session_rows": [
            {
                "transcript_id": 1,
                "order_index": 0,
                "run_relpath": "m1",
                "speaker_count": 1,
                "total_words": 50,
                "total_segments": 5,
                "total_duration": 60.0,
            },
            {
                "transcript_id": 2,
                "order_index": 1,
                "run_relpath": "m2",
                "speaker_count": 0,
                "total_words": 0,
                "total_segments": 0,
                "total_duration": 0.0,
            },
        ],
        "speaker_rows": [],
    }
    ts = TranscriptSet.create(
        transcript_ids=[str(t1), str(t2)],
        name="G",
        metadata={"group_uuid": "guuid"},
        key="gk",
    )
    members = [
        PerTranscriptResult(
            transcript_path=str(t1),
            transcript_key="k1",
            run_id="r1",
            order_index=0,
            output_dir=str(tmp_path / "m1"),
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [(60.0, "Alice", 50, 5, 0.01, 0.0)],
                        "sentiment_summary": {},
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path=str(t2),
            transcript_key="k2",
            run_id="r2",
            order_index=1,
            output_dir=str(tmp_path / "m2"),
            module_results={
                "stats": {
                    "payload": {
                        "speaker_stats": [],
                        "sentiment_summary": {},
                    }
                }
            },
        ),
    ]
    run_group_aggregate_charts(
        agg_id="stats",
        group_run_root=group_run,
        group_run_id="run1",
        outcome=outcome,
        transcript_set=ts,
        group_uuid="guuid",
        per_transcript_results=members,
        canonical_speaker_map=cmap,
    )
    manifest = build_output_manifest(
        run_dir=group_run,
        run_id="run1",
        transcript_key="guuid",
        modules_enabled=["stats"],
    )
    vids = [
        (a.get("meta") or {}).get("viz_id")
        for a in manifest["artifacts"]
        if a["kind"] in ("chart_static", "chart_dynamic")
    ]
    assert not any(
        v and "group.stats.cross_session_speaker" in str(v) for v in vids
    ), "need ≥2 sessions with word_count for stats cross-session"


def test_manifest_merges_meta_tags_into_tags(tmp_path: Path) -> None:
    from transcriptx.core.utils.artifact_writer import write_json

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = run_dir / ".transcriptx"
    meta_dir.mkdir(parents=True, exist_ok=True)
    png = run_dir / "acts" / "charts" / "global" / "static" / "x.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    write_json(
        meta_dir / "artifacts_meta.json",
        {
            "acts/charts/global/static/x.png": {
                "tags": ["group_aggregate", "custom_meta_tag"],
                "title": "T",
                "scope": "global",
            }
        },
    )
    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id="r1",
        transcript_key="tk",
        modules_enabled=["acts"],
    )
    art = next(a for a in manifest["artifacts"] if a["rel_path"].endswith(".png"))
    tags = art.get("tags") or []
    assert "group_aggregate" in tags
    assert "custom_meta_tag" in tags
