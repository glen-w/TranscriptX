"""
Batch processing resume and checkpoint functionality.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.cli.processing_state import (
    load_processing_state,
    save_processing_state,
)

logger = get_logger()

PROCESSING_STATE_FILE = Path(DATA_DIR) / "processing_state.json"
BATCH_PROGRESS_KEY = "batch_progress"


def create_batch_checkpoint(
    batch_id: str,
    total_files: int,
    processed_files: List[str],
    failed_files: List[Dict[str, Any]],
    current_file: Optional[str] = None,
) -> None:
    """
    Create or update batch processing checkpoint.

    Args:
        batch_id: Unique identifier for this batch run
        total_files: Total number of files to process
        processed_files: List of successfully processed file paths
        failed_files: List of failed files with error information
        current_file: Currently processing file (if any)
    """
    state = load_processing_state(validate=False)

    batch_progress = {
        "batch_id": batch_id,
        "started_at": state.get(BATCH_PROGRESS_KEY, {}).get("started_at")
        or datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "total_files": total_files,
        "processed_files": processed_files,
        "failed_files": failed_files,
        "current_file": current_file,
        "status": "in_progress",
    }

    state[BATCH_PROGRESS_KEY] = batch_progress
    save_processing_state(state)

    logger.debug(
        f"Created checkpoint: {len(processed_files)}/{total_files} files processed"
    )


def get_batch_checkpoint() -> Optional[Dict[str, Any]]:
    """
    Get current batch processing checkpoint.

    Returns:
        Batch progress dictionary or None if no checkpoint exists
    """
    state = load_processing_state(validate=False)
    return state.get(BATCH_PROGRESS_KEY)


def clear_batch_checkpoint() -> None:
    """Clear batch processing checkpoint."""
    state = load_processing_state(validate=False)
    if BATCH_PROGRESS_KEY in state:
        del state[BATCH_PROGRESS_KEY]
        save_processing_state(state)
        logger.debug("Cleared batch checkpoint")


def complete_batch_checkpoint() -> None:
    """Mark batch processing as completed."""
    state = load_processing_state(validate=False)
    if BATCH_PROGRESS_KEY in state:
        state[BATCH_PROGRESS_KEY]["status"] = "completed"
        state[BATCH_PROGRESS_KEY]["last_updated"] = datetime.now().isoformat()
        save_processing_state(state)
        logger.debug("Marked batch as completed")


def get_remaining_files(
    wav_files: List[Path], checkpoint: Dict[str, Any]
) -> List[Path]:
    """
    Get list of files that still need processing based on checkpoint.

    Args:
        wav_files: Original list of WAV files
        checkpoint: Batch checkpoint data

    Returns:
        List of files that still need processing
    """
    processed_paths = set(checkpoint.get("processed_files", []))
    failed_paths = {f["file"] for f in checkpoint.get("failed_files", [])}

    remaining = []
    for wav_file in wav_files:
        file_path = str(wav_file.resolve())
        if file_path not in processed_paths and file_path not in failed_paths:
            remaining.append(wav_file)

    return remaining


def resume_batch_processing(wav_files: List[Path]) -> Dict[str, Any]:
    """
    Resume batch processing from checkpoint.

    Args:
        wav_files: Original list of WAV files

    Returns:
        Dictionary with resume information
    """
    checkpoint = get_batch_checkpoint()

    if not checkpoint:
        return {"can_resume": False, "reason": "No checkpoint found"}

    if checkpoint.get("status") == "completed":
        return {"can_resume": False, "reason": "Batch already completed"}

    remaining_files = get_remaining_files(wav_files, checkpoint)

    return {
        "can_resume": True,
        "checkpoint": checkpoint,
        "remaining_files": remaining_files,
        "processed_count": len(checkpoint.get("processed_files", [])),
        "failed_count": len(checkpoint.get("failed_files", [])),
        "total_count": checkpoint.get("total_files", 0),
    }
