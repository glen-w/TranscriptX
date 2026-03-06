"""
ClipService: extract segment clips with deterministic cache (path or bytes).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

MAX_CLIP_DURATION_SEC = 60.0
DEFAULT_PAD_MS = 50
DEFAULT_FORMAT = "mp3"
# Codec params for cache key: mp3 128k; wav 16k mono 16bit
CODEC_PARAMS = {"mp3": "128k", "wav": "16k_16bit_mono"}


def _find_ffmpeg() -> Optional[str]:
    import shutil

    p = shutil.which("ffmpeg")
    if p:
        return p
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if Path(candidate).exists():
            return candidate
    return None


def _extract_segment_ffmpeg(
    audio_path: Path,
    start_s: float,
    duration_s: float,
    output_path: Path,
    *,
    format: str = "mp3",
) -> bool:
    """Extract a segment to output_path. Returns True on success."""
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        return False
    base = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-vn",
        "-sn",
        "-dn",
    ]
    if format == "mp3":
        cmd = base + [
            "-ss",
            str(start_s),
            "-i",
            str(audio_path),
            "-t",
            str(duration_s),
            "-y",
            "-acodec",
            "libmp3lame",
            "-ab",
            "128k",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]
    else:
        cmd = base + [
            "-ss",
            str(start_s),
            "-i",
            str(audio_path),
            "-t",
            str(duration_s),
            "-y",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30
        )
        if (
            result.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            return True
    except Exception as e:
        logger.warning("ClipService ffmpeg extract failed: %s", e)
    return False


class ClipService:
    """
    Clip extraction with deterministic cache. Primary API: get_clip_path().
    Cache: {data_dir}/.cache/clips/{sha1(...)}.{ext}
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else Path(DATA_DIR)
        self._cache_dir = self._data_dir / ".cache" / "clips"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        format: str,
        pad_ms: int,
    ) -> str:
        start_ms = int(round(start_s * 1000))
        end_ms = int(round(end_s * 1000))
        codec = CODEC_PARAMS.get(format, "default")
        payload = f"{audio_path.resolve()!s}{start_ms}{end_ms}{format}{pad_ms}{codec}"
        return hashlib.sha1(payload.encode()).hexdigest()

    def get_clip_path(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        *,
        format: str = DEFAULT_FORMAT,
        pad_ms: int = DEFAULT_PAD_MS,
    ) -> Path:
        """
        Return path to cached clip; generate and cache if missing.
        Duration is clamped to MAX_CLIP_DURATION_SEC; start is clamped to >= 0.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        start_s = max(0.0, float(start_s))
        end_s = float(end_s)
        duration = end_s - start_s
        if duration <= 0:
            duration = 0.4
        if duration > MAX_CLIP_DURATION_SEC:
            logger.warning(
                "Clip duration %.1fs exceeds max %s; clamping.",
                duration,
                MAX_CLIP_DURATION_SEC,
            )
            duration = MAX_CLIP_DURATION_SEC
        pad_s = pad_ms / 1000.0
        extract_start = max(0.0, start_s - pad_s)
        extract_duration = min(duration + 2 * pad_s, MAX_CLIP_DURATION_SEC + 2 * pad_s)

        key = self._cache_key(audio_path, start_s, end_s, format, pad_ms)
        ext = "mp3" if format == "mp3" else "wav"
        out_path = self._cache_dir / f"{key}.{ext}"
        if out_path.exists():
            return out_path

        if _extract_segment_ffmpeg(
            audio_path, extract_start, extract_duration, out_path, format=format
        ):
            return out_path
        raise RuntimeError(
            f"Failed to extract clip {start_s:.1f}-{start_s + duration:.1f}s from {audio_path}"
        )

    def get_clip_bytes(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        *,
        format: str = DEFAULT_FORMAT,
        pad_ms: int = DEFAULT_PAD_MS,
    ) -> bytes:
        """Convenience: return bytes of the cached clip (e.g. for st.audio or HTTP)."""
        path = self.get_clip_path(
            audio_path, start_s, end_s, format=format, pad_ms=pad_ms
        )
        return path.read_bytes()
