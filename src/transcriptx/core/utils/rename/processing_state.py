"""Processing-state mutations for managed rename (snapshot-planned, exact paths)."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (  # noqa: F401 — OUTPUTS_DIR is a monkeypatch surface (see __all_patch_surface__)
    OUTPUTS_DIR,
    PROCESSING_STATE_FILE,
)
from transcriptx.core.utils.rename.io_atomic import write_json_atomic
from transcriptx.core.utils.rename.names import RenameNames, RenamePaths

# Re-exported for test monkeypatching of output roots used via RenamePaths.
__all_patch_surface__ = ("OUTPUTS_DIR", "PROCESSING_STATE_FILE")

logger = get_logger()


@dataclass(frozen=True)
class ProcessingStateRenameMutation:
    entry_key: str
    enriched_entry: dict[str, Any]
    sibling_path_validation_msgs: tuple[str, ...] = ()

    def to_serializable(self) -> dict[str, Any]:
        return {
            "entry_key": self.entry_key,
            "enriched_entry": self.enriched_entry,
            "sibling_path_validation_msgs": list(self.sibling_path_validation_msgs),
        }

    @classmethod
    def from_serializable(cls, data: dict[str, Any]) -> ProcessingStateRenameMutation:
        return cls(
            entry_key=str(data["entry_key"]),
            enriched_entry=dict(data["enriched_entry"]),
            sibling_path_validation_msgs=tuple(
                data.get("sibling_path_validation_msgs") or []
            ),
        )


@dataclass(frozen=True)
class StagedProcessingStateWrite:
    """Serializable processing-state write for journal / dry-run / transaction."""

    state_file: str
    mutation: ProcessingStateRenameMutation
    state_snapshot: dict[str, Any]

    def to_serializable(self) -> dict[str, Any]:
        return {
            "state_file": self.state_file,
            "mutation": self.mutation.to_serializable(),
            # Snapshot may be large; journal stores mutation + path for repair.
            "has_snapshot": True,
        }


def _paths_equal(a: str | Path | None, b: str | Path | None) -> bool:
    from transcriptx.core.utils.processing_state import same_resolved_path

    return same_resolved_path(a, b)


def mutate_metadata_for_rename(
    metadata: dict,
    *,
    names: RenameNames,
    paths: RenamePaths,
    planned_old_audio: Path | None,
    planned_new_audio: Path | None,
    rename_timestamp_iso: str,
) -> None:
    """Apply path rewrites using exact Path comparisons (mutates in place)."""
    new_path_str = str(paths.new_transcript)
    old_path_str = str(paths.old_transcript)

    metadata["transcript_path"] = new_path_str
    metadata["current_transcript_path"] = new_path_str
    metadata["output_dir_path"] = str(paths.new_output_dir)
    metadata["canonical_base_name"] = names.new_canonical
    metadata["last_updated"] = rename_timestamp_iso

    if planned_new_audio is not None and planned_old_audio is not None:
        new_audio_str = str(planned_new_audio)
        old_audio_str = str(planned_old_audio)
        old_mp3 = metadata.get("mp3_path", "")
        if old_mp3 and _paths_equal(old_mp3, old_audio_str):
            metadata["mp3_path"] = new_audio_str
        steps = metadata.get("steps", {})
        if isinstance(steps, dict) and "convert" in steps:
            convert_step = steps["convert"]
            if isinstance(convert_step, dict) and convert_step.get("mp3_path"):
                if _paths_equal(convert_step.get("mp3_path"), old_audio_str):
                    convert_step["mp3_path"] = new_audio_str
        convert_top = metadata.get("convert")
        if isinstance(convert_top, dict) and convert_top.get("mp3_path"):
            if _paths_equal(convert_top.get("mp3_path"), old_audio_str):
                convert_top["mp3_path"] = new_audio_str

    steps = metadata.get("steps", {})
    if isinstance(steps, dict) and "transcribe" in steps:
        transcribe_step = steps["transcribe"]
        if isinstance(transcribe_step, dict):
            step_tp = transcribe_step.get("transcript_path")
            if _paths_equal(step_tp, old_path_str):
                transcribe_step["transcript_path"] = new_path_str

    transcribe_top = metadata.get("transcribe")
    if isinstance(transcribe_top, dict):
        step_tp = transcribe_top.get("transcript_path")
        if _paths_equal(step_tp, old_path_str):
            transcribe_top["transcript_path"] = new_path_str


def build_enriched_entry_for_rename(
    metadata: dict,
    *,
    names: RenameNames,
    paths: RenamePaths,
    planned_old_audio: Path | None,
    planned_new_audio: Path | None,
    rename_timestamp_iso: str,
) -> dict:
    from transcriptx.core.utils.state_schema import enrich_state_entry

    work = copy.deepcopy(metadata)
    mutate_metadata_for_rename(
        work,
        names=names,
        paths=paths,
        planned_old_audio=planned_old_audio,
        planned_new_audio=planned_new_audio,
        rename_timestamp_iso=rename_timestamp_iso,
    )
    enriched = enrich_state_entry(work, str(paths.new_transcript))
    # Preserve plan-injected timestamp (enrich_state_entry uses datetime.now()).
    enriched["last_updated"] = rename_timestamp_iso
    enriched["canonical_base_name"] = names.new_canonical
    enriched["output_dir_path"] = str(paths.new_output_dir)
    return enriched


def proposed_state_validation_messages(
    processed_files: dict,
    *,
    mutated_entry_key: str | None = None,
    allow_missing_paths: frozenset[str] | None = None,
) -> list[str]:
    """Validate the complete proposed processing-state document.

    All entries are schema-validated. Path existence is checked for the mutated
    entry only; paths in ``allow_missing_paths`` (planned destinations) are
    exempt.
    """
    from transcriptx.core.utils.state_schema import (
        validate_state_entry,
        validate_state_paths,
    )

    allow = allow_missing_paths or frozenset()
    msgs: list[str] = []
    for ek, em in processed_files.items():
        if not isinstance(em, dict):
            msgs.append(f"State entry {ek!r} is not an object")
            continue
        ok_schema, schema_errors = validate_state_entry(em)
        if not ok_schema:
            msgs.append(f"State entry {ek!r} schema invalid: {schema_errors!r}")
        if mutated_entry_key is not None and str(ek) != str(mutated_entry_key):
            continue
        ok_paths, path_errors = validate_state_paths(em)
        if not ok_paths:
            filtered = [
                err
                for err in path_errors
                if not any(allowed in err for allowed in allow)
            ]
            if filtered:
                msgs.append(f"State entry {ek!r} has invalid paths: {filtered!r}")
    return msgs


# Back-compat alias used by older imports/tests
def sibling_path_validation_messages(
    processed_files: dict, new_path_str: str
) -> list[str]:
    return proposed_state_validation_messages(
        processed_files,
        allow_missing_paths=frozenset({new_path_str}),
    )


def compute_processing_state_rename_mutation(
    state: dict,
    *,
    names: RenameNames,
    paths: RenamePaths,
    planned_old_audio: Path | None,
    planned_new_audio: Path | None,
    rename_timestamp_iso: str,
) -> Optional[ProcessingStateRenameMutation]:
    from transcriptx.core.utils.processing_state import find_processed_entry_for_path

    processed_files = state.get("processed_files", {})
    if not isinstance(processed_files, dict):
        return None

    key, metadata = find_processed_entry_for_path(str(paths.old_transcript), state)
    if metadata is None or key is None:
        return None

    enriched = build_enriched_entry_for_rename(
        metadata,
        names=names,
        paths=paths,
        planned_old_audio=planned_old_audio,
        planned_new_audio=planned_new_audio,
        rename_timestamp_iso=rename_timestamp_iso,
    )
    temp_processed = dict(processed_files)
    temp_processed[key] = enriched
    allow_missing = {str(paths.new_transcript), str(paths.new_output_dir)}
    if planned_new_audio is not None:
        allow_missing.add(str(planned_new_audio))
    sibling_msgs = tuple(
        proposed_state_validation_messages(
            temp_processed,
            mutated_entry_key=str(key),
            allow_missing_paths=frozenset(allow_missing),
        )
    )
    return ProcessingStateRenameMutation(
        entry_key=str(key),
        enriched_entry=enriched,
        sibling_path_validation_msgs=sibling_msgs,
    )


def persist_processing_state_mutation_strict(
    state: dict, mutation: ProcessingStateRenameMutation, state_file: Path
) -> None:
    """Apply mutation and write crash-safe; raises on I/O or validation failure."""
    if mutation.sibling_path_validation_msgs:
        raise ValueError(
            "Refusing to persist invalid processing-state mutation: "
            + "; ".join(mutation.sibling_path_validation_msgs)
        )
    processed = state.setdefault("processed_files", {})
    processed[mutation.entry_key] = mutation.enriched_entry
    write_json_atomic(Path(state_file), state)


def apply_planned_processing_state_update(
    *,
    state_snapshot: dict,
    mutation: ProcessingStateRenameMutation,
    state_file: Path,
) -> None:
    """Strict writer used inside the rename transaction (raises on failure)."""
    state = copy.deepcopy(state_snapshot)
    persist_processing_state_mutation_strict(state, mutation, Path(state_file))


def update_processing_state(
    old_path: str,
    new_path: str,
    old_name: str,
    new_name: str,
    *,
    rename_timestamp_iso: str | None = None,
    planned_new_audio: str | Path | None = None,
) -> None:
    """Compatibility wrapper only — not used by the managed-rename pipeline.

    May use ``datetime.now()`` and inferred audio rewriting. Prefer planned
    snapshot mutations in ``rename_managed_transcript``.
    """
    from datetime import datetime

    try:
        from transcriptx.core.utils import file_rename as fr

        state_path = Path(fr.PROCESSING_STATE_FILE)
    except Exception:
        state_path = Path(PROCESSING_STATE_FILE)

    if not state_path.exists():
        return
    import json

    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    old_t = Path(old_path)
    new_t = Path(new_path)
    derived = RenameNames.from_paths(old_t, new_t)
    names = RenameNames(
        old_stem=old_name,
        new_stem=new_name,
        old_canonical=derived.old_canonical,
        new_canonical=derived.new_canonical,
    )
    paths = RenamePaths.from_transcripts(old_t, new_t)
    ts = rename_timestamp_iso or datetime.now().isoformat()
    planned_old: Path | None = None
    audio: Path | None
    if planned_new_audio is not None:
        audio = Path(planned_new_audio)
        from transcriptx.core.utils.processing_state import (
            find_processed_entry_for_path,
        )

        _key, meta = find_processed_entry_for_path(str(old_t), state)
        if isinstance(meta, dict) and meta.get("mp3_path"):
            planned_old = Path(str(meta["mp3_path"]))
    else:
        audio = None
        from transcriptx.core.utils.processing_state import (
            find_processed_entry_for_path,
        )

        _key, meta = find_processed_entry_for_path(str(old_t), state)
        if isinstance(meta, dict):
            mp3 = meta.get("mp3_path") or ""
            if mp3:
                mp3_path = Path(mp3)
                if (
                    mp3_path.stem == old_name
                    or get_canonical_base_name(mp3) == names.old_canonical
                ):
                    planned_old = mp3_path
                    audio = mp3_path.parent / f"{new_name}{mp3_path.suffix}"
    mutation = compute_processing_state_rename_mutation(
        state,
        names=names,
        paths=paths,
        planned_old_audio=planned_old,
        planned_new_audio=audio,
        rename_timestamp_iso=ts,
    )
    if mutation is None:
        logger.warning(
            "No processing state entry matched rename source path %s; state not updated",
            old_path,
        )
        return
    # Compat path: clear validation msgs that only reflect not-yet-existing dests
    # so legacy callers can still write; managed pipeline blocks at plan time.
    if mutation.sibling_path_validation_msgs:
        mutation = ProcessingStateRenameMutation(
            entry_key=mutation.entry_key,
            enriched_entry=mutation.enriched_entry,
            sibling_path_validation_msgs=(),
        )
    apply_planned_processing_state_update(
        state_snapshot=state, mutation=mutation, state_file=state_path
    )
