"""Audio utilities module."""

import os
import warnings
import numpy as np
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any

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
        warnings.filterwarnings(
            "ignore", category=UserWarning, message=".*pkg_resources.*"
        )
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


def assess_audio_noise(audio_path: Path) -> Dict[str, Any]:
    """
    Assess audio noise level and suggest preprocessing steps.

    Uses multiple metrics including WebRTC VAD, SNR proxy, clipping detection,
    and DC offset to determine noise level and suggest appropriate preprocessing.

    Args:
        audio_path: Path to audio file to assess

    Returns:
        Dictionary with:
        - noise_level: "low", "medium", or "high"
        - suggested_steps: List of suggested preprocessing steps
        - confidence: Confidence score (0.0-1.0)
        - metrics: Detailed metrics (RMS, SNR proxy, clipping, DC offset, etc.)
    """
    assessment = {
        "noise_level": "low",
        "suggested_steps": [],
        "confidence": 0.0,
        "metrics": {},
    }

    if not PYDUB_AVAILABLE:
        return assessment

    try:
        # Load audio
        audio = AudioSegment.from_file(str(audio_path))

        # Convert to numpy array for analysis
        samples = np.array(audio.get_array_of_samples())

        # Handle stereo/mono
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)  # Convert to mono for analysis

        # Normalize to -1.0 to 1.0 range
        if audio.sample_width == 1:
            samples = samples.astype(np.float32) / 128.0 - 1.0
        elif audio.sample_width == 2:
            samples = samples.astype(np.float32) / 32768.0
        elif audio.sample_width == 4:
            samples = samples.astype(np.float32) / 2147483648.0

        # Calculate basic metrics
        rms = np.sqrt(np.mean(samples**2))
        rms_db = 20 * np.log10(rms + 1e-10)
        peak = np.max(np.abs(samples))
        peak_db = 20 * np.log10(peak + 1e-10)

        # Clipping detection
        max_possible = 1.0 - (1.0 / (2 ** (audio.sample_width * 8 - 1)))
        clipped_samples = np.sum(np.abs(samples) >= max_possible * 0.99)
        clipping_percentage = (clipped_samples / len(samples)) * 100

        # DC offset detection
        dc_offset = np.mean(samples)
        dc_offset_db = 20 * np.log10(abs(dc_offset) + 1e-10)

        # Zero crossing rate
        zero_crossings = np.sum(np.diff(np.signbit(samples)))
        zcr = zero_crossings / len(samples)

        # Voice Activity Detection (WebRTC VAD)
        speech_frames = 0
        total_frames = 0
        vad_available = False

        if WEBRTCVAD_AVAILABLE and audio.frame_rate in [8000, 16000, 32000, 48000]:
            try:
                vad = webrtcvad.Vad(2)  # Aggressiveness mode 2 (medium)
                frame_duration_ms = 30
                frame_size = int(audio.frame_rate * frame_duration_ms / 1000)

                # Convert samples to int16 for VAD
                int16_samples = (samples * 32767).astype(np.int16)

                for i in range(0, len(int16_samples) - frame_size, frame_size):
                    frame = int16_samples[i : i + frame_size]
                    frame_bytes = frame.tobytes()
                    if vad.is_speech(frame_bytes, audio.frame_rate):
                        speech_frames += 1
                    total_frames += 1

                if total_frames > 0:
                    vad_available = True
                    speech_ratio = speech_frames / total_frames
            except Exception as e:
                logger.debug(f"VAD analysis failed: {e}")
                speech_ratio = None
        else:
            speech_ratio = None

        # SNR proxy: speech vs non-speech energy
        # Use RMS in speech segments vs RMS in non-speech segments
        snr_proxy = None
        if vad_available and speech_ratio is not None and speech_ratio > 0.1:
            # Simple approximation: compare RMS in different frequency bands
            # Speech is typically 300-3400 Hz, noise often outside
            try:
                if SOUNDFILE_AVAILABLE:
                    data, sr = sf.read(str(audio_path))
                    if len(data.shape) > 1:
                        data = np.mean(data, axis=1)

                    # FFT for frequency analysis
                    fft = np.fft.rfft(data)
                    magnitude = np.abs(fft)
                    frequencies = np.fft.rfftfreq(len(data), 1.0 / sr)

                    # Speech band energy (300-3400 Hz)
                    speech_mask = (frequencies >= 300) & (frequencies <= 3400)
                    speech_energy = np.sum(magnitude[speech_mask])

                    # Non-speech energy (outside speech band)
                    non_speech_mask = ~speech_mask
                    non_speech_energy = np.sum(magnitude[non_speech_mask])

                    if non_speech_energy > 0:
                        snr_proxy = 20 * np.log10(
                            speech_energy / non_speech_energy + 1e-10
                        )
            except Exception as e:
                logger.debug(f"SNR proxy calculation failed: {e}")

        # Store metrics
        assessment["metrics"] = {
            "rms_db": float(rms_db),
            "peak_db": float(peak_db),
            "clipping_percentage": float(clipping_percentage),
            "dc_offset_db": float(dc_offset_db),
            "zero_crossing_rate": float(zcr),
            "speech_ratio": float(speech_ratio) if speech_ratio is not None else None,
            "snr_proxy_db": float(snr_proxy) if snr_proxy is not None else None,
        }

        # Determine noise level and suggest steps
        noise_score = 0.0
        suggested_steps = []

        # Clipping indicates problems
        if clipping_percentage > 0.1:
            noise_score += 0.3
            suggested_steps.append("normalize")

        # Low RMS indicates quiet audio (needs normalization)
        if rms_db < -40:
            noise_score += 0.2
            suggested_steps.append("normalize")

        # High DC offset indicates problems
        if abs(dc_offset_db) > -40:
            noise_score += 0.2

        # Low SNR proxy indicates high noise
        if snr_proxy is not None:
            if snr_proxy < 10:
                noise_score += 0.4
                suggested_steps.append("denoise")
                suggested_steps.append("highpass")
            elif snr_proxy < 20:
                noise_score += 0.2
                suggested_steps.append("highpass")

        # High zero crossing rate can indicate noise
        if zcr > 0.1:
            noise_score += 0.1

        # Determine noise level
        if noise_score >= 0.6:
            assessment["noise_level"] = "high"
            if "denoise" not in suggested_steps:
                suggested_steps.append("denoise")
            if "highpass" not in suggested_steps:
                suggested_steps.append("highpass")
            suggested_steps.append("normalize")
        elif noise_score >= 0.3:
            assessment["noise_level"] = "medium"
            if "highpass" not in suggested_steps:
                suggested_steps.append("highpass")
            suggested_steps.append("normalize")
        else:
            assessment["noise_level"] = "low"
            if "normalize" not in suggested_steps and rms_db < -35:
                suggested_steps.append("normalize")

        # Always suggest resample and mono for ASR optimization
        if audio.frame_rate != 16000:
            suggested_steps.insert(0, "resample")
        if audio.channels > 1:
            suggested_steps.insert(0, "mono")

        assessment["suggested_steps"] = list(
            dict.fromkeys(suggested_steps)
        )  # Remove duplicates, preserve order
        assessment["confidence"] = min(1.0, max(0.0, noise_score))

    except Exception as e:
        logger.error(f"Error assessing audio noise: {e}")
        log_error(
            "AUDIO_ASSESSMENT",
            f"Failed to assess audio noise for {audio_path}: {e}",
            exception=e,
        )

    return assessment


