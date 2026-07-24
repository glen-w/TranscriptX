"""Settings → Speakers: profile list toggles and local voice matching."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.speaker_profile_signals import (
    INCLUDE_IGNORED_SESSION_KEY,
    SHOW_ARCHIVED_SESSION_KEY,
    SHOW_MERGED_SESSION_KEY,
)


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
                    st.session_state.pop(
                        "voice_operator_bootstrap_max_links", None
                    )
                    st.success(f"Enrol link cap saved ({desired}).")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if privacy.enabled and not privacy.wipe_required:
                st.success("Local voice matching is enabled.")
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
                        st.session_state.pop(
                            "voice_privacy_revoke_confirm", None
                        )
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
