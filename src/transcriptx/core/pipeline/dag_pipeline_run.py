"""Orchestration helpers for DAGPipeline.execute_pipeline (no DAGPipeline methods)."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from transcriptx.core.pipeline.pipeline_context import PipelineContext
from transcriptx.core.utils.speaker_extraction import named_speaker_count_for_path


def gating_named_speaker_count(
    transcript_path: str,
    context: Optional[PipelineContext],
) -> Optional[int]:
    """
    Speaker count for module skip gating.

    Merges sidecar-backed resolver output with segment-derived eligible speaker
    keys from PipelineContext so file-only / fixture transcripts still gate
    correctly on segment labels.
    """
    n: Optional[int] = None
    try:
        n = named_speaker_count_for_path(transcript_path)
    except Exception:
        n = None
    if context is not None:
        keys = context.runtime_flags.get("named_speaker_keys")
        if isinstance(keys, set) and len(keys) > 0:
            n = max(n if n is not None else 0, len(keys))
    return n


def resolve_output_dir_for_run(transcript_path: str, output_dir: Optional[str]) -> str:
    if output_dir is None:
        from transcriptx.core.utils._path_core import get_transcript_dir

        return get_transcript_dir(transcript_path)
    return output_dir


def build_execute_pipeline_context(
    logger: Any,
    *,
    transcript_path: str,
    speaker_options: Any,
    output_dir: str,
    transcript_key: Optional[str],
    run_id: Optional[str],
) -> Tuple[PipelineContext, Optional[int]]:
    """Create PipelineContext for execute_pipeline; returns (context, gating count)."""
    try:
        context = PipelineContext(
            transcript_path,
            include_unidentified_speakers=speaker_options.include_unidentified,
            anonymise_speakers=speaker_options.anonymise,
            batch_mode=True,
            output_dir=output_dir,
            transcript_key=transcript_key,
            run_id=run_id,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to create PipelineContext for {transcript_path!r}"
        ) from e

    if not context.validate():
        try:
            context.close()
        except Exception:
            pass
        raise ValueError(
            "PipelineContext validation failed (empty segments or invalid state)"
        )

    logger.debug(f"Created PipelineContext with {len(context.get_segments())} segments")
    named_speaker_count = gating_named_speaker_count(transcript_path, context)
    return context, named_speaker_count
