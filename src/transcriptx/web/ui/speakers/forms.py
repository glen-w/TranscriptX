"""Speakers appearances table, edit/link forms, and lifecycle."""

from __future__ import annotations

from math import floor
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.speaker_profiles.accents import SPEAKER_ACCENTS
from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    ProfileListItem,
)
from transcriptx.core.speaker_profiles.discovery import (
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.errors import StaleUpdateError
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
)
from transcriptx.core.speaker_profiles.store_io import (
    profile_content_sha256,
    read_live_link,
)
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    normalize_diarized_id,
)
from transcriptx.web.navigation import (
    navigate_to_transcript_from_path,
)
from transcriptx.web.speaker_profile_signals import (
    consume_cache_invalidation_signal,
)


from transcriptx.web.ui.speakers.support import (
    _SELECTED_KEY,
    _appearance_samples,
    _clear_idempotency,
    _idempotency_key,
    _rerun_ui,
    _service,
    _surname_sort_key,
)


def _open_transcript(snap: AggregationSnapshot, row: AppearanceRow) -> None:
    path = None
    bundle = snap.bundles.get(row.managed_transcript_id)
    if bundle is not None and bundle.resolved is not None:
        path = bundle.resolved.transcript_path
    elif row.current_relpath:
        path = PATHS.transcripts_dir / row.current_relpath
    elif row.observed_transcript_relpath:
        path = PATHS.transcripts_dir / row.observed_transcript_relpath
    if path is None:
        st.error("Could not resolve transcript path for this appearance.")
        return
    # Transcript requires subject + run_id; path-only navigation silently
    # falls back to Home via the page access gate.
    if not navigate_to_transcript_from_path(path):
        st.error(
            "Could not open transcript: no analysis run is linked for this "
            "appearance. Open it from Library or run analysis first."
        )


