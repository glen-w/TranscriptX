"""
Shim: audio preprocessing functions have moved to core.audio.preprocessing.

This file is kept for one release cycle so any direct imports continue to
work.  Import from transcriptx.core.audio.preprocessing instead.
"""

from transcriptx.core.audio.preprocessing import (  # noqa: F401
    assess_audio_noise,
    check_audio_compliance,
    denoise_audio,
    normalize_loudness,
    apply_preprocessing,
    PYDUB_AVAILABLE,
    WEBRTCVAD_AVAILABLE,
    PYLoudnorm_AVAILABLE,
    NOISEREDUCE_AVAILABLE,
    SOUNDFILE_AVAILABLE,
)
