"""Tests for chart help/description plumbing (resolver + overview slots)."""

from __future__ import annotations

from transcriptx.core.utils.chart_registry import get_chart_definition
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.chart_view_model_service import (
    build_overview_slots,
    resolve_chart_description,
)


def _artifact(
    *,
    viz_id: str | None,
    kind: str = "chart_static",
    module: str | None = None,
    scope: str | None = None,
    meta: dict | None = "unset",  # type: ignore[assignment]
) -> Artifact:
    if meta == "unset":
        meta = {"viz_id": viz_id} if viz_id is not None else {}
    return Artifact(
        id=f"art-{viz_id or 'none'}",
        kind=kind,
        module=module,
        scope=scope,
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path=f"{module or 'm'}/charts/{viz_id or 'x'}.png",
        bytes=1,
        mtime="",
        mime="image/png",
        tags=[],
        title=None,
        meta=meta,
    )


def test_resolve_chart_description_valid_viz_id():
    viz_id = "emotion.radar.global"
    expected = get_chart_definition(viz_id).description
    art = _artifact(viz_id=viz_id, module="emotion", scope="global")
    resolved = resolve_chart_description(art)
    assert resolved == expected.strip()
    assert resolved and len(resolved) >= 20


def test_resolve_chart_description_emotion_family_charts():
    """Contextual / fine-grained emotion charts must resolve gallery descriptions."""
    for viz_id, module, scope in (
        ("contextual_emotion.label_counts.global", "contextual_emotion", "global"),
        ("contextual_emotion.label_counts.speaker", "contextual_emotion", "speaker"),
        ("fine_grained_emotion.label_counts.global", "fine_grained_emotion", "global"),
        (
            "fine_grained_emotion.label_counts.speaker",
            "fine_grained_emotion",
            "speaker",
        ),
    ):
        expected = get_chart_definition(viz_id).description
        assert expected and len(expected.strip()) >= 20
        art = _artifact(viz_id=viz_id, module=module, scope=scope)
        resolved = resolve_chart_description(art)
        assert resolved == expected.strip()
        # Distinguish from lexical emotion; name experimental channel in captions.
        assert "experimental" in resolved.lower()
        assert "lexical" in resolved.lower() or "multilabel" in resolved.lower()


def test_resolve_chart_description_missing_viz_id():
    art = _artifact(viz_id=None, meta={})
    assert resolve_chart_description(art) is None


def test_resolve_chart_description_no_meta():
    art = _artifact(viz_id=None, meta=None)
    assert resolve_chart_description(art) is None


def test_resolve_chart_description_unknown_viz_id():
    art = _artifact(viz_id="does.not.exist.global", module="x", scope="global")
    assert resolve_chart_description(art) is None


def test_resolve_chart_description_empty_registry_description(monkeypatch):
    """A blank registry description must resolve to None, not an empty string."""
    import transcriptx.web.services.chart_view_model_service as svc

    class _Blank:
        description = "   "

    monkeypatch.setattr(
        svc, "find_chart_definition_for_artifact", lambda artifact: _Blank()
    )
    art = _artifact(viz_id="emotion.radar.global", module="emotion", scope="global")
    assert resolve_chart_description(art) is None


def test_resolve_chart_description_falls_back_to_path():
    """A chart with no viz_id metadata still resolves via the registry path match."""
    viz_id = "sentiment.multi_speaker_sentiment.global"
    expected = get_chart_definition(viz_id).description
    art = Artifact(
        id="art-path-only",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        bytes=1,
        mtime="",
        mime="image/png",
        tags=[],
        title=None,
        meta=None,
    )
    resolved = resolve_chart_description(art)
    assert resolved == expected.strip()
    assert resolved and len(resolved) >= 20


def test_build_overview_slots_includes_description_key():
    viz_id = "emotion.radar.global"
    art = _artifact(
        viz_id=viz_id, kind="chart_static", module="emotion", scope="global"
    )
    slots = build_overview_slots(
        overview_candidates=[art],
        user_overview=[viz_id],
        missing_behavior="skip",
        max_items=None,
    )
    assert slots, "expected at least one overview slot"
    assert all("description" in slot for slot in slots)


def test_build_overview_slots_propagates_description_content():
    viz_id = "emotion.radar.global"
    expected = get_chart_definition(viz_id).description.strip()
    art = _artifact(
        viz_id=viz_id, kind="chart_static", module="emotion", scope="global"
    )
    slots = build_overview_slots(
        overview_candidates=[art],
        user_overview=[viz_id],
        missing_behavior="skip",
        max_items=None,
    )
    target = next(slot for slot in slots if slot["viz_id"] == viz_id)
    assert target["description"] == expected


def test_build_overview_slots_placeholder_has_none_description():
    slots = build_overview_slots(
        overview_candidates=[],
        user_overview=["totally.unknown.viz_id"],
        missing_behavior="show_placeholder",
        max_items=None,
    )
    assert slots
    assert all(slot.get("description") is None for slot in slots)


