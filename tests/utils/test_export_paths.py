"""Unit tests for export path helpers (0.3.5 export polish)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.export.paths import (
    artifact_base_path,
    resolve_artifact_source_path,
    resolve_safe_path,
)
from transcriptx.web.models.artifact import Artifact


def _artifact(*, rel_path: str, storage_root: str | None = None) -> Artifact:
    return Artifact.from_dict(
        {
            "id": "a1",
            "kind": "data",
            "module": "stats",
            "scope": "global",
            "speaker": None,
            "subview": None,
            "slice_id": None,
            "rel_path": rel_path,
            "bytes": 0,
            "mtime": "2026-01-01T00:00:00Z",
            "mime": "application/json",
            "tags": [],
            "title": None,
            "storage_root": storage_root,
        }
    )


@pytest.mark.unit
def test_artifact_base_path_prefers_storage_root(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    storage = tmp_path / "external"
    storage.mkdir()
    art = _artifact(rel_path="x.json", storage_root=str(storage))
    assert artifact_base_path(root, art) == storage.resolve()
    art2 = _artifact(rel_path="x.json")
    assert artifact_base_path(root, art2) == root.resolve()


@pytest.mark.unit
def test_resolve_safe_path_rejects_traversal(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "ok.json").write_text("{}", encoding="utf-8")
    assert resolve_safe_path(base, "../outside.json") is None
    assert resolve_safe_path(base, "../../outside.json") is None
    ok = resolve_safe_path(base, "ok.json")
    assert ok is not None
    assert ok.name == "ok.json"


@pytest.mark.unit
def test_resolve_safe_path_attributeerror_startswith_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "file.json").write_text("{}", encoding="utf-8")

    def _boom(self, *_a, **_k):
        raise AttributeError("is_relative_to unavailable")

    monkeypatch.setattr(Path, "is_relative_to", _boom)
    out = resolve_safe_path(base, "file.json")
    assert out is not None
    assert out.name == "file.json"

    # startswith reject when candidate is outside base
    assert resolve_safe_path(base, "../outside.json") is None


@pytest.mark.unit
def test_resolve_artifact_source_path_exists_and_missing(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    data = run_root / "data"
    data.mkdir(parents=True)
    file_path = data / "stats.json"
    file_path.write_text("{}", encoding="utf-8")
    art = _artifact(rel_path="data/stats.json")
    assert resolve_artifact_source_path(run_root, art) == file_path.resolve()
    missing = _artifact(rel_path="data/missing.json")
    assert resolve_artifact_source_path(run_root, missing) is None
    bad = _artifact(rel_path="../escape.json")
    assert resolve_artifact_source_path(run_root, bad) is None


@pytest.mark.unit
def test_artifact_service_path_wrappers_delegate_to_export_paths(
    tmp_path: Path,
) -> None:
    """ArtifactService path helpers must stay thin wrappers over export.paths."""
    from transcriptx.web.services.artifact_service import ArtifactService

    run_root = tmp_path / "run"
    storage = tmp_path / "external"
    storage.mkdir()
    run_root.mkdir()
    (run_root / "ok.json").write_text("{}", encoding="utf-8")
    (storage / "ext.json").write_text("{}", encoding="utf-8")

    local = _artifact(rel_path="ok.json")
    external = _artifact(rel_path="ext.json", storage_root=str(storage))
    traversal = _artifact(rel_path="../escape.json")

    assert ArtifactService._artifact_base_path(run_root, local) == artifact_base_path(
        run_root, local
    )
    assert ArtifactService._artifact_base_path(
        run_root, external
    ) == artifact_base_path(run_root, external)

    assert ArtifactService._resolve_safe_path(run_root, "ok.json") == resolve_safe_path(
        run_root, "ok.json"
    )
    assert ArtifactService._resolve_safe_path(
        run_root, "../escape.json"
    ) == resolve_safe_path(run_root, "../escape.json")

    assert ArtifactService.resolve_artifact_source_path(
        run_root, local
    ) == resolve_artifact_source_path(run_root, local)
    assert ArtifactService.resolve_artifact_source_path(
        run_root, external
    ) == resolve_artifact_source_path(run_root, external)
    assert ArtifactService.resolve_artifact_source_path(
        run_root, traversal
    ) == resolve_artifact_source_path(run_root, traversal)
    assert ArtifactService.resolve_artifact_source_path(run_root, traversal) is None
