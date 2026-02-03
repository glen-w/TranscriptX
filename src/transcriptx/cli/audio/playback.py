"""Audio utilities module."""

import hashlib
import subprocess
import shutil
import os
import sys
import signal
import tempfile
import time
import warnings
from pathlib import Path
from typing import Optional

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError, CouldntEncodeError

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None
    CouldntDecodeError = Exception
    CouldntEncodeError = Exception

try:
    # Suppress pkg_resources deprecation warning from webrtcvad
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
        import webrtcvad

    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    webrtcvad = None

try:
    import pyloudnorm as pyln

    PYLoudnorm_AVAILABLE = True
except ImportError:
    PYLoudnorm_AVAILABLE = False
    pyln = None

try:
    import noisereduce as nr

    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    nr = None

try:
    import soundfile as sf

    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False
    sf = None

from transcriptx.core.utils.logger import get_logger, log_error
from rich.console import Console

logger = get_logger()
console = Console()

# Cache for ffmpeg path to avoid repeated lookups
_FFMPEG_PATH_CACHE: str | None = None


from .cache import AudioCacheManager
from .clip_cache import ClipCache
from .persistent_player import MPVPlayer, check_mpv_available
from .slicing import slice_wav_pcm
from .tools import check_ffplay_available, check_ffmpeg_available, _find_ffmpeg_path
from .utils import get_audio_duration


