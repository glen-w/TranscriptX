"""Environment override helpers for TranscriptXConfig."""

from __future__ import annotations

import json
import os

from transcriptx.core.utils.config.config_errors import ConfigLoadError


def _reject_legacy_audio_enabled_env() -> None:
    for name in (
        "TRANSCRIPTX_AUDIO_NORMALIZE_ENABLED",
        "TRANSCRIPTX_AUDIO_DENOISE_ENABLED",
        "TRANSCRIPTX_AUDIO_HIGHPASS_ENABLED",
    ):
        if os.getenv(name):
            raise ConfigLoadError(
                f"Environment variable {name} is no longer supported. "
                "Use TRANSCRIPTX_AUDIO_NORMALIZE_MODE, TRANSCRIPTX_AUDIO_DENOISE_MODE, "
                'or TRANSCRIPTX_AUDIO_HIGHPASS_MODE with values "auto", "suggest", or "off".',
                code="unsupported_legacy_shape",
            )


def apply_env_overrides(cfg) -> None:
    """Apply TRANSCRIPTX_* environment overrides to a config instance."""
    _reject_legacy_audio_enabled_env()

    if os.getenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE"):
        try:
            cfg.analysis.sentiment_window_size = int(
                os.getenv("TRANSCRIPTX_SENTIMENT_WINDOW_SIZE", "10")
            )
        except ValueError:
            pass

    if os.getenv("TRANSCRIPTX_EMOTION_MODEL"):
        model_name = os.getenv("TRANSCRIPTX_EMOTION_MODEL")
        if model_name:
            cfg.analysis.emotion_model_name = model_name

    if os.getenv("TRANSCRIPTX_SEMANTIC_MODEL"):
        model_name = os.getenv("TRANSCRIPTX_SEMANTIC_MODEL")
        if model_name:
            cfg.analysis.semantic_model_name = model_name

    if os.getenv("TRANSCRIPTX_ACTS_MODEL"):
        model_name = os.getenv("TRANSCRIPTX_ACTS_MODEL")
        if model_name:
            cfg.analysis.acts.ml_model_name = model_name

    if os.getenv("TRANSCRIPTX_WORDCLOUD_MAX_WORDS"):
        try:
            cfg.analysis.wordcloud_max_words = int(
                os.getenv("TRANSCRIPTX_WORDCLOUD_MAX_WORDS", "100")
            )
        except ValueError:
            pass

    if os.getenv("TRANSCRIPTX_WAV_FOLDERS"):
        wav_folders_str = os.getenv("TRANSCRIPTX_WAV_FOLDERS")
        if wav_folders_str:
            try:
                wav_folders = json.loads(wav_folders_str)
                if isinstance(wav_folders, list):
                    cfg.input.wav_folders = wav_folders
            except (json.JSONDecodeError, ValueError):
                wav_folders = [
                    folder.strip()
                    for folder in wav_folders_str.split(",")
                    if folder.strip()
                ]
                if wav_folders:
                    cfg.input.wav_folders = wav_folders

    if os.getenv("TRANSCRIPTX_RECORDINGS_FOLDERS"):
        recordings_folders_str = os.getenv("TRANSCRIPTX_RECORDINGS_FOLDERS")
        if recordings_folders_str:
            try:
                recordings_folders = json.loads(recordings_folders_str)
                if isinstance(recordings_folders, list):
                    cfg.input.recordings_folders = recordings_folders
            except (json.JSONDecodeError, ValueError):
                recordings_folders = [
                    folder.strip()
                    for folder in recordings_folders_str.split(",")
                    if folder.strip()
                ]
                if recordings_folders:
                    cfg.input.recordings_folders = recordings_folders

    if os.getenv("TRANSCRIPTX_OUTPUT_DIR"):
        output_dir = os.getenv("TRANSCRIPTX_OUTPUT_DIR")
        if output_dir:
            cfg.output.base_output_dir = output_dir

    if os.getenv("TRANSCRIPTX_LOG_LEVEL"):
        log_level = os.getenv("TRANSCRIPTX_LOG_LEVEL")
        if log_level:
            cfg.logging.level = log_level

    emoji_env = os.getenv("TRANSCRIPTX_USE_EMOJIS")
    if emoji_env is not None:
        val = emoji_env.strip().lower()
        cfg.use_emojis = val in ("1", "true", "yes", "on")

    if os.getenv("TRANSCRIPTX_AUDIO_PREPROCESSING_MODE"):
        mode = os.getenv("TRANSCRIPTX_AUDIO_PREPROCESSING_MODE").strip().lower()
        if mode in ("selected", "auto", "suggest", "off"):
            cfg.audio_preprocessing.preprocessing_mode = mode

    if os.getenv("TRANSCRIPTX_AUDIO_CONVERT_TO_MONO"):
        val = os.getenv("TRANSCRIPTX_AUDIO_CONVERT_TO_MONO").strip().lower()
        if val in ("auto", "suggest", "off"):
            cfg.audio_preprocessing.convert_to_mono = val
        elif val in ("1", "true", "yes", "on"):
            cfg.audio_preprocessing.convert_to_mono = "auto"
        elif val in ("0", "false", "no", "off"):
            cfg.audio_preprocessing.convert_to_mono = "off"

    if os.getenv("TRANSCRIPTX_AUDIO_DOWNSAMPLE"):
        val = os.getenv("TRANSCRIPTX_AUDIO_DOWNSAMPLE").strip().lower()
        if val in ("auto", "suggest", "off"):
            cfg.audio_preprocessing.downsample = val
        elif val in ("1", "true", "yes", "on"):
            cfg.audio_preprocessing.downsample = "auto"
        elif val in ("0", "false", "no", "off"):
            cfg.audio_preprocessing.downsample = "off"

    if os.getenv("TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE"):
        try:
            cfg.audio_preprocessing.target_sample_rate = int(
                os.getenv("TRANSCRIPTX_AUDIO_TARGET_SAMPLE_RATE", "16000")
            )
        except ValueError:
            pass

    if os.getenv("TRANSCRIPTX_AUDIO_NORMALIZE_MODE"):
        mode = os.getenv("TRANSCRIPTX_AUDIO_NORMALIZE_MODE").strip().lower()
        if mode in ("auto", "suggest", "off"):
            cfg.audio_preprocessing.normalize_mode = mode

    if os.getenv("TRANSCRIPTX_AUDIO_TARGET_LUFS"):
        try:
            cfg.audio_preprocessing.target_lufs = float(
                os.getenv("TRANSCRIPTX_AUDIO_TARGET_LUFS", "-18.0")
            )
        except ValueError:
            pass

    if os.getenv("TRANSCRIPTX_AUDIO_DENOISE_MODE"):
        mode = os.getenv("TRANSCRIPTX_AUDIO_DENOISE_MODE").strip().lower()
        if mode in ("auto", "suggest", "off"):
            cfg.audio_preprocessing.denoise_mode = mode

    if os.getenv("TRANSCRIPTX_AUDIO_DENOISE_STRENGTH"):
        strength = (
            os.getenv("TRANSCRIPTX_AUDIO_DENOISE_STRENGTH", "medium").strip().lower()
        )
        if strength in ("low", "medium", "high"):
            cfg.audio_preprocessing.denoise_strength = strength

    if os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_MODE"):
        mode = os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_MODE").strip().lower()
        if mode in ("auto", "suggest", "off"):
            cfg.audio_preprocessing.highpass_mode = mode

    if os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_CUTOFF"):
        try:
            cfg.audio_preprocessing.highpass_cutoff = int(
                os.getenv("TRANSCRIPTX_AUDIO_HIGHPASS_CUTOFF", "80")
            )
        except ValueError:
            pass
