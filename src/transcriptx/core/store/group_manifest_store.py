"""Atomic storage for file-backed group manifests."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import NAMESPACE_URL, uuid4, uuid5

from transcriptx.core.domain.group import Group, GroupMember
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import PATHS

logger = get_logger()
_GROUPS_DIR = PATHS.data_dir / "groups"
_TRANSCRIPTS_DIR = Path(PATHS.transcripts_dir)


def groups_dir() -> Path:
    return _GROUPS_DIR


def manifest_path_for(group_id: str) -> Path:
    return groups_dir() / f"{group_id}.group.json"


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _project_relative_path(value: str | Path) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        resolved_candidates = [
            (PATHS.project_root / path).resolve(),
            (_TRANSCRIPTS_DIR / path).resolve(),
            (_GROUPS_DIR.parent / path).resolve(),
        ]
        path = next(
            (p for p in resolved_candidates if p.exists()), resolved_candidates[0]
        )
    else:
        path = path.resolve()
    if not path.exists():
        raise ValueError(f"Transcript path does not exist: {value}")
    project_root_resolved = PATHS.project_root.resolve()
    transcripts_dir_resolved = _TRANSCRIPTS_DIR.resolve()
    groups_parent_resolved = _GROUPS_DIR.parent.resolve()
    for base in (
        project_root_resolved,
        transcripts_dir_resolved,
        groups_parent_resolved,
    ):
        try:
            rel = path.relative_to(base)
            return str(rel)
        except ValueError:
            continue
    raise ValueError(
        f"Transcript path must live under the project root or transcripts dir: {value}"
    )


def canonical_group_member_path(ref: str | Path) -> str:
    """Return a single transcript ref as a stable project-relative path."""
    return _project_relative_path(ref)


def canonicalize_group_member_paths(refs: Iterable[str | Path]) -> List[str]:
    """Resolve each ref to a stable project-relative path; dedupe while preserving order."""
    seen: set[str] = set()
    out: List[str] = []
    for ref in refs:
        rel = _project_relative_path(ref)
        if rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def _project_absolute_path(relative_path: str) -> Path:
    project_root_resolved = PATHS.project_root.resolve()
    transcripts_dir_resolved = _TRANSCRIPTS_DIR.resolve()
    groups_parent_resolved = _GROUPS_DIR.parent.resolve()
    for base in (
        project_root_resolved,
        transcripts_dir_resolved,
        groups_parent_resolved,
    ):
        path = (base / relative_path).resolve()
        if path.exists():
            return path
    raise ValueError(f"Member transcript path does not exist: {relative_path}")


class GroupManifestStore:
    """Single-writer storage for group manifests."""

    def list_manifest_paths(self) -> List[Path]:
        root = groups_dir()
        if not root.exists():
            return []
        return sorted(root.glob("*.group.json"))

    def read(self, path: str | Path) -> Optional[Dict[str, Any]]:
        path = Path(path)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Group manifest at {path} is not a JSON object")
        return data

    def _validate_payload(
        self, payload: Dict[str, Any], *, path: Path
    ) -> Dict[str, Any]:
        version = payload.get("version", 1)
        if int(version) != 1:
            raise ValueError(
                f"Unsupported group manifest version in {path}: {version!r}"
            )
        group_id = str(payload.get("group_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        description = payload.get("description")
        members_raw = payload.get("members")
        created_at = payload.get("created_at")
        updated_at = payload.get("updated_at")
        if not group_id:
            raise ValueError(f"Missing group_id in {path}")
        if not name:
            raise ValueError(f"Missing name in {path}")
        if not isinstance(members_raw, list) or not members_raw:
            raise ValueError(
                f"Group manifest in {path} must contain at least one member path"
            )
        members = []
        for member in members_raw:
            if not isinstance(member, str) or not member.strip():
                raise ValueError(f"Invalid member path in {path}: {member!r}")
            _project_absolute_path(member)  # validate path exists
            members.append(member.strip())
        if created_at is not None:
            created_at = str(created_at)
        if updated_at is not None:
            updated_at = str(updated_at)
        return {
            "version": 1,
            "group_id": group_id,
            "name": name,
            "description": description if description is None else str(description),
            "members": members,
            "created_at": created_at or _now_iso(),
            "updated_at": updated_at or _now_iso(),
        }

    def load(self, path: str | Path) -> Group:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        payload = self.read(path)
        if payload is None:
            raise FileNotFoundError(str(path))
        normalized = self._validate_payload(payload, path=path)
        return Group(
            group_id=normalized["group_id"],
            name=normalized["name"],
            description=normalized.get("description"),
            members=normalized["members"],
            created_at=normalized.get("created_at"),
            updated_at=normalized.get("updated_at"),
            version=int(normalized["version"]),
        )

    def load_by_id(self, group_id: str) -> Group:
        return self.load(manifest_path_for(group_id))

    def list_groups(self) -> List[Group]:
        groups: List[Group] = []
        for path in self.list_manifest_paths():
            groups.append(self.load(path))
        groups.sort(key=lambda g: (g.updated_at or "", g.name.lower()))
        return groups

    def list_groups_best_effort(self) -> tuple[List[Group], List[str]]:
        """Load all group manifests; skip invalid ones and record warnings."""
        groups: List[Group] = []
        warnings: List[str] = []
        for path in self.list_manifest_paths():
            try:
                groups.append(self.load(path))
            except Exception as exc:
                warnings.append(f"{path.name}: {exc}")
        groups.sort(key=lambda g: (g.updated_at or "", g.name.lower()))
        warnings.sort()
        return groups, warnings

    def write(self, group: Group, *, reason: str = "write", timeout: int = 15) -> Group:
        path = manifest_path_for(group.group_id)
        payload = group.to_manifest()
        with FileLock(path, timeout=timeout):
            _atomic_write(path, payload)
        logger.debug("Wrote group manifest %s for reason=%s", path, reason)
        return group

    def delete(self, group_id: str, *, timeout: int = 15) -> bool:
        path = manifest_path_for(group_id)
        if not path.exists():
            return False
        with FileLock(path, timeout=timeout):
            path.unlink(missing_ok=True)
        logger.debug("Deleted group manifest %s", path)
        return True

    def create_group(
        self,
        *,
        name: str,
        members: Iterable[str | Path],
        description: Optional[str] = None,
    ) -> Group:
        normalized_members = canonicalize_group_member_paths(members)
        if not normalized_members:
            raise ValueError("Group must contain at least one transcript path.")
        group = Group(
            group_id=str(uuid4()),
            name=name.strip(),
            description=(
                description.strip()
                if isinstance(description, str) and description.strip()
                else None
            ),
            members=normalized_members,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        self.write(group, reason="create")
        return group

    def update_group(
        self,
        group: Group,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        members: Optional[Iterable[str | Path]] = None,
    ) -> Group:
        updated = replace(
            group,
            name=name.strip() if isinstance(name, str) and name.strip() else group.name,
            description=(
                (
                    description.strip()
                    if isinstance(description, str) and description.strip()
                    else None
                )
                if description is not None
                else group.description
            ),
            members=(
                canonicalize_group_member_paths(members)
                if members is not None
                else group.members
            ),
            updated_at=_now_iso(),
        )
        self.write(updated, reason="update")
        return updated

    def resolve_group_members(self, group: Group) -> List[GroupMember]:
        members: List[GroupMember] = []
        for member_path in group.members:
            abs_path = _project_absolute_path(member_path)
            members.append(
                GroupMember(
                    file_path=str(abs_path),
                    file_name=abs_path.name,
                    uuid=str(uuid5(NAMESPACE_URL, str(abs_path))),
                )
            )
        return members

    def resolve_group_identifier(self, identifier: str) -> Group:
        candidate = Path(identifier).expanduser()
        if (
            candidate.exists()
            and candidate.suffix == ".json"
            and candidate.name.endswith(".group.json")
        ):
            return self.load(candidate)
        if candidate.exists() and candidate.name.endswith(".group.json"):
            return self.load(candidate)
        if candidate.exists() and candidate.is_file():
            raise ValueError(
                f"Group manifests must use the .group.json suffix: {candidate}"
            )
        if identifier.endswith(".group.json"):
            return self.load(Path(identifier))
        manifest = manifest_path_for(identifier)
        if manifest.exists():
            return self.load(manifest)
        raise ValueError(f"No group manifest found for identifier: {identifier}")
