"""Anchored-prefix artifact remapping and output-directory finalization."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.rename.names import (
    ARTIFACT_SEPARATORS,
    RenameNames,
    paths_are_case_only_rename,
    unique_temp_name,
)

logger = get_logger()

TEMP_TAG = "tx_rename_tmp"


@dataclass(frozen=True)
class ArtifactRemapPlan:
    """Complete source→target map for output-tree filename remapping (filenames only)."""

    moves: tuple[tuple[Path, Path], ...] = ()
    blocked: bool = False
    block_message: str = ""
    warnings: tuple[str, ...] = ()


@dataclass
class FinalizePlan:
    """Concrete immutable-ish finalize operations shared by execute/dry-run/repair."""

    needs_output_dir_move: bool = False
    old_output_dir: Path = field(default_factory=Path)
    new_output_dir: Path = field(default_factory=Path)
    artifact_remap: ArtifactRemapPlan = field(default_factory=ArtifactRemapPlan)


def replacement_pairs(names: RenameNames) -> list[tuple[str, str]]:
    """Deduped (old_token, new_token) pairs, longest source first."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for old, new in (
        (names.old_stem, names.new_stem),
        (names.old_canonical, names.new_canonical),
    ):
        if not old or old == new:
            continue
        if old in seen:
            continue
        seen.add(old)
        pairs.append((old, new))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def remap_basename(basename: str, pairs: list[tuple[str, str]]) -> str:
    """Exactly one anchored prefix replacement on a basename, or unchanged.

    Replace only when basename equals old_token or begins with
    old_token + recognised_separator; preserve the remainder verbatim.
    """
    for old_token, new_token in pairs:
        if basename == old_token:
            return new_token
        for sep in ARTIFACT_SEPARATORS:
            prefix = old_token + sep
            if basename.startswith(prefix):
                return new_token + sep + basename[len(prefix) :]
    return basename


def build_artifact_remap_plan(
    output_dir: Path,
    names: RenameNames,
) -> ArtifactRemapPlan:
    """Snapshot files, build full map, preflight collisions (filenames only; not dirs)."""
    if not output_dir.exists():
        return ArtifactRemapPlan()

    pairs = replacement_pairs(names)
    if not pairs:
        return ArtifactRemapPlan()

    files = [p for p in output_dir.rglob("*") if p.is_file()]
    moves: list[tuple[Path, Path]] = []
    targets: dict[str, Path] = {}
    case_targets: dict[str, Path] = {}

    for file_path in files:
        new_name = remap_basename(file_path.name, pairs)
        if new_name == file_path.name:
            continue
        dest = file_path.parent / new_name
        if dest == file_path:
            continue
        dest_key = str(dest)
        if dest_key in targets:
            return ArtifactRemapPlan(
                blocked=True,
                block_message=(
                    f"Artifact remap many-to-one collision onto {dest} "
                    f"from {targets[dest_key]} and {file_path}"
                ),
            )
        folded = str(dest).casefold()
        if folded in case_targets and case_targets[folded] != dest:
            if not paths_are_case_only_rename(file_path, dest):
                return ArtifactRemapPlan(
                    blocked=True,
                    block_message=f"Artifact remap case-folded collision onto {dest}",
                )
        if dest.exists() and not paths_are_case_only_rename(file_path, dest):
            return ArtifactRemapPlan(
                blocked=True,
                block_message=f"Artifact remap destination already exists: {dest}",
            )
        targets[dest_key] = file_path
        case_targets[folded] = dest
        moves.append((file_path, dest))

    return ArtifactRemapPlan(moves=tuple(moves))


def execute_artifact_remap(plan: ArtifactRemapPlan) -> list[str]:
    """Apply remaps with case-only temp intermediates. Returns error messages.

    Idempotent: when source is absent and dest is present for a planned pair,
    the move is treated as already completed.
    """
    errors: list[str] = []
    for source, dest in plan.moves:
        try:
            if not source.exists() and dest.exists():
                # Already completed for this planned pair.
                continue
            if paths_are_case_only_rename(source, dest):
                tmp = unique_temp_name(source.parent, dest.name, tag=TEMP_TAG)
                source.rename(tmp)
                tmp.rename(dest)
            else:
                if dest.exists():
                    errors.append(f"Destination appeared before remap: {dest}")
                    continue
                if not source.exists():
                    errors.append(f"Remap source missing: {source}")
                    continue
                source.rename(dest)
        except OSError as err:
            errors.append(f"Could not remap {source} -> {dest}: {err}")
    return errors


def finalize_output_directory_move(old_dir: Path, new_dir: Path) -> str:
    """Idempotent output-directory move/merge.

    Returns a status token:
    - ``completed`` / ``already_done`` / ``noop`` on success
    - ``both_absent`` / ``both_exist_conflict`` for repair-visible states
    """
    if old_dir == new_dir:
        return "noop"
    old_exists = old_dir.exists()
    new_exists = new_dir.exists()
    if not old_exists and not new_exists:
        return "both_absent"
    if not old_exists and new_exists:
        return "already_done"
    if old_exists and new_exists:
        # Merge remaining content from old into new (idempotent repair).
        pass
    if paths_are_case_only_rename(old_dir, new_dir):
        tmp = unique_temp_name(old_dir.parent, new_dir.name, tag=TEMP_TAG)
        old_dir.rename(tmp)
        tmp.rename(new_dir)
        logger.info("Case-only renamed output directory: %s -> %s", old_dir, new_dir)
        return "completed"
    if not new_dir.exists():
        new_dir.mkdir(parents=True, exist_ok=True)
    for item in old_dir.iterdir():
        dest = new_dir / item.name
        if dest.exists():
            if item.is_dir():
                for subitem in item.rglob("*"):
                    rel_path = subitem.relative_to(item)
                    new_subitem = dest / rel_path
                    new_subitem.parent.mkdir(parents=True, exist_ok=True)
                    if subitem.is_file() and not new_subitem.exists():
                        shutil.move(str(subitem), str(new_subitem))
            else:
                logger.warning("Skipping %s - already exists in destination", item.name)
        else:
            shutil.move(str(item), str(dest))
    try:
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
    except OSError:
        pass
    logger.info("Renamed output directory: %s -> %s", old_dir.name, new_dir.name)
    return "completed"


def cleanup_abandoned_temps(
    roots: list[Path] | None = None,
    *,
    recorded_temps: list[str] | Path | None = None,
) -> list[str]:
    """Remove only operation-scoped temporary names.

    Prefer ``recorded_temps`` from the journal. Broad directory scans are not
    performed unless explicitly requested with an empty recorded list and roots
    for legacy callers — even then only exact TEMP_TAG prefixes are removed.
    """
    cleaned: list[str] = []
    if recorded_temps:
        paths = (
            [Path(p) for p in recorded_temps]
            if not isinstance(recorded_temps, (str, Path))
            else [Path(recorded_temps)]
        )
        for p in paths:
            try:
                if not p.exists():
                    continue
                if p.is_file() or p.is_symlink():
                    p.unlink()
                    cleaned.append(str(p))
                elif p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                    cleaned.append(str(p))
            except OSError as err:
                log_error(
                    "FILE_RENAME", f"temp cleanup failed {p}: {err}", exception=err
                )
        return cleaned

    # Legacy: no recorded temps — do not scan broadly.
    if roots:
        logger.debug(
            "cleanup_abandoned_temps skipped broad scan under %s (operation-scoped only)",
            roots,
        )
    return cleaned
