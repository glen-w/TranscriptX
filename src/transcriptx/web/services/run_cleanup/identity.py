"""Shared identity types and path canonicalisation for run cleanup."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from transcriptx.core.utils.path_canonical import canonicalise_path
from transcriptx.web.services.run_cleanup.models import SubjectType

LOCK_NAMESPACE_VERSION = 1
CLASSIFIER_VERSION = 1
NEWEST_RUN_POLICY_VERSION = 1


def stable_json(value: Any) -> str:
    """Deterministic JSON for plan IDs, signatures, and journal fixtures."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest_payload(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TargetKey:
    root_kind: SubjectType
    subject_type: SubjectType
    subject_id: str
    run_id: str
    canonical_source_path: str

    def as_dict(self) -> dict[str, str]:
        return {
            "root_kind": self.root_kind.value,
            "subject_type": self.subject_type.value,
            "subject_id": self.subject_id,
            "run_id": self.run_id,
            "canonical_source_path": self.canonical_source_path,
        }

    def identity_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            self.root_kind.value,
            self.subject_type.value,
            self.subject_id,
            self.run_id,
            self.canonical_source_path,
        )


@dataclass(frozen=True)
class TargetIdentity:
    key: TargetKey
    source_dev: int
    source_ino: int
    content_tree_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.key.as_dict(),
            "source_dev": self.source_dev,
            "source_ino": self.source_ino,
            "content_tree_fingerprint": self.content_tree_fingerprint,
        }

    def identity_tuple(self) -> tuple:
        return (
            *self.key.identity_tuple(),
            self.source_dev,
            self.source_ino,
            self.content_tree_fingerprint,
        )


@dataclass(frozen=True)
class SubjectKey:
    root_kind: SubjectType
    subject_type: SubjectType
    subject_id: str
    canonical_subject_path: str

    def as_dict(self) -> dict[str, str]:
        return {
            "root_kind": self.root_kind.value,
            "subject_type": self.subject_type.value,
            "subject_id": self.subject_id,
            "canonical_subject_path": self.canonical_subject_path,
        }

    def identity_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.root_kind.value,
            self.subject_type.value,
            self.subject_id,
            self.canonical_subject_path,
        )


def ensure_descendant(child_canonical: str, root_canonical: str) -> None:
    """Raise ValueError if child is not under root (canonical strings)."""
    child = Path(child_canonical)
    root = Path(root_canonical)
    try:
        child.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"path {child_canonical!r} is not under root {root_canonical!r}"
        ) from exc


def root_relative(child_canonical: str, root_canonical: str) -> str:
    ensure_descendant(child_canonical, root_canonical)
    return Path(child_canonical).relative_to(Path(root_canonical)).as_posix()


def sorted_identity_dicts(items: Sequence[TargetIdentity]) -> list[dict[str, Any]]:
    return sorted((t.as_dict() for t in items), key=lambda d: stable_json(d))


def target_key_from_cleanup_target(
    *,
    root_kind: SubjectType,
    subject_type: SubjectType,
    subject_id: str,
    run_id: str,
    canonical_path: str,
) -> TargetKey:
    return TargetKey(
        root_kind=root_kind,
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        canonical_source_path=canonicalise_path(canonical_path),
    )