def play_audio_file(audio_path: Path) -> Optional[subprocess.Popen]:
    """
    Play an audio file using platform-appropriate tool (non-blocking).

    On macOS, prefers ffplay if available (for seeking support), falls back to afplay.
    On Linux, uses ffplay if available.
    Playback runs in the background, allowing the user to continue interacting.

    Args:
        audio_path: Path to the audio file to play

    Returns:
        subprocess.Popen: Process object if playback started successfully, None otherwise
    """
    try:
        if audio_path is None:
            console.print("[red]❌ Audio file path is None[/red]")
            return None

        if not audio_path.exists():
            console.print(f"[red]❌ Audio file not found: {audio_path}[/red]")
            return None

        # Check if ffplay is available (preferred for seeking support)
        ffplay_available, _ = check_ffplay_available()
        is_macos = sys.platform == "darwin"

        if ffplay_available:
            # Use ffplay (supports seeking)
            try:
                # Find ffplay path (same logic as check_ffplay_available)
                ffplay_path = shutil.which("ffplay")
                if not ffplay_path:
                    common_paths = [
                        "/opt/homebrew/bin/ffplay",
                        "/usr/local/bin/ffplay",
                        "/usr/bin/ffplay",
                    ]
                    for path in common_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            ffplay_path = path
                            break

                if ffplay_path:
                    # On macOS, skip -nodisp as it may not route audio properly
                    # On other platforms, use -nodisp for headless playback
                    cmd = [ffplay_path, "-autoexit", str(audio_path)]
                    if not is_macos:
                        cmd.insert(1, "-nodisp")
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True,
                    )
                    return process
            except FileNotFoundError:
                # Fall through to afplay on macOS
                if not is_macos:
                    console.print(
                        "[red]❌ ffplay not found. Install ffmpeg to use audio playback on this platform.[/red]"
                    )
                    return None

        if is_macos:
            # Use afplay on macOS (built-in, no dependencies, but no seeking)
            try:
                process = subprocess.Popen(
                    ["afplay", str(audio_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                return process
            except FileNotFoundError:
                console.print(
                    "[red]❌ afplay not found. This should not happen on macOS.[/red]"
                )
                return None
        else:
            console.print(
                "[red]❌ No audio playback tool available. Install ffmpeg to use audio playback.[/red]"
            )
            return None

    except Exception as e:
        audio_name = audio_path.name if audio_path is not None else "unknown"
        error_msg = f"Error playing audio file {audio_name}: {str(e)}"
        console.print(f"[red]❌ {error_msg}[/red]")
        log_error("AUDIO_PLAYBACK", error_msg, exception=e)
        return None


def play_audio_file_from_position(
    audio_path: Path, start_position: float
) -> Optional[subprocess.Popen]:
    """
    Play an audio file starting from a specific position (requires ffplay).

    Args:
        audio_path: Path to the audio file to play
        start_position: Start position in seconds

    Returns:
        subprocess.Popen: Process object if playback started successfully, None otherwise
    """
    try:
        if audio_path is None:
            console.print("[red]❌ Audio file path is None[/red]")
            return None

        if not audio_path.exists():
            console.print(f"[red]❌ Audio file not found: {audio_path}[/red]")
            return None

        # Check if ffplay is available (required for seeking)
        ffplay_available, error_msg = check_ffplay_available()
        if not ffplay_available:
            console.print(f"[yellow]⚠️ Seeking requires ffplay: {error_msg}[/yellow]")
            return None

        # Get file duration to validate position
        duration = get_audio_duration(audio_path)
        if duration is not None:
            if start_position < 0:
                start_position = 0
            elif start_position >= duration:
                console.print(
                    f"[yellow]⚠️ Start position ({start_position:.1f}s) is beyond file duration ({duration:.1f}s)[/yellow]"
                )
                return None

        # Use ffplay with -ss option for seeking
        # Find ffplay path (same logic as check_ffplay_available)
        ffplay_path = shutil.which("ffplay")
        if not ffplay_path:
            common_paths = [
                "/opt/homebrew/bin/ffplay",
                "/usr/local/bin/ffplay",
                "/usr/bin/ffplay",
            ]
            for path in common_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    ffplay_path = path
                    break

        if not ffplay_path:
            console.print("[red]❌ ffplay not found. Cannot seek.[/red]")
            return None

        # On macOS, skip -nodisp as it may not route audio properly
        # On other platforms, use -nodisp for headless playback
        is_macos = sys.platform == "darwin"
        cmd = [
            ffplay_path,
            "-autoexit",
            "-ss",
            str(int(start_position)),
            str(audio_path),
        ]
        if not is_macos:
            cmd.insert(1, "-nodisp")

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
        )
        return process

    except Exception as e:
        audio_name = audio_path.name if audio_path is not None else "unknown"
        error_msg = f"Error playing audio file {audio_name} from position {start_position}s: {str(e)}"
        console.print(f"[red]❌ {error_msg}[/red]")
        log_error("AUDIO_PLAYBACK", error_msg, exception=e)
        return None


def stop_audio_playback(process: Optional[subprocess.Popen]) -> bool:
    """
    Stop audio playback by terminating the process.

    Args:
        process: subprocess.Popen process object to terminate

    Returns:
        bool: True if process was terminated successfully, False otherwise
    """
    if process is None:
        return False

    try:
        # Check if process is still running
        if process.poll() is None:
            # Process is still running, terminate it
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    process.terminate()
            else:
                process.terminate()
            # Wait a bit for graceful termination
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                # Force kill if it didn't terminate gracefully
                if os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        process.kill()
                else:
                    process.kill()
                process.wait()
            return True
        else:
            # Process already finished
            return True
    except Exception as e:
        error_msg = f"Error stopping audio playback: {str(e)}"
        log_error("AUDIO_PLAYBACK", error_msg, exception=e)
        return False


class SegmentPlayer:
    """Play time-bounded segments with stop-before-play behavior."""

    def __init__(self, audio_path: Optional[Path] = None) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._temp_clip: Optional[Path] = None
        self._warned_no_playback = False
        self._cache_manager: Optional[AudioCacheManager] = None
        self._clip_cache: Optional[ClipCache] = None
        self._mpv_player: Optional[MPVPlayer] = None
        self._mpv_checked = False
        self._mpv_available = False
        self._audio_path: Optional[Path] = audio_path
        self._last_playback_used_mpv = False

    def stop(self) -> None:
        """Stop any current playback and clean up temp clips."""
        if self._proc is not None:
            stop_audio_playback(self._proc)
            self._proc = None
        if self._mpv_player:
            self._mpv_player.pause()
        self._cleanup_temp_clip()

    def play_file(self, audio_path: Path) -> bool:
        """Play a full audio file with stop-before-play behavior."""
        self.stop()
        if audio_path is None or not audio_path.exists():
            self._warn_once("Audio file not found; playback disabled.")
            return False
        proc = play_audio_file(audio_path)
        if proc:
            self._proc = proc
            return True
        self._warn_once("Playback unavailable. Install ffmpeg for audio preview.")
        return False

    @property
    def current_process(self) -> Optional[subprocess.Popen]:
        return self._proc

    @property
    def is_playing(self) -> bool:
        if self._proc and self._proc.poll() is None:
            return True
        if self._last_playback_used_mpv and self._mpv_player:
            return self._mpv_player.is_running()
        return False

    def cleanup(self) -> None:
        """Release resources and clear session caches."""
        self.stop()
        if self._mpv_player:
            self._mpv_player.stop()
            self._mpv_player = None
        if self._clip_cache:
            self._clip_cache.clear_cache()
            self._clip_cache = None

    def play_segment(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        *,
        pad_before: float = 0.0,
        pad_after: float = 0.0,
        min_duration: float = 0.4,
    ) -> None:
        """Play a segment from the audio file, with optional padding."""
        self.stop()
        self._last_playback_used_mpv = False
        self._audio_path = audio_path

        if audio_path is None or not audio_path.exists():
            self._warn_once("Audio file not found; playback disabled.")
            return
        
        # Validate that the file is actually an audio file, not a JSON or other file
        audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".opus", ".mp4", ".m4v", ".webm"}
        if audio_path.suffix.lower() not in audio_extensions:
            logger.warning(
                f"File is not an audio file (extension: {audio_path.suffix}): {audio_path}. "
                f"Expected one of: {', '.join(sorted(audio_extensions))}"
            )
            self._warn_once(f"Invalid audio file format: {audio_path.name}")
            return

        start, duration = self._normalize_segment(
            audio_path, start_s, end_s, pad_before, pad_after, min_duration
        )
        if duration <= 0:
            self._warn_once("Audio segment duration invalid; playback skipped.")
            return

        # Prefer persistent mpv playback if available
        if self._try_play_with_mpv(audio_path, start, duration):
            self._last_playback_used_mpv = True
            return

        # Check LRU clip cache before slicing
        cached_clip = self._get_cached_clip(
            audio_path, start, duration, pad_before, pad_after
        )
        if cached_clip:
            proc = play_audio_file(cached_clip)
            if proc:
                self._proc = proc
                return

        # Create PCM cache and slice using wave module
        pcm_path = self._get_pcm_cache(audio_path)
        if pcm_path:
            clip_path = self._slice_to_clip(
                pcm_path, audio_path, start, duration, pad_before, pad_after
            )
            if clip_path:
                proc = play_audio_file(clip_path)
                if proc:
                    self._proc = proc
                    return

        # Fallback to ffplay/temp clip behavior
        is_macos = sys.platform == "darwin"

        if is_macos:
            proc = self._play_temp_clip(audio_path, start, duration)
            if proc:
                self._proc = proc
                logger.debug(
                    f"Using temp clip method on macOS for segment {start:.2f}s-{start+duration:.2f}s"
                )
                return
            logger.debug("Temp clip method failed on macOS, will try ffplay fallback")

        ffplay_available, _ = check_ffplay_available()
        if ffplay_available:
            proc = self._play_ffplay(audio_path, start, duration)
            if proc:
                self._proc = proc
                return

        if not is_macos:
            proc = self._play_temp_clip(audio_path, start, duration)
            if proc:
                self._proc = proc
                return

        self._warn_once("Playback unavailable. Install ffmpeg for audio preview.")

    def _normalize_segment(
        self,
        audio_path: Path,
        start_s: float,
        end_s: float,
        pad_before: float,
        pad_after: float,
        min_duration: float,
    ) -> tuple[float, float]:
        start = max(0.0, float(start_s) - pad_before)
        end = float(end_s) + pad_after if end_s is not None else start + min_duration
        if end <= start:
            end = start + min_duration

        duration = end - start
        if duration < min_duration:
            duration = min_duration
            end = start + duration

        audio_duration = get_audio_duration(audio_path)
        if audio_duration is not None:
            if start > audio_duration:
                start = max(0.0, audio_duration - min_duration)
            if end > audio_duration:
                end = audio_duration
            duration = max(0.0, end - start)
            if duration < min_duration and audio_duration > 0:
                duration = min_duration
                start = max(0.0, end - duration)

        return start, duration

    def _ensure_cache_manager(self) -> AudioCacheManager:
        if self._cache_manager is None:
            self._cache_manager = AudioCacheManager()
        return self._cache_manager

    def _ensure_clip_cache(self) -> ClipCache:
        if self._clip_cache is None:
            self._clip_cache = ClipCache()
        return self._clip_cache

    def _get_pcm_cache(self, audio_path: Path) -> Optional[Path]:
        try:
            cache_manager = self._ensure_cache_manager()
            return cache_manager.get_or_create_cache(audio_path)
        except Exception as exc:
            logger.debug(f"PCM cache unavailable: {exc}")
            return None

    def _get_cached_clip(
        self,
        audio_path: Path,
        start: float,
        duration: float,
        pad_before: float,
        pad_after: float,
    ) -> Optional[Path]:
        clip_cache = self._ensure_clip_cache()
        key = self._clip_cache_key(audio_path, start, duration, pad_before, pad_after)
        return clip_cache.get_clip(key)

    def _slice_to_clip(
        self,
        pcm_path: Path,
        audio_path: Path,
        start: float,
        duration: float,
        pad_before: float,
        pad_after: float,
    ) -> Optional[Path]:
        clip_cache = self._ensure_clip_cache()
        key = self._clip_cache_key(audio_path, start, duration, pad_before, pad_after)
        clip_name = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        clip_path = clip_cache.cache_dir / f"{clip_name}.wav"
        if clip_path.exists():
            clip_cache.put_clip(key, clip_path)
            return clip_path

        if slice_wav_pcm(pcm_path, start, duration, clip_path):
            clip_cache.put_clip(key, clip_path)
            return clip_path
        return None

    def _clip_cache_key(
        self,
        audio_path: Path,
        start: float,
        duration: float,
        pad_before: float,
        pad_after: float,
    ) -> tuple:
        audio_hash = self._compute_audio_hash(audio_path)
        return (
            audio_hash,
            int(start * 1000),
            int(duration * 1000),
            int(pad_before * 1000),
            int(pad_after * 1000),
        )

    def _compute_audio_hash(self, audio_path: Path) -> str:
        try:
            stat = audio_path.stat()
            key_source = f"{audio_path.resolve()}|{stat.st_size}|{stat.st_mtime}"
        except OSError:
            key_source = str(audio_path.resolve())
        return hashlib.sha256(key_source.encode("utf-8")).hexdigest()

    def _try_play_with_mpv(
        self, audio_path: Path, start: float, duration: float
    ) -> bool:
        if not self._mpv_checked:
            self._mpv_checked = True
            self._mpv_available, _ = check_mpv_available()
            if self._mpv_available:
                self._mpv_player = MPVPlayer()

        if not self._mpv_available or not self._mpv_player:
            return False

        return self._mpv_player.play_segment(audio_path, start, duration)

    def _play_ffplay(
        self, audio_path: Path, start: float, duration: float
    ) -> Optional[subprocess.Popen]:
        # Validate audio file exists and is readable
        if not audio_path.exists():
            logger.warning(f"Audio file does not exist: {audio_path}")
            return None
        if not os.access(audio_path, os.R_OK):
            logger.warning(f"Audio file is not readable: {audio_path}")
            return None

        ffplay_path = shutil.which("ffplay")
        if not ffplay_path:
            for path in [
                "/opt/homebrew/bin/ffplay",
                "/usr/local/bin/ffplay",
                "/usr/bin/ffplay",
            ]:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    ffplay_path = path
                    break
        if not ffplay_path:
            logger.debug("ffplay not found in PATH or common locations")
            return None

        try:
            # Use -nodisp to hide video window, but keep audio output
            # -autoexit exits when playback finishes
            # -loglevel error only shows errors (suppresses info messages)
            # Note: On macOS, -nodisp may not route audio properly, so we try
            # without it first on macOS. On other platforms, prefer -nodisp.
            is_macos = sys.platform == "darwin"
            if is_macos:
                # On macOS, use a small but visible window to ensure CoreAudio routing works
                # A 1x1 window might be rejected by macOS, so use a small but valid size
                cmd = [
                    ffplay_path,
                    "-ss",
                    str(start),
                    "-t",
                    str(duration),
                    "-autoexit",  # Exit when done
                    "-nostats",  # No stats overlay
                    "-loglevel",
                    "error",  # Only show errors
                    "-hide_banner",  # Hide banner
                    "-window_title",
                    "TranscriptX Audio",  # Window title for audio routing
                    "-x",
                    "100",  # Small but valid window width
                    "-y",
                    "100",  # Small but valid window height
                    str(audio_path),
                ]
            else:
                # On other platforms, prefer -nodisp (headless playback)
                cmd = [
                    ffplay_path,
                    "-ss",
                    str(start),
                    "-t",
                    str(duration),
                    "-autoexit",  # Exit when done
                    "-nostats",  # No stats overlay
                    "-loglevel",
                    "error",  # Only show errors
                    "-hide_banner",  # Hide banner
                    "-nodisp",  # No video display
                    str(audio_path),
                ]

            # Try the command (only one attempt now, platform-specific)
            try:
                logger.debug(
                    f"Running ffplay: -ss {start:.2f} -t {duration:.2f} {'(macOS with window)' if is_macos else '(-nodisp)'} {audio_path.name}"
                )

                # Use PIPE for stderr so we can check for errors
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,  # Capture stderr to check for errors
                    start_new_session=True,
                )
                # Check if process started successfully
                time.sleep(0.3)  # Give it time to start and potentially fail
                if process.poll() is not None:
                    # Process exited immediately - read error
                    try:
                        stderr_output = (
                            process.stderr.read().decode("utf-8", errors="ignore")
                            if process.stderr
                            else ""
                        )
                        exit_code = (
                            process.returncode
                            if process.returncode is not None
                            else "unknown"
                        )

                        if stderr_output:
                            error_msg = stderr_output[:300].strip()
                            logger.warning(
                                f"ffplay exited immediately (code {exit_code}): {error_msg}"
                            )
                            logger.debug(f"Full command: {' '.join(cmd)}")
                            console.print(
                                f"[yellow]⚠️ ffplay error: {error_msg}[/yellow]"
                            )
                            return None
                        else:
                            # Exit code 0 with no error might mean file issue or very short segment
                            logger.warning(
                                f"ffplay exited immediately (code {exit_code}) with no error message. Audio: {audio_path}, exists: {audio_path.exists()}, segment: {start:.2f}s-{start+duration:.2f}s"
                            )
                            logger.debug(f"Full command: {' '.join(cmd)}")
                            return None
                    except Exception as e:
                        logger.warning(f"Error reading ffplay stderr: {e}")
                        return None

                # Process is running - log success at debug level (only show errors to user)
                method = "macOS window" if is_macos else "nodisp"
                logger.debug(
                    f"ffplay started ({method}): PID {process.pid}, segment {start:.2f}s-{start+duration:.2f}s from {audio_path.name}"
                )
                return process
            except Exception as exc:
                logger.warning(f"ffplay segment playback failed: {exc}")
                return None
        except Exception as exc:
            logger.warning(f"ffplay setup failed: {exc}")
            return None

    def _play_afplay(
        self, audio_path: Path, start: float, duration: float
    ) -> Optional[subprocess.Popen]:
        # afplay on macOS doesn't support seeking or duration limits
        # We need to use ffmpeg to create a temp clip instead
        # This method is kept for compatibility but will always return None
        # The caller should fall back to _play_temp_clip
        return None

    def _play_temp_clip(
        self, audio_path: Path, start: float, duration: float
    ) -> Optional[subprocess.Popen]:
        ffmpeg_available, ffmpeg_error = check_ffmpeg_available()
        if not ffmpeg_available:
            logger.debug(f"ffmpeg not available: {ffmpeg_error}")
            return None

        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = Path(temp_file.name)
            temp_file.close()

            # Find ffmpeg path (same logic as check_ffmpeg_available)
            ffmpeg_path = _find_ffmpeg_path()
            if not ffmpeg_path:
                logger.debug("ffmpeg path not found")
                return None

            logger.debug(f"Creating temp clip: segment {start:.2f}s-{start+duration:.2f}s from {audio_path.name}")
            
            base_flags = [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-vn",
                "-sn",
                "-dn",
            ]
            # Try input seeking first (more accurate but may fail with some formats)
            # If that fails, try output seeking (less accurate but more compatible)
            commands_to_try = [
                # Method 1: Input seeking (more accurate timing)
                base_flags
                + [
                    "-ss",
                    str(start),
                    "-i",
                    str(audio_path),
                    "-t",
                    str(duration),
                    "-y",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(temp_path),
                ],
                # Method 2: Output seeking (more compatible with some formats)
                base_flags
                + [
                    "-i",
                    str(audio_path),
                    "-ss",
                    str(start),
                    "-t",
                    str(duration),
                    "-y",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(temp_path),
                ],
                # Method 3: Let ffmpeg auto-detect codec (most compatible)
                base_flags
                + [
                    "-i",
                    str(audio_path),
                    "-ss",
                    str(start),
                    "-t",
                    str(duration),
                    "-y",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(temp_path),
                ],
            ]
            
            result = None
            last_error = None
            for i, cmd in enumerate(commands_to_try, 1):
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.debug(f"ffmpeg temp-clip succeeded with method {i}")
                    break
                else:
                    # Extract meaningful error message (skip version banner, get actual error)
                    error_parts = []
                    if result.stderr:
                        stderr_lines = result.stderr.split('\n')
                        # Skip version banner (usually first few lines)
                        # Look for actual error messages (lines with "Error", "error", "failed", etc.)
                        for line in stderr_lines:
                            line_lower = line.lower()
                            if any(keyword in line_lower for keyword in ['error', 'failed', 'invalid', 'cannot', 'unable']):
                                error_parts.append(line.strip())
                        # If no obvious error keywords, take last non-empty lines (actual errors usually at end)
                        if not error_parts:
                            error_parts = [line.strip() for line in stderr_lines[-10:] if line.strip() and 'version' not in line.lower() and 'copyright' not in line.lower()]
                    if result.stdout:
                        stdout_lines = result.stdout.split('\n')
                        for line in stdout_lines:
                            line_lower = line.lower()
                            if any(keyword in line_lower for keyword in ['error', 'failed', 'invalid', 'cannot', 'unable']):
                                error_parts.append(line.strip())
                    
                    # Combine error parts or use full stderr if nothing extracted
                    if error_parts:
                        error_msg = ' | '.join(error_parts[:5])  # Limit to first 5 error lines
                    else:
                        # Fallback: get last 500 chars of stderr (errors usually at end)
                        error_msg = (result.stderr[-500:] if result.stderr else "Unknown error").strip()
                        if not error_msg or len(error_msg) < 10:
                            error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                    
                    last_error = (result.returncode, error_msg)
                    logger.debug(f"ffmpeg temp-clip method {i} failed (exit {result.returncode}): {error_msg[:300]}")
            
            if result is None or result.returncode != 0:
                error_code, error_msg = last_error if last_error else (0, "Unknown error")
                # Show the extracted error message
                logger.warning(
                    f"ffmpeg temp-clip failed (exit {error_code}): {error_msg}"
                )
                # Log the audio file info for debugging
                if audio_path.exists():
                    try:
                        file_size = audio_path.stat().st_size
                        logger.debug(f"Audio file: {audio_path}, size: {file_size} bytes, segment: {start:.2f}s-{start+duration:.2f}s")
                    except OSError:
                        pass
                try:
                    temp_path.unlink()
                except OSError:
                    pass
                return None

            # Check if temp file was created and has content
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                logger.warning("ffmpeg temp-clip file is empty or missing")
                try:
                    temp_path.unlink()
                except OSError:
                    pass
                return None

            self._temp_clip = temp_path
            proc = play_audio_file(temp_path)
            return proc
        except subprocess.TimeoutExpired:
            try:
                if "temp_path" in locals():
                    temp_path.unlink()
            except OSError:
                pass
            return None
        except Exception:
            return None

    def _cleanup_temp_clip(self) -> None:
        if self._temp_clip and self._temp_clip.exists():
            try:
                self._temp_clip.unlink()
            except OSError:
                pass
        self._temp_clip = None

    def _warn_once(self, message: str) -> None:
        if self._warned_no_playback:
            return
        console.print(f"[yellow]⚠️ {message}[/yellow]")
        self._warned_no_playback = True
