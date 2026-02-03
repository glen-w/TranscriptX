from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union, TYPE_CHECKING, cast

from transcriptx.core.analysis.voice.audio_io import resolve_audio_path
from transcriptx.core.utils.file_rename import find_original_audio_file


if TYPE_CHECKING:
    from transcriptx.core.pipeline.pipeline_context import PipelineContext

AudioTarget = Union[str, Path, "PipelineContext", Iterable[Union[str, Path, "PipelineContext"]]]


def has_resolvable_audio(
    target: AudioTarget | None,
    *,
    output_dir: Optional[str] = None,
) -> bool:
    """
    Determine whether audio is resolvable for a transcript or context.

    This is the single source of truth for audio availability checks used by
    default module selection and CLI badges. For iterables, returns True only
    if audio is resolvable for all items (conservative default).
    """
    if target is None:
        return False

    # Handle iterable targets (batch or group contexts).
    if isinstance(target, (list, tuple, set)):
        return all(has_resolvable_audio(item, output_dir=output_dir) for item in target)

    # PipelineContext-like object
    if hasattr(target, "transcript_path"):
        transcript_path = str(getattr(target, "transcript_path"))
        context_output_dir = None
        if hasattr(target, "get_transcript_dir"):
            try:
                context_output_dir = str(target.get_transcript_dir())
            except Exception:
                context_output_dir = None
        return _has_audio_for_path(transcript_path, output_dir=context_output_dir)

    # Plain path
    return _has_audio_for_path(str(cast(Union[str, Path], target)), output_dir=output_dir)


def _has_audio_for_path(transcript_path: str, *, output_dir: Optional[str]) -> bool:
    try:
        candidate = find_original_audio_file(transcript_path)
        if candidate and Path(candidate).exists():
            return True
    except Exception:
        pass

    try:
        resolved = resolve_audio_path(
            transcript_path=transcript_path,
            output_dir=output_dir,
        )
        if resolved and Path(resolved).exists():
            return True
    except Exception:
        pass

    return False