@st.fragment
def _render_appearances_table(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    appearances: tuple[AppearanceRow, ...],
    links_by_id: Mapping[str, Any],
    profile_blocked: bool,
) -> None:
    with st.expander("Appearances", expanded=True):
        if not appearances:
            st.info("No linked appearances.")
            return

        svc = _service()
        for row in appearances:
            link_blocked = row.link_file_key in snap.blocked_link_keys
            mutate_disabled = profile_blocked or link_blocked
            with st.container(border=True):
                date_label = (
                    row.appearance_date.isoformat()
                    if row.appearance_date is not None
                    else "Unknown date"
                )
                transcript_label = (
                    row.current_relpath or row.observed_transcript_relpath
                )
                share = (
                    f"{floor(row.speaking_share * 100)}%"
                    if row.speaking_share is not None
                    else "—"
                )
                st.markdown(
                    f"**{date_label}** · `{transcript_label}` · "
                    f"{row.local_speaker_key} · {row.flag} · "
                    f"{row.metrics.words:,} words · {row.metrics.turns:,} turns · "
                    f"share {share}"
                )
                samples = _appearance_samples(snap, row)
                if samples:
                    for line in samples:
                        st.caption(f"“{line}”")
                cols = st.columns([1, 1, 1, 2])
                with cols[0]:
                    if st.button(
                        "Open transcript",
                        key=f"speakers_open_tx_{row.link_id}",
                        icon=ic.ARTICLE,
                    ):
                        _open_transcript(snap, row)

                confirm_unlink = f"speakers_confirm_unlink_{row.link_id}"
                with cols[1]:
                    if mutate_disabled:
                        st.caption("Unlink blocked")
                    elif st.session_state.get(confirm_unlink):
                        st.caption("Confirm unlink?")
                        u1, u2 = st.columns(2)
                        with u1:
                            if st.button(
                                "Confirm",
                                key=f"speakers_unlink_yes_{row.link_id}",
                                icon=ic.CONFIRM,
                                type="primary",
                            ):
                                payload = {
                                    "managed_transcript_id": row.managed_transcript_id,
                                    "local_speaker_key": row.local_speaker_key,
                                    "expected_link_id": row.link_id,
                                }
                                try:
                                    result = svc.unlink(
                                        operation_idempotency_key=_idempotency_key(
                                            f"unlink_{row.link_id}", payload
                                        ),
                                        managed_transcript_id=row.managed_transcript_id,
                                        local_speaker_key=row.local_speaker_key,
                                        expected_link_id=row.link_id,
                                    )
                                    consume_cache_invalidation_signal(
                                        result.cache_signal
                                    )
                                    _clear_idempotency(f"unlink_{row.link_id}")
                                    st.session_state.pop(confirm_unlink, None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))
                        with u2:
                            if st.button(
                                "Cancel",
                                key=f"speakers_unlink_no_{row.link_id}",
                                icon=ic.CANCEL,
                            ):
                                _clear_idempotency(f"unlink_{row.link_id}")
                                st.session_state.pop(confirm_unlink, None)
                                _rerun_ui()
                    elif st.button(
                        "Unlink",
                        key=f"speakers_unlink_{row.link_id}",
                        icon=ic.UNLINK,
                        disabled=mutate_disabled,
                    ):
                        st.session_state[confirm_unlink] = True
                        _rerun_ui()

                with cols[2]:
                    if row.flag != "needs_review":
                        st.caption("")
                    elif mutate_disabled:
                        st.caption("Accept blocked")
                    else:
                        link = links_by_id.get(row.link_id)
                        expected_fp = (
                            link.occurrence_fingerprint if link is not None else None
                        )
                        confirm_fp = f"speakers_confirm_fp_{row.link_id}"
                        if st.session_state.get(confirm_fp):
                            st.caption("Accept fingerprint?")
                            f1, f2 = st.columns(2)
                            with f1:
                                if st.button(
                                    "Confirm",
                                    key=f"speakers_fp_yes_{row.link_id}",
                                    icon=ic.CONFIRM,
                                    type="primary",
                                ):
                                    payload = {
                                        "managed_transcript_id": row.managed_transcript_id,
                                        "local_speaker_key": row.local_speaker_key,
                                        "expected_link_id": row.link_id,
                                        "expected_fingerprint": expected_fp,
                                    }
                                    try:
                                        result = svc.supersede_link_fingerprint(
                                            operation_idempotency_key=_idempotency_key(
                                                f"fp_{row.link_id}", payload
                                            ),
                                            managed_transcript_id=row.managed_transcript_id,
                                            local_speaker_key=row.local_speaker_key,
                                            expected_link_id=row.link_id,
                                            expected_fingerprint=expected_fp,
                                        )
                                        consume_cache_invalidation_signal(
                                            result.cache_signal
                                        )
                                        _clear_idempotency(f"fp_{row.link_id}")
                                        st.session_state.pop(confirm_fp, None)
                                        st.rerun()
                                    except Exception as exc:
                                        st.error(str(exc))
                            with f2:
                                if st.button(
                                    "Cancel",
                                    key=f"speakers_fp_no_{row.link_id}",
                                    icon=ic.CANCEL,
                                ):
                                    _clear_idempotency(f"fp_{row.link_id}")
                                    st.session_state.pop(confirm_fp, None)
                                    _rerun_ui()
                        elif st.button(
                            "Accept fingerprint",
                            key=f"speakers_fp_{row.link_id}",
                            icon=ic.CHECK,
                            disabled=mutate_disabled or expected_fp is None,
                        ):
                            st.session_state[confirm_fp] = True
                            _rerun_ui()


