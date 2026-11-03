"""Speaker ID voice callbacks and suggestion UI (CCv2 + Streamlit)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.app.speaker_id import SpeakerIdCommand, new_action_id
from transcriptx.io.speaker_map_resolver import normalize_diarized_id
from transcriptx.web.cache_helpers import load_voice_segment_payload
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal
from transcriptx.web.services.transcript_context_resolver import paths_match
from transcriptx.web.workspaces.speaker_id_session_keys import (
    TranscriptProfileContext,
    _consume_flash,
    _set_flash,
    speaker_idx_key,
    voice_batch_summary_key,
    voice_display_key,
    voice_gate_key,
    voice_loaded_key,
    voice_pending_key,
    widget_key,
)


def _voice_display_from_result(result, *, profile_name_lookup) -> dict:
    """Build a lightweight session-safe display payload from an analyse result."""
    candidates: list[dict] = []
    for cand in getattr(result, "candidates_ui", None) or []:
        pid = cand.get("profile_id")
        live_name = profile_name_lookup(pid) if pid else None
        candidates.append(
            {
                "profile_id": pid,
                "display_name": live_name or cand.get("display_name") or pid,
                "confidence": cand.get("confidence"),
                "reference_count": cand.get("reference_count"),
            }
        )
    return {
        "outcome": getattr(result, "outcome", None),
        "detail": getattr(result, "detail", None),
        "candidates": candidates,
    }


def _voice_candidates_for_active(
    transcript_path: str | Path, active_id: str
) -> list[dict]:
    display = st.session_state.get(voice_display_key(transcript_path, active_id))
    if not isinstance(display, dict):
        return []
    if display.get("outcome") != "SuggestionAvailable":
        return []
    return list(display.get("candidates") or [])


def _voice_recipe_hint(*, profile_ctx: TranscriptProfileContext) -> str | None:
    if not profile_ctx.is_managed:
        return (
            "Longitudinal linking is available for managed library transcripts only. "
            "Local naming still works here."
        )
    try:
        from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
        from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
        from transcriptx.core.speaker_profiles.voice.versioning import (
            FEATURE_GATE_COMPLETE,
        )

        if not FEATURE_GATE_COMPLETE:
            return None
        status = ActivationBarrier(speaker_profiles_dir()).status()
        if not status.allowed:
            reason = status.block_reason or "unavailable"
            if reason in {
                "privacy_disabled",
                "privacy_consent_required",
                "privacy_settings_missing",
            }:
                return (
                    "Voice suggestions need Settings → Speakers: enable voice matching, "
                    "then Enrol trusted voice for all profiles, then Pre-load voice "
                    "suggestions. Confirming a suggestion still names the speaker — "
                    "nothing is applied automatically."
                )
            return (
                "Local voice suggestions are not available yet "
                f"({reason}). You can still attach this speaker to a profile by name."
            )
    except Exception:
        pass
    return (
        "To get voice suggestions on the next transcript: name and link a seed cast, "
        "then Settings → Speakers → Enrol trusted voice for all profiles, then "
        "Pre-load voice suggestions. Confirm each suggestion in Speaker ID — "
        "scores never auto-name."
    )


def _cb_load_voice(transcript_path: str) -> None:
    st.session_state[voice_loaded_key(transcript_path)] = True


def _cb_voice_analyse_one(transcript_path: str, speaker_id: str) -> None:
    st.session_state[voice_pending_key(transcript_path)] = {
        "mode": "one",
        "speaker": speaker_id,
        "transcript": str(transcript_path),
    }


def _cb_voice_analyse_all(transcript_path: str) -> None:
    st.session_state[voice_pending_key(transcript_path)] = {
        "mode": "all",
        "transcript": str(transcript_path),
    }


def _cb_voice_confirm(
    transcript_path: str,
    speaker_id: str,
    profile_id: str,
) -> None:
    """Confirm suggestion; heavy work runs here before the natural fragment rerun."""
    try:
        from transcriptx.core.speaker_profiles.identity import link_file_key
        from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
        from transcriptx.core.speaker_profiles.service import SpeakerProfileService
        from transcriptx.services.speaker_profiles.voice_facade import (
            SpeakerIdVoiceFacade,
            ensure_idempotency_key,
            voice_session_key,
        )

        resolver = ManagedTranscriptResolver()
        resolved = resolver.resolve_path(transcript_path)
        lsk = normalize_diarized_id(speaker_id)
        result_key = voice_session_key(resolved.managed_transcript_id, lsk, "result")
        result = st.session_state.get(result_key)
        if result is None or not getattr(result, "candidates_ui", None):
            _set_flash(
                transcript_path,
                level="warning",
                message="Voice suggestion is no longer available.",
            )
            return
        cand = next(
            (c for c in result.candidates_ui if c.get("profile_id") == profile_id),
            None,
        )
        if cand is None:
            _set_flash(
                transcript_path,
                level="warning",
                message="Voice suggestion is no longer available.",
            )
            return
        facade = SpeakerIdVoiceFacade()
        svc = SpeakerProfileService()
        live = svc.get_live_link(link_file_key(resolved.managed_transcript_id, lsk))
        accept_key = voice_session_key(
            resolved.managed_transcript_id,
            lsk,
            f"accept_{profile_id}",
        )
        op_key = ensure_idempotency_key(st.session_state, accept_key)
        ar = facade.accept(
            operation_idempotency_key=op_key,
            managed_transcript_id=resolved.managed_transcript_id,
            local_speaker_key=lsk,
            candidate_profile_id=profile_id,
            suggestion_id=result.suggestion_id or "",
            suggestion_digest=result.suggestion_digest or "",
            confidence_category=cand["confidence"],
            model_generation_id=result.model_generation_id or "",
            occurrence_fingerprint=result.occurrence_fingerprint or "",
            expected_link_id=(
                result.expected_link_id
                if result.expected_link_id is not None
                else (live.link_id if live else None)
            ),
            expected_owner_profile_id=(
                result.expected_owner_profile_id
                if result.expected_owner_profile_id is not None
                else (live.profile_id if live else None)
            ),
            expected_fingerprint=(
                result.expected_fingerprint
                if result.expected_fingerprint is not None
                else (live.occurrence_fingerprint if live else None)
            ),
            expected_audio_stat_fingerprint=result.audio_stat_fingerprint,
            expected_audio_content_sha256=result.audio_content_sha256,
            query_cache_key=result.query_cache_key,
        )
        consume_cache_invalidation_signal(ar.cache_signal)
        st.session_state.pop(result_key, None)
        st.session_state.pop(voice_display_key(transcript_path, speaker_id), None)
        _set_flash(
            transcript_path,
            level="success",
            message="Profile link confirmed from suggestion.",
        )
    except Exception as exc:
        _set_flash(transcript_path, level="error", message=str(exc))


def _cb_voice_reject(
    transcript_path: str,
    speaker_id: str,
    profile_id: str,
) -> None:
    try:
        from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
        from transcriptx.services.speaker_profiles.voice_facade import (
            SpeakerIdVoiceFacade,
            ensure_idempotency_key,
            voice_session_key,
        )

        resolver = ManagedTranscriptResolver()
        resolved = resolver.resolve_path(transcript_path)
        lsk = normalize_diarized_id(speaker_id)
        result_key = voice_session_key(resolved.managed_transcript_id, lsk, "result")
        result = st.session_state.get(result_key)
        if result is None or not getattr(result, "candidates_ui", None):
            st.session_state.pop(result_key, None)
            st.session_state.pop(voice_display_key(transcript_path, speaker_id), None)
            return
        cand = next(
            (c for c in result.candidates_ui if c.get("profile_id") == profile_id),
            None,
        )
        if cand is None:
            st.session_state.pop(result_key, None)
            st.session_state.pop(voice_display_key(transcript_path, speaker_id), None)
            return
        facade = SpeakerIdVoiceFacade()
        rej_key = voice_session_key(
            resolved.managed_transcript_id,
            lsk,
            f"reject_{profile_id}",
        )
        facade.reject(
            operation_idempotency_key=ensure_idempotency_key(st.session_state, rej_key),
            managed_transcript_id=resolved.managed_transcript_id,
            local_speaker_key=lsk,
            occurrence_fingerprint=result.occurrence_fingerprint or "",
            candidate_profile_id=profile_id,
            suggestion_id=result.suggestion_id or "",
            suggestion_digest=result.suggestion_digest or "",
            model_generation_id=result.model_generation_id or "",
            reference_corpus_digest=result.reference_corpus_digest or "",
            reference_count=int(cand.get("reference_count") or 0),
        )
        st.session_state.pop(result_key, None)
        st.session_state.pop(voice_display_key(transcript_path, speaker_id), None)
        _set_flash(
            transcript_path,
            level="info",
            message="Suggestion rejected for this evidence set.",
        )
    except Exception as exc:
        _set_flash(transcript_path, level="error", message=str(exc))


def _cb_voice_confirm_action(
    transcript_path: str, speaker_id: str, profile_id: str
) -> None:
    """Route confirm through SpeakerIdActionService (revisioned command)."""
    from transcriptx.web.page_modules.speaker_id import _get_action_service

    svc = _get_action_service()
    idx = int(st.session_state.get(speaker_idx_key(transcript_path), 0) or 0)
    ack = svc.execute(
        SpeakerIdCommand(
            action="voice_confirm",
            transcript_id=str(Path(transcript_path).resolve()),
            action_id=new_action_id(),
            action_seq=idx + 1,
            current_speaker_idx=idx,
            expected_speaker_id=speaker_id,
            payload={"profile_id": profile_id},
            frontend_build_id="legacy",
        )
    )
    from transcriptx.web.page_modules.speaker_id import _apply_ack

    _apply_ack(ack, transcript_path=transcript_path, speaker_count=max(idx + 1, 1))


def _cb_voice_reject_action(
    transcript_path: str, speaker_id: str, profile_id: str
) -> None:
    from transcriptx.web.page_modules.speaker_id import _get_action_service

    svc = _get_action_service()
    idx = int(st.session_state.get(speaker_idx_key(transcript_path), 0) or 0)
    ack = svc.execute(
        SpeakerIdCommand(
            action="voice_reject",
            transcript_id=str(Path(transcript_path).resolve()),
            action_id=new_action_id(),
            action_seq=idx + 1,
            current_speaker_idx=idx,
            expected_speaker_id=speaker_id,
            payload={"profile_id": profile_id},
            frontend_build_id="legacy",
        )
    )
    from transcriptx.web.page_modules.speaker_id import _apply_ack

    _apply_ack(ack, transcript_path=transcript_path, speaker_count=max(idx + 1, 1))


def _cb_voice_leave(
    transcript_path: str,
    speaker_id: str,
    profile_id: str,
) -> None:
    try:
        from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
        from transcriptx.services.speaker_profiles.voice_facade import (
            SpeakerIdVoiceFacade,
            voice_session_key,
        )

        resolver = ManagedTranscriptResolver()
        resolved = resolver.resolve_path(transcript_path)
        lsk = normalize_diarized_id(speaker_id)
        result_key = voice_session_key(resolved.managed_transcript_id, lsk, "result")
        facade = SpeakerIdVoiceFacade()
        facade.acceptance.leave_unlinked()
        st.session_state.pop(result_key, None)
        st.session_state.pop(voice_display_key(transcript_path, speaker_id), None)
        _set_flash(
            transcript_path,
            level="info",
            message="Left unlinked for this session.",
        )
    except Exception as exc:
        _set_flash(transcript_path, level="error", message=str(exc))


def _render_voice_display_payload(
    *,
    path_str: str,
    active_id: str,
    display: dict,
) -> None:
    """Render stored voice UI without constructing facades or profile services."""
    outcome = display.get("outcome")
    candidates = display.get("candidates") or []
    if outcome == "SuggestionAvailable" and candidates:
        for cand in candidates:
            st.write(
                f"**{cand.get('display_name') or cand.get('profile_id')}** — "
                f"{cand.get('confidence')} "
                f"({cand.get('reference_count')} refs)"
            )
            cols = st.columns(3)
            pid = cand.get("profile_id")
            cols[0].button(
                "Confirm this profile",
                icon=ic.CONFIRM,
                key=widget_key(path_str, f"voice_confirm_{active_id}_{pid}"),
                on_click=_cb_voice_confirm_action,
                args=(path_str, active_id, pid),
            )
            cols[1].button(
                "Reject suggestion",
                icon=ic.REJECT,
                key=widget_key(path_str, f"voice_reject_{active_id}_{pid}"),
                on_click=_cb_voice_reject_action,
                args=(path_str, active_id, pid),
            )
            cols[2].button(
                "Leave unlinked",
                icon=ic.UNLINK,
                key=widget_key(path_str, f"voice_leave_{active_id}_{pid}"),
                on_click=_cb_voice_leave,
                args=(path_str, active_id, pid),
            )
        return
    if outcome == "NoReliableMatch":
        st.info("No reliable voice match.")
        return
    if outcome == "insufficient_speech":
        st.warning(
            "Voice analyse: insufficient speech — need at least "
            "8 seconds of speech attributed to this speaker."
        )
        if display.get("detail"):
            st.caption(str(display["detail"]))
        return
    if outcome:
        st.warning(f"Voice analyse: {outcome}")
        if display.get("detail"):
            st.caption(str(display["detail"]))


def _store_voice_display_for_result(
    *,
    path_str: str,
    speaker_id: str,
    result,
) -> None:
    from transcriptx.core.speaker_profiles.service import SpeakerProfileService

    name_svc = SpeakerProfileService()

    def _lookup(pid: str) -> str | None:
        live = name_svc.get_profile(pid)
        return live.display_name if live is not None else None

    st.session_state[voice_display_key(path_str, speaker_id)] = (
        _voice_display_from_result(result, profile_name_lookup=_lookup)
    )


def _render_voice_suggestions(
    *,
    transcript_path: str | Path,
    speaker_ids: Sequence[str],
    ignored: List[str],
    active_id: str,
    profile_ctx: TranscriptProfileContext,
) -> None:
    """Conditional voice UI — services only when loading gate, pending analyse, or first display build."""
    path_str = str(transcript_path)
    loaded_key = voice_loaded_key(path_str)
    pending_key = voice_pending_key(path_str)
    batch_key = voice_batch_summary_key(path_str)
    display_key = voice_display_key(path_str, active_id)
    gate_key = voice_gate_key(path_str)

    if not st.session_state.get(loaded_key):
        # Completely unmounted before Load (no barrier / facade / profile services).
        st.button(
            "Load voice suggestions",
            key=widget_key(path_str, f"voice_load_{active_id}"),
            icon=ic.VOICE,
            on_click=_cb_load_voice,
            args=(path_str,),
            help=widget_help(
                "Prepare local voice matching controls for this transcript."
            ),
        )
        return

    pending_peek = st.session_state.get(pending_key)
    batch_peek = st.session_state.get(batch_key)
    display = st.session_state.get(display_key)

    # Cached activation gate (checked once after Load, not on every play click).
    gate = st.session_state.get(gate_key)
    if not isinstance(gate, dict):
        from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
        from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier

        status = ActivationBarrier(speaker_profiles_dir()).status()
        gate = {
            "allowed": bool(status.allowed),
            "reason": status.block_reason,
        }
        st.session_state[gate_key] = gate

    if not gate.get("allowed"):
        st.caption(
            "Local voice suggestions are not available yet "
            f"({gate.get('reason') or 'unavailable'})."
        )
        return

    st.caption(
        "Probabilistic local match — not identity verification. "
        "Confirming uses the existing profile-link workflow."
    )
    btn_one, btn_all = st.columns(2)
    btn_one.button(
        "Analyse voice",
        icon=ic.VOICE,
        key=widget_key(path_str, f"voice_analyse_{active_id}"),
        help=widget_help("Embed this speaker and rank local profile suggestions."),
        on_click=_cb_voice_analyse_one,
        args=(path_str, active_id),
    )
    btn_all.button(
        "Analyse all speakers",
        icon=ic.VOICE,
        key=widget_key(path_str, "voice_analyse_all"),
        help=widget_help(
            (
                "Run voice matching for every non-ignored speaker so "
                "suggestions are ready as you step through the list."
            )
        ),
        on_click=_cb_voice_analyse_all,
        args=(path_str,),
    )

    if batch_peek and not pending_peek:
        st.info(str(st.session_state.pop(batch_key, batch_peek)))

    # Display-only path: no facade / profile service reconstruction.
    if display is not None and not pending_peek:
        _render_voice_display_payload(
            path_str=path_str, active_id=active_id, display=display
        )
        return

    if not pending_peek:
        return

    try:
        from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
        from transcriptx.services.speaker_profiles.voice_facade import (
            SpeakerIdVoiceFacade,
            voice_session_key,
        )

        facade = SpeakerIdVoiceFacade()
        resolver = ManagedTranscriptResolver()
        resolved = resolver.resolve_path(transcript_path)
        lsk = normalize_diarized_id(active_id)
        result_key = voice_session_key(resolved.managed_transcript_id, lsk, "result")

        pending = st.session_state.pop(pending_key, None)
        pending_path = pending.get("transcript") if pending else None
        if pending and pending_path and paths_match(pending_path, transcript_path):
            voice_seg_dicts = load_voice_segment_payload(transcript_path)
            if pending.get("mode") == "one":
                raw_speaker = str(pending.get("speaker") or active_id)
                with st.spinner("Analysing voice…"):
                    try:
                        one_key = voice_session_key(
                            resolved.managed_transcript_id,
                            normalize_diarized_id(raw_speaker),
                            "result",
                        )
                        result = facade.analyse(
                            transcript_path=Path(transcript_path),
                            raw_speaker=raw_speaker,
                            segments=voice_seg_dicts,
                        )
                        st.session_state[one_key] = result
                        _store_voice_display_for_result(
                            path_str=path_str,
                            speaker_id=normalize_diarized_id(raw_speaker)
                            or raw_speaker,
                            result=result,
                        )
                        # Also map under active_id key when same speaker.
                        st.session_state[voice_display_key(path_str, active_id)] = (
                            st.session_state.get(
                                voice_display_key(
                                    path_str,
                                    normalize_diarized_id(raw_speaker) or raw_speaker,
                                )
                            )
                        )
                    except Exception as exc:
                        _set_flash(
                            path_str,
                            level="error",
                            message=f"Voice analyse failed: {exc}",
                        )
                        _consume_flash(path_str)
            elif pending.get("mode") == "all":
                from transcriptx.web.page_modules.speaker_id import (
                    _is_speaker_ignored,
                )

                targets = [
                    sid for sid in speaker_ids if not _is_speaker_ignored(ignored, sid)
                ]
                suggestions = 0
                no_match = 0
                other = 0
                with st.spinner(f"Analysing voice for {len(targets)} speakers…"):
                    from transcriptx.core.speaker_profiles.voice.match_service import (
                        AnalyseResult as _AnalyseResult,
                    )

                    for sid in targets:
                        sid_key = normalize_diarized_id(sid)
                        sid_result_key = voice_session_key(
                            resolved.managed_transcript_id, sid_key, "result"
                        )
                        try:
                            ar = facade.analyse(
                                transcript_path=Path(transcript_path),
                                raw_speaker=sid,
                                segments=voice_seg_dicts,
                            )
                        except Exception as exc:
                            ar = _AnalyseResult(
                                outcome="AnalyseFailed",
                                match=None,
                                suggestion_id=None,
                                suggestion_digest=None,
                                detail=str(exc),
                            )
                        st.session_state[sid_result_key] = ar
                        _store_voice_display_for_result(
                            path_str=path_str,
                            speaker_id=sid_key or sid,
                            result=ar,
                        )
                        if ar.outcome == "SuggestionAvailable":
                            suggestions += 1
                        elif ar.outcome == "NoReliableMatch":
                            no_match += 1
                        else:
                            other += 1
                st.session_state[batch_key] = (
                    f"Analysed {len(targets)} speakers: "
                    f"{suggestions} suggestion(s), "
                    f"{no_match} no match, "
                    f"{other} other."
                )
                st.info(st.session_state[batch_key])
                st.session_state.pop(batch_key, None)

        display = st.session_state.get(display_key)
        if display is not None:
            _render_voice_display_payload(
                path_str=path_str, active_id=active_id, display=display
            )
            return

        # Fallback: build display from stored AnalyseResult once.
        result = st.session_state.get(result_key)
        if result is None:
            return
        _store_voice_display_for_result(
            path_str=path_str, speaker_id=active_id, result=result
        )
        display = st.session_state.get(display_key)
        if display is not None:
            _render_voice_display_payload(
                path_str=path_str, active_id=active_id, display=display
            )
    except st.errors.StreamlitAPIException:
        raise
    except Exception as exc:
        st.warning(f"Voice suggestions unavailable: {exc}")
