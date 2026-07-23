"""Generation staging + commit-marker protocol for llm_custom_qa artifacts."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.errors import CustomQAArtifactCommitError
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    COMMIT_MARKER_SCHEMA_VERSION_V1,
    COMMIT_MARKER_SCHEMA_VERSION_V2,
    is_v2_execution_enabled,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_text
from transcriptx.core.utils.artifact_writer import write_json, write_text

logger = logging.getLogger(__name__)


def allocate_generation_id() -> str:
    return str(uuid.uuid4())


def _fsync_path(path: Path) -> None:
    with open(path, "rb") as handle:
        os.fsync(handle.fileno())
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _atomic_write_text(path: Path, text: str) -> None:
    # Route through artifact_writer (audit guardrail: no Path.write_text in analysis).
    write_text(path, text)
    _fsync_path(path)


def staged_paths(stem: Path, generation_id: str) -> tuple[Path, Path, Path, Path]:
    """Return (json_staging, md_staging, commit_marker, active_pointer)."""
    json_staging = Path(f"{stem}.json.staging.{generation_id}")
    md_staging = Path(f"{stem}.md.staging.{generation_id}")
    commit_marker = Path(f"{stem}.commit.{generation_id}")
    active = Path(f"{stem}.active")
    return json_staging, md_staging, commit_marker, active


def generation_paths(stem: Path, generation_id: str) -> tuple[Path, Path, Path]:
    """Authoritative v2 generation files (json, md, questions_metadata)."""
    return (
        Path(f"{stem}.json.{generation_id}"),
        Path(f"{stem}.md.{generation_id}"),
        Path(f"{stem}.questions_metadata.{generation_id}.json"),
    )


def write_staged_artifacts(
    *,
    stem: Path,
    generation_id: str,
    payload: dict[str, Any],
    markdown: str,
) -> tuple[Path, Path]:
    json_staging, md_staging, _, _ = staged_paths(stem, generation_id)
    write_json(str(json_staging), payload)
    write_text(str(md_staging), markdown)
    _fsync_path(json_staging)
    _fsync_path(md_staging)
    return json_staging, md_staging


def write_commit_marker(
    *,
    stem: Path,
    generation_id: str,
    json_staging: Path,
    md_staging: Path,
    commit_marker_schema_version: str = COMMIT_MARKER_SCHEMA_VERSION_V1,
    run_execution_id: str | None = None,
    json_name: str | None = None,
    md_name: str | None = None,
    questions_metadata_name: str | None = None,
    questions_metadata_sha256: str | None = None,
) -> Path:
    _, _, commit_marker, _ = staged_paths(stem, generation_id)
    marker: dict[str, Any] = {
        "commit_marker_schema_version": commit_marker_schema_version,
        "generation_id": generation_id,
        "json_sha256": sha256_text(json_staging.read_text(encoding="utf-8")),
        "md_sha256": sha256_text(md_staging.read_text(encoding="utf-8")),
        "json_name": json_name or json_staging.name,
        "md_name": md_name or md_staging.name,
    }
    if run_execution_id is not None:
        marker["run_execution_id"] = run_execution_id
    if questions_metadata_name is not None:
        marker["questions_metadata_name"] = questions_metadata_name
        marker["questions_metadata_sha256"] = questions_metadata_sha256 or ""
    _atomic_write_text(commit_marker, json.dumps(marker, sort_keys=True, indent=2))
    return commit_marker


def promote_generation(
    *,
    stem: Path,
    generation_id: str,
    json_final: Path,
    md_final: Path,
) -> None:
    """V1: update active pointer then promote staged files to bare finals."""
    json_staging, md_staging, commit_marker, active = staged_paths(stem, generation_id)
    if not commit_marker.exists():
        raise CustomQAArtifactCommitError(
            "Commit marker missing before promote",
            error_context={"generation_id": generation_id},
        )
    try:
        _atomic_write_text(active, generation_id + "\n")
        os.replace(str(json_staging), str(json_final))
        os.replace(str(md_staging), str(md_final))
        _fsync_path(json_final)
        _fsync_path(md_final)
    except Exception as exc:
        raise CustomQAArtifactCommitError(
            f"Artifact commit failed: {exc}",
            error_context={"generation_id": generation_id},
        ) from exc


def promote_generation_v2(
    *,
    stem: Path,
    generation_id: str,
    json_staging: Path,
    md_staging: Path,
    questions_metadata: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path | None]:
    """V2: promote staging → generation-named files, then flip active.

    Returns (json_gen, md_gen, metadata_gen_or_none).
    """
    json_gen, md_gen, meta_gen = generation_paths(stem, generation_id)
    _, _, commit_marker, active = staged_paths(stem, generation_id)
    if not commit_marker.exists():
        raise CustomQAArtifactCommitError(
            "Commit marker missing before promote",
            error_context={"generation_id": generation_id},
        )
    try:
        os.replace(str(json_staging), str(json_gen))
        os.replace(str(md_staging), str(md_gen))
        _fsync_path(json_gen)
        _fsync_path(md_gen)
        meta_path: Path | None = None
        if questions_metadata is not None:
            write_json(str(meta_gen), questions_metadata)
            _fsync_path(meta_gen)
            meta_path = meta_gen
        # Active last — generation files are already durable
        _atomic_write_text(active, generation_id + "\n")
        return json_gen, md_gen, meta_path
    except Exception as exc:
        raise CustomQAArtifactCommitError(
            f"Artifact commit failed: {exc}",
            error_context={"generation_id": generation_id},
        ) from exc


def _best_effort_aliases(
    *,
    stem: Path,
    json_gen: Path,
    md_gen: Path,
    json_alias: Path,
    md_alias: Path,
) -> int:
    """Copy generation files to bare aliases. Failures are warnings only."""
    warnings = 0
    try:
        write_text(str(json_alias), json_gen.read_text(encoding="utf-8"))
        _fsync_path(json_alias)
    except Exception as exc:
        warnings += 1
        logger.warning(
            "custom_qa alias update failed for %s: %s", json_alias.name, exc
        )
    try:
        write_text(str(md_alias), md_gen.read_text(encoding="utf-8"))
        _fsync_path(md_alias)
    except Exception as exc:
        warnings += 1
        logger.warning("custom_qa alias update failed for %s: %s", md_alias.name, exc)
    return warnings


def commit_llm_custom_qa_artifacts(
    *,
    stem: Path,
    json_final: Path,
    md_final: Path,
    payload: dict[str, Any],
    markdown: str,
    generation_id: str | None = None,
    run_execution_id: str | None = None,
    questions_metadata: dict[str, Any] | None = None,
    sweep_orphans: bool = True,
    force_protocol: str | None = None,
) -> str:
    """Full staging → commit marker → active → promote (+ optional orphan sweep).

    Protocol is selected by activation (or ``force_protocol`` in {"v1","v2"}).
    Alias failures under v2 are warnings only.
    """
    from transcriptx.core.utils.run_writer_locks import (
        LockAcquisitionError,
        assert_lease_for_run,
        get_bound_run_writer_lease,
        per_run_lock,
    )

    gid = generation_id or allocate_generation_id()
    run_dir = stem.parent
    lock_root = run_dir
    if run_dir.name == "global" and run_dir.parent.name == "data":
        lock_root = run_dir.parent.parent.parent

    use_v2 = (
        force_protocol == "v2"
        if force_protocol in ("v1", "v2")
        else is_v2_execution_enabled()
    )

    def _commit_body() -> int:
        alias_warnings = 0
        json_staging, md_staging = write_staged_artifacts(
            stem=stem,
            generation_id=gid,
            payload=payload,
            markdown=markdown,
        )
        if use_v2:
            json_gen, md_gen, meta_gen = generation_paths(stem, gid)
            meta_sha: str | None = None
            meta_name: str | None = None
            if questions_metadata is not None:
                meta_name = meta_gen.name
                meta_sha = sha256_text(
                    json.dumps(questions_metadata, sort_keys=True, ensure_ascii=False)
                )
            write_commit_marker(
                stem=stem,
                generation_id=gid,
                json_staging=json_staging,
                md_staging=md_staging,
                commit_marker_schema_version=COMMIT_MARKER_SCHEMA_VERSION_V2,
                run_execution_id=run_execution_id,
                json_name=json_gen.name,
                md_name=md_gen.name,
                questions_metadata_name=meta_name,
                questions_metadata_sha256=meta_sha,
            )
            json_auth, md_auth, _ = promote_generation_v2(
                stem=stem,
                generation_id=gid,
                json_staging=json_staging,
                md_staging=md_staging,
                questions_metadata=questions_metadata,
            )
            alias_warnings = _best_effort_aliases(
                stem=stem,
                json_gen=json_auth,
                md_gen=md_auth,
                json_alias=json_final,
                md_alias=md_final,
            )
            _ = alias_warnings
        else:
            write_commit_marker(
                stem=stem,
                generation_id=gid,
                json_staging=json_staging,
                md_staging=md_staging,
                commit_marker_schema_version=COMMIT_MARKER_SCHEMA_VERSION_V1,
                run_execution_id=run_execution_id,
            )
            promote_generation(
                stem=stem,
                generation_id=gid,
                json_final=json_final,
                md_final=md_final,
            )
        if sweep_orphans:
            sweep_orphan_staging(stem, keep_generation_id=gid)
        return alias_warnings

    try:
        lease = get_bound_run_writer_lease()
        if lease is not None:
            try:
                assert_lease_for_run(lease, lock_root)
            except LockAcquisitionError:
                lease = None
            else:
                _commit_body()
                return gid
        with per_run_lock(lock_root):
            _commit_body()
    except CustomQAArtifactCommitError:
        cleanup_failed_generation(stem=stem, generation_id=gid)
        raise
    except Exception as exc:
        cleanup_failed_generation(stem=stem, generation_id=gid)
        raise CustomQAArtifactCommitError(
            f"Artifact commit failed: {exc}",
            error_context={"generation_id": gid},
        ) from exc
    return gid


def read_active_generation_id(stem: Path) -> Optional[str]:
    active = Path(f"{stem}.active")
    if not active.exists():
        return None
    text = active.read_text(encoding="utf-8").strip()
    return text or None


def commit_marker_consistent(stem: Path, generation_id: str) -> bool:
    """Return True if commit marker hashes match generation or final content."""
    json_staging, md_staging, commit_marker, _ = staged_paths(stem, generation_id)
    if not commit_marker.exists():
        return False
    try:
        marker = json.loads(commit_marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    version = str(
        marker.get("commit_marker_schema_version") or COMMIT_MARKER_SCHEMA_VERSION_V1
    )
    json_gen, md_gen, _ = generation_paths(stem, generation_id)
    if version == COMMIT_MARKER_SCHEMA_VERSION_V2:
        candidates_json = [json_gen, json_staging]
        candidates_md = [md_gen, md_staging]
    else:
        candidates_json = [
            Path(f"{stem}.json"),
            json_gen,
            json_staging,
        ]
        candidates_md = [
            Path(f"{stem}.md"),
            md_gen,
            md_staging,
        ]
    # Prefer names listed in marker when present
    json_name = marker.get("json_name")
    md_name = marker.get("md_name")
    if isinstance(json_name, str) and json_name:
        named = stem.parent / json_name
        if named.exists():
            candidates_json.insert(0, named)
    if isinstance(md_name, str) and md_name:
        named = stem.parent / md_name
        if named.exists():
            candidates_md.insert(0, named)

    json_path = next((p for p in candidates_json if p.exists()), None)
    md_path = next((p for p in candidates_md if p.exists()), None)
    if json_path is None or md_path is None:
        return False
    try:
        jh = sha256_text(json_path.read_text(encoding="utf-8"))
        mh = sha256_text(md_path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return jh == marker.get("json_sha256") and mh == marker.get("md_sha256")


def analytical_artifacts_readable(
    *,
    stem: Path,
    module_succeeded: bool,
) -> bool:
    """Readers accept artifacts only if module success AND commit consistency."""
    if not module_succeeded:
        return False
    gid = read_active_generation_id(stem)
    if gid is None:
        return False
    return commit_marker_consistent(stem, gid)


def cleanup_failed_generation(*, stem: Path, generation_id: str) -> None:
    json_staging, md_staging, commit_marker, _ = staged_paths(stem, generation_id)
    json_gen, md_gen, meta_gen = generation_paths(stem, generation_id)
    for path in (
        json_staging,
        md_staging,
        commit_marker,
        json_gen,
        md_gen,
        meta_gen,
        Path(str(meta_gen) + ".staging"),
    ):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def _generation_id_from_commit_name(stem_name: str, path_name: str) -> str | None:
    """Exact parse: ``{stem}.commit.{gid}`` → gid; else None."""
    prefix = f"{stem_name}.commit."
    if not path_name.startswith(prefix):
        return None
    gid = path_name[len(prefix) :]
    return gid or None


def _generation_id_from_staging_name(stem_name: str, path_name: str) -> str | None:
    """Exact parse: ``{stem}.{json|md}.staging.{gid}`` → gid."""
    for kind in ("json", "md"):
        prefix = f"{stem_name}.{kind}.staging."
        if path_name.startswith(prefix):
            gid = path_name[len(prefix) :]
            return gid or None
    return None


def sweep_orphan_staging(
    stem: Path,
    *,
    keep_generation_id: str | None = None,
    rollback_generation_ids: frozenset[str] | set[str] | None = None,
) -> int:
    """Delete staging/commit files for other generations. Returns count removed.

    Preserves ``keep_generation_id`` and any ``rollback_generation_ids``.
    Generation IDs are matched by exact suffix parse — never substring search.
    """
    parent = stem.parent
    prefix = stem.name
    keep: set[str] = set()
    if keep_generation_id:
        keep.add(keep_generation_id)
    if rollback_generation_ids:
        keep.update(rollback_generation_ids)
    active_gid = read_active_generation_id(stem)
    if active_gid:
        keep.add(active_gid)

    removed = 0
    for path in parent.glob(f"{prefix}.*.staging.*"):
        gid = _generation_id_from_staging_name(prefix, path.name)
        if gid is not None and gid in keep:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    for path in parent.glob(f"{prefix}.commit.*"):
        gid = _generation_id_from_commit_name(prefix, path.name)
        if gid is not None and gid in keep:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
