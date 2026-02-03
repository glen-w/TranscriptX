"""
File I/O service for TranscriptX web interface.

This service handles loading transcript and analysis data from files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.paths import OUTPUTS_DIR, DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class FileService:
    """Service for file I/O operations."""

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
    def load_transcript_data(session_name: str) -> Optional[Dict[str, Any]]:
        """
        Load transcript from data/transcripts/ or data/outputs/{session}/.

        This function delegates to the I/O service for consistency.

        Args:
            session_name: Name of the session

        Returns:
            Transcript data dictionary or None if not found
        """
        # Try multiple possible locations
        session_dir = FileService._resolve_session_dir(session_name)
        manifest_path = session_dir / ".transcriptx" / "manifest.json"

        possible_paths = []
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
                manifest_path_value = manifest.get("transcript_path")
                if manifest_path_value:
                    possible_paths.append(Path(manifest_path_value))
            except Exception as e:
                logger.warning(f"Failed to read manifest for {session_name}: {e}")

        possible_paths.extend(
            [
                Path(DIARISED_TRANSCRIPTS_DIR) / f"{session_name}.json",
                Path(DIARISED_TRANSCRIPTS_DIR)
                / f"{session_name}_transcript_diarised.json",
            ]
        )

        from transcriptx.io.transcript_service import get_transcript_service

        service = get_transcript_service()

        for path in possible_paths:
            if path.exists():
                try:
                    # Use service for caching
                    return service.load_transcript(str(path))
                except Exception as e:
                    logger.error(f"Failed to load transcript from {path}: {e}")
                    continue

        logger.warning(f"Transcript not found for session: {session_name}")
        return None

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
        sessions: List[Dict[str, Any]] = []
        outputs_dir = Path(OUTPUTS_DIR)

        if not outputs_dir.exists():
            logger.warning(f"Outputs directory does not exist: {outputs_dir}")
            return sessions

        # Load index to get transcript_key for slug-based folders
        from datetime import datetime

        from transcriptx.core.utils.slug_manager import get_transcript_key_for_slug
        from transcriptx.web.module_registry import (
            get_analysis_modules as _get_analysis_modules,
            get_total_module_count,
        )

        for transcript_dir in outputs_dir.iterdir():
            if not transcript_dir.is_dir() or transcript_dir.name.startswith("."):
                continue

            # Get transcript_key from index (slug-based format)
            transcript_key = get_transcript_key_for_slug(transcript_dir.name)
            if transcript_key is None:
                # Skip if not in index (shouldn't happen for valid slug-based folders)
                continue

            total_modules = get_total_module_count()
            for run_dir in transcript_dir.iterdir():
                if not run_dir.is_dir() or run_dir.name.startswith("."):
                    continue
                try:
                    session_id = f"{transcript_dir.name}/{run_dir.name}"
                    modules = _get_analysis_modules(session_id)
                    module_count = len(modules)
                    analysis_completion = (
                        int((module_count / total_modules) * 100)
                        if total_modules > 0
                        else 0
                    )
                    try:
                        mtime = run_dir.stat().st_mtime
                        last_updated = datetime.fromtimestamp(mtime).isoformat()
                    except Exception:
                        last_updated = None
                    session_info = {
                        "name": session_id,
                        "slug": transcript_dir.name,  # Human-readable slug
                        "transcript_key": transcript_key,  # Hash for identity
                        "run_id": run_dir.name,
                        "path": str(run_dir),
                        "modules": modules,
                        "module_count": module_count,
                        "duration_seconds": 0,
                        "duration_minutes": 0,
                        "speaker_count": 0,
                        "word_count": 0,
                        "segment_count": 0,
                        "last_updated": last_updated,
                        "analysis_completion": analysis_completion,
                    }
                    sessions.append(session_info)
                except Exception as e:
                    logger.warning(f"Failed to load session {run_dir.name}: {e}")
                    continue

        return sorted(sessions, key=lambda x: x.get("last_updated") or "", reverse=True)
