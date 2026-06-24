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

    def find_artifact(
        self,
        module: str,
        *,
        kind: str,
        suffix: str,
        instance_id: str | None = None,
    ) -> Artifact | None:
        patterns = [suffix]
        if instance_id:
            stem, ext = suffix.rsplit(".", 1) if "." in suffix else (suffix, "")
            if ext:
                patterns.append(f"{stem}__{instance_id}.{ext}")
            else:
                patterns.append(f"{stem}__{instance_id}")
        for pattern in patterns:
            match = next(
                (
                    a
                    for a in self._artifact_list()
                    if a.module == module
                    and a.kind == kind
                    and a.rel_path.endswith(pattern)
                ),
                None,
            )
            if match is not None:
                return match
        return None

    def find_first_data_json(self, module: str) -> Artifact | None:
        for artifact in self._artifact_list():
            if artifact.module == module and artifact.kind == "data_json":
                return artifact
        return None

    def load_first_module_json(self, module: str) -> dict[str, Any] | None:
        match = self.find_first_data_json(module)
        if match is None:
            return None
        path = ArtifactService._resolve_safe_path(self._run_root, match.rel_path)
        if path is None or not path.exists():
            return None
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def load_json(
        self,
        module: str,
        suffix: str,
        *,
        instance_id: str | None = None,
    ) -> dict[str, Any] | None:
        match = self.find_artifact(
            module, kind="data_json", suffix=suffix, instance_id=instance_id
        )
        if match is None:
            return None
        path = ArtifactService._resolve_safe_path(self._run_root, match.rel_path)
        if path is None or not path.exists():
            return None
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def load_text(
        self,
        module: str,
        suffix: str,
        *,
        instance_id: str | None = None,
    ) -> str | None:
        match = self.find_artifact(
            module, kind="data_txt", suffix=suffix, instance_id=instance_id
        )
        if match is None:
            return None
        path = ArtifactService._resolve_safe_path(self._run_root, match.rel_path)
        if path is None or not path.exists():
            return None
        return cast(str, path.read_text(encoding="utf-8", errors="ignore"))
