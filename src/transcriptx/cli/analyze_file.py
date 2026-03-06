"""
Run the analysis pipeline on a single transcript JSON file.

Used by the analyze command and batch_analyze_workflow. No audio or transcription logic.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.module_registry import get_default_modules
from transcriptx.core.pipeline.run_options import SpeakerRunOptions
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def run_analysis_on_file(
    transcript_path: str | Path,
    selected_modules: Optional[List[str]] = None,
    speaker_options: Optional[SpeakerRunOptions] = None,
    persist: bool = False,
) -> Dict[str, Any]:
    """
    Run the analysis pipeline on a single transcript file.

    Args:
        transcript_path: Path to transcript JSON file
        selected_modules: Module names to run; if None, uses default modules
        speaker_options: Speaker run options; if None, uses defaults
        persist: Whether to persist run metadata to DB

    Returns:
        Result dict from run_analysis_pipeline (output_dir, module_results, etc.)
    """
    path_str = str(transcript_path)
    modules = selected_modules or get_default_modules([path_str])
    options = speaker_options or SpeakerRunOptions()
    return run_analysis_pipeline(
        transcript_path=path_str,
        selected_modules=modules,
        speaker_options=options,
        config=get_config(),
        persist=persist,
    )
