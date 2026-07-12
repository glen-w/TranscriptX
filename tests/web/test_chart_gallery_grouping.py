"""Tests for chart gallery family/slice grouping view-model."""

from __future__ import annotations

from transcriptx.core.utils.chart_registry import get_chart_definition
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.chart_view_model_service import (
    ChartGalleryFamily,
    group_charts_into_families,
    infer_session_slice_from_title,
    infer_speaker_from_chart_path,
)


def _artifact(
    *,
    id: str,
    viz_id: str | None = None,
    kind: str = "chart_dynamic",
    module: str = "acts",
    scope: str | None = "speaker",
    speaker: str | None = None,
    rel_path: str = "acts/charts/speakers/Glen/acts_temporal.html",
    title: str | None = None,
    tags: list[str] | None = None,
    subview: str | None = None,
    slice_id: str | None = None,
    meta: dict | None = None,
) -> Artifact:
    return Artifact(
        id=id,
        kind=kind,
        module=module,
        scope=scope,
        speaker=speaker,
        subview=subview,
        slice_id=slice_id,
        rel_path=rel_path,
        bytes=1,
        mtime="",
        mime="text/html",
        tags=tags or [],
        title=title,
        meta=meta if meta is not None else ({"viz_id": viz_id} if viz_id else {}),
    )


def test_speaker_set_grouping_three_speakers():
    viz_id = "acts.acts_temporal.speaker"
    family_label = get_chart_definition(viz_id).label
    charts = [
        _artifact(
            id="glen",
            viz_id=viz_id,
            speaker="Glen",
            rel_path="acts/charts/speakers/Glen/acts_temporal.html",
            title="Dialogue Acts Over Time – Glen",
        ),
        _artifact(
            id="rana",
            viz_id=viz_id,
            speaker="Rana",
            rel_path="acts/charts/speakers/Rana/acts_temporal.html",
            title="Dialogue Acts Over Time – Rana",
        ),
        _artifact(
            id="thomas",
            viz_id=viz_id,
            speaker="Thomas",
            rel_path="acts/charts/speakers/Thomas/acts_temporal.html",
            title="Dialogue Acts Over Time – Thomas",
        ),
    ]
    families = group_charts_into_families(charts)
    assert len(families) == 1
    family = families[0]
    assert family.key == viz_id
    assert family.label == family_label
    assert "Glen" not in family.label
    assert len(family.slices) == 3
    slice_keys = {s.key for s in family.slices}
    assert slice_keys == {"Glen", "Rana", "Thomas"}
    for sl in family.slices:
        assert len(sl.artifacts) == 1
        assert sl.artifacts[0].speaker == sl.key


def test_global_single_grouping():
    viz_id = "emotion.radar.global"
    art = _artifact(
        id="global-radar",
        viz_id=viz_id,
        kind="chart_static",
        module="emotion",
        scope="global",
        speaker=None,
        rel_path="emotion/charts/global/static/radar.png",
        title="Emotion Radar (All Speakers)",
    )
    families = group_charts_into_families([art])
    assert len(families) == 1
    family = families[0]
    assert family.key == viz_id
    assert len(family.slices) == 1
    assert family.slices[0].key == "all"
    assert family.slices[0].label == ""
    assert family.slices[0].artifacts == [art]


def test_paired_static_dynamic_grouping():
    viz_id = "group.acts.temporal_overlay.global"
    family_label = get_chart_definition(viz_id).label
    static = _artifact(
        id="overlay-static",
        viz_id=viz_id,
        kind="chart_static",
        module="acts",
        scope="global",
        speaker=None,
        rel_path="acts/charts/group/acts_temporal_overlay.png",
        title="Wrong Static Title – Glen",
        tags=["group_aggregate"],
    )
    dynamic = _artifact(
        id="overlay-dynamic",
        viz_id=viz_id,
        kind="chart_dynamic",
        module="acts",
        scope="global",
        speaker=None,
        rel_path="acts/charts/group/acts_temporal_overlay.html",
        title="Wrong Dynamic Title – Rana",
        tags=["group_aggregate"],
    )
    families = group_charts_into_families([static, dynamic])
    assert len(families) == 1
    family = families[0]
    assert family.label == family_label
    assert family.cardinality == "paired_static_dynamic"
    assert len(family.slices) == 1
    assert family.slices[0].key == "all"
    assert {a.id for a in family.slices[0].artifacts} == {
        "overlay-static",
        "overlay-dynamic",
    }


