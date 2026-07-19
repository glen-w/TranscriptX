"""Validating resolver for committed group LLM synthesis artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.group_llm_synthesis.digests import (
    compute_input_digests,
    sha256_file,
)
from transcriptx.core.analysis.group_llm_synthesis.generation import (
    read_active,
    read_commit,
)
from transcriptx.core.analysis.group_llm_synthesis.paths import (
    generation_dir,
    global_collect_path,
    global_summary_rel,
    speaker_index_rel,
    speaker_rows_path,
)
from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    SCHEMA_ACTIVE,
    SCHEMA_COMMIT,
    SCHEMA_GLOBAL,
    SCHEMA_SPEAKER,
    SCHEMA_SPEAKER_INDEX,
)


@dataclass
class ResolverCache:
    """Per-request cache of validated ACTIVE/COMMIT metadata."""

    active: dict[str, Any] | None = None
    commit: dict[str, Any] | None = None
    generation_id: str | None = None
    inventory: dict[str, dict[str, Any]] = field(default_factory=dict)
    valid: bool = False


def is_group_run(run_root: Path) -> bool:
    return (Path(run_root) / "group_run_metadata.json").is_file()


def _containment_ok(base: Path, target: Path) -> bool:
    try:
        resolved = target.resolve()
        resolved.relative_to(base.resolve())
        return True
    except Exception:
        return False


def load_commit_cache(run_root: Path, cache: ResolverCache) -> bool:
    if cache.valid:
        return True
    active = read_active(run_root)
    if not active or active.get("schema_id") != SCHEMA_ACTIVE:
        return False
    overall = active.get("overall_status")
    if overall not in {"success", "partial", "failed", "skipped"}:
        return False
    generation_id = str(active.get("generation_id") or "")
    if not generation_id:
        return False
    commit = read_commit(run_root, generation_id)
    if not commit or commit.get("schema_id") != SCHEMA_COMMIT:
        return False
    if str(commit.get("generation_id") or "") != generation_id:
        return False
    live = compute_input_digests(
        global_collect_path=global_collect_path(run_root),
        speaker_rows_path=speaker_rows_path(run_root),
    )
    for key in (
        "global_collect_sha256",
        "speaker_rows_sha256",
        "combined_input_digest",
    ):
        if active.get(key) != live.as_dict()[key]:
            return False
        if commit.get(key) != live.as_dict()[key]:
            return False
    inventory: dict[str, dict[str, Any]] = {}
    for entry in commit.get("artifacts") or []:
        if isinstance(entry, dict) and entry.get("rel_path"):
            inventory[str(entry["rel_path"])] = entry
    cache.active = active
    cache.commit = commit
    cache.generation_id = generation_id
    cache.inventory = inventory
    cache.valid = True
    return True


def _load_artifact(
    run_root: Path,
    rel_path: str,
    *,
    expected_schema: str,
    cache: ResolverCache,
) -> dict[str, Any] | None:
    if not load_commit_cache(run_root, cache):
        return None
    assert cache.generation_id is not None
    inv = cache.inventory.get(rel_path)
    if not inv:
        return None
    gen = generation_dir(run_root, cache.generation_id)
    path = gen / rel_path
    if not path.is_file():
        return None
    if not _containment_ok(gen, path):
        return None
    if path.is_symlink():
        # Resolve and re-check containment
        if not _containment_ok(gen, path.resolve()):
            return None
    digest = sha256_file(path)
    if digest != inv.get("sha256"):
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_id") != expected_schema:
        return None
    if str(payload.get("generation_id") or "") != cache.generation_id:
        return None
    for key in (
        "global_collect_sha256",
        "speaker_rows_sha256",
        "combined_input_digest",
    ):
        if payload.get(key) != (cache.commit or {}).get(key):
            return None
    return payload


def load_group_llm_summary(
    run_root: Path,
    *,
    cache: ResolverCache | None = None,
) -> dict[str, Any] | None:
    """Return global synth payload only when status allows display."""
    cache = cache or ResolverCache()
    if not load_commit_cache(run_root, cache):
        return None
    if (cache.active or {}).get("overall_status") not in {"success", "partial"}:
        # Still allow global success artifact when overall partial
        pass
    payload = _load_artifact(
        run_root,
        global_summary_rel(),
        expected_schema=SCHEMA_GLOBAL,
        cache=cache,
    )
    if not payload:
        return None
    if not str(payload.get("summary") or "").strip():
        return None
    return payload


def load_group_speaker_index(
    run_root: Path,
    *,
    cache: ResolverCache | None = None,
) -> dict[str, Any] | None:
    cache = cache or ResolverCache()
    return _load_artifact(
        run_root,
        speaker_index_rel(),
        expected_schema=SCHEMA_SPEAKER_INDEX,
        cache=cache,
    )


def load_group_speaker_summary(
    run_root: Path,
    rel_json: str,
    *,
    cache: ResolverCache | None = None,
) -> dict[str, Any] | None:
    cache = cache or ResolverCache()
    return _load_artifact(
        run_root,
        rel_json,
        expected_schema=SCHEMA_SPEAKER,
        cache=cache,
    )


def load_text_under_generation(
    run_root: Path,
    rel_path: str,
    *,
    cache: ResolverCache | None = None,
) -> str | None:
    cache = cache or ResolverCache()
    if not load_commit_cache(run_root, cache):
        return None
    assert cache.generation_id is not None
    inv = cache.inventory.get(rel_path)
    if not inv:
        return None
    gen = generation_dir(run_root, cache.generation_id)
    path = gen / rel_path
    if not path.is_file() or not _containment_ok(gen, path):
        return None
    if sha256_file(path) != inv.get("sha256"):
        return None
    return path.read_text(encoding="utf-8", errors="ignore")
