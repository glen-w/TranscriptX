"""Orchestrate group LLM synthesis under lock (caller holds synthesis_lock)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from transcriptx.core.analysis.group_llm_synthesis import errors as err
from transcriptx.core.analysis.group_llm_synthesis.contract import (
    parse_group_summary_json,
    response_error_code,
)
from transcriptx.core.analysis.group_llm_synthesis.digests import (
    InputDigests,
    compute_input_digests,
)
from transcriptx.core.analysis.group_llm_synthesis.generation import (
    build_commit_inventory,
    ensure_generation_dir,
    gc_uncommitted_generations,
    new_generation_id,
    write_active,
    write_commit,
    write_json_under_generation,
    write_text_under_generation,
)
from transcriptx.core.analysis.group_llm_synthesis.paths import (
    global_collect_path,
    global_summary_md_rel,
    global_summary_rel,
    speaker_artifact_rel,
    speaker_index_md_rel,
    speaker_index_rel,
    speaker_rows_path,
)
from transcriptx.core.analysis.group_llm_synthesis.prompts import (
    GROUP_LLM_SPEAKER_SUMMARY_PROMPT_VERSION,
    GROUP_LLM_SUMMARY_PROMPT_VERSION,
    build_global_system_prompt,
    build_global_user_payload,
    build_speaker_system_prompt,
    build_speaker_user_payload,
    pack_records_to_budget,
    serialize_user_prompt,
)
from transcriptx.core.analysis.group_llm_synthesis.sanitize import (
    sanitise_error_message,
)
from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    MAX_SPEAKERS,
    MAX_SUMMARY_CHARS,
    METADATA_SAMPLE_K,
    SCHEMA_GLOBAL,
    SCHEMA_OUTCOME,
    SCHEMA_SPEAKER,
    SCHEMA_SPEAKER_INDEX,
    AttemptStatus,
    OverallStatus,
    UnitStatus,
)
from transcriptx.core.analysis.group_llm_synthesis.status import compute_overall_status
from transcriptx.core.analysis.group_llm_synthesis.validate import (
    ValidationResult,
    cap_warning_samples,
    validate_global_collect,
    validate_speaker_rows,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_text
from transcriptx.core.analysis.llm_support.runtime import (
    build_ollama_analysis_client,
    require_ollama_analysis,
    resolve_llm_runtime,
)
from transcriptx.core.llm.errors import (
    LLMConfigurationError,
    LLMResponseError,
    LLMUnavailableError,
)
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class SynthesisAttemptResult:
    """Result of one synthesize attempt (may or may not have published ACTIVE)."""

    attempt_status: AttemptStatus
    published: bool
    generation_id: str | None = None
    overall_status: OverallStatus | None = None
    digests: InputDigests | None = None
    outcome: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    inventory_entries: list[dict[str, str]] = field(default_factory=list)
    prior_manifest_generation_id: str | None = None
    error_code: str | None = None
    error_message_safe: str | None = None


def _unit(
    status: UnitStatus,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    artifact_rel: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"status": status}
    if error_code:
        out["error_code"] = error_code
    if error_message:
        out["error_message_safe"] = sanitise_error_message(error_message)
    if artifact_rel:
        out["artifact_rel"] = artifact_rel
    return out


def _render_md(title: str, summary: str, provenance: dict[str, Any]) -> str:
    lines = [f"# {title}", "", summary, "", "---"]
    lines.append(f"Prompt version: {provenance.get('prompt_version', '')}")
    lines.append(f"Model: {provenance.get('model', '')}")
    lines.append("")
    return "\n".join(lines)


def _provenance(
    *,
    source_module: str,
    prompt_version: str,
    model: str,
    provider: str,
    effort: str,
    generation_id: str,
    digests: InputDigests,
    ordered_member_ids: list[str],
    omitted_count: int,
    omitted_sample: list[str],
    request_hash: str,
    collect_schema_id: str = "transcriptx.llm_summary_collect.v1",
    model_selection_source: str | None = None,
) -> dict[str, Any]:
    prov: dict[str, Any] = {
        "module": "group_llm_synthesis",
        "source_module": source_module,
        "prompt_version": prompt_version,
        "model": model,
        "provider": provider,
        "effort": effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_id": generation_id,
        "collect_schema_id": collect_schema_id,
        **digests.as_dict(),
        "ordered_member_ids_sample": ordered_member_ids[:METADATA_SAMPLE_K],
        "ordered_member_ids_digest": sha256_text("\n".join(ordered_member_ids)),
        "omitted_count": omitted_count,
        "omitted_ids_sample": omitted_sample[:METADATA_SAMPLE_K],
        "request_hash": request_hash,
        "cache_key": f"group_llm_synthesis:{generation_id}:{request_hash[:16]}",
    }
    if model_selection_source:
        prov["model_selection_source"] = model_selection_source
    return prov


def _call_summary(
    client: Any,
    *,
    system: str,
    user: str,
    max_chars: int,
    max_tokens: int,
) -> str:
    raw = client.generate(
        prompt=user,
        system_prompt=system,
        temperature=0.0,
        max_tokens=max_tokens,
        response_format="json",
    )
    parsed = parse_group_summary_json(str(raw or ""), max_chars=max_chars)
    return str(parsed["summary"])


def run_group_llm_synthesis(
    *,
    run_root: Path,
    run_id: str,
    config: Any,
    want_global: bool,
    want_speakers: bool,
    cancel_check: Callable[[], bool] | None = None,
) -> SynthesisAttemptResult:
    """Run synthesis. Caller must hold ``synthesis_lock``.

    Intentional skip/fail commits and flips ACTIVE. Cancel / unexpected
    pre-commit errors leave ACTIVE unchanged.
    """
    run_root = Path(run_root)
    warnings: list[dict[str, Any]] = []
    from transcriptx.core.analysis.group_llm_synthesis.generation import read_active

    prior = read_active(run_root)
    prior_gen = str(prior.get("generation_id") or "") if prior else None

    digests = compute_input_digests(
        global_collect_path=global_collect_path(run_root),
        speaker_rows_path=speaker_rows_path(run_root),
    )

    synth_cfg = getattr(getattr(config, "analysis", None), "group_llm_synthesis", None)
    enabled = True if synth_cfg is None else bool(getattr(synth_cfg, "enabled", True))
    effort = "high" if synth_cfg is None else str(getattr(synth_cfg, "effort", "high"))

    generation_id = new_generation_id()
    ensure_generation_dir(run_root, generation_id)
    gc_uncommitted_generations(run_root, keep_generation_id=generation_id)

    def _publish_empty(
        overall: OverallStatus,
        *,
        g_unit: dict[str, Any],
        s_meta: dict[str, Any],
        attempt: AttemptStatus,
        code: str | None = None,
        message: str | None = None,
    ) -> SynthesisAttemptResult:
        outcome = {
            "schema_id": SCHEMA_OUTCOME,
            "run_id": run_id,
            "generation_id": generation_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall,
            "global": g_unit,
            "speakers": s_meta,
            "config_snapshot": {
                "enabled": enabled,
                "effort": effort,
                "provider": getattr(getattr(config, "llm", None), "provider", None),
                "model": getattr(getattr(config, "llm", None), "model", None),
            },
            "input_digests": digests.as_dict(),
            "prompt_version": {
                "global": GROUP_LLM_SUMMARY_PROMPT_VERSION,
                "speaker": GROUP_LLM_SPEAKER_SUMMARY_PROMPT_VERSION,
            },
            "warning_count": len(warnings),
            "warnings_sample": cap_warning_samples(warnings),
        }
        write_json_under_generation(run_root, generation_id, "outcome.json", outcome)
        inventory = build_commit_inventory(
            run_root,
            generation_id,
            [
                {
                    "rel_path": "outcome.json",
                    "module": "llm_summary",
                    "kind": "data_json",
                }
            ],
        )
        write_commit(
            run_root,
            generation_id=generation_id,
            digests=digests,
            overall_status=overall,
            inventory=inventory,
        )
        write_active(
            run_root,
            generation_id=generation_id,
            digests=digests,
            overall_status=overall,
        )
        return SynthesisAttemptResult(
            attempt_status=attempt,
            published=True,
            generation_id=generation_id,
            overall_status=overall,
            digests=digests,
            outcome=outcome,
            warnings=warnings,
            inventory_entries=[
                {
                    "rel_path": f".group_llm_synthesis/generations/{generation_id}/outcome.json",
                    "module": "llm_summary",
                    "kind": "data_json",
                }
            ],
            prior_manifest_generation_id=prior_gen,
            error_code=code,
            error_message_safe=sanitise_error_message(message),
        )

    if not enabled:
        warnings.append(
            {"code": err.SYNTHESIS_DISABLED, "message": "synthesis disabled"}
        )
        return _publish_empty(
            "skipped",
            g_unit=_unit("skipped", error_code=err.SYNTHESIS_DISABLED),
            s_meta={
                "status": "skipped",
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "entries": [],
            },
            attempt="skipped",
            code=err.SYNTHESIS_DISABLED,
            message="group_llm_synthesis.enabled is false",
        )

    llm_cfg = getattr(config, "llm", None)
    try:
        if llm_cfg is None:
            raise LLMConfigurationError("LLM configuration absent")
        require_ollama_analysis(llm_cfg)
        runtime = resolve_llm_runtime(
            llm_cfg=llm_cfg, effort=effort, consumer_id="group_llm_synthesis"
        )
    except LLMConfigurationError as exc:
        code = (
            err.LLM_DISABLED
            if "not configured" in str(exc).lower()
            else err.LLM_CONFIGURATION
        )
        warnings.append({"code": code, "message": sanitise_error_message(str(exc))})
        return _publish_empty(
            "skipped" if code == err.LLM_DISABLED else "failed",
            g_unit=_unit(
                "skipped" if code == err.LLM_DISABLED else "failed",
                error_code=code,
                error_message=str(exc),
            ),
            s_meta={
                "status": "skipped",
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "entries": [],
            },
            attempt="skipped" if code == err.LLM_DISABLED else "failed",
            code=code,
            message=str(exc),
        )
    except ValueError as exc:
        warnings.append(
            {"code": err.LLM_CONFIGURATION, "message": sanitise_error_message(str(exc))}
        )
        return _publish_empty(
            "failed",
            g_unit=_unit(
                "failed", error_code=err.LLM_CONFIGURATION, error_message=str(exc)
            ),
            s_meta={
                "status": "skipped",
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "entries": [],
            },
            attempt="failed",
            code=err.LLM_CONFIGURATION,
            message=str(exc),
        )

    validation = ValidationResult()
    sessions, g_warn, g_err, g_msg = validate_global_collect(
        global_collect_path(run_root) if want_global else None,
        run_id=run_id,
        required=want_global,
    )
    validation.warnings.extend(g_warn)
    validation.sessions = sessions
    if g_err and want_global:
        validation.global_error_code = g_err
        validation.global_error_message = g_msg

    groups, tokens, displays, s_warn, s_err, s_msg = validate_speaker_rows(
        speaker_rows_path(run_root) if want_speakers else None,
        run_id=run_id,
        required=want_speakers,
    )
    validation.warnings.extend(s_warn)
    validation.speaker_groups = groups
    validation.artifact_tokens = tokens
    validation.display_names = displays
    if s_err and want_speakers:
        validation.speaker_error_code = s_err
        validation.speaker_error_message = s_msg

    warnings.extend(cap_warning_samples(validation.warnings))

    if not want_global:
        g_status: UnitStatus = "skipped"
        g_unit = _unit("skipped")
    elif validation.global_error_code == err.NO_USABLE_MEMBER_SUMMARIES:
        g_status = "skipped"
        g_unit = _unit(
            "skipped",
            error_code=validation.global_error_code,
            error_message=validation.global_error_message,
        )
    elif validation.global_error_code:
        g_status = "failed"
        g_unit = _unit(
            "failed",
            error_code=validation.global_error_code,
            error_message=validation.global_error_message,
        )
    elif not validation.sessions:
        g_status = "skipped"
        g_unit = _unit("skipped", error_code=err.NO_USABLE_MEMBER_SUMMARIES)
    else:
        g_status = "success"  # provisional until call
        g_unit = _unit("success")

    eligible_canon = sorted(validation.speaker_groups.keys())
    capped = eligible_canon[:MAX_SPEAKERS]
    overflow = eligible_canon[MAX_SPEAKERS:]

    inventory_rels: list[dict[str, str]] = []
    speaker_entries: list[dict[str, Any]] = []
    ok = fail = skip = 0
    llm_unavailable = False
    client = None
    max_summary_chars = min(MAX_SUMMARY_CHARS, int(runtime.max_output_tokens) * 8)

    def _cancelled() -> bool:
        return bool(cancel_check and cancel_check())

    try:
        if g_status == "success" or capped:
            client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime)

        # Global call
        if g_status == "success" and validation.sessions:
            if _cancelled():
                return SynthesisAttemptResult(
                    attempt_status="cancelled",
                    published=False,
                    generation_id=generation_id,
                    digests=digests,
                    warnings=warnings,
                    prior_manifest_generation_id=prior_gen,
                    error_code=err.CANCELLED,
                    error_message_safe="cancelled before global synthesis",
                )
            kept, omitted, payload = pack_records_to_budget(
                validation.sessions,
                build_payload=lambda k, omitted_ids: build_global_user_payload(
                    k, omitted_ids=omitted_ids
                ),
                max_input_chars=runtime.max_input_chars,
            )
            user = serialize_user_prompt(payload)
            if len(user) > runtime.max_input_chars:
                g_status = "failed"
                g_unit = _unit(
                    "failed",
                    error_code=err.PROMPT_BUDGET,
                    error_message="prompt exceeds budget",
                )
            else:
                try:
                    summary = _call_summary(
                        client,
                        system=build_global_system_prompt(),
                        user=user,
                        max_chars=max_summary_chars,
                        max_tokens=runtime.max_output_tokens,
                    )
                    member_ids = [s.transcript_id for s in kept]
                    prov = _provenance(
                        source_module="llm_summary",
                        prompt_version=GROUP_LLM_SUMMARY_PROMPT_VERSION,
                        model=runtime.model,
                        provider="ollama",
                        effort=runtime.effort,
                        generation_id=generation_id,
                        digests=digests,
                        ordered_member_ids=member_ids,
                        omitted_count=len(omitted),
                        omitted_sample=omitted,
                        request_hash=sha256_text(user),
                        model_selection_source=getattr(runtime, "model_source", None),
                    )
                    art = {
                        "schema_id": SCHEMA_GLOBAL,
                        "summary": summary,
                        "provenance": prov,
                        "generation_id": generation_id,
                        **digests.as_dict(),
                        "collect_schema_id": "transcriptx.llm_summary_collect.v1",
                        "synthesis": {"status": "success"},
                    }
                    write_json_under_generation(
                        run_root, generation_id, global_summary_rel(), art
                    )
                    write_text_under_generation(
                        run_root,
                        generation_id,
                        global_summary_md_rel(),
                        _render_md("Cross-session LLM Summary", summary, prov),
                    )
                    inventory_rels.extend(
                        [
                            {
                                "rel_path": global_summary_rel(),
                                "module": "llm_summary",
                                "kind": "data_json",
                            },
                            {
                                "rel_path": global_summary_md_rel(),
                                "module": "llm_summary",
                                "kind": "data_txt",
                            },
                        ]
                    )
                    g_unit = _unit("success", artifact_rel=global_summary_rel())
                except LLMUnavailableError as exc:
                    llm_unavailable = True
                    g_status = "failed"
                    g_unit = _unit(
                        "failed", error_code=err.LLM_UNAVAILABLE, error_message=str(exc)
                    )
                except (LLMResponseError, Exception) as exc:
                    code = (
                        response_error_code(exc)
                        if isinstance(exc, LLMResponseError)
                        else err.UNEXPECTED_ERROR
                    )
                    if isinstance(exc, LLMUnavailableError):
                        code = err.LLM_UNAVAILABLE
                        llm_unavailable = True
                    g_status = "failed"
                    g_unit = _unit("failed", error_code=code, error_message=str(exc))

        # Speakers
        for canon in capped:
            if llm_unavailable:
                skip += 1
                speaker_entries.append(
                    {
                        "canonical_speaker_id": canon,
                        "display_name": validation.display_names.get(canon, canon),
                        "artifact_token": validation.artifact_tokens.get(canon, canon),
                        "status": "skipped",
                        "error_code": err.LLM_UNAVAILABLE,
                        "error_message_safe": sanitise_error_message("LLM unavailable"),
                    }
                )
                continue
            if _cancelled():
                return SynthesisAttemptResult(
                    attempt_status="cancelled",
                    published=False,
                    generation_id=generation_id,
                    digests=digests,
                    warnings=warnings,
                    prior_manifest_generation_id=prior_gen,
                    error_code=err.CANCELLED,
                    error_message_safe="cancelled during speaker synthesis",
                )
            sessions_sp = validation.speaker_groups[canon]
            display = validation.display_names.get(canon, canon)
            token = validation.artifact_tokens[canon]

            def _build(k, omitted_ids, _canon=canon, _display=display):
                return build_speaker_user_payload(
                    k,
                    canonical_speaker_id=_canon,
                    display_name=_display,
                    omitted_ids=omitted_ids,
                )

            kept_s, omitted_s, payload_s = pack_records_to_budget(
                sessions_sp,
                build_payload=_build,
                max_input_chars=runtime.max_input_chars,
            )
            user_s = serialize_user_prompt(payload_s)
            if len(user_s) > runtime.max_input_chars:
                fail += 1
                speaker_entries.append(
                    {
                        "canonical_speaker_id": canon,
                        "display_name": display,
                        "artifact_token": token,
                        "status": "failed",
                        "error_code": err.PROMPT_BUDGET,
                        "error_message_safe": sanitise_error_message(
                            "prompt exceeds budget"
                        ),
                    }
                )
                continue
            try:
                summary_s = _call_summary(
                    client,
                    system=build_speaker_system_prompt(display_name=display),
                    user=user_s,
                    max_chars=max_summary_chars,
                    max_tokens=runtime.max_output_tokens,
                )
                prov_s = _provenance(
                    source_module="llm_speaker_summary",
                    prompt_version=GROUP_LLM_SPEAKER_SUMMARY_PROMPT_VERSION,
                    model=runtime.model,
                    provider="ollama",
                    effort=runtime.effort,
                    generation_id=generation_id,
                    digests=digests,
                    ordered_member_ids=[s.transcript_id for s in kept_s],
                    omitted_count=len(omitted_s),
                    omitted_sample=omitted_s,
                    request_hash=sha256_text(user_s),
                    collect_schema_id="transcriptx.llm_speaker_summary_collect.v1",
                    model_selection_source=getattr(runtime, "model_source", None),
                )
                rel_json = speaker_artifact_rel(token, "json")
                rel_md = speaker_artifact_rel(token, "md")
                art_s = {
                    "schema_id": SCHEMA_SPEAKER,
                    "canonical_speaker_id": canon,
                    "display_name": display,
                    "artifact_token": token,
                    "summary": summary_s,
                    "provenance": prov_s,
                    "generation_id": generation_id,
                    **digests.as_dict(),
                    "collect_schema_id": "transcriptx.llm_speaker_summary_collect.v1",
                    "synthesis": {"status": "success"},
                }
                write_json_under_generation(run_root, generation_id, rel_json, art_s)
                write_text_under_generation(
                    run_root,
                    generation_id,
                    rel_md,
                    _render_md(f"Cross-session Summary — {display}", summary_s, prov_s),
                )
                inventory_rels.extend(
                    [
                        {
                            "rel_path": rel_json,
                            "module": "llm_speaker_summary",
                            "kind": "data_json",
                        },
                        {
                            "rel_path": rel_md,
                            "module": "llm_speaker_summary",
                            "kind": "data_txt",
                        },
                    ]
                )
                ok += 1
                speaker_entries.append(
                    {
                        "canonical_speaker_id": canon,
                        "display_name": display,
                        "artifact_token": token,
                        "status": "success",
                        "rel_json": rel_json,
                        "rel_md": rel_md,
                    }
                )
            except LLMUnavailableError as exc:
                llm_unavailable = True
                fail += 1
                speaker_entries.append(
                    {
                        "canonical_speaker_id": canon,
                        "display_name": display,
                        "artifact_token": token,
                        "status": "failed",
                        "error_code": err.LLM_UNAVAILABLE,
                        "error_message_safe": sanitise_error_message(str(exc)),
                    }
                )
            except Exception as exc:
                fail += 1
                code = (
                    response_error_code(exc)
                    if isinstance(exc, LLMResponseError)
                    else err.UNEXPECTED_ERROR
                )
                speaker_entries.append(
                    {
                        "canonical_speaker_id": canon,
                        "display_name": display,
                        "artifact_token": token,
                        "status": "failed",
                        "error_code": code,
                        "error_message_safe": sanitise_error_message(str(exc)),
                    }
                )

        for canon in overflow:
            skip += 1
            speaker_entries.append(
                {
                    "canonical_speaker_id": canon,
                    "display_name": validation.display_names.get(canon, canon),
                    "artifact_token": validation.artifact_tokens.get(canon, canon),
                    "status": "skipped",
                    "error_code": err.MAX_SPEAKERS,
                    "error_message_safe": sanitise_error_message(
                        "exceeded max speakers"
                    ),
                }
            )

        if not want_speakers:
            s_status: UnitStatus = "skipped"
        elif validation.speaker_error_code and not capped:
            s_status = (
                "skipped"
                if validation.speaker_error_code == err.NO_USABLE_MEMBER_SUMMARIES
                else "failed"
            )
        elif ok == 0 and fail == 0:
            s_status = "skipped"
        elif fail == 0:
            s_status = "success"
        elif ok == 0:
            s_status = "failed"
        else:
            s_status = "failed"  # partial reflected in overall

        # Speaker index when any speaker work considered
        if want_speakers and (capped or overflow or speaker_entries):
            index_payload = {
                "schema_id": SCHEMA_SPEAKER_INDEX,
                "generation_id": generation_id,
                **digests.as_dict(),
                "collect_schema_id": "transcriptx.llm_speaker_summary_collect.v1",
                "speakers": speaker_entries,
                "provenance": {
                    "module": "group_llm_synthesis",
                    "source_module": "llm_speaker_summary",
                    "prompt_version": GROUP_LLM_SPEAKER_SUMMARY_PROMPT_VERSION,
                    "model": runtime.model,
                    "provider": "ollama",
                    "effort": runtime.effort,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "success_count": ok,
                    "failed_count": fail,
                    "skipped_count": skip,
                },
                "synthesis": {"status": s_status},
            }
            write_json_under_generation(
                run_root, generation_id, speaker_index_rel(), index_payload
            )
            write_text_under_generation(
                run_root,
                generation_id,
                speaker_index_md_rel(),
                "# Cross-session Per-Speaker Summaries\n\n"
                f"Success: {ok}, Failed: {fail}, Skipped: {skip}\n",
            )
            inventory_rels.extend(
                [
                    {
                        "rel_path": speaker_index_rel(),
                        "module": "llm_speaker_summary",
                        "kind": "data_json",
                    },
                    {
                        "rel_path": speaker_index_md_rel(),
                        "module": "llm_speaker_summary",
                        "kind": "data_txt",
                    },
                ]
            )

        overall = compute_overall_status(
            global_status=g_status,
            speaker_ok=ok,
            speaker_fail=fail,
            speaker_skip=skip,
        )
        if not want_global and not want_speakers:
            overall = "skipped"
        if (
            not validation.sessions
            and not capped
            and want_global
            and want_speakers
            and g_status == "skipped"
            and s_status == "skipped"
        ):
            overall = "skipped"

        s_meta = {
            "status": s_status,
            "success_count": ok,
            "failed_count": fail,
            "skipped_count": skip,
            "entries": speaker_entries,
        }
        outcome = {
            "schema_id": SCHEMA_OUTCOME,
            "run_id": run_id,
            "generation_id": generation_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall,
            "global": g_unit,
            "speakers": s_meta,
            "config_snapshot": {
                "enabled": enabled,
                "effort": effort,
                "provider": "ollama",
                "model": runtime.model,
            },
            "input_digests": digests.as_dict(),
            "bounds": {
                "max_input_chars": runtime.max_input_chars,
                "max_output_tokens": runtime.max_output_tokens,
                "max_speakers": MAX_SPEAKERS,
            },
            "prompt_version": {
                "global": GROUP_LLM_SUMMARY_PROMPT_VERSION,
                "speaker": GROUP_LLM_SPEAKER_SUMMARY_PROMPT_VERSION,
            },
            "warning_count": len(warnings),
            "warnings_sample": cap_warning_samples(warnings),
        }
        write_json_under_generation(run_root, generation_id, "outcome.json", outcome)
        inventory_rels.append(
            {"rel_path": "outcome.json", "module": "llm_summary", "kind": "data_json"}
        )
        inventory = build_commit_inventory(run_root, generation_id, inventory_rels)
        write_commit(
            run_root,
            generation_id=generation_id,
            digests=digests,
            overall_status=overall,
            inventory=inventory,
        )
        write_active(
            run_root,
            generation_id=generation_id,
            digests=digests,
            overall_status=overall,
        )
        prefix = f".group_llm_synthesis/generations/{generation_id}/"
        manifest_entries = [
            {
                "rel_path": prefix + e["rel_path"],
                "module": e["module"],
                "kind": e["kind"],
            }
            for e in inventory_rels
        ]
        attempt: AttemptStatus = overall  # type: ignore[assignment]
        return SynthesisAttemptResult(
            attempt_status=attempt,
            published=True,
            generation_id=generation_id,
            overall_status=overall,
            digests=digests,
            outcome=outcome,
            warnings=warnings,
            inventory_entries=manifest_entries,
            prior_manifest_generation_id=prior_gen,
        )
    except Exception as exc:
        logger.exception("group LLM synthesis failed before commit: %s", exc)
        return SynthesisAttemptResult(
            attempt_status="failed",
            published=False,
            generation_id=generation_id,
            digests=digests,
            warnings=warnings,
            prior_manifest_generation_id=prior_gen,
            error_code=err.UNEXPECTED_ERROR,
            error_message_safe=sanitise_error_message(str(exc)),
        )
