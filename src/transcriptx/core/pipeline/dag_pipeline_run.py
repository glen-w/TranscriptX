"""Orchestration helpers for DAGPipeline.execute_pipeline (no DAGPipeline methods)."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from transcriptx.core.pipeline.pipeline_context import PipelineContext
from transcriptx.core.utils.speaker_extraction import (
    count_turn_taking_speakers,
    named_speaker_count_for_path,
)


def gating_turn_taking_speaker_count(
    context: Optional[PipelineContext],
) -> Optional[int]:
    """
    Distinct turn-taking speaker count for module skip gating.

    Counts diarization-style labels (e.g. ``SPEAKER_00``) as speakers, unlike
    :func:`gating_named_speaker_count`. Returns ``None`` when segments are not
    available so callers fail open (do not skip).
    """
    if context is None:
        return None
    try:
        return count_turn_taking_speakers(context.get_segments())
    except Exception:
        return None


def speaker_gate_skip_reason(
    module_info: Any,
    *,
    named_speaker_count: Optional[int],
    turn_taking_speaker_count: Optional[int],
) -> Optional[str]:
    """
    Return a skip reason if a module fails its speaker-count gate, else ``None``.

    Modules flagged with ``gate_on_turn_taking_speakers`` are gated on the count
    of distinct turn-taking speakers (diarization labels allowed); all other
    modules are gated on the count of human-named speakers.
    """
    from transcriptx.core.pipeline.module_registry import (
        effective_min_named_speakers,
    )

    min_required = effective_min_named_speakers(module_info)
    if getattr(module_info, "gate_on_turn_taking_speakers", False):
        count = turn_taking_speaker_count
        reason = f"requires at least {min_required} speakers"
    else:
        count = named_speaker_count
        reason = f"requires at least {min_required} named speakers"

    if count is not None and count < min_required:
        return reason
    return None


def llm_gate_skip_reason(module_info: Any) -> Optional[str]:
    """Return a skip reason when an LLM module is selected but LLM is disabled."""
    if not getattr(module_info, "requires_llm", False):
        return None
    from transcriptx.core.utils.config import get_config

    llm = get_config().llm
    provider = (llm.provider or "null").strip().lower()
    if not llm.enabled or provider in ("null", ""):
        return "LLM disabled"
    return None


def module_spec_requires_llm(module_name: str) -> bool:
    """Return whether static registry metadata marks a module as LLM-backed."""
    from transcriptx.core.domain.module_requirements import Requirement
    from transcriptx.core.pipeline.module_registry_specs import build_module_definitions

    spec = build_module_definitions([Requirement.SEGMENTS]).get(module_name)
    return bool(spec and spec.get("requires_llm"))


def evaluate_llm_gate(module_name: str) -> tuple[str, Optional[str], Optional[str]]:
    """
    Evaluate LLM gating for one module.

    Returns ``(action, skip_reason, fail_message)`` where action is one of
    ``run``, ``skip``, or ``fail``.
    """
    from transcriptx.core.pipeline.module_registry import get_module_info

    module_info = None
    registry_error: Optional[Exception] = None
    try:
        module_info = get_module_info(module_name)
    except Exception as exc:
        registry_error = exc

    requires_llm = False
    if module_info is not None:
        requires_llm = bool(getattr(module_info, "requires_llm", False))
    elif registry_error is not None:
        requires_llm = module_spec_requires_llm(module_name)

    if not requires_llm:
        return ("run", None, None)

    if registry_error is not None:
        return (
            "fail",
            None,
            f"LLM module registry metadata unavailable: {registry_error}",
        )

    try:
        llm_reason = llm_gate_skip_reason(module_info)
    except Exception as exc:
        return ("fail", None, f"LLM configuration unavailable: {exc}")

    if llm_reason:
        return ("skip", llm_reason, None)
    return ("run", None, None)


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
