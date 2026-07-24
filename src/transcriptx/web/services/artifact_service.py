"""
Artifact-centric service layer for the TranscriptX dashboard.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.core.pipeline.manifest_loader import (
    load_artifact_manifest,
    load_group_member_runs,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.web.models.artifact import (
    Artifact,
    ArtifactFilters,
    filter_artifacts,
)

logger = get_logger()

# Canonical user-facing report artifact names (run root).
USER_REPORT_JSON = "report.json"
USER_REPORT_MD = "report.md"
USER_REPORT_TXT = "report.txt"

MAX_INLINE_HTML_BYTES = 5 * 1024 * 1024
MAX_FULLSCREEN_HTML_BYTES = 10 * 1024 * 1024


class ArtifactService:
    """Service for run and artifact access."""

    @staticmethod
    def _load_manifest(run_dir: Path) -> Optional[Dict]:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            mtime = manifest_path.stat().st_mtime
            return _cached_manifest(str(manifest_path), mtime)
        except Exception as exc:
            logger.warning(f"Failed to load manifest: {exc}")
            return None

    @staticmethod
    def _artifact_base_path(run_root: Path, artifact: Artifact) -> Path:
        from transcriptx.export.paths import artifact_base_path

        return artifact_base_path(run_root, artifact)

    @staticmethod
    def _resolve_safe_path(base_dir: Path, rel_path: str) -> Optional[Path]:
        from transcriptx.export.paths import resolve_safe_path

        return resolve_safe_path(base_dir, rel_path)

    @staticmethod
    def _group_run_modules_enabled(run_root: Path) -> List[str]:
        """Modules selected for this group run (for richer merged-artifact manifest metadata)."""
        meta_path = run_root / "group_run_metadata.json"
        if not meta_path.exists():
            return []
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        raw = meta.get("selected_modules")
        if not isinstance(raw, list):
            return []
        return [str(x) for x in raw if x is not None]

    @staticmethod
    def _merge_group_member_artifacts(run_root: Path) -> List[Artifact]:
        """Attach artifacts from each member's transcript run (group analysis)."""
        members = load_group_member_runs(run_root / "group_member_runs.json")
        if not members:
            return []
        modules_enabled = ArtifactService._group_run_modules_enabled(run_root)
        merged: List[Artifact] = []
        for m in members:
            if not isinstance(m, dict):
                continue
            out_dir = m.get("output_dir")
            if not out_dir:
                continue
            p = Path(str(out_dir))
            if not p.is_dir():
                continue
            run_id = str(m.get("run_id") or p.name)
            transcript_key = str(m.get("transcript_key") or "unknown")
            try:
                man = build_output_manifest(p, run_id, transcript_key, modules_enabled)
            except Exception:
                continue
            label = Path(str(m.get("transcript_path") or "session")).stem
            order = m.get("order_index", 0)
            base_root = str(p.resolve())
            for item in man.get("artifacts", []):
                d = dict(item)
                orig_id = str(d.get("id", ""))
                d["id"] = hashlib.sha1(
                    f"{order}|{orig_id}|{d.get('rel_path', '')}".encode("utf-8")
                ).hexdigest()
                title = d.get("title") or d.get("rel_path", "")
                d["title"] = f"{label}: {title}"
                tags = list(d.get("tags") or [])
                tags.append("member_session")
                d["tags"] = sorted(set(tags))
                d["storage_root"] = base_root
                if not d.get("slice_id"):
                    d["slice_id"] = f"member_{order}"
                merged.append(Artifact.from_dict(d))
        return merged

    @staticmethod
    def _artifacts_for_export(
        run_root: Path, artifact_ids: List[str]
    ) -> List[Artifact]:
        """Resolve export selection, augmenting full exports with a fresh disk scan."""
        catalog = ArtifactService.list_artifacts(run_root)
        by_id = {artifact.id: artifact for artifact in catalog}
        selected = [
            by_id[artifact_id] for artifact_id in artifact_ids if artifact_id in by_id
        ]
        if not selected:
            return []

        if set(artifact_ids) != set(by_id.keys()):
            return selected

        try:
            fresh_manifest = build_output_manifest(
                run_root, run_root.name, "unknown", []
            )
            fresh_artifacts = [
                Artifact.from_dict(item)
                for item in fresh_manifest.get("artifacts", [])
                if isinstance(item, dict)
            ]
        except Exception:
            fresh_artifacts = []

        by_rel = {artifact.rel_path: artifact for artifact in catalog}
        for artifact in fresh_artifacts:
            by_rel.setdefault(artifact.rel_path, artifact)
        return list(by_rel.values())

    @staticmethod
    def list_artifacts(
        run_root: Path, filters: Optional[ArtifactFilters] = None
    ) -> List[Artifact]:
        manifest_path = run_root / "manifest.json"
        mtime = manifest_path.stat().st_mtime if manifest_path.exists() else 0
        artifacts_payload = _cached_artifacts(str(run_root), mtime)
        artifacts = [Artifact.from_dict(item) for item in artifacts_payload]
        member_runs_path = run_root / "group_member_runs.json"
        if member_runs_path.exists():
            artifacts.extend(
                _cached_group_member_artifacts(
                    str(run_root), member_runs_path.stat().st_mtime
                )
            )
        from transcriptx.core.analysis.topic_shift.visibility import (
            suppress_topic_shift_surface_artifacts,
        )

        artifacts = suppress_topic_shift_surface_artifacts(artifacts, run_root=run_root)
        return filter_artifacts(artifacts, filters)

    @staticmethod
    def get_artifact_bytes(run_root: Path, artifact_id: str) -> Optional[bytes]:
        artifacts = ArtifactService.list_artifacts(run_root)
        match = next((a for a in artifacts if a.id == artifact_id), None)
        if not match:
            return None
        path = ArtifactService.resolve_artifact_source_path(run_root, match)
        if path is None or not path.exists():
            return None
        return path.read_bytes()

    @staticmethod
    def resolve_artifact_source_path(
        run_root: Path, artifact: Artifact
    ) -> Optional[Path]:
        """Resolve and safety-check the on-disk source path for an artifact."""
        from transcriptx.export.paths import (
            resolve_artifact_source_path as resolve_path,
        )

        return resolve_path(run_root, artifact)

    @staticmethod
    def read_for_download(path: Path, max_size: int = 500_000_000) -> bytes:
        size = path.stat().st_size
        if size > max_size:
            raise ValueError("File exceeds download size limit.")
        return path.read_bytes()

    @staticmethod
    def generate_thumbnail(run_root: Path, artifact: Artifact) -> Optional[Path]:
        if artifact.kind != "chart_static":
            return None
        source = ArtifactService.resolve_artifact_source_path(run_root, artifact)
        if source is None or not source.exists():
            return None
        from transcriptx.core.utils.run_writer_locks import per_run_lock

        with per_run_lock(run_root):
            thumb_dir = source.parent / ".thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = thumb_dir / source.name
            if thumb_path.exists():
                return thumb_path
            try:
                from PIL import Image

                with Image.open(source) as img:
                    # Use higher resolution and high-quality resampling for crisp thumbnails
                    img.thumbnail((1024, 768), resample=Image.Resampling.LANCZOS)
                    # Save with high quality settings
                    if thumb_path.suffix.lower() in (".jpg", ".jpeg"):
                        img.save(thumb_path, quality=95, optimize=True)
                    else:
                        img.save(thumb_path, optimize=True)
                return thumb_path
            except Exception as exc:
                logger.warning(f"Failed to generate thumbnail: {exc}")
                return None

    @staticmethod
    def load_html_artifact(
        run_root: Path, artifact: Artifact
    ) -> Optional[Dict[str, object]]:
        if artifact.kind != "chart_dynamic":
            return None
        path = ArtifactService.resolve_artifact_source_path(run_root, artifact)
        if path is None or not path.exists():
            return None
        size = path.stat().st_size
        content = path.read_text(encoding="utf-8", errors="ignore")
        return {"content": content, "bytes": size, "path": path}

    @staticmethod
    def check_run_health(run_root: Path) -> Dict[str, object]:
        """
        Return artifact-health status only.

        This reflects filesystem/output completeness for artifacts, not canonical
        execution truth from run_results.json.
        """
        run_dir = run_root
        manifest = ArtifactService._load_manifest(run_dir)
        manifest_path = run_dir / "manifest.json"
        manifest_mtime = manifest_path.stat().st_mtime if manifest_path.exists() else 0
        return _cached_health(str(run_root), manifest_mtime, bool(manifest))


