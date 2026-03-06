from __future__ import annotations

"""Tests for chart registry defaults."""

from dataclasses import dataclass

from transcriptx.core.utils.chart_registry import (
    CHART_DEFINITIONS,
    DEFAULT_OVERVIEW_VIZ_IDS,
    get_chart_definition,
    get_chart_registry,
    get_default_overview_charts,
    iter_chart_definitions,
    select_preferred_artifacts,
)


@dataclass
class FakeArtifact:
    id: str
    kind: str
    module: str | None
    scope: str | None
    speaker: str | None
    rel_path: str
    meta: dict | None = None
    title: str | None = None


def test_registry_unique_viz_ids():
    viz_ids = [c.viz_id for c in CHART_DEFINITIONS]
    assert len(viz_ids) == len(set(viz_ids))


def test_registry_fields_are_valid():
    allowed_scopes = {"global", "speaker"}
    allowed_cardinality = {"single", "multi", "speaker_set", "paired_static_dynamic"}
    for chart_def in CHART_DEFINITIONS:
        assert chart_def.viz_id
        assert chart_def.label
        assert isinstance(chart_def.rank_default, int)
        assert chart_def.scope in allowed_scopes
        assert chart_def.cardinality in allowed_cardinality
        matcher = chart_def.match
        assert any(
            [
                matcher.by_viz_id,
                matcher.by_artifact_key_prefix,
                matcher.by_chart_slug_regex,
                matcher.by_filename_glob,
            ]
        )


def test_registry_stability_core_viz_ids():
    core_viz_ids = [
        "sentiment.multi_speaker_sentiment.global",
        "emotion.radar.global",
        "interactions.network.global",
        "interactions.dominance.global",
        "temporal_dynamics.temporal_dashboard.global",
        "wordcloud.wordcloud.global.basic",
    ]
    for viz_id in core_viz_ids:
        assert get_chart_definition(viz_id) is not None


def test_matcher_prefers_viz_id_metadata():
    chart_def = get_chart_definition("sentiment.multi_speaker_sentiment.global")
    assert chart_def is not None
    artifact = FakeArtifact(
        id="a1",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        meta={"viz_id": "sentiment.multi_speaker_sentiment.global"},
    )
    assert chart_def.match.matches(artifact, chart_def) is True


def test_matcher_falls_back_to_path():
    chart_def = get_chart_definition("sentiment.multi_speaker_sentiment.global")
    assert chart_def is not None
    artifact = FakeArtifact(
        id="a2",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        meta=None,
    )
    assert chart_def.match.matches(artifact, chart_def) is True


def test_select_preferred_artifacts_single():
    chart_def = get_chart_definition("emotion.radar.global")
    assert chart_def is not None
    artifacts = [
        FakeArtifact(
            id="a_html",
            kind="chart_dynamic",
            module="emotion",
            scope="global",
            speaker=None,
            rel_path="emotion/charts/global/dynamic/emotion_all_radar.html",
            meta={"format": "html"},
        ),
        FakeArtifact(
            id="a_png",
            kind="chart_static",
            module="emotion",
            scope="global",
            speaker=None,
            rel_path="emotion/charts/global/static/emotion_all_radar.png",
            meta={"format": "png"},
        ),
    ]
    selected = select_preferred_artifacts(artifacts, chart_def)
    assert len(selected) == 1
    assert selected[0].id == "a_html"


def test_default_overview_viz_ids_exist():
    for viz_id in DEFAULT_OVERVIEW_VIZ_IDS:
        assert get_chart_definition(viz_id) is not None


def test_default_overview_charts_exist_in_registry():
    registry = get_chart_registry()
    missing = [
        viz_id for viz_id in get_default_overview_charts() if viz_id not in registry
    ]
    assert not missing


def test_iter_chart_definitions_returns_definitions():
    defs = list(iter_chart_definitions())
    assert defs
    assert all(hasattr(defn, "viz_id") for defn in defs)
