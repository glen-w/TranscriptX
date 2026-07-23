"""Low-level read/write helpers for speaker_profiles canonical files."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from transcriptx.core.speaker_profiles.errors import (
    CorruptLinkError,
    SpeakerProfileContractError,
)
from transcriptx.core.speaker_profiles.hashing import sha256_bytes, sha256_file
from transcriptx.core.speaker_profiles.layout import (
    event_path,
    link_path,
    profile_path,
)
from transcriptx.core.speaker_profiles.models import (
    SpeakerProfileEventV1,
    SpeakerProfileLinkV1,
    SpeakerProfileOperationV1,
    SpeakerProfileV1,
)
from transcriptx.core.speaker_profiles.path_safety import (
    assert_not_symlink,
    assert_operation_path_under_root,
)
from transcriptx.io.atomic_json import strict_json_dumps, write_bytes_atomic

T = TypeVar("T", bound=BaseModel)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_layout(root: Path) -> None:
    for sub in ("profiles", "links", "events", "operations"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def dumps_model(model: BaseModel) -> bytes:
    return strict_json_dumps(model.model_dump(mode="python"), indent=2).encode("utf-8")


def write_bytes_under_root(path: Path, data: bytes, *, root: Path) -> str:
    """Atomic write; returns content sha256. Rejects symlink targets."""
    assert_operation_path_under_root(path, root, what="write path")
    if path.exists():
        assert_not_symlink(path, what="write path")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_atomic(path, data)
    return sha256_bytes(data)


def fsync_parent(path: Path) -> None:
    """Best-effort fsync of the parent directory after delete/replace."""
    parent = Path(path).parent
    try:
        fd = os.open(str(parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def delete_under_root(path: Path, *, root: Path) -> None:
    assert_operation_path_under_root(path, root, what="delete path")
    if path.exists():
        assert_not_symlink(path, what="delete path")
        path.unlink()
        fsync_parent(path)


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise SpeakerProfileContractError(f"invalid JSON at {path}: {exc}") from exc
    except OSError as exc:
        raise SpeakerProfileContractError(f"unreadable JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SpeakerProfileContractError(f"JSON root must be object: {path}")
    return data


def parse_model(model_type: type[T], path: Path) -> T:
    data = read_json_object(path)
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise SpeakerProfileContractError(
            f"invalid {model_type.__name__} at {path}: {exc}"
        ) from exc


def read_profile(profile_id: str, *, root: Path) -> SpeakerProfileV1 | None:
    path = profile_path(profile_id, root=root)
    if not path.is_file():
        return None
    return parse_model(SpeakerProfileV1, path)


def read_live_link(link_file_key: str, *, root: Path) -> SpeakerProfileLinkV1 | None:
    """Read live link or None if absent. Corrupt file → CorruptLinkError."""
    path = link_path(link_file_key, root=root)
    if not path.exists():
        return None
    if not path.is_file():
        raise CorruptLinkError(f"live link path is not a regular file: {path}")
    try:
        assert_not_symlink(path, what="live link")
        return parse_model(SpeakerProfileLinkV1, path)
    except SpeakerProfileContractError as exc:
        raise CorruptLinkError(f"corrupt live link at {path}: {exc}") from exc


def read_event(idempotency_id: str, *, root: Path) -> SpeakerProfileEventV1 | None:
    path = event_path(idempotency_id, root=root)
    if not path.is_file():
        return None
    return parse_model(SpeakerProfileEventV1, path)


def profile_content_sha256(profile_id: str, *, root: Path) -> str | None:
    return sha256_file(profile_path(profile_id, root=root))


def load_operation(path: Path) -> SpeakerProfileOperationV1:
    return parse_model(SpeakerProfileOperationV1, path)


def find_operations_by_idempotency_key(
    key: str, *, root: Path
) -> list[SpeakerProfileOperationV1]:
    ops_dir = root / "operations"
    if not ops_dir.is_dir():
        return []
    out: list[SpeakerProfileOperationV1] = []
    for path in sorted(ops_dir.glob("*.op.json")):
        try:
            op = load_operation(path)
        except SpeakerProfileContractError:
            continue
        if op.operation_idempotency_key == key:
            out.append(op)
    return out


def find_operation_by_idempotency_key(
    key: str, *, root: Path
) -> SpeakerProfileOperationV1 | None:
    ops = find_operations_by_idempotency_key(key, root=root)
    if not ops:
        return None
    # Prefer a completed receipt when multiple historical attempts share a key.
    for op in ops:
        if op.phase == "complete" and op.receipt is not None:
            return op
    return ops[-1]


def write_operation(op: SpeakerProfileOperationV1, *, root: Path) -> Path:
    from transcriptx.core.speaker_profiles.layout import operation_path

    path = operation_path(op.operation_id, root=root)
    write_bytes_under_root(path, dumps_model(op), root=root)
    return path
