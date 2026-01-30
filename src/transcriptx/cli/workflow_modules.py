"""
Workflow Modules for TranscriptX CLI.

This module provides a centralized import point for all workflow modules,
making the main CLI cleaner and more maintainable.
"""

def run_single_analysis_workflow(*args, **kwargs):
    from .analysis_workflow import run_single_analysis_workflow as _impl

    return _impl(*args, **kwargs)


def run_transcription_workflow(*args, **kwargs):
    from .transcription_workflow import run_transcription_workflow as _impl

    return _impl(*args, **kwargs)


def run_speaker_identification_workflow(*args, **kwargs):
    from .speaker_workflow import run_speaker_identification_workflow as _impl

    return _impl(*args, **kwargs)


def run_wav_processing_workflow(*args, **kwargs):
    from .wav_processing_workflow import run_wav_processing_workflow as _impl

    return _impl(*args, **kwargs)


def run_batch_wav_workflow(*args, **kwargs):
    from .batch_wav_workflow import run_batch_wav_workflow as _impl

    return _impl(*args, **kwargs)


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
