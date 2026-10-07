"""Orchestrate assistive speaker name suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.hashing import sha256_text
from transcriptx.core.speaker_profiles.identify.suggestions.cache import (
    load_cached_suggestions,
    write_cached_suggestions,
)
from transcriptx.core.speaker_profiles.identify.suggestions.deterministic import (
    build_deterministic_options,
)
from transcriptx.core.speaker_profiles.identify.suggestions.llm_assign import (
    merge_llm_options,
    run_llm_assignments,
)
from transcriptx.core.speaker_profiles.identify.suggestions.models import (
    NameSuggestionsResult,
)
from transcriptx.core.speaker_profiles.identify.suggestions.roster import (
    allowed_name_keys,
    build_roster,
)
from transcriptx.core.speaker_profiles.resolver import load_transcript_segments
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

SPEAKER_NAME_SUGGESTIONS_CONSUMER_ID = "speaker_name_suggestions"


EXTRACTOR_REVISION = "name-extract.v2"


def fingerprint_segments(segments: Sequence[Mapping[str, Any]]) -> str:
    """Stable hash of diarized speaker + text content."""
    rows: list[dict[str, str]] = []
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        spk = str(segment.get("speaker_diarized_id") or segment.get("speaker") or "")
        text = str(segment.get("text") or segment.get("transcript") or "")
        rows.append({"speaker": spk, "text": text})
    payload = {"rev": EXTRACTOR_REVISION, "rows": rows}
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _try_llm_assignments(
    segments: Sequence[Mapping[str, Any]],
    per_speaker: dict,
    roster,
) -> tuple[dict, bool, str, str | None, str | None]:
    """Run the optional LLM pass using the project model-selection pack.

    Returns (per_speaker, llm_used, status, model, model_source).
    """
    from transcriptx.core.analysis.llm_support.runtime import (
        build_ollama_analysis_client,
        require_ollama_analysis,
        resolve_llm_runtime,
    )
    from transcriptx.core.llm.errors import LLMConfigurationError, LLMModelMissingError
    from transcriptx.core.llm.thinking_models import is_thinking_model

    config = get_config()
    llm_cfg = config.llm
    try:
        require_ollama_analysis(llm_cfg)
    except LLMConfigurationError:
        return (
            per_speaker,
            False,
            "Suggestions from transcript names (no LLM).",
            None,
            None,
        )

    try:
        runtime = resolve_llm_runtime(
            llm_cfg=llm_cfg,
            effort="low",
            consumer_id=SPEAKER_NAME_SUGGESTIONS_CONSUMER_ID,
        )
    except (LLMModelMissingError, ValueError) as exc:
        logger.warning("Speaker name suggestion model resolve failed: %s", exc)
        return (
            per_speaker,
            False,
            "No model configured for speaker name suggestions; "
            "showing transcript cues only.",
            None,
            None,
        )

    if is_thinking_model(runtime.model):
        return (
            per_speaker,
            False,
            f"Model `{runtime.model}` is unsafe for JSON speaker naming; "
            "showing transcript cues only. Pick a non-thinking tag under "
            "Settings → Models for `speaker_name_suggestions`.",
            runtime.model,
            runtime.model_source,
        )

    client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime)
    speaker_ids = sorted(per_speaker.keys())
    allowed = allowed_name_keys(roster, segments)
    llm_opts = run_llm_assignments(
        client,
        segments,
        speaker_ids,
        [p.display_name for p in roster],
        allowed,
        temperature=float(llm_cfg.default_temperature),
        max_tokens=int(runtime.max_output_tokens),
        max_input_chars=int(runtime.max_input_chars),
    )
    if llm_opts:
        return (
            merge_llm_options(per_speaker, llm_opts),
            True,
            f"Suggestions refined with local LLM (`{runtime.model}`).",
            runtime.model,
            runtime.model_source,
        )
    if client.is_available():
        return (
            per_speaker,
            False,
            f"LLM `{runtime.model}` could not suggest names; "
            "showing transcript cues only.",
            runtime.model,
            runtime.model_source,
        )
    return (
        per_speaker,
        False,
        "Ollama is not reachable; showing transcript cues only.",
        runtime.model,
        runtime.model_source,
    )


def suggest_speaker_names(
    transcript_path: Path | str,
    *,
    managed_transcript_id: str | None = None,
    force_refresh: bool = False,
    use_llm: bool = True,
) -> NameSuggestionsResult:
    """Build assistive name suggestions for a transcript (never writes names)."""
    path = Path(transcript_path)
    try:
        segments = load_transcript_segments(path)
    except Exception as exc:
        return NameSuggestionsResult(
            transcript_path=str(path),
            managed_transcript_id=managed_transcript_id,
            transcript_fingerprint="",
            error=str(exc),
        )

    fp = fingerprint_segments(segments)
    if managed_transcript_id and not force_refresh:
        cached = load_cached_suggestions(
            managed_transcript_id,
            transcript_fingerprint=fp,
        )
        if cached is not None:
            return cached

    roster = build_roster(segments)
    per_speaker = build_deterministic_options(segments, roster)
    llm_used = False
    llm_model: str | None = None
    llm_model_source: str | None = None
    status = (
        "Suggestions from names found in the transcript (no LLM)."
        if not roster
        else "Suggestions from transcript names (no LLM)."
    )

    if use_llm and roster:
        per_speaker, llm_used, status, llm_model, llm_model_source = (
            _try_llm_assignments(segments, per_speaker, roster)
        )

    result = NameSuggestionsResult(
        transcript_path=str(path),
        managed_transcript_id=managed_transcript_id,
        transcript_fingerprint=fp,
        roster=roster,
        per_speaker=per_speaker,
        status_message=status,
        llm_used=llm_used,
        llm_model=llm_model,
        llm_model_source=llm_model_source,
    )
    if managed_transcript_id:
        try:
            write_cached_suggestions(result)
        except Exception as exc:
            logger.warning("Failed to cache name suggestions: %s", exc)
    return result
