"""
Artifact-centric service layer for the TranscriptX dashboard.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.web.models.artifact import (
    Artifact,
    ArtifactFilters,
    RunDescriptor,
    filter_artifacts,
)

logger = get_logger()

HARD_CAP_BYTES = 2 * 1024 * 1024 * 1024
MAX_INLINE_HTML_BYTES = 5 * 1024 * 1024
MAX_FULLSCREEN_HTML_BYTES = 10 * 1024 * 1024


class ArtifactService:
    """Service for run and artifact access."""

    @staticmethod
    def _resolve_run_dir(session: str, run_id: str) -> Path:
        return Path(OUTPUTS_DIR) / session / run_id

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
    def _resolve_safe_path(run_dir: Path, rel_path: str) -> Optional[Path]:
        if ".." in rel_path.split("/"):
            return None
        candidate = (run_dir / rel_path).resolve()
        try:
            if not candidate.is_relative_to(run_dir.resolve()):
                return None
        except AttributeError:
            if not str(candidate).startswith(str(run_dir.resolve())):
                return None
        return candidate

    @staticmethod
    def get_run(session: str, run_id: str) -> RunDescriptor:
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        manifest = ArtifactService._load_manifest(run_dir)
        manifest_path = run_dir / "manifest.json" if manifest else None
        return RunDescriptor.from_manifest(
            session=session,
            run_id=run_id,
            run_dir=run_dir,
            manifest_path=manifest_path,
            manifest=manifest,
        )

    @staticmethod
    def list_artifacts(
        session: str, run_id: str, filters: Optional[ArtifactFilters] = None
    ) -> List[Artifact]:
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        manifest_path = run_dir / "manifest.json"
        mtime = manifest_path.stat().st_mtime if manifest_path.exists() else 0
        artifacts_payload = _cached_artifacts(session, run_id, mtime)
        artifacts = [Artifact.from_dict(item) for item in artifacts_payload]
        return filter_artifacts(artifacts, filters)

    @staticmethod
    def get_artifact_bytes(session: str, run_id: str, artifact_id: str) -> Optional[bytes]:
        artifacts = ArtifactService.list_artifacts(session, run_id)
        match = next((a for a in artifacts if a.id == artifact_id), None)
        if not match:
            return None
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        path = ArtifactService._resolve_safe_path(run_dir, match.rel_path)
        if path is None or not path.exists():
            return None
        return path.read_bytes()

    @staticmethod
    def zip_artifacts(session: str, run_id: str, artifact_ids: List[str]) -> Optional[Path]:
        artifacts = ArtifactService.list_artifacts(session, run_id)
        selected = [a for a in artifacts if a.id in artifact_ids]
        if not selected:
            return None
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        total_bytes = sum(a.bytes for a in selected)
        if total_bytes > HARD_CAP_BYTES:
            raise ValueError("Export exceeds hard cap.")

        temp_dir = Path(tempfile.mkdtemp(prefix="transcriptx_export_"))
        zip_path = temp_dir / f"{session}_{run_id}_export.zip"
        with tempfile.TemporaryDirectory() as staging:
            staging_dir = Path(staging)
            for artifact in selected:
                path = ArtifactService._resolve_safe_path(run_dir, artifact.rel_path)
                if path is None or not path.exists():
                    continue
                target = staging_dir / artifact.rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", staging_dir)
        return zip_path

    @staticmethod
    def read_for_download(path: Path, max_size: int = 500_000_000) -> bytes:
        size = path.stat().st_size
        if size > max_size:
            raise ValueError("File exceeds download size limit.")
        return path.read_bytes()

    @staticmethod
    def generate_thumbnail(session: str, run_id: str, artifact: Artifact) -> Optional[Path]:
        if artifact.kind != "chart_static":
            return None
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        source = ArtifactService._resolve_safe_path(run_dir, artifact.rel_path)
        if source is None or not source.exists():
            return None
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
                if thumb_path.suffix.lower() in ('.jpg', '.jpeg'):
                    img.save(thumb_path, quality=95, optimize=True)
                else:
                    img.save(thumb_path, optimize=True)
            return thumb_path
        except Exception as exc:
            logger.warning(f"Failed to generate thumbnail: {exc}")
            return None

    @staticmethod
    def load_html_artifact(
        session: str, run_id: str, artifact: Artifact
    ) -> Optional[Dict[str, object]]:
        if artifact.kind != "chart_dynamic":
            return None
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        path = ArtifactService._resolve_safe_path(run_dir, artifact.rel_path)
        if path is None or not path.exists():
            return None
        size = path.stat().st_size
        content = path.read_text(encoding="utf-8", errors="ignore")
        return {"content": content, "bytes": size, "path": path}

    @staticmethod
    def check_run_health(session: str, run_id: str) -> Dict[str, object]:
        run_dir = ArtifactService._resolve_run_dir(session, run_id)
        manifest = ArtifactService._load_manifest(run_dir)
        manifest_path = run_dir / "manifest.json"
        manifest_mtime = manifest_path.stat().st_mtime if manifest_path.exists() else 0
        return _cached_health(session, run_id, manifest_mtime, bool(manifest))


@st.cache_data(show_spinner=False)
def _cached_manifest(manifest_path: str, mtime: float) -> Optional[Dict]:
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.warning(f"Failed to read manifest: {exc}")
        return None


@st.cache_data(show_spinner=False)
def _cached_artifacts(session: str, run_id: str, manifest_mtime: float) -> List[Dict]:
    run_dir = Path(OUTPUTS_DIR) / session / run_id
    manifest = None
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        manifest = _cached_manifest(str(manifest_path), manifest_mtime)
    if manifest is None:
        manifest = build_output_manifest(
            run_dir=run_dir,
            run_id=run_id,
            transcript_key="unknown",
            modules_enabled=[],
        )
    return manifest.get("artifacts", [])


@st.cache_data(show_spinner=False)
def _cached_health(
    session: str, run_id: str, manifest_mtime: float, manifest_exists: bool
) -> Dict[str, object]:
    run_dir = Path(OUTPUTS_DIR) / session / run_id
    errors: List[str] = []
    warnings: List[str] = []

    if not manifest_exists:
        errors.append("Manifest missing or unreadable.")
    else:
        manifest_path = run_dir / "manifest.json"
        manifest = _cached_manifest(str(manifest_path), manifest_mtime) or {}
        if "schema_version" not in manifest or "run_id" not in manifest:
            errors.append("Manifest missing required fields.")

        artifacts_payload = manifest.get("artifacts", [])
        artifacts = [Artifact.from_dict(item) for item in artifacts_payload]
        has_transcript = any(a.kind == "transcript" for a in artifacts)
        if not has_transcript:
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
            if rel == "manifest.json" or rel.startswith(".transcriptx/"):
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
