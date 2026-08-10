"""Semantic identity and source helpers for Corrections Studio candidates."""

from __future__ import annotations

from hashlib import sha1
from typing import Iterable, List, Optional

from transcriptx.services.corrections_studio.schema import CandidateSource


def compute_semantic_identity_key(
    wrong_text: str,
    right_text: str,
    *,
    condition_sig: str = "",
) -> str:
    """Kind-agnostic identity for review migration across regenerations."""
    signature = f"{wrong_text.casefold()}|{right_text.casefold()}|{condition_sig}"
    return sha1(signature.encode("utf-8")).hexdigest()


_KIND_TO_SOURCE = {
    "memory_hit": CandidateSource.detector_memory,
    "acronym": CandidateSource.detector_acronym,
    "consistency": CandidateSource.detector_consistency,
    "fuzzy": CandidateSource.detector_fuzzy,
    "ner_variant": CandidateSource.llm_discovery,
    "manual": CandidateSource.viewer_manual,
}


def sources_from_kind(kind: str) -> List[CandidateSource]:
    src = _KIND_TO_SOURCE.get(str(kind))
    if src is None:
        return []
    return [src]


def compute_manual_semantic_identity_key(wrong_text: str, right_text: str) -> str:
    """Identity for viewer_manual candidates (includes manual marker)."""
    return compute_semantic_identity_key(
        wrong_text, right_text, condition_sig="viewer_manual"
    )


def merge_sources(
    *groups: Iterable[CandidateSource],
) -> List[CandidateSource]:
    seen = set()
    out: List[CandidateSource] = []
    for group in groups:
        for s in group:
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def condition_sig_from_rule_id(
    rule_id: Optional[str],
    rules_by_id: Optional[dict] = None,
) -> str:
    if not rule_id or not rules_by_id:
        return ""
    rule = rules_by_id.get(rule_id)
    if rule is None:
        return ""
    cond = getattr(rule, "conditions", None)
    if cond is None:
        return ""
    return repr(
        (
            getattr(cond, "speaker", None),
            getattr(cond, "min_token_len", None),
            tuple(sorted(getattr(cond, "context_any", None) or [])),
            getattr(cond, "case_sensitive", False),
            getattr(cond, "word_boundary", True),
        )
    )