def test_build_overview_slots_speaker_set_uses_family_label_not_first_artifact_title():
    """Per-speaker chart families must not inherit one speaker's name in the slot header."""
    viz_id = "acts.acts_temporal.speaker"
    family_label = get_chart_definition(viz_id).label
    candidates = [
        Artifact(
            id="art-glen",
            kind="chart_dynamic",
            module="acts",
            scope="speaker",
            speaker="Glen",
            subview=None,
            slice_id=None,
            rel_path="acts/charts/speakers/Glen/acts_temporal.html",
            bytes=1,
            mtime="",
            mime="text/html",
            tags=[],
            title="Dialogue Acts Over Time – Glen",
            meta={"viz_id": viz_id},
        ),
        Artifact(
            id="art-rana",
            kind="chart_dynamic",
            module="acts",
            scope="speaker",
            speaker="Rana",
            subview=None,
            slice_id=None,
            rel_path="acts/charts/speakers/Rana/acts_temporal.html",
            bytes=1,
            mtime="",
            mime="text/html",
            tags=[],
            title="Dialogue Acts Over Time – Rana",
            meta={"viz_id": viz_id},
        ),
    ]
    slots = build_overview_slots(
        overview_candidates=candidates,
        user_overview=[viz_id],
        missing_behavior="skip",
        max_items=None,
    )
    target = next(slot for slot in slots if slot["viz_id"] == viz_id)
    assert target["label"] == family_label
    assert "Glen" not in target["label"]
    assert len(target["artifacts"]) == 2


def test_build_overview_slots_single_uses_artifact_title():
    viz_id = "emotion.radar.global"
    custom_title = "Custom Emotion Radar Title"
    art = Artifact(
        id="art-single-custom",
        kind="chart_static",
        module="emotion",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="emotion/charts/global/static/radar.png",
        bytes=1,
        mtime="",
        mime="image/png",
        tags=[],
        title=custom_title,
        meta={"viz_id": viz_id},
    )
    slots = build_overview_slots(
        overview_candidates=[art],
        user_overview=[viz_id],
        missing_behavior="skip",
        max_items=None,
    )
    target = next(slot for slot in slots if slot["viz_id"] == viz_id)
    assert target["label"] == custom_title


def test_build_overview_slots_paired_static_dynamic_uses_family_label():
    viz_id = "group.acts.temporal_overlay.global"
    family_label = get_chart_definition(viz_id).label
    candidates = [
        Artifact(
            id="static",
            kind="chart_static",
            module="acts",
            scope="global",
            speaker=None,
            subview=None,
            slice_id=None,
            rel_path="acts/charts/group/overlay.png",
            bytes=1,
            mtime="",
            mime="image/png",
            tags=["group_aggregate"],
            title="Wrong Title – Glen",
            meta={"viz_id": viz_id},
        ),
        Artifact(
            id="dynamic",
            kind="chart_dynamic",
            module="acts",
            scope="global",
            speaker=None,
            subview=None,
            slice_id=None,
            rel_path="acts/charts/group/overlay.html",
            bytes=1,
            mtime="",
            mime="text/html",
            tags=["group_aggregate"],
            title="Wrong Title – Rana",
            meta={"viz_id": viz_id},
        ),
    ]
    slots = build_overview_slots(
        overview_candidates=candidates,
        user_overview=[viz_id],
        missing_behavior="skip",
        max_items=None,
    )
    target = next(slot for slot in slots if slot["viz_id"] == viz_id)
    assert target["label"] == family_label
    assert "Glen" not in target["label"]


def test_build_overview_slots_multi_uses_family_label(monkeypatch):
    """Non-single cardinalities must use registry label even if artifacts have titles."""
    import transcriptx.web.services.chart_view_model_service as svc

    viz_id = "acts.acts_temporal.speaker"
    family_label = get_chart_definition(viz_id).label

    class _MultiDef:
        cardinality = "multi"
        label = family_label
        description = "multi test"
        rank_default = 520
        match = get_chart_definition(viz_id).match

        def __getattr__(self, name):
            return getattr(get_chart_definition(viz_id), name)

    monkeypatch.setitem(svc.get_chart_registry(), viz_id, _MultiDef())
    art = Artifact(
        id="art-multi",
        kind="chart_dynamic",
        module="acts",
        scope="speaker",
        speaker="Glen",
        subview=None,
        slice_id=None,
        rel_path="acts/charts/speakers/Glen/acts_temporal.html",
        bytes=1,
        mtime="",
        mime="text/html",
        tags=[],
        title="Dialogue Acts Over Time – Glen",
        meta={"viz_id": viz_id},
    )
    slots = build_overview_slots(
        overview_candidates=[art],
        user_overview=[viz_id],
        missing_behavior="skip",
        max_items=None,
    )
    target = next(slot for slot in slots if slot["viz_id"] == viz_id)
    assert target["label"] == family_label
