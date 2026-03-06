from __future__ import annotations

import hashlib
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, Tuple

from transcriptx.core.utils.lazy_imports import optional_import  # type: ignore[import-untyped]
from transcriptx.core.utils.run_manifest import compute_file_hash  # type: ignore[import-untyped]


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
SEEKABLE_EXTENSIONS = {".wav", ".flac", ".ogg"}  # soundfile typically supports these


def resolve_audio_path(*, transcript_path: str, output_dir: str | None) -> str | None:
    """
    Resolve an audio file path for a transcript.

    Primary: processing state / resolver via find_original_audio_file()
    Fallback: scan output_dir for any audio artifacts.
    """
    try:
        from transcriptx.core.utils.file_rename import find_original_audio_file

        p = find_original_audio_file(transcript_path)
        if p and Path(p).exists():
            return str(Path(p))
    except Exception:
        pass

    if output_dir:
        try:
            root = Path(output_dir)
            if root.exists():
                for ext in AUDIO_EXTENSIONS:
                    matches = list(root.rglob(f"*{ext}"))
                    if matches:
                        return str(matches[0])
        except Exception:
            pass

    return None


def compute_audio_fingerprint(path: str, *, strict: bool) -> str:
    """
    Compute a cache key for an audio file.

    - strict=False: sha256(size:mtime_ns) fast fingerprint
    - strict=True: sha256 file content hash (may be slow on long audio)
    """
    p = Path(path)
    if not p.exists():
        return "missing"
    if not strict:
        st = p.stat()
        payload = f"{st.st_size}:{getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9))}"
        return "fastsha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    full = compute_file_hash(p, algorithm="sha256")
    return full or "sha256:unknown"


def ensure_cached_wav(
    audio_path: str, *, cache_dir: Path, sample_rate: int
) -> Tuple[str, Dict[str, Any]]:
    """
    Ensure we have a seekable (wav) file for segment-level random access.

    For mp3/m4a/aac: prefer ffmpeg to cached wav. If ffmpeg missing, fall back to
    librosa full-decode (still returns a cached wav for repeatability).
    """
    src = Path(audio_path)
    meta: Dict[str, Any] = {"source_path": str(src), "source_ext": src.suffix.lower()}
    cache_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() in {".wav"}:
        meta["decoder"] = "soundfile"
        return str(src), meta

    # If soundfile can read it seekably (flac/ogg), just use it directly
    if src.suffix.lower() in SEEKABLE_EXTENSIONS:
        meta["decoder"] = "soundfile"
        return str(src), meta

    # Convert to wav in cache
    fp = compute_audio_fingerprint(str(src), strict=False)
    target = cache_dir / f"{src.stem}.{fp.replace(':', '_')}.{sample_rate}hz.wav"
    if target.exists() and target.stat().st_size > 0:
        meta["decoder"] = "ffmpeg_cached"
        meta["cached"] = True
        meta["cached_path"] = str(target)
        return str(target), meta

    ffmpeg = shutil_which("ffmpeg")
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(target),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        meta["decoder"] = "ffmpeg"
        meta["cached"] = True
        meta["cached_path"] = str(target)
        return str(target), meta

    # Fallback: librosa full decode then write wav via soundfile
    librosa = optional_import(
        "librosa", "audio decoding for voice features", "voice", auto_install=True
    )
    sf = optional_import(
        "soundfile", "audio decoding for voice features", "voice", auto_install=True
    )
    y, sr = librosa.load(str(src), sr=sample_rate, mono=True)
    sf.write(str(target), y, sample_rate)
    meta["decoder"] = "librosa"
    meta["cached"] = True
    meta["cached_path"] = str(target)
    return str(target), meta


def read_audio_segment(
    *,
    wav_path: str,
    start_s: float,
    end_s: float,
    sample_rate: int,
    pad_s: float,
) -> "np.ndarray":
    """
    Read a padded segment of audio as mono float32, resampled to sample_rate.
    """
    import numpy as np

    sf = optional_import(
        "soundfile", "voice feature extraction", "voice", auto_install=True
    )
    p = Path(wav_path)
    if not p.exists():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    start_s = max(0.0, float(start_s) - float(pad_s))
    end_s = max(start_s, float(end_s) + float(pad_s))

    with sf.SoundFile(str(p), "r") as f:
        src_sr = int(f.samplerate)
        start_frame = int(start_s * src_sr)
        end_frame = int(end_s * src_sr)
        start_frame = max(0, min(start_frame, len(f)))
        end_frame = max(start_frame, min(end_frame, len(f)))
        f.seek(start_frame)
        frames = end_frame - start_frame
        audio = f.read(frames, dtype="float32", always_2d=True)

    # Mono
    if audio.shape[1] > 1:
        audio = np.mean(audio, axis=1)
    else:
        audio = audio[:, 0]

    if src_sr != sample_rate:
        librosa = optional_import(
            "librosa", "resampling for voice features", "voice", auto_install=True
        )
        audio = librosa.resample(audio, orig_sr=src_sr, target_sr=sample_rate)

    return audio.astype("float32", copy=False)


def shutil_which(binary: str) -> str | None:
    """Wrapper around shutil.which to avoid env lookups here."""
    return shutil.which(binary)
