"""
Builds a lightweight, artifact-focused manifest for a single run directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.core.config.persistence import compute_config_hash
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.module_hashing import compute_module_source_hash

logger = get_logger()

SCHEMA_VERSION = 1

STANDARD_TAGS = {
    "timeline",
    "distribution",
    "rolling",
    "heatmap",
    "network",
    "map",
    "entities",
    "per_speaker",
}

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}


@dataclass(frozen=True)
class ManifestArtifact:
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
    preview: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "kind": self.kind,
            "module": self.module,
            "scope": self.scope,
            "speaker": self.speaker,
            "subview": self.subview,
            "slice_id": self.slice_id,
            "rel_path": self.rel_path,
            "bytes": self.bytes,
            "mtime": self.mtime,
            "mime": self.mime,
            "tags": self.tags,
            "title": self.title,
            "produced_by": self.produced_by,
            "preview": self.preview,
            "meta": self.meta,
        }
        return {k: v for k, v in payload.items() if v is not None}


def _safe_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _hash_artifact_id(
    kind: str,
    module: Optional[str],
    scope: Optional[str],
    speaker: Optional[str],
    rel_path: str,
) -> str:
    payload = "|".join(
        [
            kind or "",
            module or "",
            scope or "",
            speaker or "",
            rel_path or "",
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _infer_scope_and_speaker(parts: List[str]) -> tuple[Optional[str], Optional[str]]:
    if "speakers" in parts:
        idx = parts.index("speakers")
        speaker = parts[idx + 1] if idx + 1 < len(parts) else None
        return "speaker", speaker
    if "global" in parts:
        return "global", None
    return None, None


def _infer_subview_and_slice(parts: List[str]) -> tuple[Optional[str], Optional[str]]:
    if not parts:
        return None, None
    for token in ("combined", "comparisons", "by_session", "by_speaker"):
        if token in parts:
            idx = parts.index(token)
            slice_id = None
            if token in {"by_session", "by_speaker"} and idx + 1 < len(parts):
                slice_id = parts[idx + 1]
            return token, slice_id
    return None, None


def _infer_kind(
    rel_path: str, parts: List[str], artifact_meta: Optional[Dict[str, Any]] = None
) -> str:
    suffix = Path(rel_path).suffix.lower()
    if rel_path.startswith(".transcriptx/") and suffix == ".json":
        return "config"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if "transcripts" in parts:
        return "transcript"
    # Check for maps (NER location maps)
    if "maps" in parts:
        # Check metadata first for render_hint
        if artifact_meta and isinstance(artifact_meta, dict):
            render_hint = artifact_meta.get("render_hint")
            if render_hint == "static" and suffix == ".png":
                return "chart_static"
            if render_hint == "dynamic" and suffix == ".html":
                return "chart_dynamic"
        # Fallback to file extension and location
        if suffix == ".png" and "images" in parts:
            return "chart_static"
        if suffix == ".html" and "html" in parts:
            return "chart_dynamic"
    # Check for charts
    if "charts" in parts and suffix == ".png":
        return "chart_static"
    if "charts" in parts and suffix == ".html":
        return "chart_dynamic"
    if suffix == ".json":
        return "data_json"
    if suffix == ".csv":
        return "data_csv"
    if suffix in {".txt", ".md"}:
        return "data_txt"
    return "other"


def _infer_tags(module: Optional[str], rel_path: str, parts: List[str]) -> List[str]:
    tags: set[str] = set()
    if module:
        tags.add(module)
    lower_name = rel_path.lower()
    for tag in STANDARD_TAGS:
        if tag in lower_name:
            tags.add(tag)
    if "speakers" in parts or "speaker" in lower_name:
        tags.add("per_speaker")
    if "timeline" in lower_name or "timeseries" in lower_name:
        tags.add("timeline")
    if "hist" in lower_name or "distribution" in lower_name:
        tags.add("distribution")
    if "rolling" in lower_name:
        tags.add("rolling")
    if "heatmap" in lower_name:
        tags.add("heatmap")
    if "network" in lower_name:
        tags.add("network")
    if "map" in lower_name:
        tags.add("map")
    if "ner" in lower_name or "entity" in lower_name:
        tags.add("entities")
    return sorted(tags)


def _infer_title(rel_path: str) -> Optional[str]:
    name = Path(rel_path).stem.replace("_", " ").strip()
    return name.title() if name else None


def _load_artifact_metadata(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    meta_path = run_dir / ".transcriptx" / "artifacts_meta.json"
    if not meta_path.exists():
        return {}
    try:
        payload = meta_path.read_text(encoding="utf-8")
        data = json.loads(payload)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _detect_audio_rel_path(run_dir: Path) -> Optional[str]:
    for ext in AUDIO_EXTENSIONS:
        matches = list(run_dir.rglob(f"*{ext}"))
        if matches:
            return str(matches[0].relative_to(run_dir))
    return None


def _iter_files(run_dir: Path) -> Iterable[Path]:
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(run_dir).as_posix()
        if rel_path.startswith(".transcriptx/"):
            # Skip internal metadata except config artifacts
            if rel_path not in {
                ".transcriptx/run_config_effective.json",
                ".transcriptx/run_config_override.json",
            }:
                continue
        if rel_path == "manifest.json":
            continue
        if "/.thumbnails/" in rel_path:
            continue
        yield path


def _load_config_metadata(run_dir: Path) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {
        "config_effective_path": None,
        "config_override_path": None,
        "config_hash": None,
        "config_schema_version": None,
        "config_source": None,
    }
    effective_path = run_dir / ".transcriptx" / "run_config_effective.json"
    override_path = run_dir / ".transcriptx" / "run_config_override.json"
    if effective_path.exists():
        meta["config_effective_path"] = ".transcriptx/run_config_effective.json"
        try:
            payload = json.loads(effective_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                schema_version = payload.get("schema_version")
                if schema_version is not None:
                    meta["config_schema_version"] = schema_version
                config_body = (
                    payload.get("config")
                    if isinstance(payload.get("config"), dict)
                    else None
                )
                if config_body is not None:
                    meta["config_hash"] = compute_config_hash(config_body)
        except Exception:
            pass
    if override_path.exists():
        meta["config_override_path"] = ".transcriptx/run_config_override.json"
        meta["config_source"] = "run_override"
    if meta["config_source"] is None:
        try:
            from transcriptx.core.config.persistence import get_project_config_path

            if get_project_config_path().exists():
                meta["config_source"] = "project"
            elif meta["config_effective_path"]:
                meta["config_source"] = "default"
        except Exception:
            pass
    return meta


def build_output_manifest(
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
) -> Dict[str, Any]:
    run_dir = run_dir.resolve()
    artifact_meta = _load_artifact_metadata(run_dir)
    module_versions = {
        module: compute_module_source_hash(module) for module in modules_enabled
    }
    artifacts: List[ManifestArtifact] = []
    total_size = 0
    for path in _iter_files(run_dir):
        rel_path = path.relative_to(run_dir).as_posix()
        parts = rel_path.split("/")
        module = parts[0] if parts and parts[0] not in {"transcripts"} else None
        # Get artifact metadata before inferring scope/speaker/kind (so they can use metadata)
        meta = artifact_meta.get(rel_path)
        # Use metadata for scope/speaker if available, otherwise infer from path
        if isinstance(meta, dict) and "scope" in meta:
            scope = meta.get("scope")
            speaker = meta.get("speaker") if scope == "speaker" else None
        else:
            scope, speaker = _infer_scope_and_speaker(parts)
        if isinstance(meta, dict) and "subview" in meta:
            subview = meta.get("subview")
            slice_id = meta.get("slice_id")
        else:
            subview, slice_id = _infer_subview_and_slice(parts)
        kind = _infer_kind(rel_path, parts, artifact_meta=meta)
        stats = path.stat()
        total_size += stats.st_size
        tags = _infer_tags(module, rel_path, parts)
        produced_by = None
        if module and module in module_versions:
            module_hash = module_versions[module]
            produced_by = f"{module}/{module_hash}" if module_hash else module
        title = None
        if isinstance(meta, dict):
            title = meta.get("title")
        if not title:
            title = _infer_title(rel_path)
        artifact_id = _hash_artifact_id(kind, module, scope, speaker, rel_path)
        artifact = ManifestArtifact(
            id=artifact_id,
            kind=kind,
            module=module,
            scope=scope,
            speaker=speaker,
            subview=subview,
            slice_id=slice_id,
            rel_path=rel_path,
            bytes=stats.st_size,
            mtime=datetime.utcfromtimestamp(stats.st_mtime).isoformat() + "Z",
            mime=_safe_mime_type(path),
            tags=tags,
            title=title,
            produced_by=produced_by,
            preview={"thumbnail": None} if kind == "chart_static" else None,
            meta=meta if isinstance(meta, dict) else None,
        )
        artifacts.append(artifact)

    timestamp = datetime.utcnow().isoformat() + "Z"
    config_meta = _load_config_metadata(run_dir)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_metadata": {
            "timestamp": timestamp,
            "transcript_key": transcript_key,
            "audio_rel_path": _detect_audio_rel_path(run_dir),
            "modules_enabled": modules_enabled,
            "version_hash": module_versions,
            "total_size_bytes": total_size,
            **{k: v for k, v in config_meta.items() if v is not None},
        },
        "artifacts": [artifact.to_dict() for artifact in artifacts],
    }
    return manifest


def write_output_manifest(
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
) -> Optional[Path]:
    try:
        manifest = build_output_manifest(
            run_dir, run_id, transcript_key, modules_enabled
        )
        output_path = run_dir / "manifest.json"
        write_json(output_path, manifest, indent=2, ensure_ascii=False)
        logger.info(f"Saved output manifest to {output_path}")
        return output_path
    except Exception as exc:
        logger.warning(f"Failed to build output manifest: {exc}")
        return None


def _normalize_skipped_modules(
    skipped_modules: List[Any],
) -> List[Dict[str, str]]:
    """Normalize skipped_modules to list of {module, reason} dicts."""
    out: List[Dict[str, str]] = []
    for entry in skipped_modules or []:
        if isinstance(entry, dict) and "module" in entry:
            out.append(
                {
                    "module": str(entry["module"]),
                    "reason": str(entry.get("reason", "Skipped")),
                }
            )
        elif isinstance(entry, str):
            out.append({"module": entry, "reason": "Not in registry"})
    return out


def build_run_results_summary(
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
    modules_run: List[str],
    skipped_modules: List[Any],
    errors: List[str],
    preset_explanation: Optional[str] = None,
) -> Dict[str, Any]:
    """Build run-level results summary for machine and human consumption."""
    skipped = _normalize_skipped_modules(skipped_modules)
    modules_run_set = {m for m in modules_run}
    failed = [
        m
        for m in modules_enabled
        if m not in modules_run_set and not any(s["module"] == m for s in skipped)
    ]
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "transcript_key": transcript_key,
        "modules_enabled": modules_enabled,
        "modules_run": modules_run,
        "modules_skipped": skipped,
        "modules_failed": failed,
        "errors": errors,
    }
    if preset_explanation:
        payload["preset_explanation"] = preset_explanation
    return payload


def write_run_results_summary(
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
    modules_run: List[str],
    skipped_modules: List[Any],
    errors: List[str],
    preset_explanation: Optional[str] = None,
) -> Optional[Path]:
    """Write run_results.json so CLI and Web UI can show run/skip/fail and why."""
    try:
        payload = build_run_results_summary(
            run_id=run_id,
            transcript_key=transcript_key,
            modules_enabled=modules_enabled,
            modules_run=modules_run,
            skipped_modules=skipped_modules,
            errors=errors,
            preset_explanation=preset_explanation,
        )
        output_path = Path(run_dir).resolve() / "run_results.json"
        write_json(output_path, payload, indent=2, ensure_ascii=False)
        logger.info(f"Saved run results summary to {output_path}")
        return output_path
    except Exception as exc:
        logger.warning(f"Failed to write run results summary: {exc}")
        return None
