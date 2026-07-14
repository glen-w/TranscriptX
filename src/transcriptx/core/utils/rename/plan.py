"""Rename plan types and build_rename_plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.rename.audio_association import (
    AudioAssociation,
    AudioAssociationKind,
    resolve_audio_association,
)
from transcriptx.core.utils.rename.finalize import (
    ArtifactRemapPlan,
    FinalizePlan,
    build_artifact_remap_plan,
)
from transcriptx.core.utils.rename.names import (
    RenameNames,
    RenamePaths,
    paths_are_case_only_rename,
)
from transcriptx.core.utils.rename.processing_state import (
    ProcessingStateRenameMutation,
    StagedProcessingStateWrite,
    compute_processing_state_rename_mutation,
)
from transcriptx.core.utils.rename.sidecars import (
    SidecarMove,
    plan_managed_sidecar_moves,
    unique_quarantine_path,
)
from transcriptx.io.import_metadata_sidecar import validate_managed_transcript

logger = get_logger()

ROLLBACK_POLICY = (
    "Use RenameTransaction.rollback() only for failures during execute(); "
    "never rollback to fix post-commit finalize failures."
)


@dataclass(frozen=True)
class RenameContext:
    """Read-only inputs for building a rename plan (compat + internal)."""

    old_name: str
    new_name: str
    transcript_path: str
    transcript_file: Path
    new_transcript_path: Path
    old_output_dir: Path
    new_output_dir: Path
    names: RenameNames | None = None
    paths: RenamePaths | None = None


@dataclass(frozen=True)
class RenamePlanValidation:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class RenamePlan:
    blocked: bool = False
    block_message: str = ""
    validations: tuple[RenamePlanValidation, ...] = ()
    warnings: list[str] = field(default_factory=list)
    transaction_file_renames: list[tuple[Path, Path, str]] = field(default_factory=list)
    staged_state_write: StagedProcessingStateWrite | None = None
    # Deprecated callable form retained empty for shim compatibility.
    transaction_state_updates: list = field(default_factory=list)
    sidecar_moves: tuple[SidecarMove, ...] = ()
    state_mutation: ProcessingStateRenameMutation | None = None
    state_snapshot: dict | None = None
    missing_state_row_warning: bool = False
    audio: AudioAssociation | None = None
    planned_old_audio: Path | None = None
    planned_new_audio: Path | None = None
    audio_renamed: bool = False
    needs_output_finalize: bool = False
    finalize_ops: tuple[str, ...] = ()
    finalize_plan: FinalizePlan | None = None
    old_output_dir: Path = field(default_factory=Path)
    new_output_dir: Path = field(default_factory=Path)
    old_name: str = ""
    new_name: str = ""
    transcript_path_before: str = ""
    transcript_path_after: str = ""
    cache_invalidation_targets: tuple[str, str] = ("", "")
    names: RenameNames | None = None
    paths: RenamePaths | None = None
    rename_history_at_iso: str = ""
    planned_old_slug: str | None = None
    planned_new_slug: str | None = None
    processing_state_file: str = ""


def preflight_transaction_rename_map(
    renames: list[tuple[Path, Path, str]],
) -> str | None:
    """Detect duplicate or case-folded destination collisions across all renames."""
    targets: dict[str, Path] = {}
    case_targets: dict[str, Path] = {}
    for src, dest, _desc in renames:
        key = str(dest)
        if key in targets and targets[key] != src:
            return (
                f"Rename blocked: multiple sources target the same path {dest} "
                f"({targets[key]} and {src})"
            )
        folded = str(dest).casefold()
        if folded in case_targets and case_targets[folded] != dest:
            if not paths_are_case_only_rename(src, dest):
                return f"Rename blocked: case-folded destination collision onto {dest}"
        targets[key] = src
        case_targets[folded] = dest
    return None


def build_rename_plan(
    ctx: RenameContext,
    state_snapshot: Optional[dict],
    rename_history_at_iso: str,
    *,
    processing_state_file: Path | None = None,
) -> RenamePlan:
    """Build a deterministic rename plan (read-only: no filesystem mutations)."""
    transcript_file = Path(ctx.transcript_file)
    new_transcript_path = Path(ctx.new_transcript_path)
    names = ctx.names or RenameNames.from_paths(transcript_file, new_transcript_path)
    paths = ctx.paths or RenamePaths.from_transcripts(
        transcript_file, new_transcript_path
    )
    old_name = names.old_stem
    new_name = names.new_stem
    transcript_path = str(paths.old_transcript)
    state_file_str = str(processing_state_file) if processing_state_file else ""

    vals: list[RenamePlanValidation] = []

    if not transcript_file.exists():
        vals.append(
            RenamePlanValidation("transcript_file_exists", False, str(transcript_path))
        )
        return RenamePlan(
            blocked=True,
            block_message=f"Transcript file not found: {transcript_path}",
            validations=tuple(vals),
            names=names,
            paths=paths,
        )
    vals.append(
        RenamePlanValidation("transcript_file_exists", True, str(transcript_file))
    )

    managed_validation = validate_managed_transcript(transcript_file)
    if not managed_validation.ok:
        vals.append(
            RenamePlanValidation(
                "managed_library_transcript",
                False,
                managed_validation.message
                or "transcript is not library-valid managed transcript",
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=managed_validation.message
            or "transcript is not library-valid managed transcript",
            validations=tuple(vals),
            names=names,
            paths=paths,
        )
    vals.append(RenamePlanValidation("managed_library_transcript", True, ""))

    plan_warnings: list[str] = list(managed_validation.warnings or [])

    target_exists = new_transcript_path.exists() and not paths_are_case_only_rename(
        transcript_file, new_transcript_path
    )
    if target_exists and new_transcript_path != transcript_file:
        vals.append(
            RenamePlanValidation(
                "target_transcript_path_available",
                False,
                str(new_transcript_path),
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=f"Rename blocked: file already exists: {new_transcript_path}",
            validations=tuple(vals),
            names=names,
            paths=paths,
        )
    vals.append(RenamePlanValidation("target_transcript_path_available", True, ""))

    old_out, new_out = paths.old_output_dir, paths.new_output_dir
    out_collision = (
        new_out.exists()
        and new_out != old_out
        and not paths_are_case_only_rename(old_out, new_out)
    )
    if out_collision:
        vals.append(
            RenamePlanValidation(
                "target_output_dir_available",
                False,
                str(new_out),
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=(
                f"Rename blocked: output directory already exists: {new_out}"
            ),
            validations=tuple(vals),
            names=names,
            paths=paths,
        )
    vals.append(RenamePlanValidation("target_output_dir_available", True, ""))

    transaction_file_renames: list[tuple[Path, Path, str]] = []
    if transcript_file != new_transcript_path:
        transaction_file_renames.append(
            (
                transcript_file,
                new_transcript_path,
                f"Rename transcript: {old_name} -> {new_name}",
            )
        )

    sidecar_result = plan_managed_sidecar_moves(
        transcript_file,
        new_transcript_path,
        rename_history_at_iso=rename_history_at_iso,
    )
    if isinstance(sidecar_result, str):
        return RenamePlan(
            blocked=True,
            block_message=sidecar_result,
            validations=tuple(vals),
            warnings=plan_warnings,
            names=names,
            paths=paths,
        )
    sidecar_moves = sidecar_result
    for move in sidecar_moves:
        if move.source != move.dest:
            transaction_file_renames.append((move.source, move.dest, move.description))
        if move.quarantine_legacy and move.quarantine_legacy.exists():
            qdest = unique_quarantine_path(move.quarantine_legacy)
            if qdest.exists():
                return RenamePlan(
                    blocked=True,
                    block_message=(
                        f"Rename blocked: quarantine destination already exists: {qdest}"
                    ),
                    validations=tuple(vals),
                    warnings=plan_warnings,
                    names=names,
                    paths=paths,
                )
            transaction_file_renames.append(
                (
                    move.quarantine_legacy,
                    qdest,
                    f"Quarantine legacy import sidecar: {move.quarantine_legacy}",
                )
            )
        # Preflight staged JSON destination collisions
        if move.staged_payload is not None:
            dest = move.dest
            for src, existing_dest, _d in transaction_file_renames:
                if existing_dest == dest and src != move.source and move.source != dest:
                    # Same dest as a file rename of a different source — ok if
                    # this is an in-place write after rename to dest.
                    pass

    # Audio association (single resolve)
    audio = resolve_audio_association(transcript_path, state_snapshot=state_snapshot)
    planned_old_audio: Path | None = None
    planned_new_audio: Path | None = None
    audio_renamed = False
    if audio.warning:
        plan_warnings.append(audio.warning)

    if audio.kind == AudioAssociationKind.recordings_working_copy and audio.renameable:
        assert audio.path is not None
        planned_old_audio = audio.path
        planned_new_audio = audio.path.parent / f"{new_name}{audio.path.suffix}"
        if planned_new_audio.exists() and not paths_are_case_only_rename(
            planned_old_audio, planned_new_audio
        ):
            return RenamePlan(
                blocked=True,
                block_message=(
                    "Rename blocked: linked working-copy audio target already exists: "
                    f"{planned_new_audio}"
                ),
                validations=tuple(vals),
                warnings=plan_warnings,
                names=names,
                paths=paths,
                audio=audio,
            )
        if planned_old_audio != planned_new_audio:
            transaction_file_renames.append(
                (
                    planned_old_audio,
                    planned_new_audio,
                    f"Rename working-copy audio: {planned_old_audio.name} -> {planned_new_audio.name}",
                )
            )
            audio_renamed = True
    vals.append(RenamePlanValidation("audio_association", True, audio.kind.value))

    state_mutation: ProcessingStateRenameMutation | None = None
    missing_state_row_warning = False
    staged_state_write: StagedProcessingStateWrite | None = None

    if state_snapshot is None:
        vals.append(RenamePlanValidation("processing_state", True, "absent_noop"))
    else:
        from transcriptx.core.utils.processing_state import (
            find_processed_entry_for_path,
        )

        key, _meta = find_processed_entry_for_path(transcript_path, state_snapshot)
        if key is None:
            missing_state_row_warning = True
            plan_warnings.append(
                "Processing state file has no matching row for this transcript; "
                "state paths will not be updated"
            )
            vals.append(
                RenamePlanValidation("processing_state", True, "no_matching_row")
            )
        else:
            state_mutation = compute_processing_state_rename_mutation(
                state_snapshot,
                names=names,
                paths=paths,
                planned_old_audio=planned_old_audio if audio_renamed else None,
                planned_new_audio=planned_new_audio if audio_renamed else None,
                rename_timestamp_iso=rename_history_at_iso,
            )
            if state_mutation is None:
                return RenamePlan(
                    blocked=True,
                    block_message="Failed to compute processing-state rename mutation",
                    validations=tuple(vals),
                    warnings=plan_warnings,
                    names=names,
                    paths=paths,
                )
            if state_mutation.sibling_path_validation_msgs:
                return RenamePlan(
                    blocked=True,
                    block_message=(
                        "Rename blocked: invalid proposed processing-state document: "
                        + "; ".join(state_mutation.sibling_path_validation_msgs)
                    ),
                    validations=tuple(vals),
                    warnings=plan_warnings,
                    names=names,
                    paths=paths,
                )
            if processing_state_file is not None:
                staged_state_write = StagedProcessingStateWrite(
                    state_file=str(processing_state_file),
                    mutation=state_mutation,
                    state_snapshot=state_snapshot,
                )
            vals.append(RenamePlanValidation("processing_state", True, "planned"))

    # Finalize / remap preflight (before commit)
    remap_scan_dir = old_out if old_out.exists() else new_out
    artifact_remap = build_artifact_remap_plan(remap_scan_dir, names)
    if artifact_remap.blocked:
        return RenamePlan(
            blocked=True,
            block_message=artifact_remap.block_message,
            validations=tuple(vals),
            warnings=plan_warnings,
            names=names,
            paths=paths,
        )

    adjusted_moves: list[tuple[Path, Path]] = []
    if old_out != new_out and old_out.exists():
        for src, dest in artifact_remap.moves:
            try:
                rel_parent = dest.parent.relative_to(old_out)
            except ValueError:
                rel_parent = Path(".")
            adjusted_dest = new_out / rel_parent / dest.name
            try:
                rel_src_parent = src.parent.relative_to(old_out)
            except ValueError:
                rel_src_parent = Path(".")
            adjusted_src = new_out / rel_src_parent / src.name
            adjusted_moves.append((adjusted_src, adjusted_dest))
        artifact_remap = ArtifactRemapPlan(moves=tuple(adjusted_moves))

    # Include remap destinations in global collision preflight
    for src, dest in artifact_remap.moves:
        transaction_file_renames.append(
            (src, dest, f"Planned artifact remap: {src.name} -> {dest.name}")
        )

    collision = preflight_transaction_rename_map(transaction_file_renames)
    if collision:
        return RenamePlan(
            blocked=True,
            block_message=collision,
            validations=tuple(vals),
            warnings=plan_warnings,
            names=names,
            paths=paths,
        )

    # Remap entries are planned for finalize, not the transaction — strip them back.
    remap_set = {(str(s), str(d)) for s, d in artifact_remap.moves}
    transaction_file_renames = [
        t for t in transaction_file_renames if (str(t[0]), str(t[1])) not in remap_set
    ]

    finalize_plan = FinalizePlan(
        needs_output_dir_move=old_out.exists() and old_out != new_out,
        old_output_dir=old_out,
        new_output_dir=new_out,
        artifact_remap=artifact_remap,
    )
    needs_finalize = finalize_plan.needs_output_dir_move or bool(artifact_remap.moves)
    finalize_ops: tuple[str, ...] = ()
    if finalize_plan.needs_output_dir_move:
        finalize_ops = finalize_ops + ("output_dir_move",)
    if artifact_remap.moves:
        finalize_ops = finalize_ops + ("artifact_remap",)

    # Planned slug preview (deterministic from paths)
    planned_old_slug: str | None = None
    planned_new_slug: str | None = None
    try:
        from transcriptx.core.utils.slug_manager import (
            generate_slug_from_path,
            load_index,
        )

        planned_new_slug = generate_slug_from_path(str(paths.new_transcript))
        index = load_index()
        for _key, entry in (index.get("transcripts") or {}).items():
            sp = entry.get("source_path", "")
            if not sp:
                continue
            try:
                if Path(sp).expanduser().resolve() == paths.old_transcript.resolve():
                    planned_old_slug = entry.get("slug")
                    break
            except OSError:
                if sp == str(paths.old_transcript):
                    planned_old_slug = entry.get("slug")
                    break
    except Exception as exc:
        logger.debug("Could not preview slug mapping: %s", exc)

    vals.append(RenamePlanValidation("rename_plan_complete", True, ""))

    return RenamePlan(
        blocked=False,
        validations=tuple(vals),
        warnings=plan_warnings,
        transaction_file_renames=transaction_file_renames,
        staged_state_write=staged_state_write,
        sidecar_moves=sidecar_moves,
        state_mutation=state_mutation,
        state_snapshot=state_snapshot,
        missing_state_row_warning=missing_state_row_warning,
        audio=audio,
        planned_old_audio=planned_old_audio,
        planned_new_audio=planned_new_audio,
        audio_renamed=audio_renamed,
        needs_output_finalize=needs_finalize,
        finalize_ops=finalize_ops,
        finalize_plan=finalize_plan,
        old_output_dir=old_out,
        new_output_dir=new_out,
        old_name=old_name,
        new_name=new_name,
        transcript_path_before=str(paths.old_transcript),
        transcript_path_after=str(paths.new_transcript),
        cache_invalidation_targets=(
            str(paths.old_transcript),
            str(paths.new_transcript),
        ),
        names=names,
        paths=paths,
        rename_history_at_iso=rename_history_at_iso,
        planned_old_slug=planned_old_slug,
        planned_new_slug=planned_new_slug,
        processing_state_file=state_file_str,
    )
