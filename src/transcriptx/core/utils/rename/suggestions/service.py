"""Orchestrate assistive rename suggestions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.identify.suggestions.service import (
    fingerprint_segments,
)
from transcriptx.core.speaker_profiles.resolver import load_transcript_segments
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.rename.smart_name import (
    build_rename_tokens,
    parse_recording_datetime,
    render_smart_rename,
    resolve_smart_rename_pattern,
)
from transcriptx.core.utils.rename.suggestions.cache import (
    load_cached_rename_suggestions,
    write_cached_rename_suggestions,
)
from transcriptx.core.utils.rename.suggestions.llm import (
    RENAME_LLM_INSTRUCTION,
    RENAME_LLM_SUGGESTION_COUNT,
    build_llm_excerpt,
    run_rename_llm,
)
from transcriptx.core.utils.rename.suggestions.models import (
    RawRenameCue,
    RenameOption,
    RenameSuggestionsResult,
)
from transcriptx.core.utils.rename.suggestions.render import (
    list_sibling_stems,
    render_stem_from_cue,

)
from transcriptx.core.utils.rename.suggestions.transcript_cues import (
    extract_transcript_cues,
    looks_like_public_event,
    transcript_source_mtime,
)
from transcriptx.core.utils.rename.suggestions.web import build_web_query, fetch_web_cue

logger = get_logger()

RENAME_SUGGESTIONS_CONSUMER_ID = "rename_suggestions"

_CONF_RANK = {"strong": 0, "likely": 1, "possible": 2, "file": 3}
_BASIS_RANK = {
    "transcript_date": 0,
    "web": 1,
    "filename_datetime": 2,
    "llm": 3,
    "transcript_title": 4,
    "file_mtime": 5,
}


def _empty_result(path: Path, pattern: str, status: str = "") -> RenameSuggestionsResult:
    return RenameSuggestionsResult(
        transcript_path=str(path),
        transcript_fingerprint="",
        pattern=pattern,
        status=status,
    )


def build_rename_suggestions_cache_key(
    *,
    fingerprint: str,
    content_mode: str,
    suggest_transcript: bool,
    suggest_llm: bool,
    suggest_web: bool,
    effort: str,
    pattern: str,
    llm_model_tag: str,
) -> str:
    payload = {
        "fingerprint": fingerprint,
        "content_mode": content_mode,
        "suggest_transcript": suggest_transcript,
        "suggest_llm": suggest_llm,
        "suggest_web": suggest_web,
        "effort": effort,
        "pattern": pattern,
        "llm_model": llm_model_tag,
        "llm_suggestion_count": RENAME_LLM_SUGGESTION_COUNT,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _filename_cue(path: Path) -> RawRenameCue | None:
    dt = parse_recording_datetime(path, fallback_mtime=False)
    if dt is None:
        return None
    return RawRenameCue(
        basis="filename_datetime",
        confidence="likely",
        detail="Date/time from recording filename",
        event_date=dt.date(),
        _priority=2,
    )


def _file_mtime_cue(path: Path) -> RawRenameCue | None:
    dt = transcript_source_mtime(str(path))
    if dt is None:
        try:
            if path.is_file():
                dt = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return None
    if dt is None:
        return None
    return RawRenameCue(
        basis="file_mtime",
        confidence="file",
        detail="File date, not the event date",
        event_date=dt.date(),
        _priority=5,
    )


def _effective_suggest_llm(input_cfg: Any, *, on_demand: bool) -> bool:
    configured = bool(getattr(input_cfg, "rename_suggest_llm", False))
    if configured:
        return True
    if not on_demand:
        return False
    config = get_config()
    llm_cfg = config.llm
    if not llm_cfg.enabled or (llm_cfg.provider or "").strip().lower() != "ollama":
        return False
    try:
        from transcriptx.core.analysis.llm_support.model_selection import (
            resolve_module_llm_model,
        )

        resolve_module_llm_model(llm_cfg, RENAME_SUGGESTIONS_CONSUMER_ID)
        return True
    except Exception:
        return False


def _maybe_llm_cues(
    segments: Sequence[Mapping[str, Any]],
    *,
    effort: str,
) -> tuple[list[RawRenameCue], str, str | None, str | None]:
    from transcriptx.core.analysis.llm_support.runtime import (
        build_ollama_analysis_client,
        require_ollama_analysis,
        resolve_llm_runtime,
    )
    from transcriptx.core.analysis.llm_support.prompts import build_bounded_user_prompt
    from transcriptx.core.llm.errors import LLMConfigurationError, LLMModelMissingError
    from transcriptx.core.llm.prompting import require_prompt_budget
    from transcriptx.core.llm.thinking_models import is_thinking_model

    config = get_config()
    llm_cfg = config.llm
    try:
        require_ollama_analysis(llm_cfg)
    except LLMConfigurationError:
        return [], "Transcript cues only (LLM disabled).", None, None
    try:
        runtime = resolve_llm_runtime(
            llm_cfg=llm_cfg,
            effort=effort,
            consumer_id=RENAME_SUGGESTIONS_CONSUMER_ID,
        )
    except (LLMModelMissingError, ValueError) as exc:
        logger.warning("Rename suggestion model resolve failed: %s", exc)
        return (
            [],
            "No model configured for rename_suggestions; showing other cues only.",
            None,
            None,
        )
    if is_thinking_model(runtime.model):
        return (
            [],
            f"Model `{runtime.model}` is unsafe for JSON rename suggestions; "
            "pick a non-thinking tag under Settings → Models for "
            "`rename_suggestions`.",
            runtime.model,
            runtime.model_source,
        )
    try:
        require_prompt_budget(
            max_input_chars=int(runtime.max_input_chars),
            instruction=RENAME_LLM_INSTRUCTION,
            module_name="rename_suggestions",
        )
    except LLMConfigurationError as exc:
        logger.warning("Rename suggestion prompt budget: %s", exc)
        return [], str(exc), runtime.model, runtime.model_source

    excerpt = build_llm_excerpt(segments)
    n = RENAME_LLM_SUGGESTION_COUNT
    body = f"""<<<EXCERPT>>>
{excerpt}
<<<END EXCERPT>>>

