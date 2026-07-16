"""Validate configured analysis output roots before cleanup discovery."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Mapping

from transcriptx.core.utils.path_canonical import canonicalise_path
from transcriptx.web.services.run_cleanup.models import RootIdentity, SubjectType


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _samefile_or_equal(a: Path, b: Path) -> bool:
    try:
        if a.exists() and b.exists():
            return os.path.samefile(a, b)
    except OSError:
        pass
    try:
        return Path(canonicalise_path(a)) == Path(canonicalise_path(b))
    except OSError:
        return str(a) == str(b)


def _is_under_lexical(child: Path, parent: Path) -> bool:
    """Containment using canonicalised paths (works when one side is missing)."""
    try:
        child_c = Path(canonicalise_path(child))
        parent_c = Path(canonicalise_path(parent))
        child_c.relative_to(parent_c)
        return child_c != parent_c
    except (ValueError, OSError, RuntimeError):
        return False


def paths_overlap(a: Path, b: Path) -> bool:
    """True if paths are the same or either is an ancestor of the other."""
    if _samefile_or_equal(a, b):
        return True
    return _is_under_lexical(a, b) or _is_under_lexical(b, a)


def _equals_broad(configured: Path, canonical: Path, unsafe: Path) -> bool:
    return (
        _samefile_or_equal(canonical, unsafe)
        or _samefile_or_equal(configured, unsafe)
        or canonicalise_path(configured) == canonicalise_path(unsafe)
        or canonicalise_path(canonical) == canonicalise_path(unsafe)
    )


class OutputRootValidator:
    """Validate OUTPUTS_DIR / GROUP_OUTPUTS_DIR against broad and protected rules."""

    @staticmethod
    def validate(
        outputs_dir: Path,
        group_outputs_dir: Path,
        protected_paths: Mapping[str, Path],
        *,
        project_root: Path | None = None,
        data_dir: Path | None = None,
        state_dir: Path | None = None,
        home_dir: Path | None = None,
    ) -> tuple[list[RootIdentity], list[str]]:
        """Return root identities and blocking errors (fail closed on unsafe roots)."""
        identities: list[RootIdentity] = []
        blocking: list[str] = []

        broad_unsafe: dict[str, Path] = {
            "filesystem_root": Path("/"),
            "home": Path(home_dir) if home_dir is not None else Path.home(),
        }
        if project_root is not None:
            broad_unsafe["project_root"] = Path(project_root)
        if data_dir is not None:
            broad_unsafe["data_dir"] = Path(data_dir)
        if state_dir is not None:
            broad_unsafe["state_dir"] = Path(state_dir)

        for kind, configured in (
            (SubjectType.transcript, Path(outputs_dir)),
            (SubjectType.group, Path(group_outputs_dir)),
        ):
            identity, errors = OutputRootValidator._validate_one(
                kind=kind,
                configured=configured,
                broad_unsafe=broad_unsafe,
                protected_paths=protected_paths,
            )
            identities.append(identity)
            blocking.extend(errors)

        # Cross-root rules
        if len(identities) == 2:
            tx, grp = identities[0], identities[1]
            blocking.extend(OutputRootValidator._cross_root_errors(tx, grp))

        return identities, blocking

    @staticmethod
    def _cross_root_errors(transcript: RootIdentity, group: RootIdentity) -> list[str]:
        errors: list[str] = []
        tx_c = Path(transcript.canonical_path)
        grp_c = Path(group.canonical_path)
        if _samefile_or_equal(tx_c, grp_c) or canonicalise_path(
            transcript.canonical_path
        ) == canonicalise_path(group.canonical_path):
            errors.append("transcript and group output roots must not be equal")
            return errors
        # Allow group nested under transcript
        group_under_tx = _is_under_lexical(grp_c, tx_c)
        tx_under_group = _is_under_lexical(tx_c, grp_c)
        if tx_under_group:
            errors.append(
                "transcript output root must not be nested under group output root"
            )
        elif not group_under_tx and paths_overlap(tx_c, grp_c):
            errors.append("transcript and group output roots have unexpected overlap")
        return errors

    @staticmethod
    def _validate_one(
        *,
        kind: SubjectType,
        configured: Path,
        broad_unsafe: Mapping[str, Path],
        protected_paths: Mapping[str, Path],
    ) -> tuple[RootIdentity, list[str]]:
        errors: list[str] = []
        configured = Path(configured).expanduser()
        configured_str = str(configured)
        exists = _lexists(configured)

        try:
            canonical_str = canonicalise_path(configured)
        except (OSError, RuntimeError):
            canonical_str = configured_str
        canonical = Path(canonical_str)

        # Broad-unsafe and protected checks always (even if missing)
        for label, unsafe in broad_unsafe.items():
            if _equals_broad(configured, canonical, Path(unsafe)):
                errors.append(
                    f"{kind.value} output root must not equal {label} ({unsafe})"
                )

        for label, protected in protected_paths.items():
            try:
                if paths_overlap(canonical, Path(protected)) or paths_overlap(
                    configured, Path(protected)
                ):
                    errors.append(
                        f"{kind.value} output root overlaps protected path "
                        f"'{label}' ({protected})"
                    )
            except OSError as exc:
                errors.append(
                    f"cannot compare {kind.value} root to protected '{label}': {exc}"
                )

        if not exists:
            return (
                RootIdentity(
                    kind=kind,
                    configured_path=configured_str,
                    canonical_path=canonical_str,
                    dev=None,
                    ino=None,
                    is_symlink=False,
                    exists=False,
                ),
                errors,
            )

        if configured.is_symlink():
            errors.append(
                f"{kind.value} output root is a symlink (forbidden): {configured_str}"
            )
            return (
                RootIdentity(
                    kind=kind,
                    configured_path=configured_str,
                    canonical_path=canonical_str,
                    dev=None,
                    ino=None,
                    is_symlink=True,
                    exists=True,
                ),
                errors,
            )

        try:
            st = configured.lstat()
        except OSError as exc:
            errors.append(
                f"cannot lstat {kind.value} output root {configured_str}: {exc}"
            )
            return (
                RootIdentity(
                    kind=kind,
                    configured_path=configured_str,
                    canonical_path=canonical_str,
                    dev=None,
                    ino=None,
                    is_symlink=False,
                    exists=True,
                ),
                errors,
            )

        if not stat.S_ISDIR(st.st_mode):
            errors.append(
                f"{kind.value} output root is not a directory: {configured_str}"
            )

        return (
            RootIdentity(
                kind=kind,
                configured_path=configured_str,
                canonical_path=canonical_str,
                dev=int(st.st_dev),
                ino=int(st.st_ino),
                is_symlink=False,
                exists=True,
            ),
            errors,
        )
