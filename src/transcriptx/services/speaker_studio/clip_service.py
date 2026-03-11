"""
ClipService: extract segment clips with deterministic, versioned disk cache.

Key design points:
- Persistent ThreadPoolExecutor for background pre-warming.
- Unified in-flight registry: foreground get_clip_path() joins an already-running
  warm job rather than spawning a second ffmpeg process.
- Atomic generation: ffmpeg writes to a collision-proof temp file; os.replace()
  moves it to the final path so readers never see a partial file.
- Versioned cache key includes audio mtime_ns + size so stale clips from replaced
  source files are never reused.
- Bump CLIP_CACHE_SCHEMA_VERSION whenever ffmpeg args, padding, or normalization
  logic changes. Old files are ignored by disuse — no migration needed.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# ── constants ─────────────────────────────────────────────────────────────────

MAX_CLIP_DURATION_SEC = 60.0
DEFAULT_PAD_MS = 50
DEFAULT_FORMAT = "mp3"

# Bump this whenever ffmpeg args, normalization, or padding logic changes.
# Old cache files (different key) are ignored by disuse — no migration needed.
CLIP_CACHE_SCHEMA_VERSION = 2

# Codec params included in cache key so format changes invalidate correctly.
CODEC_PARAMS = {"mp3": "128k", "wav": "16k_16bit_mono"}

# Cache cleanup thresholds
_PRUNE_MAX_AGE_DAYS = 30
_PRUNE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


# ── ffmpeg helpers ────────────────────────────────────────────────────────────


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


# ── ClipService ───────────────────────────────────────────────────────────────


class ClipService:
    """
    Clip extraction with versioned, disk-backed cache and background pre-warming.

    Cache location: {data_dir}/.cache/clips/{sha1(...)}.{ext}
    Primary API:
        get_clip_path()   — guaranteed foreground path; joins in-flight warm job if present.
        get_clip_bytes()  — convenience wrapper returning bytes for st.audio.
        warm_clips()      — best-effort background pre-generation; never blocks caller.
        ffmpeg_available()— True if ffmpeg is installed.
        close()           — shutdown background executor on process teardown.

    Cache is process/session agnostic and shared via disk. Session state controls
    only UI behaviour and warm triggers, not clip ownership.
    """

    _MAX_INFLIGHT = 8  # backpressure: stop enqueuing warm jobs beyond this
    _WARM_WORKERS = 2  # keep narrow; ffmpeg is CPU-bound

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else Path(DATA_DIR)
        self._cache_dir = self._data_dir / ".cache" / "clips"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._executor = ThreadPoolExecutor(
            max_workers=self._WARM_WORKERS,
            thread_name_prefix="clip_warm",
        )
        # Unified in-flight registry for both warm-path and foreground collapses.
        self._inflight: Dict[str, Future] = {}
        self._lock = threading.Lock()

        # Observability counters — approximate (incremented under lock where possible).
        self._stats: Dict[str, float] = {
            "hits": 0,
            "misses": 0,
            "warm_enqueued": 0,
            "warm_ok": 0,
            "warm_fail": 0,
            "gen_ms_total": 0.0,
            "inflight_peak": 0,
        }

        # Lazy cache pruning — runs in background at startup if thresholds exceeded.
        self._prune_cache_if_needed()

    # ── cache key ─────────────────────────────────────────────────────────────

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
        try:
            stat = audio_path.stat()
            mtime_ns = stat.st_mtime_ns
            fsize = stat.st_size
        except OSError:
            mtime_ns = 0
            fsize = 0
        payload = (
            f"{audio_path.resolve()!s}"
            f":{mtime_ns}:{fsize}"
            f":{start_ms}:{end_ms}:{format}:{pad_ms}:{codec}"
            f":v{CLIP_CACHE_SCHEMA_VERSION}"
        )
        return hashlib.sha1(payload.encode()).hexdigest()

    # ── parameter computation ─────────────────────────────────────────────────

    def _compute_extract_params(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        format: str,
        pad_ms: int,
    ) -> Tuple[float, float, float, float, str, Path]:
        """Return (clamped_start_s, end_s, extract_start, extract_duration, key, out_path)."""
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
        return start_s, end_s, extract_start, extract_duration, key, out_path

    # ── atomic generation ─────────────────────────────────────────────────────

    def _generate_sync(
        self,
        audio_path: Path,
        extract_start: float,
        extract_duration: float,
        out_path: Path,
        format: str,
    ) -> None:
        """
        Generate clip synchronously, writing atomically via a collision-proof temp file.
        Uses pid + thread_id + uuid so concurrent callers never clobber each other's
        in-progress work. Cleans up the temp file on any failure.
        """
        tmp_path = out_path.with_name(
            f"{out_path.stem}"
            f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
        )
        t0 = time.monotonic()
        try:
            success = _extract_segment_ffmpeg(
                audio_path, extract_start, extract_duration, tmp_path, format=format
            )
            if success:
                os.replace(tmp_path, out_path)  # atomic on POSIX
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                with self._lock:
                    self._stats["gen_ms_total"] += elapsed_ms
                logger.debug(
                    "ClipService generated %s in %.0fms", out_path.name, elapsed_ms
                )
            else:
                raise RuntimeError(
                    f"ffmpeg failed for {audio_path!s} "
                    f"[{extract_start:.1f}s + {extract_duration:.1f}s]"
                )
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    # ── warm worker ───────────────────────────────────────────────────────────

    def _generate_safe(
        self,
        audio_path: Path,
        extract_start: float,
        extract_duration: float,
        key: str,
        out_path: Path,
        format: str,
    ) -> None:
        """
        Background warm worker. Generates clip, then clears inflight entry.
        Never raises — all exceptions are logged and swallowed.
        Worker threads never touch Streamlit APIs.
        """
        try:
            if not out_path.exists():
                self._generate_sync(
                    audio_path, extract_start, extract_duration, out_path, format=format
                )
            with self._lock:
                self._stats["warm_ok"] += 1
            logger.debug("clip_warm ok key=%s…", key[:8])
        except Exception as e:
            with self._lock:
                self._stats["warm_fail"] += 1
            logger.warning("clip_warm failed key=%s…: %s", key[:8], e)
        finally:
            with self._lock:
                self._inflight.pop(key, None)

    # ── public API ────────────────────────────────────────────────────────────

    def ffmpeg_available(self) -> bool:
        """Return True if ffmpeg is installed and locatable."""
        return _find_ffmpeg() is not None

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
        Return path to cached clip; generate if missing.

        If a warm job for the same key is already running, joins that future
        rather than spawning a second ffmpeg process. Falls back to synchronous
        generation if no warm job is in-flight or if the warm job failed.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        _, _, extract_start, extract_duration, key, out_path = (
            self._compute_extract_params(audio_path, start_s, end_s, format, pad_ms)
        )

        # Fast path: already cached.
        if out_path.exists():
            with self._lock:
                self._stats["hits"] += 1
            return out_path

        # Check whether a warm job is in-flight for this key.
        fut_to_join: Optional[Future] = None
        with self._lock:
            if out_path.exists():
                self._stats["hits"] += 1
                return out_path
            existing = self._inflight.get(key)
            if existing is not None and not existing.done():
                fut_to_join = existing

        if fut_to_join is not None:
            # Collapse onto the already-running warm job instead of duplicating work.
            try:
                fut_to_join.result(timeout=30)
            except Exception:
                pass
            if out_path.exists():
                with self._lock:
                    self._stats["hits"] += 1
                return out_path
            # Warm job failed; fall through to synchronous generation.

        # Generate synchronously in the calling (foreground) thread.
        with self._lock:
            self._stats["misses"] += 1
        self._generate_sync(
            audio_path, extract_start, extract_duration, out_path, format=format
        )
        if not out_path.exists():
            raise RuntimeError(
                f"Failed to extract clip {start_s:.1f}–{end_s:.1f}s from {audio_path}"
            )
        return out_path

    def get_clip_bytes(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        *,
        format: str = DEFAULT_FORMAT,
        pad_ms: int = DEFAULT_PAD_MS,
    ) -> bytes:
        """Convenience: return bytes of the cached clip (e.g. for st.audio)."""
        path = self.get_clip_path(
            audio_path, start_s, end_s, format=format, pad_ms=pad_ms
        )
        return path.read_bytes()

    def warm_clips(
        self,
        audio_path: Path,
        segments: List[Tuple[float, float]],
        *,
        format: str = DEFAULT_FORMAT,
    ) -> None:
        """
        Best-effort fire-and-forget: enqueue background clip generation for a list
        of (start_s, end_s) pairs.

        Returns immediately. Safe to call from the Streamlit render thread.
        Worker threads do only file I/O — never touch Streamlit APIs.

        Deduplicates: clips already cached or already in-flight are skipped.
        Applies backpressure: stops enqueuing when inflight cap is reached.
        """
        if not self.ffmpeg_available():
            return
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return

        for start_s, end_s in segments:
            try:
                _, _, extract_start, extract_duration, key, out_path = (
                    self._compute_extract_params(
                        audio_path, start_s, end_s, format, DEFAULT_PAD_MS
                    )
                )
            except Exception:
                continue

            if out_path.exists():
                continue

            with self._lock:
                if out_path.exists():
                    continue
                if len(self._inflight) >= self._MAX_INFLIGHT:
                    logger.debug("clip_warm: inflight cap reached, skipping remaining")
                    return
                if key in self._inflight and not self._inflight[key].done():
                    continue  # already queued or running

                fut = self._executor.submit(
                    self._generate_safe,
                    audio_path,
                    extract_start,
                    extract_duration,
                    key,
                    out_path,
                    format,
                )
                self._inflight[key] = fut
                self._stats["warm_enqueued"] += 1
                n = len(self._inflight)
                if n > self._stats["inflight_peak"]:
                    self._stats["inflight_peak"] = n

    def close(self) -> None:
        """Shutdown background executor. Call on app/process teardown."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ── cache cleanup ─────────────────────────────────────────────────────────

    def _prune_cache_if_needed(self) -> None:
        """Trigger lazy cache pruning in a background daemon thread."""
        t = threading.Thread(
            target=self._prune_cache, daemon=True, name="clip_prune"
        )
        t.start()

    def _prune_cache(self) -> None:
        """
        Delete cache files older than _PRUNE_MAX_AGE_DAYS or when total cache
        exceeds _PRUNE_MAX_BYTES. Oldest files are removed first.
        """
        try:
            now = time.time()
            max_age_s = _PRUNE_MAX_AGE_DAYS * 86400
            files: List[Tuple[Path, float, int]] = []
            total_size = 0
            for f in self._cache_dir.iterdir():
                if f.suffix not in (".mp3", ".wav"):
                    continue
                try:
                    stat = f.stat()
                    files.append((f, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size
                except OSError:
                    continue

            # Phase 1: delete files older than max age.
            survivors: List[Tuple[Path, float, int]] = []
            for f, mtime, size in files:
                if (now - mtime) > max_age_s:
                    try:
                        f.unlink()
                        total_size -= size
                        logger.debug("clip_prune deleted old file: %s", f.name)
                    except OSError:
                        pass
                else:
                    survivors.append((f, mtime, size))

            # Phase 2: if still over size limit, delete oldest first.
            if total_size > _PRUNE_MAX_BYTES:
                survivors.sort(key=lambda x: x[1])  # oldest mtime first
                for f, _mtime, size in survivors:
                    if total_size <= _PRUNE_MAX_BYTES:
                        break
                    try:
                        f.unlink()
                        total_size -= size
                        logger.debug("clip_prune deleted oversized: %s", f.name)
                    except OSError:
                        pass
        except Exception as e:
            logger.warning("clip_prune failed: %s", e)
