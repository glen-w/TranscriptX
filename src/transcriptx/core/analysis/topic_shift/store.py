"""Deterministic generational store for topic_shift (emotion_family-style)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from transcriptx.io.atomic_json import write_json_atomic

INDEX_NAME = "artifact_index.json"
GENERATIONS = "generations"
INDEX_SCHEMA = "topic_shift_artifact_index_v1"


@dataclass
class TopicShiftArtifactIndex:
    module_id: str = "topic_shift"
    current_complete_generation: str | None = None
    latest_attempt_generation: str | None = None
    attempt_history: list[dict[str, Any]] | None = None
    schema_version: str = INDEX_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "current_complete_generation": self.current_complete_generation,
            "latest_attempt_generation": self.latest_attempt_generation,
            "attempt_history": list(self.attempt_history or []),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TopicShiftArtifactIndex":
        return cls(
            module_id=str(data.get("module_id") or "topic_shift"),
            current_complete_generation=data.get("current_complete_generation"),
            latest_attempt_generation=data.get("latest_attempt_generation"),
            attempt_history=list(data.get("attempt_history") or []),
            schema_version=str(data.get("schema_version") or INDEX_SCHEMA),
        )


def new_generation_id() -> str:
    return uuid.uuid4().hex


def content_digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def store_root(module_output_dir: Path) -> Path:
    return Path(module_output_dir) / ".topic_shift_generations"


def generation_dir(root: Path, generation_id: str) -> Path:
    return root / GENERATIONS / generation_id


def load_index(root: Path) -> TopicShiftArtifactIndex | None:
    path = root / INDEX_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return TopicShiftArtifactIndex.from_dict(data)


def save_index(root: Path, index: TopicShiftArtifactIndex) -> None:
    root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(root / INDEX_NAME, index.to_dict(), indent=2)


@dataclass
class StagedDeterministicGeneration:
    root: Path
    generation_id: str
    directory: Path
    inventory: dict[str, str]

    def write_json(self, name: str, payload: Any) -> Path:
        path = self.directory / name
        write_json_atomic(path, payload, indent=2)
        self.inventory[name] = content_digest(payload)
        return path


def begin_attempt(module_output_dir: Path) -> StagedDeterministicGeneration:
    root = store_root(module_output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / GENERATIONS).mkdir(parents=True, exist_ok=True)
    gid = new_generation_id()
    directory = generation_dir(root, gid)
    directory.mkdir(parents=True, exist_ok=True)

    index = load_index(root) or TopicShiftArtifactIndex()
    index.latest_attempt_generation = gid
    history = list(index.attempt_history or [])
    history.append({"generation_id": gid, "status": "started"})
    index.attempt_history = history[-50:]
    save_index(root, index)

    return StagedDeterministicGeneration(
        root=root, generation_id=gid, directory=directory, inventory={}
    )


def commit_and_activate(
    staged: StagedDeterministicGeneration,
    *,
    required_names: tuple[str, ...] = (
        "topic_shift.spans.json",
        "topic_shift.events.json",
        "topic_shift.stats.json",
    ),
) -> None:
    """COMMIT only when required files exist with non-empty digests; then ACTIVE."""
    for name in required_names:
        path = staged.directory / name
        if not path.is_file():
            raise RuntimeError(f"missing required artifact before COMMIT: {name}")
        digest = staged.inventory.get(name) or ""
        if not digest:
            raise RuntimeError(f"empty digest before COMMIT: {name}")

    commit = {
        "schema_version": "topic_shift_commit_v1",
        "generation_id": staged.generation_id,
        "inventory": dict(staged.inventory),
        "status": "complete",
    }
    write_json_atomic(staged.directory / "COMMIT.json", commit, indent=2)

    index = load_index(staged.root) or TopicShiftArtifactIndex()
    index.current_complete_generation = staged.generation_id
    index.latest_attempt_generation = staged.generation_id
    history = list(index.attempt_history or [])
    history.append({"generation_id": staged.generation_id, "status": "complete"})
    index.attempt_history = history[-50:]
    save_index(staged.root, index)

    # Stable convenience copies for discovery (active generation only)
    active_data = staged.directory.parent.parent  # .topic_shift_generations
    # Also mirror into module data/global via caller (OutputService)


def record_failed_attempt(module_output_dir: Path, generation_id: str | None) -> None:
    """Mark attempt failed without activating; keep prior current_complete."""
    root = store_root(module_output_dir)
    index = load_index(root) or TopicShiftArtifactIndex()
    if generation_id:
        index.latest_attempt_generation = generation_id
        history = list(index.attempt_history or [])
        history.append({"generation_id": generation_id, "status": "failed"})
        index.attempt_history = history[-50:]
    save_index(root, index)


def resolve_active_generation(module_output_dir: Path) -> Path | None:
    root = store_root(module_output_dir)
    index = load_index(root)
    if index is None or not index.current_complete_generation:
        return None
    # Suppress if latest attempt failed and differs from current complete
    if (
        index.latest_attempt_generation
        and index.latest_attempt_generation != index.current_complete_generation
    ):
        # Check history for failed latest
        for row in reversed(index.attempt_history or []):
            if row.get("generation_id") == index.latest_attempt_generation:
                if row.get("status") == "failed":
                    return None
                break
    path = generation_dir(root, index.current_complete_generation)
    if not (path / "COMMIT.json").is_file():
        return None
    return path
