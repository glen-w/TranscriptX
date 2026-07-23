"""Immutable UnroutedCustomQAPlan and RoutedCustomQAPlan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

from transcriptx.core.analysis.llm_custom_qa.evidence_catalog import EvidenceSnapshot
from transcriptx.core.analysis.llm_custom_qa.question_identity import CanonicalQuestion
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    V2_CONTRACT_VERSION,
    is_v2_execution_enabled,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json

RouteSource = Literal["router", "fallback"]


@dataclass(frozen=True)
class QuestionRoute:
    question_id: str
    pack_ids: tuple[str, ...]
    use_transcript: bool
    source: RouteSource


@dataclass(frozen=True)
class UnroutedCustomQAPlan:
    """Frozen pre-routing plan — no routes field."""

    questions: tuple[CanonicalQuestion, ...]
    question_order: tuple[str, ...]
    questions_hash: str
    expanded_pack_ids: tuple[str, ...]
    snapshots: Mapping[str, EvidenceSnapshot]
    include_transcript: bool
    routing_enabled: bool
    max_packs_per_question: int
    speaker_keys: tuple[str, ...]
    speaker_display: Mapping[str, str]
    speaker_grouping_keys: Mapping[str, tuple[str, ...]]
    speaker_limit: int
    speakers_omitted_by_cap: tuple[str, ...]
    max_llm_calls_per_run: int
    max_reasoning_chars: int
    max_answer_chars: int
    catalog_version: str
    contract_version: str
    scheduler_version: str
    eligibility_policy_version: str
    transcript_global_fingerprint: str
    transcript_speaker_fingerprints: Mapping[str, str]
    model_id: str
    effort: str
    resolved_from: str


@dataclass(frozen=True)
class RoutedCustomQAPlan:
    unrouted: UnroutedCustomQAPlan
    routes: tuple[QuestionRoute, ...]
    routes_hash: str

    def route_for(self, question_id: str) -> Optional[QuestionRoute]:
        for route in self.routes:
            if route.question_id == question_id:
                return route
        return None


def assert_v2_execution_allowed() -> None:
    if not is_v2_execution_enabled():
        raise RuntimeError(
            "v2 custom QA execution is disabled (activation=v1_live); "
            "do not build plans, route, or write v2 caches"
        )


def routes_hash_for(routes: tuple[QuestionRoute, ...]) -> str:
    payload = [
        {
            "question_id": r.question_id,
            "pack_ids": list(r.pack_ids),
            "use_transcript": r.use_transcript,
            "source": r.source,
        }
        for r in sorted(routes, key=lambda x: x.question_id)
    ]
    return sha256_canonical_json(payload)


def validate_routed_plan(plan: RoutedCustomQAPlan) -> None:
    qids = {q.question_id for q in plan.unrouted.questions}
    seen: set[str] = set()
    for route in plan.routes:
        if route.question_id not in qids:
            raise ValueError(f"route references unknown question_id {route.question_id}")
        if route.question_id in seen:
            raise ValueError(f"duplicate route for {route.question_id}")
        seen.add(route.question_id)
        if len(route.pack_ids) > plan.unrouted.max_packs_per_question:
            raise ValueError("route exceeds max_packs_per_question")
        for pid in route.pack_ids:
            if pid not in plan.unrouted.expanded_pack_ids:
                raise ValueError(f"pack_id not in expanded set: {pid}")
        if route.use_transcript and not plan.unrouted.include_transcript:
            raise ValueError("use_transcript forbidden when include_transcript=false")
    if seen != qids:
        raise ValueError("routes must cover every canonical question exactly once")
    if plan.routes_hash != routes_hash_for(plan.routes):
        raise ValueError("routes_hash mismatch")


def build_fallback_routes(unrouted: UnroutedCustomQAPlan) -> tuple[QuestionRoute, ...]:
    available = tuple(
        pid
        for pid in unrouted.expanded_pack_ids
        if unrouted.snapshots.get(pid) is not None
        and unrouted.snapshots[pid].state == "available"
    )
    capped = available[: unrouted.max_packs_per_question]
    use_tx = unrouted.include_transcript
    return tuple(
        QuestionRoute(
            question_id=q.question_id,
            pack_ids=capped,
            use_transcript=use_tx,
            source="fallback",
        )
        for q in unrouted.questions
    )


def make_routed_plan(
    unrouted: UnroutedCustomQAPlan,
    routes: tuple[QuestionRoute, ...],
) -> RoutedCustomQAPlan:
    plan = RoutedCustomQAPlan(
        unrouted=unrouted,
        routes=routes,
        routes_hash=routes_hash_for(routes),
    )
    validate_routed_plan(plan)
    return plan
