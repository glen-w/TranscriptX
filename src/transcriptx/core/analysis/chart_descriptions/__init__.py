"""Chart descriptions finalize-phase package."""

from __future__ import annotations

from transcriptx.core.analysis.chart_descriptions.coordinator import (
    FinalizationResult,
    run_finalization_coordinator,
)
from transcriptx.core.analysis.chart_descriptions.resolve import (
    invalidate_resolver_cache,
    resolve_chart_llm_description_by_key,
)
from transcriptx.core.analysis.chart_descriptions.schemas import MODULE_ID

__all__ = [
    "MODULE_ID",
    "FinalizationResult",
    "run_finalization_coordinator",
    "resolve_chart_llm_description_by_key",
    "invalidate_resolver_cache",
]
