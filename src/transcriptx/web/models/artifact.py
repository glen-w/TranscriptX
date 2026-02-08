"""
Artifact and run descriptor models for the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Preview:
    thumbnail: Optional[str] = None
    title: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Preview":
        return cls(
            thumbnail=data.get("thumbnail"),
            title=data.get("title"),
        )


@dataclass(frozen=True)
class Artifact:
    id: str
    kind: str
    module: Optional[str]
    scope: Optional[str]
    speaker: Optional[str]
    subview: Optional[str]
    slice_id: Optional[str]
    rel_path: str
    bytes: int
    mtime: str
    mime: str
    tags: List[str]
    title: Optional[str] = None
    produced_by: Optional[str] = None
    preview: Optional[Preview] = None
    meta: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Artifact":
        preview = data.get("preview")
        return cls(
            id=data["id"],
            kind=data["kind"],
            module=data.get("module"),
            scope=data.get("scope"),
            speaker=data.get("speaker"),
            subview=data.get("subview"),
            slice_id=data.get("slice_id"),
            rel_path=data["rel_path"],
            bytes=data.get("bytes", 0),
            mtime=data.get("mtime", ""),
            mime=data.get("mime", ""),
            tags=list(data.get("tags", [])),
            title=data.get("title"),
            produced_by=data.get("produced_by"),
            preview=Preview.from_dict(preview) if isinstance(preview, dict) else None,
            meta=data.get("meta") if isinstance(data.get("meta"), dict) else None,
        )

    def mtime_datetime(self) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(self.mtime.replace("Z", "+00:00"))
        except Exception:
            return None

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags


@dataclass(frozen=True)
class ArtifactFilters:
    module: Optional[str] = None
    scope: Optional[str] = None
    kind: Optional[str] = None
    speaker: Optional[str] = None
    subview: Optional[str] = None
    slice_id: Optional[str] = None
    tags: Optional[List[str]] = None

    def matches(self, artifact: Artifact) -> bool:
        if self.module and artifact.module != self.module:
            return False
        if self.scope and artifact.scope != self.scope:
            return False
        if self.kind and artifact.kind != self.kind:
            return False
        if self.speaker and artifact.speaker != self.speaker:
            return False
        if self.subview and artifact.subview != self.subview:
            return False
        if self.slice_id and artifact.slice_id != self.slice_id:
            return False
        if self.tags:
            for tag in self.tags:
                if tag not in artifact.tags:
                    return False
        return True


@dataclass(frozen=True)
class RunDescriptor:
    session: str
    run_id: str
    run_dir: Path
    manifest_path: Optional[Path]
    schema_version: Optional[int]
    run_metadata: Dict[str, Any]

    @classmethod
    def from_manifest(
        cls,
        session: str,
        run_id: str,
        run_dir: Path,
        manifest_path: Optional[Path],
        manifest: Optional[Dict[str, Any]],
    ) -> "RunDescriptor":
        schema_version = manifest.get("schema_version") if manifest else None
        run_metadata = manifest.get("run_metadata", {}) if manifest else {}
        return cls(
            session=session,
            run_id=run_id,
            run_dir=run_dir,
            manifest_path=manifest_path,
            schema_version=schema_version,
            run_metadata=run_metadata,
        )


def filter_artifacts(
    artifacts: Iterable[Artifact], filters: Optional[ArtifactFilters]
) -> List[Artifact]:
    if filters is None:
        return list(artifacts)
    return [artifact for artifact in artifacts if filters.matches(artifact)]
