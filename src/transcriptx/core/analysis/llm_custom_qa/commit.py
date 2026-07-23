"""Generation staging + commit-marker protocol for llm_custom_qa artifacts."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.errors import CustomQAArtifactCommitError
from transcriptx.core.analysis.llm_support.hashing import sha256_text
from transcriptx.core.utils.artifact_writer import write_json, write_text


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
) -> Path:
    _, _, commit_marker, _ = staged_paths(stem, generation_id)
    marker = {
        "generation_id": generation_id,
        "json_sha256": sha256_text(json_staging.read_text(encoding="utf-8")),
        "md_sha256": sha256_text(md_staging.read_text(encoding="utf-8")),
        "json_name": json_staging.name,
        "md_name": md_staging.name,
    }
    _atomic_write_text(commit_marker, json.dumps(marker, sort_keys=True, indent=2))
    return commit_marker


def promote_generation(
    *,
    stem: Path,
    generation_id: str,
    json_final: Path,
    md_final: Path,
) -> None:
    """Update active pointer then promote staged files to finals."""
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


def commit_llm_custom_qa_artifacts(
    *,
    stem: Path,
    json_final: Path,
    md_final: Path,
    payload: dict[str, Any],
    markdown: str,
    generation_id: str | None = None,
) -> str:
    """Full staging → validate hashes → commit marker → active → promote."""
    from transcriptx.core.utils.run_writer_locks import per_run_lock

    gid = generation_id or allocate_generation_id()
    run_dir = stem.parent
    # Prefer locking the run root (two levels up from data/global when present).
    lock_root = run_dir
    if run_dir.name == "global" and run_dir.parent.name == "data":
        lock_root = run_dir.parent.parent.parent
    try:
        with per_run_lock(lock_root):
            json_staging, md_staging = write_staged_artifacts(
                stem=stem,
                generation_id=gid,
                payload=payload,
                markdown=markdown,
            )
            write_commit_marker(
                stem=stem,
                generation_id=gid,
                json_staging=json_staging,
                md_staging=md_staging,
            )
            promote_generation(
                stem=stem,
                generation_id=gid,
                json_final=json_final,
                md_final=md_final,
            )
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
    """Return True if commit marker hashes match staged-or-final content names."""
    json_staging, md_staging, commit_marker, _ = staged_paths(stem, generation_id)
    if not commit_marker.exists():
        return False
    try:
        marker = json.loads(commit_marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    # After promote, finals should match marker hashes.
    parent = stem.parent
    json_final = parent / marker.get("json_name", "").replace(
        f".staging.{generation_id}", ""
    )
    # Prefer explicit finals next to stem
    candidates_json = [
        Path(f"{stem}.json"),
        json_staging,
    ]
    candidates_md = [
        Path(f"{stem}.md"),
        md_staging,
    ]
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
        # Fallback: finals exist without pointer ⇒ treat as missing per contract
        return False
    return commit_marker_consistent(stem, gid)


def cleanup_failed_generation(*, stem: Path, generation_id: str) -> None:
    json_staging, md_staging, commit_marker, _ = staged_paths(stem, generation_id)
    for path in (json_staging, md_staging, commit_marker):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def sweep_orphan_staging(stem: Path, *, keep_generation_id: str | None = None) -> int:
    """Delete staging/commit files for other generations. Returns count removed."""
    parent = stem.parent
    prefix = stem.name
    removed = 0
    for path in parent.glob(f"{prefix}.*.staging.*"):
        if keep_generation_id and keep_generation_id in path.name:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    for path in parent.glob(f"{prefix}.commit.*"):
        if keep_generation_id and path.name.endswith(keep_generation_id):
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