def clear_artifact_caches() -> None:
    """Invalidate artifact/health caches only (avoids nuking all app caches)."""
    _cached_manifest.clear()  # type: ignore[attr-defined]
    _cached_artifacts.clear()  # type: ignore[attr-defined]
    _cached_health.clear()  # type: ignore[attr-defined]
    _cached_group_member_artifacts.clear()  # type: ignore[attr-defined]
    from transcriptx.web.services.artifact_index import _cached_artifact_index

    _cached_artifact_index.clear()  # type: ignore[attr-defined]


@st.cache_data(show_spinner=False)
def _cached_group_member_artifacts(
    run_root: str, member_runs_mtime: float
) -> List[Artifact]:
    """Merged group-member artifacts (rebuilds member manifests; expensive uncached)."""
    return ArtifactService._merge_group_member_artifacts(Path(run_root))


@st.cache_data(show_spinner=False)
def _cached_manifest(manifest_path: str, mtime: float) -> Optional[Dict]:
    try:
        return load_artifact_manifest(manifest_path)
    except Exception as exc:
        logger.warning(f"Failed to read manifest: {exc}")
        return None


@st.cache_data(show_spinner=False)
def _cached_artifacts(run_root: str, manifest_mtime: float) -> List[Dict]:
    run_dir = Path(run_root)
    manifest = None
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        manifest = _cached_manifest(str(manifest_path), manifest_mtime)
    if manifest is None:
        manifest = build_output_manifest(
            run_dir=run_dir,
            run_id=run_dir.name,
            transcript_key="unknown",
            modules_enabled=[],
        )
    return manifest.get("artifacts", [])


