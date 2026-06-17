"""
Artifact-centric service layer for the TranscriptX dashboard.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
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

HARD_CAP_BYTES = 2 * 1024 * 1024 * 1024
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
        if artifact.storage_root:
            return Path(artifact.storage_root).resolve()
        return run_root.resolve()

    @staticmethod
    def _resolve_safe_path(base_dir: Path, rel_path: str) -> Optional[Path]:
        if ".." in rel_path.split("/"):
            return None
        candidate = (base_dir / rel_path).resolve()
        try:
            if not candidate.is_relative_to(base_dir.resolve()):
                return None
        except AttributeError:
            if not str(candidate).startswith(str(base_dir.resolve())):
                return None
        return candidate

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
    def _merge_group_member_chart_artifacts(run_root: Path) -> List[Artifact]:
        """Attach chart artifacts from each member's transcript run (group analysis)."""
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
                if item.get("kind") not in ("chart_static", "chart_dynamic"):
                    continue
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
    def list_artifacts(
        run_root: Path, filters: Optional[ArtifactFilters] = None
    ) -> List[Artifact]:
        manifest_path = run_root / "manifest.json"
        mtime = manifest_path.stat().st_mtime if manifest_path.exists() else 0
        artifacts_payload = _cached_artifacts(str(run_root), mtime)
        artifacts = [Artifact.from_dict(item) for item in artifacts_payload]
        artifacts.extend(ArtifactService._merge_group_member_chart_artifacts(run_root))
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
        base = ArtifactService._artifact_base_path(run_root, artifact)
        path = ArtifactService._resolve_safe_path(base, artifact.rel_path)
        if path is None or not path.exists():
            return None
        return path

    @staticmethod
    def zip_artifacts(run_root: Path, artifact_ids: List[str]) -> Optional[Path]:
        artifacts = ArtifactService.list_artifacts(run_root)
        selected = [a for a in artifacts if a.id in artifact_ids]
        if not selected:
            return None
        total_bytes = sum(a.bytes for a in selected)
        if total_bytes > HARD_CAP_BYTES:
            raise ValueError("Export exceeds hard cap.")

        temp_dir = Path(tempfile.mkdtemp(prefix="transcriptx_export_"))
        zip_path = temp_dir / f"{run_root.name}_export.zip"
        with tempfile.TemporaryDirectory() as staging:
            staging_dir = Path(staging)
            copied: List[tuple[Artifact, Path]] = []
            for artifact in selected:
                path = ArtifactService.resolve_artifact_source_path(run_root, artifact)
                if path is None or not path.exists():
                    continue
                prefix = Path(artifact.id[:16]) if artifact.storage_root else Path()
                rel = prefix / artifact.rel_path
                target = staging_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                copied.append((artifact, rel))
            ArtifactService._write_export_index(
                staging_dir, run_root.name, copied, run_root=run_root
            )
            shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", staging_dir)
        return zip_path

    @staticmethod
    def _write_export_index(
        staging_dir: Path,
        run_title: str,
        copied: List["tuple[Artifact, Path]"],
        *,
        run_root: Optional[Path] = None,
    ) -> None:
        """Write a self-contained ``index.html`` approximating the GUI.

        Renders a basic transcript displayer, optional LLM transcript summary, and an
        unfiltered charts gallery for the copied artifacts. Each section fails
        independently; the file is written when at least one section is produced and
        skipped only when none are. Never raises: index generation must not break
        the raw-file export.
        """
        try:
            from transcriptx.utils.charts_export import _ExportableItem
            from transcriptx.utils.export_index import (
                build_export_index_html,
                resolve_export_llm_summary,
                resolve_export_page_title,
                resolve_export_transcript_data,
            )

            transcript_data = resolve_export_transcript_data(
                staging_dir=staging_dir,
                run_root=run_root,
                copied=copied,
            )
            llm_summary = resolve_export_llm_summary(
                staging_dir=staging_dir,
                copied=copied,
            )
            page_title = resolve_export_page_title(
                staging_dir=staging_dir,
                run_root=run_root,
                fallback=run_title,
            )

            chart_items: List[_ExportableItem] = []
            for artifact, rel in copied:
                if artifact.kind in {"chart_static", "chart_dynamic"}:
                    chart_items.append(
                        _ExportableItem(
                            artifact=artifact,
                            source_path=staging_dir / rel,
                            export_rel_path=rel,
                            size_bytes=0,
                        )
                    )

            html_payload = build_export_index_html(
                page_title=page_title,
                transcript_data=transcript_data,
                chart_items=chart_items,
                llm_summary=llm_summary,
            )
            if html_payload:
                (staging_dir / "index.html").write_text(html_payload, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to generate export index.html: %s", exc)

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
