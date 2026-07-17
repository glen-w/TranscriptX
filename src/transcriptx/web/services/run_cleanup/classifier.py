"""Classify positively identified analysis run directories under output roots."""

from __future__ import annotations

import os
from pathlib import Path

from transcriptx.core.utils.run_identity import (
    is_valid_group_uuid,
    is_valid_run_id,
    is_valid_transcript_slug,
)
from transcriptx.web.services.run_cleanup.fingerprint import (
    TreeFingerprintError,
    compute_tree_fingerprint,
)
from transcriptx.web.services.run_cleanup.models import (
    STAGING_DIR_NAME,
    CleanupExclusion,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    SubjectType,
)


def _samefile(a: Path, b: Path) -> bool:
    try:
        if a.exists() and b.exists():
            return os.path.samefile(a, b)
    except OSError:
        pass
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _exclusion(
    path_relative: str,
    classification: EntryClassification,
    reason: str,
    *,
    root_kind: SubjectType,
) -> CleanupExclusion:
    return CleanupExclusion(
        path_relative=path_relative,
        classification=classification,
        reason=reason,
        root_kind=root_kind,
    )


class RunRootClassifier:
    """Discover eligible run roots; fail closed on unsafe / non-canonical shapes."""

    @staticmethod
    def discover(
        outputs_dir: Path,
        group_outputs_dir: Path,
        root_identities: list[RootIdentity] | tuple[RootIdentity, ...],
    ) -> tuple[list[CleanupTarget], list[CleanupExclusion]]:
        targets: list[CleanupTarget] = []
        exclusions: list[CleanupExclusion] = []

        by_kind = {r.kind: r for r in root_identities}
        transcript_root = by_kind.get(SubjectType.transcript)
        group_root = by_kind.get(SubjectType.group)

        group_canonical: Path | None = None
        if group_root is not None and group_root.dev is not None:
            group_canonical = Path(group_root.canonical_path)

        if transcript_root is not None and transcript_root.dev is not None:
            t_targets, t_excl = RunRootClassifier._scan_transcript_root(
                Path(outputs_dir),
                transcript_root,
                nested_group_root=group_canonical,
            )
            targets.extend(t_targets)
            exclusions.extend(t_excl)

        if group_root is not None and group_root.dev is not None:
            g_targets, g_excl = RunRootClassifier._scan_group_root(
                Path(group_outputs_dir),
                group_root,
            )
            targets.extend(g_targets)
            exclusions.extend(g_excl)

        targets.sort(
            key=lambda t: (
                t.subject_type.value,
                t.subject_id,
                t.run_id,
                t.root_relative_path,
            )
        )
        exclusions.sort(key=lambda e: (e.path_relative, e.classification.value))
        return targets, exclusions

    @staticmethod
    def _scan_transcript_root(
        outputs_dir: Path,
        root_identity: RootIdentity,
        *,
        nested_group_root: Path | None,
    ) -> tuple[list[CleanupTarget], list[CleanupExclusion]]:
        targets: list[CleanupTarget] = []
        exclusions: list[CleanupExclusion] = []
        base = Path(outputs_dir)
        if not base.is_dir() or base.is_symlink():
            return targets, exclusions

        assert root_identity.dev is not None
        root_dev = int(root_identity.dev)

        try:
            with os.scandir(base) as subject_entries:
                subjects = sorted(subject_entries, key=lambda e: e.name)
        except OSError as exc:
            exclusions.append(
                _exclusion(
                    path_relative=".",
                    classification=EntryClassification.unreadable,
                    reason=f"cannot scandir transcript outputs: {exc}",
                    root_kind=SubjectType.transcript,
                )
            )
            return targets, exclusions

        for subject_entry in subjects:
            name = subject_entry.name
            rel_subject = name
            if name == STAGING_DIR_NAME:
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.staging,
                        reason="cleanup staging directory",
                        root_kind=SubjectType.transcript,
                    )
                )
                continue

            try:
                st = subject_entry.stat(follow_symlinks=False)
            except OSError as exc:
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.unreadable,
                        reason=str(exc),
                        root_kind=SubjectType.transcript,
                    )
                )
                continue

            if subject_entry.is_symlink():
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.symlink,
                        reason="subject path is a symlink",
                        root_kind=SubjectType.transcript,
                    )
                )
                continue

            if nested_group_root is not None and _samefile(
                Path(subject_entry.path), nested_group_root
            ):
                # Exact nested GROUP_OUTPUTS_DIR under OUTPUTS_DIR — skip as group tree.
                continue

            if not subject_entry.is_dir(follow_symlinks=False):
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.unknown,
                        reason="not a subject directory",
                        root_kind=SubjectType.transcript,
                    )
                )
                continue

            if not is_valid_transcript_slug(name):
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.invalid,
                        reason="invalid transcript slug",
                        root_kind=SubjectType.transcript,
                    )
                )
                continue

            if int(st.st_dev) != root_dev:
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.mount,
                        reason="subject on different device than output root",
                        root_kind=SubjectType.transcript,
                    )
                )
                continue

            t, e = RunRootClassifier._scan_runs(
                subject_dir=Path(subject_entry.path),
                subject_type=SubjectType.transcript,
                subject_id=name,
                root_relative_prefix=name,
                root_dev=root_dev,
            )
            targets.extend(t)
            exclusions.extend(e)

        return targets, exclusions

    @staticmethod
    def _scan_group_root(
        group_outputs_dir: Path,
        root_identity: RootIdentity,
    ) -> tuple[list[CleanupTarget], list[CleanupExclusion]]:
        targets: list[CleanupTarget] = []
        exclusions: list[CleanupExclusion] = []
        base = Path(group_outputs_dir)
        if not base.is_dir() or base.is_symlink():
            return targets, exclusions

        assert root_identity.dev is not None
        root_dev = int(root_identity.dev)
        # Display paths under group root use "groups/<uuid>/..." when nested naming
        # is helpful; prefer path relative to the group outputs root itself.
        try:
            with os.scandir(base) as subject_entries:
                subjects = sorted(subject_entries, key=lambda e: e.name)
        except OSError as exc:
            exclusions.append(
                _exclusion(
                    path_relative=".",
                    classification=EntryClassification.unreadable,
                    reason=f"cannot scandir group outputs: {exc}",
                    root_kind=SubjectType.group,
                )
            )
            return targets, exclusions

        for subject_entry in subjects:
            name = subject_entry.name
            rel_subject = name
            if name == STAGING_DIR_NAME:
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.staging,
                        reason="cleanup staging directory",
                        root_kind=SubjectType.group,
                    )
                )
                continue

            try:
                st = subject_entry.stat(follow_symlinks=False)
            except OSError as exc:
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.unreadable,
                        reason=str(exc),
                        root_kind=SubjectType.group,
                    )
                )
                continue

            if subject_entry.is_symlink():
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.symlink,
                        reason="subject path is a symlink",
                        root_kind=SubjectType.group,
                    )
                )
                continue

            if not subject_entry.is_dir(follow_symlinks=False):
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.unknown,
                        reason="not a subject directory",
                        root_kind=SubjectType.group,
                    )
                )
                continue

            if not is_valid_group_uuid(name):
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.invalid,
                        reason="invalid group uuid",
                        root_kind=SubjectType.group,
                    )
                )
                continue

            if int(st.st_dev) != root_dev:
                exclusions.append(
                    _exclusion(
                        path_relative=rel_subject,
                        classification=EntryClassification.mount,
                        reason="subject on different device than group output root",
                        root_kind=SubjectType.group,
                    )
                )
                continue

            t, e = RunRootClassifier._scan_runs(
                subject_dir=Path(subject_entry.path),
                subject_type=SubjectType.group,
                subject_id=name,
                root_relative_prefix=name,
                root_dev=root_dev,
            )
            targets.extend(t)
            exclusions.extend(e)

        return targets, exclusions

    @staticmethod
    def _scan_runs(
        *,
        subject_dir: Path,
        subject_type: SubjectType,
        subject_id: str,
        root_relative_prefix: str,
        root_dev: int,
    ) -> tuple[list[CleanupTarget], list[CleanupExclusion]]:
        targets: list[CleanupTarget] = []
        exclusions: list[CleanupExclusion] = []

        try:
            with os.scandir(subject_dir) as run_entries:
                runs = sorted(run_entries, key=lambda e: e.name)
        except OSError as exc:
            exclusions.append(
                _exclusion(
                    path_relative=root_relative_prefix,
                    classification=EntryClassification.unreadable,
                    reason=f"cannot scandir subject: {exc}",
                    root_kind=subject_type,
                )
            )
            return targets, exclusions

        for run_entry in runs:
            run_id = run_entry.name
            rel = f"{root_relative_prefix}/{run_id}"

            if run_id == STAGING_DIR_NAME:
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.staging,
                        reason="cleanup staging directory",
                        root_kind=subject_type,
                    )
                )
                continue

            try:
                st = run_entry.stat(follow_symlinks=False)
            except OSError as exc:
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.unreadable,
                        reason=str(exc),
                        root_kind=subject_type,
                    )
                )
                continue

            if run_entry.is_symlink():
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.symlink,
                        reason="run path is a symlink",
                        root_kind=subject_type,
                    )
                )
                continue

            if not run_entry.is_dir(follow_symlinks=False):
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.unknown,
                        reason="not a run directory",
                        root_kind=subject_type,
                    )
                )
                continue

            if not is_valid_run_id(run_id):
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.invalid,
                        reason="invalid run_id",
                        root_kind=subject_type,
                    )
                )
                continue

            if int(st.st_dev) != root_dev:
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.mount,
                        reason="run on different device than output root",
                        root_kind=subject_type,
                    )
                )
                continue

            run_path = Path(run_entry.path)
            try:
                fingerprint, size_est, file_count = compute_tree_fingerprint(
                    run_path, root_dev
                )
            except TreeFingerprintError as exc:
                try:
                    classification = EntryClassification(exc.classification)
                except ValueError:
                    classification = EntryClassification.unreadable
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=classification,
                        reason=exc.reason,
                        root_kind=subject_type,
                    )
                )
                continue

            try:
                canonical = str(run_path.resolve())
            except OSError as exc:
                exclusions.append(
                    _exclusion(
                        path_relative=rel,
                        classification=EntryClassification.unreadable,
                        reason=f"cannot resolve canonical path: {exc}",
                        root_kind=subject_type,
                    )
                )
                continue

            mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
            targets.append(
                CleanupTarget(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    run_id=run_id,
                    root_relative_path=rel,
                    canonical_path=canonical,
                    mtime_ns=mtime_ns,
                    filesystem_dev=int(st.st_dev),
                    filesystem_ino=int(st.st_ino),
                    size_estimate_bytes=int(size_est),
                    file_count=int(file_count),
                    tree_fingerprint=fingerprint,
                    safety_status=EntryClassification.eligible,
                )
            )

        return targets, exclusions