@st.fragment
def _render_edit_form(profile: SpeakerProfileV1, *, root) -> None:
    with st.expander("Edit profile", expanded=True):
        form_prefix = f"speakers_edit_{profile.profile_id}"
        display_name = st.text_input(
            "Display name",
            value=profile.display_name,
            key=f"{form_prefix}_display_name",
        )
        aliases_text = st.text_area(
            "Aliases (one per line)",
            value="\n".join(profile.aliases),
            key=f"{form_prefix}_aliases",
        )
        notes = st.text_area(
            "Notes",
            value=profile.notes or "",
            key=f"{form_prefix}_notes",
        )
        clear_notes = st.checkbox(
            "Clear notes",
            value=False,
            key=f"{form_prefix}_clear_notes",
        )

        clear_accent = st.checkbox(
            "Auto from name (clear stored accent)",
            value=False,
            key=f"{form_prefix}_clear_accent",
            help=widget_help(
                "Clears accent_color so display falls back to the name-hash palette."
            ),
        )
        default_accent = profile.accent_color or SPEAKER_ACCENTS[0]
        chosen_accent: str | None = None
        with st.popover("Choose colour"):
            chosen_accent = st.color_picker(
                "Accent colour",
                value=(
                    default_accent
                    if str(default_accent).startswith("#")
                    else SPEAKER_ACCENTS[0]
                ),
                key=f"{form_prefix}_color_picker",
                disabled=clear_accent,
            )
            st.caption("Quick palette")
            chip_cols = st.columns(len(SPEAKER_ACCENTS))
            for idx, accent in enumerate(SPEAKER_ACCENTS):
                with chip_cols[idx]:
                    if st.button(
                        accent,
                        key=f"{form_prefix}_chip_{accent}",
                        help=widget_help(accent),
                        disabled=clear_accent,
                    ):
                        st.session_state[f"{form_prefix}_color_picker"] = accent
                        _rerun_ui()

        st.markdown("##### Photo")
        upload = st.file_uploader(
            "Upload photo (JPEG/PNG/WebP, max 2 MB)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"{form_prefix}_avatar_upload",
        )
        clear_avatar = st.checkbox(
            "Remove photo",
            value=False,
            key=f"{form_prefix}_clear_avatar",
            help=widget_help(
                "Clears the stored avatar; chip falls back to initials + accent."
            ),
        )
        if st.button(
            "Save photo changes",
            key=f"{form_prefix}_avatar_save",
            icon=ic.PHOTO,
            disabled=upload is None and not clear_avatar,
        ):
            try:
                sha_avatar = profile_content_sha256(profile.profile_id, root=root)
                if not sha_avatar:
                    raise RuntimeError("Could not read profile content hash")
                if clear_avatar:
                    result = _service().clear_avatar(
                        operation_idempotency_key=_idempotency_key(
                            f"clear_avatar_{profile.profile_id}",
                            {"profile_id": profile.profile_id, "sha": sha_avatar},
                        ),
                        profile_id=profile.profile_id,
                        expected_content_sha256=sha_avatar,
                    )
                else:
                    assert upload is not None
                    result = _service().set_avatar(
                        operation_idempotency_key=_idempotency_key(
                            f"set_avatar_{profile.profile_id}",
                            {
                                "profile_id": profile.profile_id,
                                "sha": sha_avatar,
                                "name": upload.name,
                                "size": upload.size,
                            },
                        ),
                        profile_id=profile.profile_id,
                        expected_content_sha256=sha_avatar,
                        image_bytes=upload.getvalue(),
                    )
                consume_cache_invalidation_signal(result.cache_signal)
                _clear_idempotency(f"set_avatar_{profile.profile_id}")
                _clear_idempotency(f"clear_avatar_{profile.profile_id}")
                st.success("Photo updated.")
                st.rerun()
            except StaleUpdateError as exc:
                st.error(f"Stale update — refresh and try again. {exc}")
            except Exception as exc:
                st.error(str(exc))

        sha = profile_content_sha256(profile.profile_id, root=root)
        if not sha:
            st.error("Could not read profile content hash; edit disabled.")
            return

        aliases = [line.strip() for line in aliases_text.splitlines() if line.strip()]
        picker_value = st.session_state.get(
            f"{form_prefix}_color_picker", chosen_accent
        )
        payload = {
            "profile_id": profile.profile_id,
            "expected_content_sha256": sha,
            "display_name": display_name,
            "aliases": aliases,
            "notes": None if clear_notes else notes,
            "clear_notes": clear_notes,
            "accent_color": None if clear_accent else picker_value,
            "clear_accent": clear_accent,
        }

        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "Save changes",
                key=f"{form_prefix}_save",
                type="primary",
                icon=ic.SAVE,
            ):
                try:
                    result = _service().update_profile(
                        operation_idempotency_key=_idempotency_key(
                            f"update_{profile.profile_id}", payload
                        ),
                        profile_id=profile.profile_id,
                        expected_content_sha256=sha,
                        display_name=display_name,
                        aliases=aliases,
                        notes=None if clear_notes else (notes or None),
                        clear_notes=clear_notes,
                        accent_color=None if clear_accent else picker_value,
                        clear_accent=clear_accent,
                    )
                    consume_cache_invalidation_signal(result.cache_signal)
                    _clear_idempotency(f"update_{profile.profile_id}")
                    st.success("Profile updated.")
                    st.rerun()
                except StaleUpdateError as exc:
                    st.error(f"Stale update — refresh and try again. {exc}")
                except Exception as exc:
                    st.error(str(exc))
        with c2:
            if st.button("Cancel edit", key=f"{form_prefix}_cancel", icon=ic.CANCEL):
                _clear_idempotency(f"update_{profile.profile_id}")
                for suffix in (
                    "display_name",
                    "aliases",
                    "notes",
                    "clear_notes",
                    "clear_accent",
                    "color_picker",
                ):
                    st.session_state.pop(f"{form_prefix}_{suffix}", None)
                _rerun_ui()


