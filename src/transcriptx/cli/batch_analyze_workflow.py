"""
Batch analysis: discover transcript JSONs in folder, run analysis pipeline on each.

No audio or transcription. Uses batch_workflows.run_batch_analysis_pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List

from transcriptx.cli.batch_workflows import run_batch_analysis_pipeline
from transcriptx.cli.file_selection_utils import discover_all_transcript_paths
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def run_batch_analyze_workflow(
    folder: Path,
    analysis_mode: str = "quick",
    selected_modules: List[str] | None = None,
    skip_speaker_gate: bool = False,
    persist: bool = False,
) -> Dict[str, Any]:
    """
    Discover transcript JSON files in folder and run analysis pipeline on all.

    Args:
        folder: Path to folder containing transcript JSON files
        analysis_mode: quick or full
        selected_modules: Optional list of module names; if None, uses defaults
        skip_speaker_gate: Skip speaker identification gate
        persist: Persist run metadata to DB

    Returns:
        Dict with status, transcript_count, etc.
    """
    if not folder.exists() or not folder.is_dir():
        return {
            "status": "failed",
            "error": f"Folder not found or not a directory: {folder}",
        }
    transcript_paths = discover_all_transcript_paths(folder)
    if not transcript_paths:
        return {
            "status": "completed",
            "transcript_count": 0,
            "message": "No transcript JSON files found",
        }
    path_strs = [str(p) for p in transcript_paths]
    run_batch_analysis_pipeline(
        path_strs,
        analysis_mode=analysis_mode,
        selected_modules=selected_modules,
        skip_speaker_gate=skip_speaker_gate,
        persist=persist,
    )
    return {"status": "completed", "transcript_count": len(path_strs)}


def run_batch_analyze_non_interactive(
    folder: Path,
    analysis_mode: str = "quick",
    selected_modules: List[str] | None = None,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    """CLI entry point for batch-analyze command."""
    return run_batch_analyze_workflow(
        folder,
        analysis_mode=analysis_mode,
        selected_modules=selected_modules,
        skip_speaker_gate=False,
        persist=False,
    )
