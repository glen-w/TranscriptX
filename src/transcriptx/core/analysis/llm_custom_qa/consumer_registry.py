"""Explicit consumer registry / contract matrix for llm_custom_qa activation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConsumerRole = Literal[
    "reader",
    "ui_block",
    "exporter",
    "aggregator",
    "output_service",
    "cache",
]


@dataclass(frozen=True)
class ConsumerEntry:
    consumer_id: str
    role: ConsumerRole
    module_path: str
    requires_authoritative_loader: bool
    placement_only: bool = False
    structured_ready: bool = False
    notes: str = ""


# Maintained inventory — activation tests assert against this list.
CUSTOM_QA_CONSUMER_REGISTRY: tuple[ConsumerEntry, ...] = (
    ConsumerEntry(
        "readers.load_committed",
        "reader",
        "transcriptx.core.analysis.llm_custom_qa.readers",
        True,
        structured_ready=True,
        notes="active→marker; schema dispatch",
    ),
    ConsumerEntry(
        "insights_custom_qa_block",
        "ui_block",
        "transcriptx.web.blocks.implementations.insights_custom_qa",
        True,
        placement_only=False,
        structured_ready=True,
        notes="Actions placement until Stage 6; must skip unknown schema",
    ),
    ConsumerEntry(
        "export.summary_bodies",
        "exporter",
        "transcriptx.export.summary_bodies",
        True,
        structured_ready=True,
        notes="must use authoritative loader",
    ),
    ConsumerEntry(
        "export.resolve_summaries",
        "exporter",
        "transcriptx.export.resolve_summaries",
        True,
        structured_ready=True,
        notes="must not rediscover by suffix alone",
    ),
    ConsumerEntry(
        "aggregation.llm_custom_qa",
        "aggregator",
        "transcriptx.core.analysis.aggregation.registry",
        True,
        structured_ready=True,
        notes="disabled at registry until v2 agg enabled",
    ),
    ConsumerEntry(
        "cache.try_load",
        "cache",
        "transcriptx.core.analysis.llm_custom_qa.cache",
        True,
        structured_ready=True,
    ),
    ConsumerEntry(
        "group_ui.member_failures",
        "ui_block",
        "transcriptx.web.blocks.implementations.insights_custom_qa",
        True,
        structured_ready=True,
        notes="failures via load_group_member_failures",
    ),
)


def activation_blocking_consumers() -> tuple[ConsumerEntry, ...]:
    """Consumers that must be structured_ready before Stage 5 writer activation."""
    return tuple(
        c
        for c in CUSTOM_QA_CONSUMER_REGISTRY
        if not c.placement_only and c.requires_authoritative_loader
    )
