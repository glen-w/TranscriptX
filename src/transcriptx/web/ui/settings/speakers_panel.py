"""Settings → Speakers: profile list toggles and local voice matching."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.speaker_profile_signals import (
    INCLUDE_IGNORED_SESSION_KEY,
    SHOW_ARCHIVED_SESSION_KEY,
    SHOW_MERGED_SESSION_KEY,
)

_ENROL_PREVIEW_KEY = "_voice_bulk_enrol_preview"
_ENROL_RESULT_KEY = "_voice_bulk_enrol_last_result"
_PRELOAD_PREVIEW_KEY = "_voice_bulk_preload_preview"
_PRELOAD_RESULT_KEY = "_voice_bulk_preload_last_result"


def _render_enrol_all_result(result) -> None:
    summary = (
        f"Enrolled {result.ok_count} profile(s); skipped {result.skipped_count}; "
        f"errors {result.error_count}; "
        f"{result.links_enrolled_total} link(s); {result.samples_total} sample(s)."
    )
    if result.error_count:
        st.warning(f"Bulk voice enrol finished with issues. {summary}")
    elif result.ok_count == 0 and result.skipped_count > 0:
        st.info(f"Nothing new to enrol. {summary}")
    else:
        st.success(f"Bulk voice enrol complete. {summary}")

    with st.expander("Per-profile results", expanded=bool(result.error_count)):
        if not result.targets:
            st.caption("No profiles processed.")
            return
        for target in result.targets:
            detail = (
                f"{target.display_name or target.profile_id}: "
                f"{target.status.value}"
            )
            if target.links_attempted or target.links_enrolled:
                detail += (
                    f" — {target.links_enrolled}/{target.links_attempted} link(s), "
                    f"{target.sample_count} sample(s)"
                )
            if target.message:
                detail += f" — {target.message}"
            if target.status.value == "error":
                st.error(detail)
            else:
                st.text(detail)


def _render_preload_result(result) -> None:
    summary = (
        f"Analysed {result.ok_count}; skipped {result.skipped_count}; "
        f"errors {result.error_count}; "
        f"{result.suggestion_count} suggestion(s); "
        f"{result.no_match_count} no match."
    )
    if result.error_count:
        st.warning(f"Voice suggestion pre-load finished with issues. {summary}")
    elif result.ok_count == 0 and result.skipped_count > 0:
        st.info(f"Nothing to analyse. {summary}")
    else:
        st.success(f"Voice suggestion pre-load complete. {summary}")

    with st.expander("Per-occurrence results", expanded=bool(result.error_count)):
        if not result.targets:
            st.caption("No occurrences processed.")
            return
        for target in result.targets:
            detail = (
                f"{target.transcript_label} / {target.local_speaker_key}: "
                f"{target.status.value}"
            )
            if target.outcome:
                detail += f" ({target.outcome})"
            if target.message:
                detail += f" — {target.message}"
            if target.status.value == "error":
                st.error(detail)
            else:
                st.text(detail)


def _render_bulk_voice_ops() -> None:
    """Library-wide enrol-all and suggestion pre-load (privacy must already be on)."""
    from transcriptx.services.speaker_profiles.bulk_voice_ops import BulkVoiceOpsService
    from transcriptx.services.speaker_profiles.voice_facade import ensure_idempotency_key

    st.subheader("Library voice batch")
    st.caption(
        "Explicit batch ops for Speaker Identification. Enrol trusted voice for "
        "active profiles first so suggestion pre-load has a reference corpus; "
        "an empty corpus still analyses but usually returns no match."
    )

    pending_enrol = st.session_state.pop(_ENROL_RESULT_KEY, None)
    if pending_enrol is not None:
        _render_enrol_all_result(pending_enrol)

    pending_preload = st.session_state.pop(_PRELOAD_RESULT_KEY, None)
    if pending_preload is not None:
        _render_preload_result(pending_preload)

    st.markdown("##### Enrol trusted voice for all profiles")
    st.caption(
        "Runs Speakers → Enrol trusted voice from confirmed links for every "
        "active persisted profile (archived/merged skipped). Uses the enrol "
        "link cap above."
    )
    if st.button(
        "Refresh enrol inventory",
        key="voice_bulk_enrol_preview_btn",
    ):
        try:
            preview = BulkVoiceOpsService().preview_enrol_all_profiles()
            st.session_state[_ENROL_PREVIEW_KEY] = preview
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    enrol_preview = st.session_state.get(_ENROL_PREVIEW_KEY)
    if enrol_preview is None:
        st.info("Refresh enrol inventory to see active profiles with confirmed links.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Active profiles", enrol_preview.profile_count)
        c2.metric("With links", enrol_preview.with_confirmed_links)
        c3.metric("Without links", enrol_preview.without_confirmed_links)
        c4.metric("Actionable", enrol_preview.actionable_count)
        with st.expander("Profile inventory", expanded=False):
            st.dataframe(
                [
                    {
                        "name": row.display_name,
                        "links": row.link_count,
                        "eligible samples": row.eligible_sample_count,
                        "status": "enrol" if row.actionable else "no links",
                        "profile_id": row.profile_id,
                    }
                    for row in enrol_preview.targets
                ],
                width="stretch",
                hide_index=True,
            )
        if enrol_preview.actionable_count == 0:
            st.info("No active profiles with confirmed links to enrol.")
        else:
            enrol_key = ensure_idempotency_key(
                st.session_state, "voice_bulk_enrol_all"
            )
            if st.button(
                "Enrol trusted voice for all profiles",
                type="primary",
                key="voice_bulk_enrol_all_btn",
                help=(
                    "Explicit bootstrap for every active profile with confirmed "
                    "links. Privacy opt-in alone does not enrol anything."
                ),
            ):
                try:
                    progress = st.progress(0.0, text="Starting…")
                    status = st.empty()

                    def _on_progress(index: int, total: int, name: str) -> None:
                        frac = index / total if total else 1.0
                        progress.progress(
                            min(frac, 1.0), text=f"{index}/{total}: {name}"
                        )
                        status.caption(f"Enrolling {name}")

                    result = BulkVoiceOpsService().enrol_all_profiles(
                        operation_idempotency_key=enrol_key,
                        progress_callback=_on_progress,
                    )
                    progress.progress(1.0, text="Done")
                    st.session_state.pop("voice_bulk_enrol_all", None)
                    st.session_state.pop(_ENROL_PREVIEW_KEY, None)
                    st.session_state[_ENROL_RESULT_KEY] = result
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    st.markdown("##### Pre-load voice suggestions")
    st.caption(
        "Analyses every non-ignored speaker occurrence across managed "
        "transcripts and writes suggestion/query caches used by Speaker "
        "Identification. Ignored and collision speakers are skipped."
    )
    if st.button(
        "Refresh suggestion inventory",
        key="voice_bulk_preload_preview_btn",
    ):
        try:
            preview = BulkVoiceOpsService().preview_preload_suggestions()
            st.session_state[_PRELOAD_PREVIEW_KEY] = preview
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    preload_preview = st.session_state.get(_PRELOAD_PREVIEW_KEY)
    if preload_preview is None:
        st.info(
            "Refresh suggestion inventory to see how many speakers will be analysed."
        )
        return

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Transcripts", preload_preview.transcript_count)
    p2.metric("Occurrences", preload_preview.occurrence_count)
    p3.metric("Skipped", preload_preview.ignored_count + preload_preview.collision_count)
    p4.metric("Actionable", preload_preview.actionable_count)
    with st.expander("Occurrence inventory", expanded=False):
        st.dataframe(
            [
                {
                    "transcript": row.transcript_label,
                    "speaker": row.local_speaker_key,
                    "status": (
                        "analyse"
                        if row.actionable
                        else ("ignored" if row.ignored else "collision")
                    ),
                }
                for row in preload_preview.targets
            ],
            width="stretch",
            hide_index=True,
        )
    if preload_preview.actionable_count == 0:
        st.info("No non-ignored speaker occurrences to analyse.")
        return

    if st.button(
        "Pre-load voice suggestions",
        type="primary",
        key="voice_bulk_preload_btn",
        help=(
            "Warm local voice suggestion caches for Speaker Identification "
            "across the managed library."
        ),
    ):
        try:
            progress = st.progress(0.0, text="Starting…")
            status = st.empty()

            def _on_progress(index: int, total: int, name: str) -> None:
                frac = index / total if total else 1.0
                progress.progress(min(frac, 1.0), text=f"{index}/{total}: {name}")
                status.caption(f"Analysing {name}")

            result = BulkVoiceOpsService().preload_suggestions(
                progress_callback=_on_progress
            )
            progress.progress(1.0, text="Done")
            st.session_state.pop(_PRELOAD_PREVIEW_KEY, None)
            st.session_state[_PRELOAD_RESULT_KEY] = result
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_speakers_panel() -> None:
    """Show speaker-profile list preferences and local voice matching controls."""
    st.subheader("Speaker profiles")
    st.checkbox(
        "Include ignored appearances in headline totals",
        value=False,
        key=INCLUDE_IGNORED_SESSION_KEY,
        help=(
            "When enabled, Speakers directory and profile headline totals include "
            "appearances flagged as ignored. Default excludes them along with "
            "needs-review, missing-source, and collision appearances."
        ),
    )
    st.checkbox(
        "Show archived profiles",
        value=False,
        key=SHOW_ARCHIVED_SESSION_KEY,
        help=(
            "When enabled, Speakers lists archived profiles and shows an "
            "Archived count card."
        ),
    )
    st.checkbox(
        "Show merged profiles",
        value=False,
        key=SHOW_MERGED_SESSION_KEY,
        help=(
            "When enabled, Speakers lists merged profiles and shows a "
            "Merged count card."
        ),
    )

    st.subheader("Local voice matching")
    try:
        from uuid import uuid4

        from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
        from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
        from transcriptx.core.speaker_profiles.voice.privacy import (
            VOICE_PRIVACY_USER_NOTICE,
            VoicePrivacyStore,
        )
        from transcriptx.core.speaker_profiles.voice.privacy_service import (
            VoicePrivacyService,
        )
        from transcriptx.core.speaker_profiles.voice.versioning import (
            FEATURE_GATE_COMPLETE,
        )
        from transcriptx.services.speaker_profiles.voice_facade import (
            ensure_idempotency_key,
        )

        root = speaker_profiles_dir()
        status = ActivationBarrier(root).status()
        if not FEATURE_GATE_COMPLETE:
            st.caption(
                "Voice matching Settings enablement is not available yet "
                f"({status.block_reason or 'feature_gate_closed'}). "
                "Consent will be recorded only in privacy.voice_settings.json "
                "once the lifecycle gate opens — there is no separate config flag."
            )
        elif status.block_reason == "privacy_settings_invalid":
            st.warning(
                status.detail
                or (
                    "privacy.voice_settings.json is incompatible with the "
                    "current schema epoch. Re-enable below to replace it."
                )
            )
            st.info(VOICE_PRIVACY_USER_NOTICE)
            enable_key = ensure_idempotency_key(
                st.session_state, "voice_privacy_enable_replace"
            )
            if st.button(
                "Replace settings and enable voice matching",
                key="voice_privacy_enable_replace",
                type="primary",
            ):
                try:
                    VoicePrivacyService().enable(
                        operation_idempotency_key=enable_key
                    )
                    st.session_state.pop("voice_privacy_enable_replace", None)
                    st.success("Voice matching enabled with current privacy settings.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            privacy = VoicePrivacyStore(root).read()
            st.info(VOICE_PRIVACY_USER_NOTICE)
            st.caption(
                "Voice matching consent is controlled solely by "
                "privacy.voice_settings.json under speaker_profiles."
            )
            st.caption(
                "Enrolled samples live on the host under "
                f"`{root / 'voice'}` (Docker: `./data` bind mount). "
                "Image rebuild / recreate keeps them; "
                "Revoke consent or Delete voice evidence removes them."
            )
            from transcriptx.core.speaker_profiles.voice.operator import (
                VoiceOperatorStore,
            )
            from transcriptx.core.speaker_profiles.voice.operator_service import (
                VoiceOperatorService,
            )
            from transcriptx.core.speaker_profiles.voice.versioning import (
                BOOTSTRAP_MAX_LINKS_MAX,
                BOOTSTRAP_MAX_LINKS_MIN,
                DEFAULT_BOOTSTRAP_MAX_LINKS,
            )

            operator = VoiceOperatorStore(root).read()
            if "voice_bootstrap_max_links" not in st.session_state:
                st.session_state["voice_bootstrap_max_links"] = (
                    operator.bootstrap_max_links
                )
            st.number_input(
                "Max confirmed links per voice enrol",
                min_value=BOOTSTRAP_MAX_LINKS_MIN,
                max_value=BOOTSTRAP_MAX_LINKS_MAX,
                step=1,
                key="voice_bootstrap_max_links",
                help=(
                    "Speakers → Enrol trusted voice walks confirmed links in "
                    f"deterministic order up to this cap (default "
                    f"{DEFAULT_BOOTSTRAP_MAX_LINKS}). Stored in "
                    "operator.voice_settings.json; survives privacy revoke. "
                    "Match-time still caps references per link separately."
                ),
            )
            save_cap_key = ensure_idempotency_key(
                st.session_state, "voice_operator_bootstrap_max_links"
            )
            if st.button(
                "Save enrol link cap",
                key="voice_operator_save_bootstrap_max_links",
            ):
                try:
                    desired = int(st.session_state["voice_bootstrap_max_links"])
                    VoiceOperatorService().update_bootstrap_max_links(
                        operation_idempotency_key=save_cap_key,
                        bootstrap_max_links=desired,
                    )
                    st.session_state.pop("voice_operator_bootstrap_max_links", None)
                    st.success(f"Enrol link cap saved ({desired}).")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if privacy.enabled and not privacy.wipe_required:
                st.success("Local voice matching is enabled.")
                _render_bulk_voice_ops()
                revoke_key = ensure_idempotency_key(
                    st.session_state, "voice_privacy_revoke"
                )
                st.checkbox(
                    "I understand revoke permanently deletes all enrolled "
                    "voice samples, embeddings, and vectors",
                    key="voice_privacy_revoke_confirm",
                )
                if st.button(
                    "Revoke voice matching consent",
                    key="voice_privacy_revoke",
                    disabled=not st.session_state.get(
                        "voice_privacy_revoke_confirm", False
                    ),
                    help=(
                        "Disables voice matching and runs a bounded wipe of "
                        "speaker_profiles/voice evidence. Does not delete "
                        "profiles or confirmed links. Docker image rebuild "
                        "does not wipe voice data — this button does."
                    ),
                ):
                    try:
                        VoicePrivacyService().revoke(
                            operation_idempotency_key=revoke_key
                        )
                        st.session_state.pop("voice_privacy_revoke", None)
                        st.session_state.pop("voice_privacy_revoke_confirm", None)
                        st.warning(
                            "Consent revoked and voice artefacts wiped. "
                            "Profiles and confirmed links were kept. "
                            "Re-enable and re-enrol to restore matching."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            elif privacy.wipe_required:
                st.warning("Voice wipe required after revocation.")
                wipe_key = ensure_idempotency_key(
                    st.session_state, "voice_privacy_wipe_resume"
                )
                if st.button("Resume voice wipe", key="voice_wipe_resume"):
                    try:
                        from transcriptx.core.speaker_profiles.voice.wipe import (
                            VoiceWipeService,
                        )

                        VoiceWipeService().wipe_until_complete(
                            base_idempotency_key=wipe_key
                        )
                        VoicePrivacyService().clear_wipe_required(
                            operation_idempotency_key=str(uuid4())
                        )
                        st.session_state.pop("voice_privacy_wipe_resume", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                st.info(
                    "Local voice matching is disabled (default). "
                    "Set TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED=1 for a "
                    "local/dev missing-file default, or enable below."
                )
                enable_key = ensure_idempotency_key(
                    st.session_state, "voice_privacy_enable"
                )
                if st.button(
                    "Enable local voice matching",
                    key="voice_privacy_enable",
                    type="primary",
                ):
                    try:
                        VoicePrivacyService().enable(
                            operation_idempotency_key=enable_key
                        )
                        st.session_state.pop("voice_privacy_enable", None)
                        st.success("Voice matching enabled.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
    except Exception:
        st.caption("Voice matching status unavailable.")