def check_audio_compliance(audio_path: Path, config: Any = None) -> Dict[str, Any]:
    """
    Check if audio file already meets preprocessing requirements.

    Args:
        audio_path: Path to audio file
        config: Optional AudioPreprocessingConfig (uses defaults if None)

    Returns:
        Dictionary with compliance status and details
    """
    compliance: Dict[str, Any] = {
        "is_compliant": False,
        "details": {},
        "missing_requirements": [],
    }

    if not PYDUB_AVAILABLE:
        return compliance

    # Type hint for missing_requirements to help type checker
    missing_requirements: List[str] = compliance["missing_requirements"]

    try:
        audio = AudioSegment.from_file(str(audio_path))

        # Check sample rate
        target_rate = 16000
        if config and hasattr(config, "target_sample_rate"):
            target_rate = config.target_sample_rate

        is_mono = audio.channels == 1
        is_16k = audio.frame_rate == target_rate

        # Check loudness (rough check - would need actual LUFS measurement for precise)
        # For now, check if RMS is reasonable
        samples = np.array(audio.get_array_of_samples())
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)

        if audio.sample_width == 2:
            samples = samples.astype(np.float32) / 32768.0
        else:
            samples = samples.astype(np.float32) / (2 ** (audio.sample_width * 8 - 1))

        rms = np.sqrt(np.mean(samples**2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Consider compliant if RMS is between -25 and -15 dB (reasonable range)
        is_normalized = -25 <= rms_db <= -15

        compliance["details"] = {
            "channels": audio.channels,
            "sample_rate": audio.frame_rate,
            "rms_db": float(rms_db),
            "is_mono": is_mono,
            "is_16k": is_16k,
            "is_normalized": is_normalized,
        }

        if not is_mono:
            missing_requirements.append("mono")
        if not is_16k:
            missing_requirements.append("16kHz")
        if not is_normalized:
            missing_requirements.append("normalized")

        compliance["is_compliant"] = len(missing_requirements) == 0

    except Exception as e:
        logger.error(f"Error checking audio compliance: {e}")
        log_error(
            "AUDIO_COMPLIANCE",
            f"Failed to check compliance for {audio_path}: {e}",
            exception=e,
        )

    return compliance


def normalize_loudness(
    audio: AudioSegment, target_lufs: float = -18.0, limiter_peak_db: float = -1.0
) -> AudioSegment:
    """
    Normalize audio loudness to target LUFS with optional limiter.

    Args:
        audio: AudioSegment to normalize
        target_lufs: Target loudness in LUFS (default: -18.0)
        limiter_peak_db: Peak limiter threshold in dB (default: -1.0)

    Returns:
        Normalized AudioSegment
    """
    if not PYDUB_AVAILABLE:
        return audio

    try:
        # Try pyloudnorm first (more accurate)
        if PYLoudnorm_AVAILABLE and SOUNDFILE_AVAILABLE:
            try:
                # Export to temporary WAV for pyloudnorm
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                    audio.export(tmp_path, format="wav")

                    # Load with soundfile
                    data, rate = sf.read(tmp_path)

                    # Measure loudness
                    meter = pyln.Meter(rate)
                    loudness = meter.integrated_loudness(data)

                    # Normalize
                    normalized = pyln.normalize.loudness(data, loudness, target_lufs)

                    # Apply limiter if enabled (negative dB values indicate limiter is active)
                    if limiter_peak_db < 0:
                        peak_linear = 10 ** (limiter_peak_db / 20)
                        normalized = np.clip(normalized, -peak_linear, peak_linear)

                    # Save back to temporary file
                    sf.write(tmp_path, normalized, rate)

                    # Load back as AudioSegment
                    normalized_audio = AudioSegment.from_wav(tmp_path)

                    # Clean up
                    os.unlink(tmp_path)

                    return normalized_audio
            except Exception as e:
                logger.warning(
                    f"pyloudnorm normalization failed, falling back to RMS: {e}"
                )

        # Fallback to RMS normalization
        target_rms_db = target_lufs + 3.0  # Approximate conversion
        target_rms_linear = 10 ** (target_rms_db / 20)

        samples = np.array(audio.get_array_of_samples())
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)

        if audio.sample_width == 2:
            samples = samples.astype(np.float32) / 32768.0
        else:
            samples = samples.astype(np.float32) / (2 ** (audio.sample_width * 8 - 1))

        current_rms = np.sqrt(np.mean(samples**2))
        if current_rms > 0:
            gain = target_rms_linear / current_rms
            # Apply gain
            samples = samples * gain

            # Apply limiter (negative dB values indicate limiter is active)
            if limiter_peak_db < 0:
                peak_linear = 10 ** (limiter_peak_db / 20)
                samples = np.clip(samples, -peak_linear, peak_linear)

            # Convert back to int16
            samples_int16 = (samples * 32767).astype(np.int16)

            # Create new AudioSegment
            normalized_audio = AudioSegment(
                samples_int16.tobytes(),
                frame_rate=audio.frame_rate,
                channels=1 if len(samples_int16.shape) == 1 else 2,
                sample_width=2,
            )

            return normalized_audio

    except Exception as e:
        logger.error(f"Error normalizing loudness: {e}")
        log_error("AUDIO_NORMALIZE", f"Failed to normalize loudness: {e}", exception=e)

    return audio


def denoise_audio(audio: AudioSegment, strength: str = "medium") -> AudioSegment:
    """
    Apply denoising to audio using RNNoise or spectral gating.

    Args:
        audio: AudioSegment to denoise
        strength: Denoising strength: "low", "medium", or "high"

    Returns:
        Denoised AudioSegment
    """
    if not PYDUB_AVAILABLE:
        return audio

    try:
        # Try RNNoise via noisereduce first
        if NOISEREDUCE_AVAILABLE and SOUNDFILE_AVAILABLE:
            try:
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                    audio.export(tmp_path, format="wav")

                    # Load with soundfile
                    data, rate = sf.read(tmp_path)

                    # Convert to mono if stereo
                    if len(data.shape) > 1:
                        data = np.mean(data, axis=1)

                    # Map strength to noisereduce parameters
                    if strength == "low":
                        stationary = True
                        prop_decrease = 0.3
                    elif strength == "high":
                        stationary = False
                        prop_decrease = 0.9
                    else:  # medium
                        stationary = False
                        prop_decrease = 0.6

                    # Apply denoising
                    denoised = nr.reduce_noise(
                        y=data,
                        sr=rate,
                        stationary=stationary,
                        prop_decrease=prop_decrease,
                    )

                    # Save back
                    sf.write(tmp_path, denoised, rate)

                    # Load back as AudioSegment
                    denoised_audio = AudioSegment.from_wav(tmp_path)

                    # Clean up
                    os.unlink(tmp_path)

                    return denoised_audio
            except Exception as e:
                logger.warning(f"RNNoise denoising failed, using spectral gating: {e}")

        # Fallback to simple spectral gating
        samples = np.array(audio.get_array_of_samples())
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)

        if audio.sample_width == 2:
            samples = samples.astype(np.float32) / 32768.0
        else:
            samples = samples.astype(np.float32) / (2 ** (audio.sample_width * 8 - 1))

        # Simple energy-based gating
        rms = np.sqrt(np.mean(samples**2))
        threshold = rms * (
            0.3 if strength == "low" else 0.5 if strength == "medium" else 0.7
        )

        # Gate samples below threshold
        gate_mask = np.abs(samples) > threshold
        gated_samples = samples * gate_mask.astype(np.float32)

        # Convert back
        samples_int16 = (gated_samples * 32767).astype(np.int16)
        denoised_audio = AudioSegment(
            samples_int16.tobytes(),
            frame_rate=audio.frame_rate,
            channels=1,
            sample_width=2,
        )

        return denoised_audio

    except Exception as e:
        logger.error(f"Error denoising audio: {e}")
        log_error("AUDIO_DENOISE", f"Failed to denoise audio: {e}", exception=e)

    return audio