def test_unregistered_artifact_fallback():
    art = _artifact(
        id="unreg",
        viz_id=None,
        meta={},
        module="custom",
        scope="speaker",
        speaker="Glen",
        rel_path="custom/charts/speakers/Glen/special_plot.html",
        title="Special Plot – Glen",
    )
    families = group_charts_into_families([art])
    assert len(families) == 1
    family = families[0]
    assert family.key.startswith("unregistered:custom:")
    assert family.label == "Special Plot – Glen"
    assert family.cardinality == "unknown"
    assert family.rank == 9999
    assert len(family.slices) == 1
    assert family.slices[0].key == "all"


def test_member_session_grouping_by_slice_id():
    viz_id = "sentiment.multi_speaker_sentiment.global"
    charts = [
        _artifact(
            id="m0",
            viz_id=viz_id,
            kind="chart_static",
            module="sentiment",
            scope="global",
            speaker=None,
            rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
            title="session_a: Multi Speaker Sentiment",
            tags=["member_session"],
            slice_id="member_0",
        ),
        _artifact(
            id="m1",
            viz_id=viz_id,
            kind="chart_static",
            module="sentiment",
            scope="global",
            speaker=None,
            rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
            title="session_b: Multi Speaker Sentiment",
            tags=["member_session"],
            slice_id="member_1",
        ),
    ]
    families = group_charts_into_families(charts)
    assert len(families) == 1
    assert len(families[0].slices) == 2
    assert {s.key for s in families[0].slices} == {"member_0", "member_1"}


def test_infer_session_slice_from_title():
    assert infer_session_slice_from_title("session_a: Chart Title") == "session_a"
    assert infer_session_slice_from_title("No Prefix Title") is None
    assert infer_session_slice_from_title(None) is None


def test_tfidf_wordcloud_slice_uses_path_speaker_not_filename_title():
    viz_id = "wordcloud.wordcloud.speaker.tfidf"
    art = _artifact(
        id="ana-tfidf",
        viz_id=viz_id,
        kind="chart_static",
        module="wordclouds",
        scope="speaker",
        speaker=None,
        rel_path="wordclouds/charts/speakers/Ana/static/tfidf/tfidf.png",
        title="Tfidf",
        meta={"viz_id": viz_id, "scope": "speaker"},
    )
    families = group_charts_into_families([art])
    assert len(families) == 1
    assert families[0].key == viz_id
    assert len(families[0].slices) == 1
    assert families[0].slices[0].key == "Ana"
    assert families[0].slices[0].label == "Ana"


def test_infer_speaker_from_chart_path():
    assert (
        infer_speaker_from_chart_path(
            "wordclouds/charts/speakers/Ana/static/tfidf/tfidf.png"
        )
        == "Ana"
    )
    assert (
        infer_speaker_from_chart_path(
            "wordclouds/charts/global/static/tfidf/tfidf-ALL.png"
        )
        is None
    )


def test_member_session_title_prefix_fallback():
    viz_id = "emotion.radar.global"
    art = _artifact(
        id="member-title",
        viz_id=viz_id,
        kind="chart_static",
        module="emotion",
        scope="global",
        speaker=None,
        rel_path="emotion/charts/global/static/radar.png",
        title="session_c: Emotion Radar",
        tags=["member_session"],
        slice_id=None,
        meta={"viz_id": viz_id},
    )
    families = group_charts_into_families([art])
    assert len(families) == 1
    assert families[0].slices[0].key == "session_c"


def test_deterministic_family_and_slice_sorting():
    viz_low = "acts.acts_temporal.speaker"
    viz_high = "emotion.radar.speaker"
    charts = [
        _artifact(
            id="z-speaker",
            viz_id=viz_low,
            speaker="Zoe",
            rel_path="acts/charts/speakers/Zoe/acts_temporal.html",
        ),
        _artifact(
            id="a-speaker",
            viz_id=viz_low,
            speaker="Ana",
            rel_path="acts/charts/speakers/Ana/acts_temporal.html",
        ),
        _artifact(
            id="radar-b",
            viz_id=viz_high,
            speaker="Bob",
            rel_path="emotion/charts/speakers/Bob/radar.html",
            module="emotion",
        ),
    ]
    families = group_charts_into_families(charts)
    assert len(families) == 2
    assert families[0].key == viz_high
    assert [s.key for s in families[1].slices] == ["Ana", "Zoe"]


def test_family_artifact_count_property():
    from transcriptx.web.services.chart_view_model_service import ChartGallerySlice

    family = ChartGalleryFamily(
        key="k",
        label="L",
        description=None,
        cardinality="speaker_set",
        rank=1,
        slices=[
            ChartGallerySlice(key="a", label="A", artifacts=[]),
            ChartGallerySlice(
                key="b",
                label="B",
                artifacts=[
                    _artifact(id="1", viz_id="acts.acts_temporal.speaker", speaker="A"),
                    _artifact(id="2", viz_id="acts.acts_temporal.speaker", speaker="B"),
                ],
            ),
        ],
    )
    assert family.artifact_count == 2