@st.cache_data(show_spinner=False)
def _cached_health(
    run_root: str, manifest_mtime: float, manifest_exists: bool
) -> Dict[str, object]:
    run_dir = Path(run_root)
    errors: List[str] = []
    warnings: List[str] = []

    is_group_run = (run_dir / "group_run_metadata.json").exists()

    if not manifest_exists:
        if is_group_run:
            warnings.append(
                "Artifact manifest (manifest.json) missing; UI will scan on-disk layout."
            )
        else:
            errors.append("Manifest missing or unreadable.")
    else:
        manifest_path = run_dir / "manifest.json"
        manifest = _cached_manifest(str(manifest_path), manifest_mtime) or {}
        if "schema_version" not in manifest or "run_id" not in manifest:
            errors.append("Manifest missing required fields.")

        artifacts_payload = manifest.get("artifacts", [])
        artifacts = [Artifact.from_dict(item) for item in artifacts_payload]
        has_transcript = any(a.kind == "transcript" for a in artifacts)
        if not has_transcript and not is_group_run:
            errors.append("Core transcript artifact missing.")

        for artifact in artifacts:
            path = ArtifactService._resolve_safe_path(run_dir, artifact.rel_path)
            if path is None or not path.exists():
                if artifact.kind == "transcript":
                    errors.append(f"Missing transcript file: {artifact.rel_path}")
                else:
                    warnings.append(f"Missing artifact: {artifact.rel_path}")
                continue
            if artifact.kind == "chart_dynamic":
                try:
                    path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    errors.append(f"Unreadable HTML: {artifact.rel_path}")
            if artifact.kind == "chart_static" and not artifact.preview:
                warnings.append(f"Missing preview thumbnail: {artifact.rel_path}")

        manifest_paths = {a.rel_path for a in artifacts}
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(run_dir).as_posix()
            if (
                rel == "manifest.json"
                or rel == "run_results.json"
                or rel.startswith(".transcriptx/")
            ):
                continue
            if "/.thumbnails/" in rel:
                continue
            if rel not in manifest_paths:
                warnings.append(f"Orphaned file: {rel}")

    status = "healthy"
    if errors:
        status = "error"
    elif warnings:
        status = "warning"

    return {"status": status, "errors": errors, "warnings": warnings}
