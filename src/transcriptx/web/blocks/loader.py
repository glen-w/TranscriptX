"""Thin artifact content loader wrapping ArtifactService."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services import ArtifactService


class ArtifactContentLoader:
    """Load JSON/text artifacts by module + suffix without duplicating manifest logic."""

    def __init__(
        self,
        run_root: Path,
        artifacts: tuple[Artifact, ...] | None = None,
    ) -> None:
        self._run_root = run_root
        self._artifacts = artifacts

    def _artifact_list(self) -> tuple[Artifact, ...]:
        if self._artifacts is not None:
            return self._artifacts
        return tuple(ArtifactService.list_artifacts(self._run_root))

    def _resolve_path(self, artifact: Artifact) -> Path | None:
        return ArtifactService.resolve_artifact_source_path(self._run_root, artifact)

    def find_artifact(
        self,
        module: str,
        *,
        kind: str,
        suffix: str,
        instance_id: str | None = None,
        storage_root: str | None = None,
        prefer_group_root: bool = False,
    ) -> Artifact | None:
        patterns = [suffix]
        if instance_id:
            stem, ext = suffix.rsplit(".", 1) if "." in suffix else (suffix, "")
            if ext:
                patterns.append(f"{stem}__{instance_id}.{ext}")
            else:
                patterns.append(f"{stem}__{instance_id}")
        candidates = [
            a
            for a in self._artifact_list()
            if a.module == module
            and a.kind == kind
            and any(a.rel_path.endswith(pattern) for pattern in patterns)
        ]
        if storage_root is not None:
            root = str(Path(storage_root).resolve())
            candidates = [
                a
                for a in candidates
                if a.storage_root and str(Path(a.storage_root).resolve()) == root
            ]
        elif prefer_group_root:
            group_only = [a for a in candidates if not a.storage_root]
            if group_only:
                candidates = group_only
        else:
            # Prefer group-root artifacts before member_session merges.
            candidates = sorted(
                candidates,
                key=lambda a: (1 if a.storage_root else 0, a.rel_path),
            )
        for match in candidates:
            return match
        return None

    def find_first_data_json(
        self,
        module: str,
        *,
        prefer_group_root: bool = False,
    ) -> Artifact | None:
        candidates = [
            a
            for a in self._artifact_list()
            if a.module == module and a.kind == "data_json"
        ]
        if prefer_group_root:
            group_only = [a for a in candidates if not a.storage_root]
            if group_only:
                candidates = group_only
        return candidates[0] if candidates else None

    def load_first_module_json(self, module: str) -> dict[str, Any] | None:
        match = self.find_first_data_json(module, prefer_group_root=True)
        if match is None:
            match = self.find_first_data_json(module)
        if match is None:
            return None
        path = self._resolve_path(match)
        if path is None or not path.exists():
            return None
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def load_json(
        self,
        module: str,
        suffix: str,
        *,
        instance_id: str | None = None,
        storage_root: str | None = None,
        prefer_group_root: bool = False,
    ) -> dict[str, Any] | None:
        match = self.find_artifact(
            module,
            kind="data_json",
            suffix=suffix,
            instance_id=instance_id,
            storage_root=storage_root,
            prefer_group_root=prefer_group_root,
        )
        if match is None:
            return None
        path = self._resolve_path(match)
        if path is None or not path.exists():
            return None
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def load_text(
        self,
        module: str,
        suffix: str,
        *,
        instance_id: str | None = None,
        storage_root: str | None = None,
        prefer_group_root: bool = False,
    ) -> str | None:
        match = self.find_artifact(
            module,
            kind="data_txt",
            suffix=suffix,
            instance_id=instance_id,
            storage_root=storage_root,
            prefer_group_root=prefer_group_root,
        )
        if match is None:
            return None
        path = self._resolve_path(match)
        if path is None or not path.exists():
            return None
        return cast(str, path.read_text(encoding="utf-8", errors="ignore"))
