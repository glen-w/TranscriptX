"""
Canonical run-outcome read model for cross-consumer status projection.

This module defines one vocabulary for consumer-facing module status and one
projection path from run_results + manifest-backed context.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from transcriptx.core.pipeline.module_registry import canonical_module_id

OutcomeStatus = Literal[
    "requested",
    "enabled",
    "blocked",
    "skipped",
    "failed",
    "succeeded",
]
GroupStatus = Literal["blocked", "skipped", "failed", "partial", "succeeded"]


@dataclass(frozen=True)
class CanonicalOutcomeRow:
    """Canonical consumer-facing status row for one module in one run."""

    module_id: str
    status: OutcomeStatus
    reason: Optional[str] = None
    used_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "module_id": self.module_id,
            "status": self.status,
        }
        if self.reason:
            out["reason"] = self.reason
        if self.used_cache:
            out["used_cache"] = True
        return out


@dataclass(frozen=True)
class MemberOutcomeDetail:
    """Canonical member-level outcome bundle for one member inside a group run."""

    order_index: int
    transcript_path: str
    transcript_key: str
    run_id: str
    output_dir: str
    outcomes: List[CanonicalOutcomeRow]
    outcome_unavailable: bool = False


@dataclass(frozen=True)
class GroupRunOutcome:
    """Canonical group-level truth projection for one group run directory."""

    status: GroupStatus
    group_outcomes: List[CanonicalOutcomeRow]
    members: List[MemberOutcomeDetail]
    group_phase_metadata: List[Dict[str, Any]]
    missing_member_outcomes: int = 0
    any_member_usable: bool = False
    group_phase_terminal_failure: bool = False
    all_members_blocked: bool = False
    all_members_skipped: bool = False


def _extract_skipped_map(modules_skipped: List[Any]) -> Dict[str, Dict[str, Any]]:
    skipped_map: Dict[str, Dict[str, Any]] = {}
    for entry in modules_skipped:
        if not isinstance(entry, dict) or not entry.get("module"):
            continue
        mid = canonical_module_id(str(entry["module"]))
        skipped_map[mid] = {
            "execution_status": str(entry.get("execution_status", "skipped")),
            "reason": str(entry.get("reason", "Skipped")),
        }
    return skipped_map


def project_canonical_outcomes(
    run_results: Dict[str, Any],
) -> List[CanonicalOutcomeRow]:
    """
    Project run_results payload to canonical consumer-facing outcome rows.

    Rules:
    - Start from modules_enabled (enabled set).
    - Use modules_run for succeeded.
    - Use modules_skipped entries for skipped/blocked.
    - Use modules_failed for failed.
    - Include requested rows for modules present in run lists but absent from enabled.
    """
    modules_enabled = [str(x) for x in (run_results.get("modules_enabled") or []) if x]
    modules_run = [str(x) for x in (run_results.get("modules_run") or []) if x]
    modules_failed = [str(x) for x in (run_results.get("modules_failed") or []) if x]
    modules_skipped = run_results.get("modules_skipped") or []
    outcomes_payload = run_results.get("module_outcomes") or []

    ran_ids = {canonical_module_id(m) for m in modules_run}
    failed_ids = {canonical_module_id(m) for m in modules_failed}
    skipped_map = _extract_skipped_map(modules_skipped)

    # Cache-hit hints come from canonical module_outcomes rows.
    cache_hit_ids = set()
    for row in outcomes_payload:
        if isinstance(row, dict) and row.get("used_cache") and row.get("module_id"):
            cache_hit_ids.add(canonical_module_id(str(row["module_id"])))

    enabled_ids = {canonical_module_id(m) for m in modules_enabled}
    all_ids = set(enabled_ids) | ran_ids | failed_ids | set(skipped_map.keys())

    rows: List[CanonicalOutcomeRow] = []
    for mid in sorted(all_ids):
        if mid in failed_ids:
            rows.append(CanonicalOutcomeRow(module_id=mid, status="failed"))
            continue
        if mid in skipped_map:
            sk = skipped_map[mid]
            sk_status = sk.get("execution_status")
            if sk_status == "blocked":
                rows.append(
                    CanonicalOutcomeRow(
                        module_id=mid,
                        status="blocked",
                        reason=sk.get("reason"),
                    )
                )
            else:
                rows.append(
                    CanonicalOutcomeRow(
                        module_id=mid,
                        status="skipped",
                        reason=sk.get("reason"),
                    )
                )
            continue
        if mid in ran_ids:
            rows.append(
                CanonicalOutcomeRow(
                    module_id=mid,
                    status="succeeded",
                    used_cache=mid in cache_hit_ids,
                    reason="cache_hit" if mid in cache_hit_ids else None,
                )
            )
            continue
        if mid in enabled_ids:
            rows.append(CanonicalOutcomeRow(module_id=mid, status="enabled"))
        else:
            rows.append(CanonicalOutcomeRow(module_id=mid, status="requested"))
    return rows


def status_for_module(
    module_id: str,
    run_results: Dict[str, Any],
    default_if_missing: OutcomeStatus = "requested",
) -> OutcomeStatus:
    """Return canonical consumer-facing status for one module id."""
    mid = canonical_module_id(module_id)
    for row in project_canonical_outcomes(run_results):
        if row.module_id == mid:
            return row.status
    return default_if_missing


def _load_group_member_entries(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / "group_member_runs.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    members = raw.get("members")
    if not isinstance(members, list):
        return []
    return [m for m in members if isinstance(m, dict)]


def _member_terminal_status(
    outcomes: List[CanonicalOutcomeRow],
) -> Optional[OutcomeStatus]:
    if not outcomes:
        return None
    statuses = {o.status for o in outcomes}
    if "failed" in statuses:
        return "failed"
    if "succeeded" in statuses:
        return "succeeded"
    if "blocked" in statuses and statuses.issubset({"blocked", "enabled", "requested"}):
        return "blocked"
    if "skipped" in statuses and statuses.issubset({"skipped", "enabled", "requested"}):
        return "skipped"
    if statuses.issubset({"blocked", "skipped", "enabled", "requested"}):
        return "blocked" if "blocked" in statuses else "skipped"
    return "enabled" if "enabled" in statuses else "requested"


def _derive_group_status(
    member_statuses: List[Optional[OutcomeStatus]],
    phase_rows: List[Dict[str, Any]],
) -> GroupRunOutcome:
    known = [s for s in member_statuses if s is not None]
    has_members = bool(member_statuses)
    all_members_blocked = bool(known) and all(s == "blocked" for s in known)
    all_members_skipped = bool(known) and all(s == "skipped" for s in known)
    any_member_usable = any(s == "succeeded" for s in known)
    has_mixed_non_success = any(s in {"failed", "blocked", "skipped"} for s in known)
    # Treat any explicit phase error/failure signal as terminal.
    group_phase_terminal_failure = any(
        isinstance(w, dict)
        and str(w.get("code") or "").upper()
        in {"GROUP_FINALIZATION_FAILED", "TERMINAL_FAILURE"}
        for w in phase_rows
    )
    has_phase_nonterminal_issues = bool(phase_rows) and not group_phase_terminal_failure

    if group_phase_terminal_failure:
        status: GroupStatus = "failed"
    elif has_members and all_members_blocked and not any_member_usable:
        status = "blocked"
    elif has_members and all_members_skipped and not any_member_usable:
        status = "skipped"
    elif (
        any_member_usable
        and not has_mixed_non_success
        and not has_phase_nonterminal_issues
    ):
        status = "succeeded"
    elif any_member_usable:
        status = "partial"
    else:
        status = "failed"

    return GroupRunOutcome(
        status=status,
        group_outcomes=[],
        members=[],
        group_phase_metadata=phase_rows,
        missing_member_outcomes=sum(1 for s in member_statuses if s is None),
        any_member_usable=any_member_usable,
        group_phase_terminal_failure=group_phase_terminal_failure,
        all_members_blocked=all_members_blocked,
        all_members_skipped=all_members_skipped,
    )


def _derive_group_status_from_rollup(
    group_rows: List[CanonicalOutcomeRow],
    phase_rows: List[Dict[str, Any]],
) -> GroupRunOutcome:
    statuses = {row.status for row in group_rows}
    group_phase_terminal_failure = any(
        isinstance(w, dict)
        and str(w.get("code") or "").upper()
        in {"GROUP_FINALIZATION_FAILED", "TERMINAL_FAILURE"}
        for w in phase_rows
    )
    has_phase_nonterminal_issues = bool(phase_rows) and not group_phase_terminal_failure
    if group_phase_terminal_failure:
        status: GroupStatus = "failed"
    elif statuses == {"blocked"}:
        status = "blocked"
    elif statuses == {"skipped"}:
        status = "skipped"
    elif statuses and statuses.issubset({"succeeded"}):
        status = "partial" if has_phase_nonterminal_issues else "succeeded"
    elif "succeeded" in statuses:
        status = "partial"
    elif statuses:
        status = "failed"
    else:
        status = "failed"
    return GroupRunOutcome(
        status=status,
        group_outcomes=group_rows,
        members=[],
        group_phase_metadata=phase_rows,
        missing_member_outcomes=0,
        any_member_usable="succeeded" in statuses,
        group_phase_terminal_failure=group_phase_terminal_failure,
        all_members_blocked=statuses == {"blocked"},
        all_members_skipped=statuses == {"skipped"},
    )


def project_group_outcomes(run_dir: str | Path) -> GroupRunOutcome:
    """
    Project canonical group truth from a group run directory.

    Relevant members are entries in group_member_runs.json where execution was
    attempted. Members with missing member run_results remain relevant but are
    marked outcome_unavailable.
    """
    from transcriptx.core.pipeline.manifest_loader import (
        load_group_phase_metadata,
        load_run_results,
    )

    run_dir = Path(run_dir)
    group_rows: List[CanonicalOutcomeRow] = []
    rr_path = run_dir / "run_results.json"
    if rr_path.exists():
        try:
            group_rows = project_canonical_outcomes(load_run_results(rr_path))
        except Exception:
            group_rows = []
    phase_rows = load_group_phase_metadata(run_dir)
    member_entries = _load_group_member_entries(run_dir)

    members: List[MemberOutcomeDetail] = []
    member_statuses: List[Optional[OutcomeStatus]] = []
    for entry in member_entries:
        out_dir_raw = entry.get("output_dir")
        out_dir = Path(str(out_dir_raw)).resolve() if out_dir_raw else None
        outcomes: List[CanonicalOutcomeRow] = []
        unavailable = False
        if out_dir is not None:
            rr_path = out_dir / "run_results.json"
            if rr_path.exists():
                try:
                    outcomes = project_canonical_outcomes(load_run_results(rr_path))
                except Exception:
                    unavailable = True
            else:
                unavailable = True
        else:
            unavailable = True
        members.append(
            MemberOutcomeDetail(
                order_index=int(entry.get("order_index", 0)),
                transcript_path=str(entry.get("transcript_path", "")),
                transcript_key=str(entry.get("transcript_key", "")),
                run_id=str(entry.get("run_id", "")),
                output_dir=str(entry.get("output_dir", "")),
                outcomes=outcomes,
                outcome_unavailable=unavailable,
            )
        )
        member_statuses.append(
            None if unavailable else _member_terminal_status(outcomes)
        )

    if member_statuses:
        base = _derive_group_status(member_statuses, phase_rows)
    else:
        base = _derive_group_status_from_rollup(group_rows, phase_rows)
    return GroupRunOutcome(
        status=base.status,
        group_outcomes=group_rows,
        members=members,
        group_phase_metadata=phase_rows,
        missing_member_outcomes=base.missing_member_outcomes,
        any_member_usable=base.any_member_usable,
        group_phase_terminal_failure=base.group_phase_terminal_failure,
        all_members_blocked=base.all_members_blocked,
        all_members_skipped=base.all_members_skipped,
    )