def _get_effective_mode(global_mode: str, per_step_mode: str) -> str:
    """
    Get the effective preprocessing mode for a step.

    If global_mode is "selected", use per_step_mode. Otherwise, use global_mode.

    Args:
        global_mode: Global preprocessing mode ("selected", "auto", "suggest", "off")
        per_step_mode: Per-step preprocessing mode ("auto", "suggest", "off")

    Returns:
        Effective mode to use for this preprocessing step
    """
    if global_mode == "selected":
        return per_step_mode
    return global_mode


def apply_preprocessing(
    audio: AudioSegment,
    config: Any = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    preprocessing_decisions: Dict[str, bool] | None = None,
) -> Tuple[AudioSegment, List[str]]:
    """
    Apply preprocessing steps to audio based on configuration.

    Each preprocessing step supports three modes:
    - "auto": Always apply if needed (check audio characteristics)
    - "suggest": Use per-file decision from preprocessing_decisions parameter
    - "off": Never apply

    Args:
        audio: AudioSegment to preprocess
        config: Optional AudioPreprocessingConfig (uses defaults if None)
        progress_callback: Optional progress callback
        preprocessing_decisions: Optional dict of per-file preprocessing decisions
            Keys: "denoise", "highpass", "lowpass", "bandpass", "normalize", "mono", "resample"
            Values: True to apply, False to skip

    Returns:
        Tuple of (processed AudioSegment, list of applied steps)
    """
    if not PYDUB_AVAILABLE:
        return audio, []

    applied_steps: List[str] = []
    processed_audio = audio

    # Get config or use defaults
    from transcriptx.core.utils.config import get_config

    if config is None:
        full_config = get_config()
        config = full_config.audio_preprocessing

    # Helper to check if a step should be applied
    def should_apply_step(step_name: str, per_step_mode: str) -> bool:
        """Check if a preprocessing step should be applied."""
        effective_mode = _get_effective_mode(config.preprocessing_mode, per_step_mode)

        if effective_mode == "off":
            return False
        elif effective_mode == "auto":
            # Auto mode: apply if needed (check audio characteristics)
            if step_name == "resample":
                return bool(processed_audio.frame_rate != config.target_sample_rate)
            elif step_name == "mono":
                return bool(processed_audio.channels > 1)
            elif step_name in (
                "denoise",
                "highpass",
                "lowpass",
                "bandpass",
                "normalize",
            ):
                # For these steps, auto mode always applies (they're always "needed" if enabled)
                return True
            return False
        elif effective_mode == "suggest":
            # Suggest mode: use preprocessing_decisions if provided
            if preprocessing_decisions is not None:
                return bool(preprocessing_decisions.get(step_name, False))
            # If no decisions provided, skip (should have been handled by assessment)
            return False
        return False

    # Check if already compliant and skip if enabled
    if config.skip_if_already_compliant:
        if (
            processed_audio.channels == 1
            and processed_audio.frame_rate == config.target_sample_rate
        ):
            # Rough check for normalization (RMS between -25 and -15 dB)
            samples = np.array(processed_audio.get_array_of_samples())
            if processed_audio.sample_width == 2:
                samples = samples.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(samples**2))
            rms_db = 20 * np.log10(rms + 1e-10)
            if -25 <= rms_db <= -15:
                logger.info("Audio already compliant, skipping preprocessing")
                return processed_audio, ["skipped_already_compliant"]

    # Step 1: Resample if needed
    if should_apply_step("resample", config.downsample):
        if progress_callback:
            progress_callback(
                10, 100, f"Resampling to {config.target_sample_rate} Hz..."
            )
        processed_audio = processed_audio.set_frame_rate(config.target_sample_rate)
        applied_steps.append(f"resample_to_{config.target_sample_rate}hz")
        logger.info(
            f"Resampled from {audio.frame_rate} Hz to {config.target_sample_rate} Hz"
        )

    # Step 2: Convert to mono if needed
    if should_apply_step("mono", config.convert_to_mono):
        if progress_callback:
            progress_callback(20, 100, "Converting to mono...")
        processed_audio = processed_audio.set_channels(1)
        applied_steps.append("mono")
        logger.info(f"Converted from {audio.channels} channels to mono")

    # Step 3: High-pass filter
    if should_apply_step("highpass", config.highpass_mode):
        if progress_callback:
            progress_callback(
                30, 100, f"Applying high-pass filter at {config.highpass_cutoff} Hz..."
            )
        processed_audio = processed_audio.high_pass_filter(config.highpass_cutoff)
        applied_steps.append(f"highpass_{config.highpass_cutoff}hz")
        logger.info(f"Applied high-pass filter at {config.highpass_cutoff} Hz")

    # Step 4: Low-pass filter
    if should_apply_step("lowpass", config.lowpass_mode):
        if progress_callback:
            progress_callback(
                40, 100, f"Applying low-pass filter at {config.lowpass_cutoff} Hz..."
            )
        processed_audio = processed_audio.low_pass_filter(config.lowpass_cutoff)
        applied_steps.append(f"lowpass_{config.lowpass_cutoff}hz")
        logger.info(f"Applied low-pass filter at {config.lowpass_cutoff} Hz")

    # Step 5: Band-pass filter (manual/last resort)
    if should_apply_step("bandpass", config.bandpass_mode):
        if progress_callback:
            progress_callback(
                45,
                100,
                f"Applying band-pass filter {config.bandpass_low}-{config.bandpass_high} Hz...",
            )
        processed_audio = processed_audio.high_pass_filter(config.bandpass_low)
        processed_audio = processed_audio.low_pass_filter(config.bandpass_high)
        applied_steps.append(f"bandpass_{config.bandpass_low}_{config.bandpass_high}hz")
        logger.info(
            f"Applied band-pass filter {config.bandpass_low}-{config.bandpass_high} Hz"
        )

    # Step 6: Denoise
    if should_apply_step("denoise", config.denoise_mode):
        if progress_callback:
            progress_callback(
                50, 100, f"Applying denoising ({config.denoise_strength})..."
            )
        processed_audio = denoise_audio(processed_audio, config.denoise_strength)
        applied_steps.append(f"denoise_{config.denoise_strength}")
        logger.info(f"Applied denoising with strength {config.denoise_strength}")

    # Step 7: Normalize loudness
    if should_apply_step("normalize", config.normalize_mode):
        if progress_callback:
            progress_callback(
                60, 100, f"Normalizing loudness to {config.target_lufs} LUFS..."
            )
        limiter_peak = config.limiter_peak_db if config.limiter_enabled else 0.0
        processed_audio = normalize_loudness(
            processed_audio, config.target_lufs, limiter_peak
        )
        applied_steps.append(f"normalize_{config.target_lufs}lufs")
        if config.limiter_enabled:
            applied_steps.append(f"limiter_{config.limiter_peak_db}db")
        logger.info(f"Normalized loudness to {config.target_lufs} LUFS")

    return processed_audio, applied_steps
