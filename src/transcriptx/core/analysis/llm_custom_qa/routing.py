"""Dormant router: returns RoutedCustomQAPlan (requires v2 activation)."""

from __future__ import annotations

from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.evidence_catalog import router_catalog_entries
from transcriptx.core.analysis.llm_custom_qa.plan import (
    QuestionRoute,
    RoutedCustomQAPlan,
    UnroutedCustomQAPlan,
    assert_v2_execution_allowed,
    build_fallback_routes,
    make_routed_plan,
)


def route_questions(
    unrouted: UnroutedCustomQAPlan,
    *,
    router_client: Any = None,
) -> RoutedCustomQAPlan:
    """Route or fall back. Production analyze must not call until v2_live."""
    assert_v2_execution_allowed()
    if not unrouted.routing_enabled or router_client is None:
        return make_routed_plan(unrouted, build_fallback_routes(unrouted))

    catalog = router_catalog_entries(dict(unrouted.snapshots))
    try:
        raw = router_client.route(
            questions=[
                {"question_id": q.question_id, "text": q.text}
                for q in unrouted.questions
            ],
            catalog=catalog,
            max_packs=unrouted.max_packs_per_question,
            include_transcript=unrouted.include_transcript,
        )
        routes = _parse_router_payload(unrouted, raw)
        return make_routed_plan(unrouted, routes)
    except Exception:
        return make_routed_plan(unrouted, build_fallback_routes(unrouted))


def _parse_router_payload(
    unrouted: UnroutedCustomQAPlan, raw: Any
) -> tuple[QuestionRoute, ...]:
    if not isinstance(raw, dict):
        raise ValueError("router payload must be object")
    rows = raw.get("routes")
    if not isinstance(rows, list):
        raise ValueError("routes must be a list")
    by_qid = {q.question_id: q for q in unrouted.questions}
    available = {
        pid
        for pid, snap in unrouted.snapshots.items()
        if snap.state == "available" and pid in unrouted.expanded_pack_ids
    }
    parsed: list[QuestionRoute] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        qid = str(row.get("question_id") or "")
        if qid not in by_qid or qid in seen:
            continue
        packs = [
            str(p)
            for p in (row.get("pack_ids") or [])
            if str(p) in available
        ][: unrouted.max_packs_per_question]
        use_tx = bool(row.get("use_transcript", True)) and unrouted.include_transcript
        parsed.append(
            QuestionRoute(
                question_id=qid,
                pack_ids=tuple(packs),
                use_transcript=use_tx,
                source="router",
            )
        )
        seen.add(qid)
    # Fill missing with fallback for those questions
    fallback = {r.question_id: r for r in build_fallback_routes(unrouted)}
    for q in unrouted.questions:
        if q.question_id not in seen:
            parsed.append(fallback[q.question_id])
    return tuple(parsed)
