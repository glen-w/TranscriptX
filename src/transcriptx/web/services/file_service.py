"""
File I/O service for TranscriptX web interface.

This service handles loading transcript and analysis data from files.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    GROUP_OUTPUTS_DIR,
    OUTPUTS_DIR,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.io.metadata_display_options import get_metadata_config
from transcriptx.io.metadata_stats import (
    DEFAULT_SESSION_STATS,
    listing_stats_from_document,
)
from transcriptx.web.services.run_visibility import has_user_artifacts, is_viewable_run
from transcriptx.web.perf import (
    increment_count,
    observe_transcript_path,
    record_file_read,
    section,
)

logger = get_logger()


def _extract_metadata_stats(doc: dict) -> dict[str, int | float]:
    """Thin wrapper around shared listing stat resolution."""
    return listing_stats_from_document(doc, meta_cfg=get_metadata_config())


@st.cache_data(show_spinner=False)
def _cached_transcript_listing_stats(
    path_str: str, mtime: float, size: int
) -> dict[str, int | float]:
    """Listing stats per transcript file, keyed by (path, mtime, size).

    Unchanged files are parsed at most once per process instead of on every
    session-listing cache miss.
    """
    from transcriptx.io.transcript_loader import load_transcript

    path = Path(path_str)
    with section(
        "file_service.load_transcript_for_session_stats",
        bucket="session_discovery",
        extra={"transcript_path": path_str},
    ):
        try:
            observe_transcript_path(path)
            record_file_read(
                path,
                section="file_service.list_available_sessions",
                purpose="metadata_extraction",
            )
            doc = load_transcript(path_str)
        except Exception as exc:
            logger.debug("Skipping metadata stats for %s: %s", path_str, exc)
            return {}
    return _extract_metadata_stats(doc) if doc else {}


@st.cache_data(ttl=60, show_spinner=False)
def _cached_session_modules(session_id: str, run_dir_mtime: float) -> List[str]:
    """Module dir scan per run, keyed by run dir mtime (new module dirs bump it)."""
    from transcriptx.web.module_registry import get_analysis_modules

    return get_analysis_modules(session_id)


class FileService:
    """Service for file I/O operations."""

    @staticmethod
    def _has_user_artifacts(run_dir: Path) -> bool:
        return has_user_artifacts(run_dir)

    @staticmethod
    def _is_viewable_run(run_dir: Path) -> bool:
        """Only index runs that produced at least one user-visible artifact."""
        with section(
            "file_service._is_viewable_run",
            bucket="session_discovery",
            extra={"run_dir": str(run_dir)},
        ):
            return is_viewable_run(run_dir)

    @staticmethod
    def _resolve_session_dir(session_id: str) -> Path:
        """
        Resolve session directory path using slug-based folder structure.

        Format: <slug>/<run_id>

        Args:
            session_id: Session identifier in format "slug/run_id" or just "slug"

        Returns:
            Path to session directory
        """
        if "/" in session_id:
            slug, run_id = session_id.split("/", 1)
            return Path(OUTPUTS_DIR) / slug / run_id

        # No run_id specified, find first available run
        slug_path = Path(OUTPUTS_DIR) / session_id
        if slug_path.exists():
            # Return first run_id directory found
            for item in sorted(slug_path.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    return item
            return slug_path

        return Path(OUTPUTS_DIR) / session_id

    @staticmethod
    def resolve_transcript_path(session_name: str) -> Optional[Path]:
        """
        Resolve session to the transcript file path (single source of truth).

        Tries: manifest transcript_path, then DIARISED_TRANSCRIPTS_DIR variants.

        Args:
            session_name: Session identifier (e.g. "slug/run_id")

        Returns:
            Path to the transcript file, or None if not found
        """
        with section(
            "file_service.resolve_transcript_path",
            bucket="session_discovery",
            extra={"session_name": session_name},
        ):
            session_dir = FileService._resolve_session_dir(session_name)
            manifest_path = session_dir / ".transcriptx" / "manifest.json"

            slug = (
                session_name.split("/", 1)[0] if "/" in session_name else session_name
            )

            if manifest_path.exists():
                try:
                    from transcriptx.core.pipeline.manifest_loader import (
                        load_run_manifest,
                    )

                    manifest = load_run_manifest(manifest_path)
                    manifest_path_value = manifest.get("transcript_path")
                    if manifest_path_value:
                        path = Path(manifest_path_value)
                        if path.exists():
                            observe_transcript_path(path)
                            return path
                        # Manifest path often absolute host path; in Docker it may not exist.
                        # Fallback: transcript copied into run dir (same basename).
                        run_dir_candidate = session_dir / path.name
                        if run_dir_candidate.exists():
                            observe_transcript_path(run_dir_candidate)
                            return run_dir_candidate
                except Exception as e:
                    logger.warning(f"Failed to read manifest for {session_name}: {e}")

            # Run dir: transcript may live next to manifest (e.g. pipeline or Docker layout)
            for candidate in [
                session_dir / f"{slug}.json",
                session_dir / "transcript.json",
                session_dir / f"{slug}_transcript_diarised.json",
            ]:
                if candidate.exists():
                    observe_transcript_path(candidate)
                    return candidate

            for candidate in [
                Path(DIARISED_TRANSCRIPTS_DIR) / f"{session_name}.json",
                Path(DIARISED_TRANSCRIPTS_DIR)
                / f"{session_name}_transcript_diarised.json",
                Path(DIARISED_TRANSCRIPTS_DIR) / f"{slug}.json",
                Path(DIARISED_TRANSCRIPTS_DIR) / f"{slug}_transcript_diarised.json",
            ]:
                if candidate.exists():
                    observe_transcript_path(candidate)
                    return candidate

            return None

    @staticmethod
    def resolve_session_for_transcript_path(
        file_path: str,
        sessions: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Tuple[str, str]]:
        """
        Resolve a transcript file path to a (slug, run_id) session tuple.

        Uses list_available_sessions + resolve_transcript_path to match paths.
        """
        if not file_path:
            return None

        try:
            target_path = Path(file_path).resolve()
        except Exception:
            return None

        sessions_list = (
            sessions if sessions is not None else FileService.list_available_sessions()
        )
        for session_info in sessions_list:
            session_name = session_info.get("name", "")
            if "/" not in session_name:
                continue
            resolved_path = FileService.resolve_transcript_path(session_name)
            if resolved_path is None:
                continue
            try:
                rp = resolved_path.resolve()
                if rp == target_path:
                    slug, run_id = session_name.split("/", 1)
                    return slug, run_id
                if os.path.samefile(rp, target_path):
                    slug, run_id = session_name.split("/", 1)
                    return slug, run_id
            except (OSError, ValueError):
                continue
        return None

    @staticmethod
    def load_transcript_with_path_by_session(
        session_name: str,
    ) -> Optional[tuple[Dict[str, Any], Path]]:
        """
        Load transcript and return ``(data, canonical_path)`` actually used.

        The returned path is the file that was loaded — callers that need
        playback or sidecar resolution must use this path rather than calling
        ``resolve_transcript_path`` again on a composite ``session_slug/run_id``.
        """
        # Single-char session_name usually means a bug (e.g. iterating over a
        # UUID string); skip to avoid log spam and still resolve normally.
        if not session_name or len(session_name) <= 1:
            logger.debug("Skipping invalid session name (too short): %r", session_name)
            return None
        path: Optional[Path] = None
        try:
            from transcriptx.web.cache_helpers import cached_resolve_transcript_path

            path_str = cached_resolve_transcript_path(session_name)
            if path_str:
                path = Path(path_str)
                if not path.exists():
                    # Stale cached resolution (renamed/moved file): re-resolve below.
                    path = None
        except Exception:
            path = None
        if path is None:
            path = FileService.resolve_transcript_path(session_name)
        if path is None:
            logger.warning(f"Transcript not found for session: {session_name}")
            return None

        from transcriptx.io.transcript_service import get_transcript_service

        service = get_transcript_service()
        try:
            data = service.load_transcript(str(path))
        except Exception as e:
            logger.error(f"Failed to load transcript from {path}: {e}")
            return None
        if data is None:
            return None
        return data, path

    @staticmethod
    def load_transcript_by_session(session_name: str) -> Optional[Dict[str, Any]]:
        """
        Load transcript from data/transcripts/ or data/outputs/{session}/.

        Web viewer only: loads by session name (run/slug), not by file path.
        Uses resolve_transcript_path for a single source of truth, then loads via
        transcript service.

        Args:
            session_name: Name of the session

        Returns:
            Transcript data dictionary or None if not found
        """
        loaded = FileService.load_transcript_with_path_by_session(session_name)
        if loaded is None:
            return None
        return loaded[0]

    @staticmethod
    def load_analysis_data(
        session_name: str, module_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load analysis JSON data for a module.

        Args:
            session_name: Name of the session
            module_name: Name of the analysis module

        Returns:
            Analysis data dictionary or None if not found
        """
        module_dir = FileService._resolve_session_dir(session_name) / module_name

        if not module_dir.exists():
            return None

        # Look for JSON files in the module directory (recursive)
        json_files = list(module_dir.rglob("*.json"))

        if not json_files:
            return None

        # Try to find a summary or main data file
        preferred_names = [
            "summary.json",
            f"{module_name}_summary.json",
        ]

        for preferred_name in preferred_names:
            preferred_path = next(
                (p for p in json_files if p.name == preferred_name), None
            )
            if preferred_path and preferred_path.exists():
                try:
                    with open(preferred_path, "r") as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(
                        f"Failed to load analysis data from {preferred_path}: {e}"
                    )
                    continue

        # Fallback to first JSON file
        try:
            with open(json_files[0], "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load analysis data from {json_files[0]}: {e}")
            return None

    @staticmethod
    def list_charts(session_name: str, module_name: str) -> List[Dict[str, str]]:
        """
        List available chart images for a module.

        Args:
            session_name: Name of the session
            module_name: Name of the analysis module

        Returns:
            List of chart dictionaries with name and path
        """
        charts = []
        module_dir = FileService._resolve_session_dir(session_name) / module_name

        if not module_dir.exists():
            return charts

        # Look for PNG files
        png_files = list(module_dir.glob("*.png"))

        for png_file in sorted(png_files):
            charts.append(
                {
                    "name": png_file.name,
                    "path": f"/api/charts/{session_name}/{module_name}/{png_file.name}",
                }
            )

        return charts

    @staticmethod
    def list_available_sessions() -> List[Dict[str, Any]]:
        """
        Scan data/outputs/<slug>/<run_id> for available runs.

        Returns:
            List of session dictionaries with metadata
        """
        with section(
            "file_service.list_available_sessions", bucket="session_discovery"
        ):
            sessions: List[Dict[str, Any]] = []
            outputs_dir = Path(OUTPUTS_DIR)

            if not outputs_dir.exists():
                logger.warning(f"Outputs directory does not exist: {outputs_dir}")
                return sessions

            # Load index to get transcript_key for slug-based folders
            from datetime import datetime

            from transcriptx.core.utils.slug_manager import get_transcript_key_for_slug
            from transcriptx.web.module_registry import get_total_module_count

            group_root = Path(GROUP_OUTPUTS_DIR)
            total_modules = get_total_module_count()
            stats_cache: dict[str, dict] = {}
            with section(
                "file_service.outputs_dir_iteration",
                bucket="session_discovery",
                extra={"outputs_dir": str(outputs_dir)},
            ):
                for transcript_dir in outputs_dir.iterdir():
                    if not transcript_dir.is_dir() or transcript_dir.name.startswith(
                        "."
                    ):
                        continue
                    # outputs/groups/<uuid>/<run_id> is not slug/run transcript sessions; skip entirely.
                    try:
                        if transcript_dir.resolve() == group_root.resolve():
                            continue
                    except (OSError, ValueError):
                        if transcript_dir.name == "groups":
                            continue

                    # Prefer transcript_key from index; use slug as fallback so runs still appear in dropdown
                    # (e.g. when index wasn't updated or run was created in Docker with different paths)
                    transcript_key = get_transcript_key_for_slug(transcript_dir.name)
                    if transcript_key is None:
                        transcript_key = transcript_dir.name

                    for run_dir in transcript_dir.iterdir():
                        if not run_dir.is_dir() or run_dir.name.startswith("."):
                            continue
                        increment_count("output_run_dirs")
                        if not FileService._is_viewable_run(run_dir):
                            continue
                        try:
                            session_id = f"{transcript_dir.name}/{run_dir.name}"
                            try:
                                run_dir_mtime = run_dir.stat().st_mtime
                            except Exception:
                                run_dir_mtime = 0.0
                            # Include session even when transcript path is not resolvable (e.g. Docker path
                            # in manifest); run will appear in dropdown and may load transcript from run dir
                            modules = _cached_session_modules(session_id, run_dir_mtime)
                            module_count = len(modules)
                            analysis_completion = (
                                int((module_count / total_modules) * 100)
                                if total_modules > 0
                                else 0
                            )
                            last_updated = (
                                datetime.fromtimestamp(run_dir_mtime).isoformat()
                                if run_dir_mtime
                                else None
                            )
                            session_info = {
                                "name": session_id,
                                "slug": transcript_dir.name,  # Human-readable slug
                                "transcript_key": transcript_key,  # Hash for identity
                                "run_id": run_dir.name,
                                "path": str(run_dir),
                                "modules": modules,
                                "module_count": module_count,
                                **DEFAULT_SESSION_STATS,
                                "last_updated": last_updated,
                                "analysis_completion": analysis_completion,
                            }
                            # word_count is metadata-first; stats cached per (path, mtime, size)
                            # so unchanged transcripts are not re-parsed on later scans.
                            transcript_path = FileService.resolve_transcript_path(
                                session_id
                            )
                            if transcript_path is not None:
                                try:
                                    cache_key = str(transcript_path.resolve())
                                except (OSError, RuntimeError):
                                    cache_key = str(transcript_path)
                                if cache_key not in stats_cache:
                                    try:
                                        file_stat = os.stat(cache_key)
                                        stats_cache[cache_key] = (
                                            _cached_transcript_listing_stats(
                                                cache_key,
                                                file_stat.st_mtime,
                                                file_stat.st_size,
                                            )
                                        )
                                    except OSError:
                                        stats_cache[cache_key] = {}
                                if stats_cache[cache_key]:
                                    session_info.update(stats_cache[cache_key])
                            sessions.append(session_info)
                        except Exception as e:
                            logger.warning(
                                f"Failed to load session {run_dir.name}: {e}"
                            )
                            continue

            return sorted(
                sessions, key=lambda x: x.get("last_updated") or "", reverse=True
            )
