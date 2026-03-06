"""
Workflow Modules for TranscriptX CLI.

This module provides a centralized import point for all workflow modules,
making the main CLI cleaner and more maintainable.
"""


def run_single_analysis_workflow(*args, **kwargs):
    from .analysis_workflow import run_single_analysis_workflow as _impl

    return _impl(*args, **kwargs)


def run_transcription_workflow(*args, **kwargs):
    """Deprecated. TranscriptX no longer transcribes; see docs/transcription.md."""
    import sys

    print(
        "ERROR: command deprecated\nTranscriptX no longer transcribes audio. See docs/transcription.md.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def run_speaker_identification_workflow(*args, **kwargs):
    from .speaker_workflow import run_speaker_identification_workflow as _impl

    return _impl(*args, **kwargs)


def run_wav_processing_workflow(*args, **kwargs):
    from .wav_processing_workflow import run_wav_processing_workflow as _impl

    return _impl(*args, **kwargs)


def run_batch_wav_workflow(*args, **kwargs):
    """Replaced by prep_audio_workflow + batch_analyze_workflow. Use prep-audio and batch-analyze commands."""
    from .prep_audio_workflow import run_prep_audio_workflow
    from .batch_analyze_workflow import run_batch_analyze_workflow
    from pathlib import Path

    folder = kwargs.get("folder") or (args[0] if args else None)
    if folder is not None:
        folder = Path(folder)
        run_prep_audio_workflow(folder)
        run_batch_analyze_workflow(folder)
    return None


def run_deduplication_workflow(*args, **kwargs):
    from .deduplication_workflow import run_deduplication_workflow as _impl

    return _impl(*args, **kwargs)


def run_vtt_import_workflow(*args, **kwargs):
    from .vtt_import_workflow import run_vtt_import_workflow as _impl

    return _impl(*args, **kwargs)


def run_srt_import_workflow(*args, **kwargs):
    from .srt_import_workflow import run_srt_import_workflow as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "run_single_analysis_workflow",
    "run_transcription_workflow",
    "run_speaker_identification_workflow",
    "run_wav_processing_workflow",
    "run_batch_wav_workflow",
    "run_deduplication_workflow",
    "run_vtt_import_workflow",
    "run_srt_import_workflow",
]