Return JSON:
{{
  "suggestions": [
    {{
      "event_date": "YYYY-MM-DD" or null,
      "title": string or null,
      "quote": string (verbatim span from EXCERPT supporting event_date, or empty)
    }}
  ]
}}
Provide exactly {n} objects in suggestions with distinct short titles.
Only set event_date when quote is copied verbatim from EXCERPT."""
    user_prompt, _ = build_bounded_user_prompt(
        instruction=RENAME_LLM_INSTRUCTION,
        transcript_block=body,
        max_input_chars=int(runtime.max_input_chars),
    )
    client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime)
    if not client.is_available():
        return (
            [],
            "Ollama is not reachable; showing other cues only.",
            runtime.model,
            runtime.model_source,
        )
    cues = run_rename_llm(
        client,
        user_prompt=user_prompt,
        excerpt_for_quotes=excerpt,
        temperature=float(llm_cfg.default_temperature),
        max_tokens=int(runtime.max_output_tokens),
    )
    if len(cues) >= n:
        status = (
            f"{len(cues)} rename suggestions from local LLM (`{runtime.model}`)."
        )
    elif cues:
        status = (
            f"LLM `{runtime.model}` returned {len(cues)} of {n} suggestions; "
            "showing other cues too."
        )
    else:
        status = (
            f"LLM `{runtime.model}` could not suggest metadata; showing other cues."
        )
    return cues, status, runtime.model, runtime.model_source


def _rank_and_dedupe(options: list[RenameOption]) -> tuple[RenameOption, ...]:
    seen: set[str] = set()
    ordered = sorted(
        options,
        key=lambda o: (
            _CONF_RANK.get(o.confidence, 9),
            _BASIS_RANK.get(o.basis, 9),
            o.stem,
        ),
    )
    out: list[RenameOption] = []
    for opt in ordered:
        if not opt.stem or opt.stem in seen:
            continue
        seen.add(opt.stem)
        out.append(opt)
        if len(out) >= 8:
            break
    return tuple(out)


def _best_title(cues: Sequence[RawRenameCue]) -> str:
    for cue in cues:
        if cue.title:
            return cue.title
    return ""


def suggest_rename_stems(
    transcript_path: Path | str,
    *,
    force_refresh: bool = False,
    on_demand: bool = False,
) -> RenameSuggestionsResult:
    """Build assistive rename stems (never writes library names)."""
    path = Path(transcript_path)
    config = get_config()
    input_cfg = config.input
    content_mode = str(getattr(input_cfg, "rename_content_suggestions", "off") or "off")
    pattern = str(
        getattr(input_cfg, "smart_rename_pattern", "{yymmdd}_{period}_{n}")
        or "{yymmdd}_{period}_{n}"
    )
    if content_mode != "auto" and not on_demand:
        return _empty_result(path, pattern)

    suggest_transcript = bool(getattr(input_cfg, "rename_suggest_transcript", True))
    suggest_llm = _effective_suggest_llm(input_cfg, on_demand=on_demand)
    suggest_web = bool(getattr(input_cfg, "rename_suggest_web", False))
    effort = str(getattr(input_cfg, "rename_suggestions_effort", "low") or "low")

    segments = load_transcript_segments(path)
    fingerprint = fingerprint_segments(segments)

    llm_model_tag = "llm-off"
    if suggest_llm:
        try:
            from transcriptx.core.analysis.llm_support.model_selection import (
                resolve_module_llm_model,
            )

            llm_model_tag = resolve_module_llm_model(config.llm, RENAME_SUGGESTIONS_CONSUMER_ID).model
        except Exception:
            llm_model_tag = "llm-unresolved"

    cache_key = build_rename_suggestions_cache_key(
        fingerprint=fingerprint,
        content_mode=content_mode,
        suggest_transcript=suggest_transcript,
        suggest_llm=suggest_llm,
        suggest_web=suggest_web,
        effort=effort,
        pattern=pattern,
        llm_model_tag=llm_model_tag,
    )
    if not force_refresh:
        cached = load_cached_rename_suggestions(
            cache_key=cache_key,
            transcript_fingerprint=fingerprint,
        )
        if cached is not None:
            return cached

    raw_cues: list[RawRenameCue] = []
    status_parts: list[str] = []
    llm_model: str | None = None
    llm_model_source: str | None = None

    fn_cue = _filename_cue(path)
    if fn_cue:
        raw_cues.append(fn_cue)
    if suggest_transcript:
        raw_cues.extend(extract_transcript_cues(segments))
    if suggest_llm:
        llm_cues, llm_status, llm_model, llm_model_source = _maybe_llm_cues(
            segments, effort=effort
        )
        status_parts.append(llm_status)
        raw_cues.extend(llm_cues)
    title_for_web = _best_title(raw_cues)
    if suggest_web and looks_like_public_event(path.name, segments):
        query = build_web_query(title=title_for_web, filename=path.name)
        web_cue = fetch_web_cue(query)
        if web_cue:
            raw_cues.append(web_cue)
    mtime_cue = _file_mtime_cue(path)
    if mtime_cue is not None:
        raw_cues.append(mtime_cue)

    existing = list_sibling_stems(path)
    options: list[RenameOption] = []
    for cue in raw_cues:
        if cue.basis == "file_mtime" and not cue.event_date:
            continue
        rendered = render_stem_from_cue(
            cue,
            pattern=pattern,
            transcript_stem=path.stem,
            existing_stems=existing,
        )
        if rendered:
            options.append(rendered)

    ranked = _rank_and_dedupe(options)
    prefill = ranked[0].stem if ranked else ""
    if not prefill and fn_cue and fn_cue.event_date:
        resolved = resolve_smart_rename_pattern(pattern)
        tokens = build_rename_tokens(
            datetime.combine(fn_cue.event_date, datetime.min.time()),
            stem=path.stem,
        )
        prefill = render_smart_rename(
            resolved,
            tokens,
            existing_stems=existing,
            exclude_stem=path.stem,
        )

    status = " ".join(s for s in status_parts if s).strip() or (
        "Rename suggestions from transcript and filename cues."
        if ranked
        else "No content-based rename suggestions; edit the name manually."
    )
    result = RenameSuggestionsResult(
        transcript_path=str(path),
        transcript_fingerprint=fingerprint,
        pattern=pattern,
        options=ranked,
        prefill=prefill,
        status=status,
        llm_model=llm_model,
        llm_model_source=llm_model_source,
        effort=effort,
        cache_key=cache_key,
    )
    write_cached_rename_suggestions(result)
    return result
