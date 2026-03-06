"""
File metadata formatters for the file selection interface.

This module provides formatter functions that convert file paths into
display strings with metadata (size, duration, etc.).
"""

from pathlib import Path

from transcriptx.cli.audio import get_audio_duration


def format_audio_file_fast(file_path: Path) -> str:
    """
    Format audio file metadata quickly (name + size only).

    Args:
        file_path: Path to the audio file

    Returns:
        Formatted string with file name and size
    """
    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        return f"🎵 {file_path.name} ({size_mb:.1f} MB)"
    except Exception:
        return f"🎵 {file_path.name}"


def format_audio_file(file_path: Path) -> str:
    """
    Format audio file metadata for display.

    Args:
        file_path: Path to the audio file

    Returns:
        Formatted string with file name, size, and duration
    """
    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        duration = get_audio_duration(file_path)
        if duration:
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
            return f"🎵 {file_path.name} ({size_mb:.1f} MB, {duration_str})"
        return f"🎵 {file_path.name} ({size_mb:.1f} MB)"
    except Exception:
        return f"🎵 {file_path.name}"


def format_transcript_file(file_path: Path) -> str:
    """
    Format transcript file metadata for display.

    Args:
        file_path: Path to the transcript file

    Returns:
        Formatted string with file name, size, and segment count
    """
    try:
        size_kb = file_path.stat().st_size / 1024

        # Try to read transcript to get segment count
        try:
            import json

            with open(file_path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "segments" in data:
                        segments = len(data["segments"])
                        return f"📄 {file_path.name} ({size_kb:.1f} KB, {segments} segments)"
                    elif "text" in data:
                        text_length = len(data["text"])
                        return f"📄 {file_path.name} ({size_kb:.1f} KB, {text_length} chars)"
        except Exception:
            pass

        return f"📄 {file_path.name} ({size_kb:.1f} KB)"
    except Exception:
        return f"📄 {file_path.name}"


def format_readable_transcript_file(file_path: Path) -> str:
    """
    Format readable transcript file (CSV/TXT) metadata for display.

    Args:
        file_path: Path to the readable transcript file

    Returns:
        Formatted string with file name, size, and type
    """
    try:
        size_kb = file_path.stat().st_size / 1024
        file_type = file_path.suffix.upper()
        return f"📄 {file_path.name} ({size_kb:.1f} KB, {file_type})"
    except Exception:
        return f"📄 {file_path.name}"


def format_generic_file(file_path: Path) -> str:
    """
    Format generic file metadata for display.

    Args:
        file_path: Path to the file

    Returns:
        Formatted string with file name and size
    """
    try:
        size_bytes = file_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        if size_mb < 1:
            size_kb = size_bytes / 1024
            return f"📄 {file_path.name} ({size_kb:.1f} KB)"
        return f"📄 {file_path.name} ({size_mb:.1f} MB)"
    except Exception:
        return f"📄 {file_path.name}"


def is_audio_file(file_path: Path) -> bool:
    """Check if a file is an audio file based on extension."""
    audio_extensions = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
    return file_path.suffix.lower() in audio_extensions
