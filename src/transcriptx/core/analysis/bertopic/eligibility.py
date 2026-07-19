"""Pure eligibility / resource limits for BERTopic (transcript + group).

Corpus preparation stays in analysis / aggregation; this module only decides
whether a prepared document list may attempt a fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

# Minimum documents after preprocessing (shared by transcript and group paths).
MIN_DOCUMENTS = 3

# Soft resource limits — measured/diagnostic, not killable timeouts.
DEFAULT_MAX_DOCUMENTS = 50_000
DEFAULT_MAX_TOTAL_CHARS = 5_000_000


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reason: Optional[str] = None
    documents_count: int = 0
    total_chars: int = 0


def count_document_chars(documents: Sequence[str]) -> int:
    return sum(len(doc) for doc in documents)


def evaluate_bertopic_eligibility(
    documents: Sequence[str],
    *,
    min_documents: int = MIN_DOCUMENTS,
    max_documents: int = DEFAULT_MAX_DOCUMENTS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> EligibilityDecision:
    """
    Decide whether a BERTopic fit may be attempted.

    Duplicate texts are retained as separate documents (no pre-fit dedup);
    counts are over the document list, not unique strings.
    """
    n = len(documents)
    total_chars = count_document_chars(documents)
    if n < min_documents:
        return EligibilityDecision(
            eligible=False,
            reason="insufficient_documents",
            documents_count=n,
            total_chars=total_chars,
        )
    if n > max_documents:
        return EligibilityDecision(
            eligible=False,
            reason="max_documents_exceeded",
            documents_count=n,
            total_chars=total_chars,
        )
    if total_chars > max_total_chars:
        return EligibilityDecision(
            eligible=False,
            reason="max_total_chars_exceeded",
            documents_count=n,
            total_chars=total_chars,
        )
    return EligibilityDecision(
        eligible=True,
        reason=None,
        documents_count=n,
        total_chars=total_chars,
    )
