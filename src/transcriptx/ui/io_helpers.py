from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from transcriptx.core.utils.paths import PROJECT_ROOT

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
}
UPLOADS_DIR = Path(PROJECT_ROOT) / "data" / "ui_uploads"
SOFT_WARN_MB = 500


def human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.1f} GB"


def save_uploaded_file(uploaded_file) -> tuple[Path, list[str]]:
    """
    Save an uploaded file into a unique ui_uploads directory.
    Returns (saved_path, warnings).
    """
    if uploaded_file is None:
        raise ValueError("No uploaded file provided")

    if isinstance(uploaded_file, (str, Path)):
        source_path = Path(uploaded_file)
    else:
        source_path = Path(getattr(uploaded_file, "name", ""))

    if not source_path or not source_path.exists():
        raise FileNotFoundError("Uploaded file path is not available")

    warnings: list[str] = []
    suffix = source_path.suffix.lower()
    if suffix and suffix not in ALLOWED_AUDIO_EXTENSIONS:
        warnings.append(f"Unrecognized extension '{suffix}'. Proceeding anyway.")

    upload_dir = UPLOADS_DIR / str(uuid4())
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / source_path.name
    shutil.copy2(source_path, target_path)

    file_size_mb = target_path.stat().st_size / (1024 * 1024)
    if file_size_mb >= SOFT_WARN_MB:
        warnings.append(
            f"Large file ({file_size_mb:.1f} MB). This may take a long time."
        )

    return target_path, warnings


def format_recording_label(path: Path) -> str:
    try:
        size = path.stat().st_size
        return f"{path.name} ({human_size(size)})"
    except OSError:
        return path.name


def filter_audio_files(paths: Iterable[Path]) -> list[Path]:
    allowed = []
    for path in paths:
        if path.is_file():
            allowed.append(path)
    return allowed
