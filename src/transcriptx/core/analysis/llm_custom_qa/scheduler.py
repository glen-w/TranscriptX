"""Deterministic LLM call scheduler for llm_custom_qa v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from transcriptx.core.analysis.llm_custom_qa.plan import (
    RoutedCustomQAPlan,
    UnroutedCustomQAPlan,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import SCHEDULER_VERSION

CallKind = Literal["router", "global_answer", "speaker_answer", "repair"]


@dataclass(frozen=True)
class ScheduledCall:
    kind: CallKind
    logical_index: int
    question_ids: tuple[str, ...]
    speaker_key: str | None = None
    is_repair: bool = False


@dataclass(frozen=True)
class CallSchedule:
    calls: tuple[ScheduledCall, ...]
    max_logical_calls: int
    scheduler_version: str = SCHEDULER_VERSION


@dataclass
class CallAccounting:
    logical_calls: int = 0
    http_attempts: int = 0

    def record_logical(self) -> None:
        self.logical_calls += 1

    def record_http_attempt(self) -> None:
        self.http_attempts += 1

    def remaining(self, max_calls: int) -> int:
        return max(0, max_calls - self.logical_calls)


def build_call_schedule(
    unrouted: UnroutedCustomQAPlan,
    *,
    max_questions_per_batch: int = 8,
) -> CallSchedule:
    """
    Pure schedule builder.

    Priority: router → reserved global batch(es) → speaker batches → repairs are
    NOT reserved here; repairs only consume remainder at execution time.
    """
    calls: list[ScheduledCall] = []
    idx = 0
    if unrouted.routing_enabled and unrouted.questions:
        calls.append(
            ScheduledCall(
                kind="router",
                logical_index=idx,
                question_ids=tuple(q.question_id for q in unrouted.questions),
            )
        )
        idx += 1

    global_qids = tuple(
        q.question_id for q in unrouted.questions if q.scopes.global_scope
    )
    for i in range(0, len(global_qids), max_questions_per_batch):
        chunk = global_qids[i : i + max_questions_per_batch]
        calls.append(
            ScheduledCall(
                kind="global_answer",
                logical_index=idx,
                question_ids=chunk,
            )
        )
        idx += 1

    per_speaker_qids = tuple(
        q.question_id for q in unrouted.questions if q.scopes.per_speaker
    )
    if per_speaker_qids:
        for speaker_key in unrouted.speaker_keys:
            for i in range(0, len(per_speaker_qids), max_questions_per_batch):
                chunk = per_speaker_qids[i : i + max_questions_per_batch]
                calls.append(
                    ScheduledCall(
                        kind="speaker_answer",
                        logical_index=idx,
                        question_ids=chunk,
                        speaker_key=speaker_key,
                    )
                )
                idx += 1

    return CallSchedule(
        calls=tuple(calls),
        max_logical_calls=unrouted.max_llm_calls_per_run,
    )


def primary_calls_within_budget(schedule: CallSchedule) -> tuple[ScheduledCall, ...]:
    """Truncate primary schedule to max_logical_calls (repairs use remainder)."""
    return tuple(schedule.calls[: schedule.max_logical_calls])


def repair_budget_remaining(schedule: CallSchedule, accounting: CallAccounting) -> int:
    return accounting.remaining(schedule.max_logical_calls)
