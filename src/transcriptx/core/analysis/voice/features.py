from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from transcriptx.core.analysis.voice.schema import EGEMAPS_CANONICAL_FIELDS

from transcriptx.core.utils.lazy_imports import optional_import


def compute_rms_db(wave: np.ndarray) -> float | None:
    if wave is None or len(wave) == 0:
        return None
    rms = float(np.sqrt(np.mean(np.square(wave), dtype=np.float64)))
    if rms <= 0:
        return None
    return float(20.0 * np.log10(rms + 1e-12))


def compute_voiced_ratio(
    wave: np.ndarray, sample_rate: int, vad_mode: int
) -> float | None:
    """
    Voice activity ratio using webrtcvad (20ms frames).

    Returns None if webrtcvad is unavailable or sample_rate unsupported.
    """
    try:
        webrtcvad = optional_import("webrtcvad", "voice activity detection")
    except ImportError:
        return None

    if sample_rate not in {8000, 16000, 32000, 48000}:
        return None

    vad = webrtcvad.Vad(int(vad_mode))
    # Convert float32 [-1,1] to 16-bit PCM bytes
    pcm = np.clip(wave, -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype(np.int16, copy=False)
    pcm_bytes = pcm16.tobytes()

    frame_ms = 20
    frame_len = int(sample_rate * frame_ms / 1000)
    bytes_per_frame = frame_len * 2
    if bytes_per_frame <= 0:
        return None

    total = 0
    voiced = 0
    for i in range(0, len(pcm_bytes) - bytes_per_frame + 1, bytes_per_frame):
        frame = pcm_bytes[i : i + bytes_per_frame]
        total += 1
        try:
            if vad.is_speech(frame, sample_rate):
                voiced += 1
        except Exception:
            # If VAD throws (rare), treat frame as unvoiced
            continue

    if total == 0:
        return None
    return float(voiced / total)


def compute_vad_runs(
    wave: np.ndarray, sample_rate: int, vad_mode: int
) -> tuple[float | None, list[float], list[float]]:
    """
    Compute voiced/silence run lengths (in seconds) and voiced ratio.
    """
    try:
        webrtcvad = optional_import("webrtcvad", "voice activity detection")
    except ImportError:
        return (None, [], [])

    if sample_rate not in {8000, 16000, 32000, 48000}:
        return (None, [], [])

    vad = webrtcvad.Vad(int(vad_mode))
    pcm = np.clip(wave, -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype(np.int16, copy=False)
    pcm_bytes = pcm16.tobytes()

    frame_ms = 20
    frame_len = int(sample_rate * frame_ms / 1000)
    bytes_per_frame = frame_len * 2
    if bytes_per_frame <= 0:
        return (None, [], [])

    voiced_runs: list[float] = []
    silence_runs: list[float] = []
    total_frames = 0
    voiced_frames = 0
    current_state: bool | None = None
    current_len = 0

    for i in range(0, len(pcm_bytes) - bytes_per_frame + 1, bytes_per_frame):
        frame = pcm_bytes[i : i + bytes_per_frame]
        total_frames += 1
        try:
            is_voiced = bool(vad.is_speech(frame, sample_rate))
        except Exception:
            is_voiced = False
        if is_voiced:
            voiced_frames += 1
        if current_state is None:
            current_state = is_voiced
            current_len = 1
            continue
        if is_voiced == current_state:
            current_len += 1
        else:
            run_seconds = (current_len * frame_ms) / 1000.0
            if current_state:
                voiced_runs.append(run_seconds)
            else:
                silence_runs.append(run_seconds)
            current_state = is_voiced
            current_len = 1

    if current_state is not None and current_len > 0:
        run_seconds = (current_len * frame_ms) / 1000.0
        if current_state:
            voiced_runs.append(run_seconds)
        else:
            silence_runs.append(run_seconds)

    if total_frames == 0:
        return (None, voiced_runs, silence_runs)
    return (float(voiced_frames / total_frames), voiced_runs, silence_runs)


def compute_pitch_stats(
    wave: np.ndarray, sample_rate: int, *, max_seconds: float
) -> Tuple[float | None, float | None, float | None]:
    """
    Compute pitch stats using librosa.yin (CPU-friendly).

    Guardrail: only analyze up to max_seconds of audio.
    """
    try:
        librosa = optional_import("librosa", "pitch estimation for voice features")
    except ImportError:
        return (None, None, None)

    if wave is None or len(wave) == 0:
        return (None, None, None)

    max_len = int(max(0.0, float(max_seconds)) * sample_rate)
    if max_len > 0 and len(wave) > max_len:
        wave = wave[:max_len]

    # yin returns f0 for each frame, with unvoiced as nan when using `trough_threshold`?
    try:
        f0 = librosa.yin(
            wave,
            fmin=50.0,
            fmax=500.0,
            sr=sample_rate,
        )
    except Exception:
        return (None, None, None)

    f0 = np.asarray(f0, dtype=np.float64)
    f0 = f0[np.isfinite(f0)]
    if f0.size < 5:
        return (None, None, None)

    mean_hz = float(np.mean(f0))
    std_hz = float(np.std(f0))
    p5 = float(np.percentile(f0, 5))
    p95 = float(np.percentile(f0, 95))
    if p5 <= 0 or p95 <= 0 or p95 <= p5:
        return (mean_hz, std_hz, None)
    range_semitones = float(12.0 * np.log2(p95 / p5))
    return (mean_hz, std_hz, range_semitones)


def compute_speech_rate_wps(text: str, duration_s: float) -> float | None:
    if duration_s is None or duration_s <= 0:
        return None
    if not text:
        return 0.0
    word_count = len([w for w in str(text).strip().split() if w])
    return float(word_count / float(duration_s))


_OPENSMILE_EXTRACTOR: Any | None = None


def build_opensmile_extractor() -> Any | None:
    """
    Build a singleton openSMILE extractor (eGeMAPS functionals).

    Returns None if opensmile is unavailable.
    """
    global _OPENSMILE_EXTRACTOR
    if _OPENSMILE_EXTRACTOR is not None:
        return _OPENSMILE_EXTRACTOR
    try:
        opensmile = optional_import("opensmile", "openSMILE eGeMAPS voice features")
    except ImportError:
        return None

    _OPENSMILE_EXTRACTOR = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.Functionals,
    )
    return _OPENSMILE_EXTRACTOR


# Mapping layer: openSMILE column -> short name (stored as eg_<short>)
# Note: openSMILE column names are versioned; missing keys should be handled gracefully.
EGEMAPS_FIELDS: dict[str, str] = {
    # Voice quality / periodicity
    "jitterLocal_sma3nz_amean": "jitter",
    "shimmerLocaldB_sma3nz_amean": "shimmer_db",
    "HNRdBACF_sma3nz_amean": "hnr_db",
    # Spectral balance
    "alphaRatioV_sma3nz_amean": "alpha_ratio",
    "hammarbergIndexV_sma3nz_amean": "hammarberg",
    # Energy proxy
    "loudness_sma3_amean": "loudness",
}


def extract_egemaps(wave: np.ndarray, sample_rate: int) -> Dict[str, float]:
    extractor = build_opensmile_extractor()
    if extractor is None:
        return {}
    # openSMILE expects a 1D array
    try:
        df = extractor.process_signal(wave, sample_rate)
    except Exception:
        return {}
    if df is None or len(df) == 0:
        return {}
    row = df.iloc[0].to_dict()
    out: Dict[str, float] = {}
    for col, short in EGEMAPS_FIELDS.items():
        if col not in row:
            continue
        if short not in EGEMAPS_CANONICAL_FIELDS:
            continue
        val = row.get(col)
        try:
            if val is None:
                continue
            out[short] = float(val)
        except Exception:
            continue
    return out

