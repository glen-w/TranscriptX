"""Shared discovery/partition/signature builder for preview and locked rediscovery."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from transcriptx.core.utils.run_identity import newest_run_sort_key_desc
from transcriptx.web.services.run_cleanup.classifier import RunRootClassifier
from transcriptx.web.services.run_cleanup.identity import (
    CLASSIFIER_VERSION,
    NEWEST_RUN_POLICY_VERSION,
    digest_payload,
)
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    CleanupExclusion,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    RootIdentity,
    SubjectType,
    compute_plan_id,
)


@dataclass(frozen=True)
class ExecutionSet:
    mode: CleanupMode
    roots: tuple[RootIdentity, ...]
    eligible: tuple[CleanupTarget, ...]
    candidates: tuple[CleanupTarget, ...]
    retained: tuple[CleanupTarget, ...]
    exclusions: tuple[CleanupExclusion, ...]
    policy_version: int
    classifier_version: int
    newest_run_policy_version: int
    can_execute: bool
    blocking_errors: tuple[str, ...]
    warnings: tuple[str, ...]


def partition_for_mode(
    mode: CleanupMode, eligible: list[CleanupTarget]
) -> tuple[list[CleanupTarget], list[CleanupTarget]]:
    """Partition eligible runs into candidates and retained (DELETE_OLD)."""
    if mode is CleanupMode.DELETE_ALL:
        ordered = sorted(
            eligible,
            key=lambda t: (
                t.subject_type.value,
                t.subject_id,
                t.run_id,
                t.root_relative_path,
            ),
        )
        return ordered, []

    by_subject: dict[tuple[SubjectType, str], list[CleanupTarget]] = defaultdict(list)
    for target in eligible:
        by_subject[(target.subject_type, target.subject_id)].append(target)

    candidates: list[CleanupTarget] = []
    retained: list[CleanupTarget] = []
    for _key, runs in sorted(
        by_subject.items(), key=lambda kv: (kv[0][0].value, kv[0][1])
    ):
        ordered = sorted(
            runs,
            key=lambda t: newest_run_sort_key_desc(
                mtime_ns=t.mtime_ns,
                run_id=t.run_id,
                path=t.canonical_path,
            ),
            reverse=True,
        )
        if not ordered:
            continue
        retained.append(ordered[0])
        candidates.extend(ordered[1:])

    candidates.sort(
        key=lambda t: (
            t.subject_type.value,
            t.subject_id,
            t.run_id,
            t.root_relative_path,
        )
    )
    retained.sort(
        key=lambda t: (
            t.subject_type.value,
            t.subject_id,
            t.run_id,
            t.root_relative_path,
        )
    )
    return candidates, retained


def build_execution_set(
    mode: CleanupMode,
    roots: list[RootIdentity],
    blocking: list[str],
    outputs_dir: Path,
    group_outputs_dir: Path,
    *,
    warnings: list[str] | None = None,
) -> ExecutionSet:
    warnings = list(warnings or [])
    eligible: list[CleanupTarget] = []
    exclusions: list[CleanupExclusion] = []
    candidates: list[CleanupTarget] = []
    retained: list[CleanupTarget] = []

    if not blocking:
        eligible, exclusions = RunRootClassifier.discover(
            outputs_dir, group_outputs_dir, roots
        )
        candidates, retained = partition_for_mode(mode, eligible)
    else:
        warnings.append("Output roots failed validation; discovery skipped.")

    if blocking:
        can_execute = False
    else:
        # Empty DELETE_OLD candidates is a safe NOOP, not a blocking error.
        can_execute = True

    return ExecutionSet(
        mode=mode,
        roots=tuple(roots),
        eligible=tuple(
            sorted(
                eligible,
                key=lambda t: (
                    t.subject_type.value,
                    t.subject_id,
                    t.run_id,
                    t.canonical_path,
                ),
            )
        ),
        candidates=tuple(candidates),
        retained=tuple(retained),
        exclusions=tuple(
            sorted(
                exclusions,
                key=lambda e: (e.path_relative, e.classification.value, e.reason),
            )
        ),
        policy_version=CLEANUP_POLICY_VERSION,
        classifier_version=CLASSIFIER_VERSION,
        newest_run_policy_version=NEWEST_RUN_POLICY_VERSION,
        can_execute=can_execute,
        blocking_errors=tuple(blocking),
        warnings=tuple(warnings),
    )


def _target_sig(t: CleanupTarget) -> dict:
    return {
        "subject_type": t.subject_type.value,
        "subject_id": t.subject_id,
        "run_id": t.run_id,
        "canonical_path": t.canonical_path,
        "filesystem_dev": t.filesystem_dev,
        "filesystem_ino": t.filesystem_ino,
        "tree_fingerprint": t.tree_fingerprint,
    }


def execution_set_signature(es: ExecutionSet) -> str:
    """Deterministic signature for locked rediscovery comparison."""
    payload = {
        "mode": es.mode.value,
        "policy_version": es.policy_version,
        "classifier_version": es.classifier_version,
        "newest_run_policy_version": es.newest_run_policy_version,
        "roots": [
            {
                "kind": r.kind.value,
                "configured_path": r.configured_path,
                "canonical_path": r.canonical_path,
                "dev": r.dev,
                "ino": r.ino,
                "is_symlink": r.is_symlink,
                "exists": getattr(r, "exists", True),
            }
            for r in es.roots
        ],
        "eligible": [_target_sig(t) for t in es.eligible],
        "candidates": [_target_sig(t) for t in es.candidates],
        "retained": [_target_sig(t) for t in es.retained],
        "exclusions": [
            {
                "path_relative": e.path_relative,
                "classification": e.classification.value,
                "reason": e.reason,
            }
            for e in es.exclusions
        ],
    }
    return digest_payload(payload)


def execution_set_to_plan(es: ExecutionSet) -> CleanupPlan:
    plan_id = compute_plan_id(
        mode=es.mode,
        policy_version=es.policy_version,
        roots=es.roots,
        candidates=es.candidates,
        retained=es.retained,
        exclusions=es.exclusions,
    )
    return CleanupPlan(
        plan_id=plan_id,
        mode=es.mode,
        policy_version=es.policy_version,
        created_at_iso=datetime.now(timezone.utc).isoformat(),
        roots=es.roots,
        candidates=es.candidates,
        retained=es.retained,
        exclusions=es.exclusions,
        warnings=es.warnings,
        blocking_errors=es.blocking_errors,
        can_execute=es.can_execute,
    )
