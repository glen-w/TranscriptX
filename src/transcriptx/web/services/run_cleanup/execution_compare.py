"""Compare planned vs rediscovered execution sets with lock-skip masks."""

from __future__ import annotations

from typing import Iterable

from transcriptx.web.services.run_cleanup.models import (
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    CleanupTargetResult,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup.plan_builder import ExecutionSet


def _target_key(t: CleanupTarget) -> tuple[str, str, str]:
    ident = t.identity()
    return (ident.subject_type.value, ident.subject_id, ident.run_id)


def _core_identity(t: CleanupTarget) -> tuple:
    """Identity excluding content fingerprint (lock-skip maskable)."""
    snap = t.snapshot()
    ident = snap.identity
    return (
        ident.subject_type.value,
        ident.subject_id,
        ident.run_id,
        ident.canonical_path,
        int(snap.filesystem_dev),
        int(snap.filesystem_ino),
        ident.root_relative_path,
    )


def _full_identity(t: CleanupTarget) -> tuple:
    return (*_core_identity(t), t.snapshot().tree_fingerprint)


def _root_tuple(r) -> tuple:
    return (
        r.kind.value,
        r.configured_path,
        r.canonical_path,
        r.dev,
        r.ino,
        r.is_symlink,
        getattr(r, "exists", True),
    )


def _exclusion_tuple(e) -> tuple:
    root_kind = e.root_kind.value if getattr(e, "root_kind", None) is not None else None
    return (e.path_relative, e.classification.value, e.reason, root_kind)


def compare_with_lock_skip_masks(
    *,
    planned: CleanupPlan,
    rediscovered: ExecutionSet,
    lock_results: Iterable[CleanupTargetResult],
) -> tuple[bool, str]:
    """Return (ok, reason). False means STALE_PLAN (content/eligibility change).

    DELETE_ALL LOCKED_SKIP may mask only the content fingerprint of that exact
    planned target (same path/dev/ino/subject/run must still be present).

    DELETE_OLD SUBJECT_LOCKED_SKIP may mask descendant fingerprints within that
    subject only; membership and core identities must still match.
    """
    if planned.mode is not rediscovered.mode:
        return False, "mode mismatch under lock"
    if planned.policy_version != rediscovered.policy_version:
        return False, "policy_version mismatch under lock"
    if planned.classifier_version != rediscovered.classifier_version:
        return False, "classifier_version mismatch under lock"
    if planned.newest_run_policy_version != rediscovered.newest_run_policy_version:
        return False, "newest_run_policy_version mismatch under lock"
    if list(map(_root_tuple, planned.roots)) != list(
        map(_root_tuple, rediscovered.roots)
    ):
        return False, "root identity mismatch under lock"
    if sorted(map(_exclusion_tuple, planned.exclusions)) != sorted(
        map(_exclusion_tuple, rediscovered.exclusions)
    ):
        return False, "completeness exclusions changed under lock"

    locked_skip_keys = {
        (r.subject_type.value, r.subject_id, r.run_id)
        for r in lock_results
        if r.status is TargetStatus.LOCKED_SKIP
    }
    subject_skip_keys = {
        (r.subject_type.value, r.subject_id)
        for r in lock_results
        if r.status is TargetStatus.SUBJECT_LOCKED_SKIP
    }

    def fingerprint_masked(t: CleanupTarget) -> bool:
        key = _target_key(t)
        if planned.mode is CleanupMode.DELETE_ALL and key in locked_skip_keys:
            return True
        if (
            planned.mode is CleanupMode.DELETE_OLD
            and (
                t.subject_type.value,
                t.subject_id,
            )
            in subject_skip_keys
        ):
            return True
        return False

    def compare_sets(
        planned_targets: tuple[CleanupTarget, ...],
        rediscovered_targets: tuple[CleanupTarget, ...],
        label: str,
    ) -> tuple[bool, str]:
        planned_map = {_target_key(t): t for t in planned_targets}
        redis_map = {_target_key(t): t for t in rediscovered_targets}
        if set(planned_map) != set(redis_map):
            return False, f"{label} membership changed under lock"
        for key, pt in planned_map.items():
            rt = redis_map[key]
            if fingerprint_masked(pt):
                if _core_identity(pt) != _core_identity(rt):
                    return False, (
                        f"{label} core identity changed for lock-skipped "
                        f"target {key}"
                    )
            elif _full_identity(pt) != _full_identity(rt):
                return False, f"{label} identity/fingerprint mismatch for {key}"
        return True, ""

    ok, reason = compare_sets(planned.candidates, rediscovered.candidates, "candidates")
    if not ok:
        return False, reason
    ok, reason = compare_sets(planned.retained, rediscovered.retained, "retained")
    if not ok:
        return False, reason

    # Eligible must match candidates∪retained for DELETE_OLD / all candidates for DELETE_ALL
    planned_eligible_keys = {_target_key(t) for t in planned.candidates} | {
        _target_key(t) for t in planned.retained
    }
    redis_eligible_keys = {_target_key(t) for t in rediscovered.eligible}
    if planned_eligible_keys != redis_eligible_keys:
        # Rediscovered eligible is the full discovery set; compare to union
        if redis_eligible_keys != {_target_key(t) for t in rediscovered.candidates} | {
            _target_key(t) for t in rediscovered.retained
        }:
            return False, "eligible partition inconsistent under lock"
        if planned_eligible_keys != redis_eligible_keys:
            return False, "eligible set changed under lock"

    return True, ""
