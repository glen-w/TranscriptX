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

    monkeypatch.setattr(svc, "get_chart_definition", lambda viz_id: _Blank())
    art = _artifact(viz_id="emotion.radar.global", module="emotion", scope="global")
    assert resolve_chart_description(art) is None


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
