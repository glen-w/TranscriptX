"""
Warning schema and helpers for group aggregation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AggregationWarning(TypedDict, total=False):
    severity: str
    code: str
    message: str
    aggregation_key: str
    missing_deps: List[str]
    transcripts_affected: List[str]
    details: Dict[str, Any]


def build_warning(
    *,
    code: str,
    message: str,
    aggregation_key: str,
    severity: str = "warning",
    missing_deps: Optional[List[str]] = None,
    transcripts_affected: Optional[List[str]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AggregationWarning:
    warning: AggregationWarning = {
        "severity": severity,
        "code": code,
        "message": message,
        "aggregation_key": aggregation_key,
    }
    if missing_deps:
        warning["missing_deps"] = list(missing_deps)
    if transcripts_affected:
        warning["transcripts_affected"] = list(transcripts_affected)
    if details:
        warning["details"] = details
    return warning