@st.fragment
def _render_link_another(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
) -> None:
    with st.expander("Link another occurrence", expanded=False):
        if profile.profile_id in snap.blocked_profile_ids:
            st.caption("Linking disabled while this profile is blocked.")
            return

        resolver = ManagedTranscriptResolver()
        try:
            from transcriptx.io.import_metadata.persist import is_library_archived

            admitted = [
                row
                for row in resolver.list_admitted()
                if not is_library_archived(row.transcript_path)
            ]
        except Exception as exc:
            st.error(f"Could not list managed transcripts: {exc}")
            return
        if not admitted:
            st.caption("No admitted managed transcripts.")
            return

        labels = {
            r.managed_transcript_id: (
                Path(r.current_relpath).stem
                if getattr(r, "current_relpath", None)
                else r.managed_transcript_id
            )
            for r in admitted
        }
        options = [r.managed_transcript_id for r in admitted]
        chosen_tid = st.selectbox(
            "Managed transcript",
            options=[""] + options,
            format_func=lambda tid: (
                "— Select a transcript —" if tid == "" else labels.get(tid, tid)
            ),
            key=f"speakers_link_tid_{profile.profile_id}",
        )
        if not chosen_tid:
            return

        resolved = next(
            (r for r in admitted if r.managed_transcript_id == chosen_tid), None
        )
        if resolved is None:
            st.error("Selected transcript is no longer admitted.")
            return

        try:
            occurrences = discover_occurrences_for_resolved(resolved)
        except Exception as exc:
            st.error(f"Occurrence discovery failed: {exc}")
            return
        if not occurrences:
            st.info("No speaker occurrences in this transcript.")
            return

        map_state = None
        try:
            map_state = SpeakerMapResolver().load_mapping(str(resolved.transcript_path))
        except Exception:
            map_state = None
        occ_labels = {}
        bundle = snap.bundles.get(chosen_tid)
        for o in occurrences:
            mapped = ""
            if map_state is not None:
                mapped = str(
                    (map_state.speaker_map or {}).get(o.local_speaker_key) or ""
                )
            label = mapped or o.local_speaker_key
            extra = f"{o.segment_count} lines"
            if o.collision:
                extra += " · collision"
            sample = ""
            if bundle is not None:
                for segment in bundle.segments:
                    key = normalize_diarized_id(segment.get("speaker"))
                    if key != o.local_speaker_key:
                        continue
                    sample = str(segment.get("text") or "").strip()
                    if sample:
                        break
            if sample:
                snippet = sample if len(sample) <= 72 else sample[:69] + "…"
                occ_labels[o.local_speaker_key] = f"{label} — {snippet} ({extra})"
            else:
                occ_labels[o.local_speaker_key] = f"{label} ({extra})"
        chosen_key = st.selectbox(
            "Speaker in this transcript",
            options=[""] + [o.local_speaker_key for o in occurrences],
            format_func=lambda key: (
                "— Select occurrence —" if key == "" else occ_labels.get(key, key)
            ),
            key=f"speakers_link_key_{profile.profile_id}",
        )
        if not chosen_key:
            return

        existing = read_live_link(
            next(
                o.link_file_key
                for o in occurrences
                if o.local_speaker_key == chosen_key
            ),
            root=snap.root,
        )
        svc = _service()
        if existing is None:
            if st.button(
                "Link to this profile",
                key=f"speakers_link_existing_{profile.profile_id}",
                icon=ic.LINK,
                type="primary",
            ):
                payload = {
                    "managed_transcript_id": chosen_tid,
                    "local_speaker_key": chosen_key,
                    "profile_id": profile.profile_id,
                }
                try:
                    result = svc.link_existing_profile(
                        operation_idempotency_key=_idempotency_key(
                            f"link_{profile.profile_id}", payload
                        ),
                        managed_transcript_id=chosen_tid,
                        local_speaker_key=chosen_key,
                        profile_id=profile.profile_id,
                    )
                    consume_cache_invalidation_signal(result.cache_signal)
                    _clear_idempotency(f"link_{profile.profile_id}")
                    st.success("Occurrence linked.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            return

        if existing.profile_id == profile.profile_id:
            st.info("This occurrence is already linked to this profile.")
            return

        owner_name = next(
            (
                p.display_name
                for p in snap.profiles
                if p.profile_id == existing.profile_id
            ),
            existing.profile_id,
        )
        st.warning(
            f"Occurrence is linked to **{owner_name}** (`{existing.profile_id}`). "
            "Relink to move it to this profile."
        )
        confirm_key = f"speakers_confirm_relink_{profile.profile_id}_{chosen_key}"
        if st.session_state.get(confirm_key):
            r1, r2 = st.columns(2)
            with r1:
                if st.button(
                    "Confirm relink",
                    key=f"speakers_relink_yes_{profile.profile_id}",
                    icon=ic.CONFIRM,
                    type="primary",
                ):
                    payload = {
                        "managed_transcript_id": chosen_tid,
                        "local_speaker_key": chosen_key,
                        "profile_id": profile.profile_id,
                        "expected_owner_profile_id": existing.profile_id,
                        "expected_link_id": existing.link_id,
                    }
                    try:
                        result = svc.relink(
                            operation_idempotency_key=_idempotency_key(
                                f"relink_{profile.profile_id}", payload
                            ),
                            managed_transcript_id=chosen_tid,
                            local_speaker_key=chosen_key,
                            profile_id=profile.profile_id,
                            expected_link_id=existing.link_id,
                            expected_owner_profile_id=existing.profile_id,
                        )
                        consume_cache_invalidation_signal(result.cache_signal)
                        _clear_idempotency(f"relink_{profile.profile_id}")
                        st.session_state.pop(confirm_key, None)
                        st.success("Occurrence relinked.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with r2:
                if st.button(
                    "Cancel",
                    key=f"speakers_relink_no_{profile.profile_id}",
                    icon=ic.CANCEL,
                ):
                    _clear_idempotency(f"relink_{profile.profile_id}")
                    st.session_state.pop(confirm_key, None)
                    _rerun_ui()
        elif st.button(
            "Relink to this profile",
            key=f"speakers_relink_{profile.profile_id}",
            icon=ic.LINK,
        ):
            st.session_state[confirm_key] = True
            _rerun_ui()


@st.fragment
def _render_lifecycle(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    directory_items: list[ProfileListItem],
    profile_blocked: bool,
) -> None:
    with st.expander("Lifecycle", expanded=False):
        sha = profile_content_sha256(profile.profile_id, root=snap.root)
        if not sha:
            st.error("Could not read profile content hash; lifecycle disabled.")
            return
        if profile_blocked:
            st.caption("Lifecycle actions disabled while this profile is blocked.")
            return

        svc = _service()
        c1, c2, c3 = st.columns(3)

        with c1:
            if profile.status == "active":
                if st.button(
                    "Archive profile",
                    key=f"speakers_archive_{profile.profile_id}",
                    icon=ic.ARCHIVE,
                ):
                    payload = {
                        "profile_id": profile.profile_id,
                        "expected_content_sha256": sha,
                    }
                    try:
                        result = svc.archive_profile(
                            operation_idempotency_key=_idempotency_key(
                                f"archive_{profile.profile_id}", payload
                            ),
                            profile_id=profile.profile_id,
                            expected_content_sha256=sha,
                        )
                        consume_cache_invalidation_signal(result.cache_signal)
                        _clear_idempotency(f"archive_{profile.profile_id}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            elif profile.status == "archived":
                if st.button(
                    "Unarchive profile",
                    key=f"speakers_unarchive_{profile.profile_id}",
                    icon=ic.UNARCHIVE,
                ):
                    payload = {
                        "profile_id": profile.profile_id,
                        "expected_content_sha256": sha,
                    }
                    try:
                        result = svc.unarchive_profile(
                            operation_idempotency_key=_idempotency_key(
                                f"unarchive_{profile.profile_id}", payload
                            ),
                            profile_id=profile.profile_id,
                            expected_content_sha256=sha,
                        )
                        consume_cache_invalidation_signal(result.cache_signal)
                        _clear_idempotency(f"unarchive_{profile.profile_id}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

        with c2:
            active_others = sorted(
                (
                    i
                    for i in directory_items
                    if i.status == "active" and i.profile_id != profile.profile_id
                ),
                key=_surname_sort_key,
            )
            if profile.status == "active" and active_others:
                target = st.selectbox(
                    "Merge into",
                    options=[i.profile_id for i in active_others],
                    format_func=lambda pid: next(
                        (i.display_name for i in active_others if i.profile_id == pid),
                        pid,
                    ),
                    key=f"speakers_merge_target_{profile.profile_id}",
                )
                confirm_merge = f"speakers_confirm_merge_{profile.profile_id}"
                if st.session_state.get(confirm_merge):
                    st.caption(f"Merge into `{target}`?")
                    m1, m2 = st.columns(2)
                    with m1:
                        if st.button(
                            "Confirm merge",
                            key=f"speakers_merge_yes_{profile.profile_id}",
                            icon=ic.CONFIRM,
                            type="primary",
                        ):
                            payload = {
                                "source_profile_id": profile.profile_id,
                                "target_profile_id": target,
                                "expected_source_sha256": sha,
                            }
                            try:
                                result = svc.merge_profiles(
                                    operation_idempotency_key=_idempotency_key(
                                        f"merge_{profile.profile_id}", payload
                                    ),
                                    source_profile_id=profile.profile_id,
                                    target_profile_id=target,
                                    expected_source_sha256=sha,
                                )
                                consume_cache_invalidation_signal(result.cache_signal)
                                _clear_idempotency(f"merge_{profile.profile_id}")
                                st.session_state.pop(confirm_merge, None)
                                st.session_state[_SELECTED_KEY] = target
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                    with m2:
                        if st.button(
                            "Cancel",
                            key=f"speakers_merge_no_{profile.profile_id}",
                            icon=ic.CANCEL,
                        ):
                            _clear_idempotency(f"merge_{profile.profile_id}")
                            st.session_state.pop(confirm_merge, None)
                            _rerun_ui()
                elif st.button(
                    "Merge into selected",
                    key=f"speakers_merge_{profile.profile_id}",
                    icon=ic.MERGE,
                ):
                    st.session_state[confirm_merge] = True
                    _rerun_ui()

        with c3:
            st.caption(f"profile_id `{profile.profile_id}`")
