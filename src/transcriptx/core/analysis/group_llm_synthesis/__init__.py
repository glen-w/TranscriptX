"""Cross-session group LLM synthesis (finalize post-step).

Authoritative contract: docs/groups/group_llm_synthesis_contract.md
"""

from __future__ import annotations

from transcriptx.core.analysis.group_llm_synthesis.lock import (
    SynthesisLockTimeout,
    synthesis_lock,
)
from transcriptx.core.analysis.group_llm_synthesis.resolve import (
    ResolverCache,
    is_group_run,
    load_group_llm_summary,
    load_group_speaker_index,
    load_group_speaker_summary,
    load_text_under_generation,
)
from transcriptx.core.analysis.group_llm_synthesis.synthesize import (
    SynthesisAttemptResult,
    run_group_llm_synthesis,
)

__all__ = [
    "SynthesisLockTimeout",
    "synthesis_lock",
    "ResolverCache",
    "is_group_run",
    "load_group_llm_summary",
    "load_group_speaker_index",
    "load_group_speaker_summary",
    "load_text_under_generation",
    "SynthesisAttemptResult",
    "run_group_llm_synthesis",
]
