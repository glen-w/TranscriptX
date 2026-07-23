"""Dedicated deletable voice excerpt cache (not playback ClipService)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from transcriptx.core.speaker_profiles.path_safety import assert_safe_relpath
from transcriptx.core.speaker_profiles.voice.excerpts import ExcerptPlan
from transcriptx.core.speaker_profiles.voice.versioning import (
    PREPROCESSING_POLICY_ID,
    QUALITY_POLICY_ID,
)

VOICE_EXCERPT_CACHE_SCHEMA_VERSION = 1


def _find_ffmpeg() -> str | None:
    import shutil

    p = shutil.which("ffmpeg")
    if p:
        return p
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if Path(candidate).exists():
            return candidate
    return None


def excerpt_cache_key(
    *,
    audio_content_sha256: str,
    start_us: int,
    end_us: int,
    sample_rate: int = 16000,
    model_generation_id: str = "",
) -> str:
    payload = json.dumps(
        [
            "voice_excerpt_cache.v1",
            VOICE_EXCERPT_CACHE_SCHEMA_VERSION,
            audio_content_sha256,
            start_us,
            end_us,
            sample_rate,
            PREPROCESSING_POLICY_ID,
            QUALITY_POLICY_ID,
            model_generation_id,
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class VoiceExcerptStore:
    """WAV excerpt store under ``speaker_profiles/.cache/voice/excerpts/``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.cache_root = self.root / ".cache" / "voice" / "excerpts"

    def path_for_key(self, key: str) -> Path:
        assert_safe_relpath(f".cache/voice/excerpts/{key}.wav", what="voice excerpt")
        # keys are hex digests — still validate no separators
        if "/" in key or "\\" in key or ".." in key:
            from transcriptx.core.speaker_profiles.voice.errors import VoicePathError

            raise VoicePathError(f"invalid excerpt cache key: {key!r}")
        return self.cache_root / f"{key}.wav"

    def get_or_extract(
        self,
        *,
        audio_path: Path,
        audio_content_sha256: str,
        plan: ExcerptPlan,
        sample_rate: int = 16000,
        model_generation_id: str = "",
    ) -> Path:
        key = excerpt_cache_key(
            audio_content_sha256=audio_content_sha256,
            start_us=plan.start_us,
            end_us=plan.end_us,
            sample_rate=sample_rate,
            model_generation_id=model_generation_id,
        )
        dest = self.path_for_key(key)
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
        self.cache_root.mkdir(parents=True, exist_ok=True)
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            from transcriptx.core.speaker_profiles.voice.errors import VoiceFeatureError

            raise VoiceFeatureError("ffmpeg required for voice excerpt extraction")
        duration = max(0.0, plan.end - plan.start)
        fd, tmp_name = tempfile.mkstemp(
            suffix=".wav", dir=str(self.cache_root), prefix=".tmp_"
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{plan.start:.6f}",
                "-t",
                f"{duration:.6f}",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                str(tmp_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            os.replace(tmp_path, dest)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        return dest

    def clear_all(self) -> int:
        """Delete all cached excerpts. Returns number of files removed."""
        if not self.cache_root.is_dir():
            return 0
        n = 0
        for path in self.cache_root.glob("*.wav"):
            path.unlink(missing_ok=True)
            n += 1
        for path in self.cache_root.glob(".tmp_*"):
            path.unlink(missing_ok=True)
            n += 1
        return n
