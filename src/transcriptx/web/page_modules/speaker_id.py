"""
Speaker Identification page — interactive speaker-by-speaker naming.

Groups segments by diarized speaker ID, shows sample lines for the active
speaker, supports audio clip playback (if audio is available), and lets the
user assign a name or mark as ignored before moving to the next speaker.

The post-picker workspace runs in ``_speaker_id_workspace_fragment``. Ordinary
actions (Save / Ignore / Prev / Next / Jump / Voice) use module-level
``on_click`` / ``on_change`` callbacks so mutations run before the natural
fragment rerun — no mid-render ``_rerun_ui``. Transcript selection and
completion may full-app rerun. Playback uses ``render_playback_panel_body``
inside the workspace (no nested fragments). Voice is a lightweight conditional
block, not a sibling/nested fragment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

import streamlit as st

from transcriptx.app.models.results import RunSummary
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
)
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.components.playback_panel import (
    clear_playback_session_keys,
    fmt_time as _fmt_time,
    render_playback_panel_body,
    resolve_playback_context,
    sanitize_lines_shown,
    sanitize_play_index,
)
from transcriptx.web.components.recent_run_row import render_recent_run_actions
from transcriptx.web.cache_helpers import (
    cached_speaker_id_segments,
    cached_transcript_paths_for_speaker_views,
    cached_transcript_summary_for_path,
    invalidate_transcript_summary_for_path,
    load_speaker_identification_index,
    load_voice_segment_payload,
    transcript_segments_signature,
    transcript_summary_signature,
)
from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.state import (
    IMPORT_LAST_TRANSCRIPT_PATH,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    WORKFLOW_NAV_TRANSCRIPT_PATH,
)
from transcriptx.web.transcript_option_format import (
    format_transcript_option_with_speaker_status,
)
from transcriptx.web.navigation import (
    make_session_path_resolver,
)
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import (
    paths_match,
    resolve_transcript_context,
)

# How many sample lines to show per speaker by default
_LINES_PER_PAGE = 10
# Non-widget persistence: sidebar can clear canonical subject_id after the page
# selectbox runs; the widget key alone is not enough if Streamlit remounts it.
_SPEAKER_ID_SELECTED_PATH = "speaker_id_selected_path"
_SPEAKER_ID_COMPLETION_APP_RERUN = "sid_completion_app_rerun"

# Legacy aliases used by older tests / call sites that expect module constants.
# Prefer the transcript-scoped helpers below for new code.
_PLAY_KEY = "speaker_id_play_seg"
_LINES_KEY = "speaker_id_lines_shown"
_SPEAKER_ID_VOICE_PENDING = "sid_voice_pending"


# ── transcript-scoped session keys ────────────────────────────────────────────


def _transcript_ns(transcript_path: str | Path) -> str:
    """Stable short namespace from resolved transcript path."""
    try:
        resolved = str(Path(transcript_path).resolve())
    except OSError:
        resolved = str(transcript_path)
    return hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:12]


def speaker_idx_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:speaker_idx"


def jump_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:jump"


def play_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:play_seg"


def lines_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:lines_shown"


def name_widget_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:name:{speaker_id}"


def link_profile_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:link:{speaker_id}"


def voice_pending_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_pending"


def voice_loaded_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_loaded"


def voice_batch_summary_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_batch_summary"


def flash_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:flash"


def widget_key(transcript_path: str | Path, suffix: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:{suffix}"


@dataclass(frozen=True)
class TranscriptProfileContext:
    """Immutable managed-transcript gate for Speaker ID UI."""

    is_managed: bool
    managed_transcript_id: str | None = None


def voice_display_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_display:{speaker_id}"


def voice_gate_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_gate"


@st.cache_data(ttl=300, show_spinner=False)
def _cached_transcript_profile_context(path_str: str) -> TranscriptProfileContext:
    """Process-scoped profile context keyed by resolved transcript path."""
    from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver

    resolver = ManagedTranscriptResolver()
    if not resolver.is_managed_path(path_str):
        return TranscriptProfileContext(is_managed=False)
    try:
        resolved = resolver.resolve_path(path_str)
        return TranscriptProfileContext(
            is_managed=True,
            managed_transcript_id=resolved.managed_transcript_id,
        )
    except Exception:
        return TranscriptProfileContext(is_managed=True, managed_transcript_id=None)


def _resolve_profile_context(transcript_path: str | Path) -> TranscriptProfileContext:
    try:
        path_str = str(Path(transcript_path).resolve())
    except OSError:
        path_str = str(transcript_path)
    return _cached_transcript_profile_context(path_str)


def _voice_display_from_result(result, *, profile_name_lookup) -> dict:
    """Build a lightweight session-safe display payload from an analyse result."""
    candidates: list[dict] = []
    for cand in getattr(result, "candidates_ui", None) or []:
        pid = cand.get("profile_id")
        live_name = profile_name_lookup(pid) if pid else None
        candidates.append(
            {
                "profile_id": pid,
                "display_name": live_name
                or cand.get("display_name")
                or pid,
                "confidence": cand.get("confidence"),
                "reference_count": cand.get("reference_count"),
            }
        )
    return {
        "outcome": getattr(result, "outcome", None),
        "detail": getattr(result, "detail", None),
        "candidates": candidates,
    }


# ── flash ─────────────────────────────────────────────────────────────────────


def _set_flash(
    transcript_path: str | Path,
    *,
    level: str,
    message: str,
) -> None:
    st.session_state[flash_key(transcript_path)] = {
        "level": level,
        "message": message,
    }


def _consume_flash(transcript_path: str | Path) -> None:
    payload = st.session_state.pop(flash_key(transcript_path), None)
    if not payload or not isinstance(payload, dict):
        return
    level = str(payload.get("level") or "info")
    message = str(payload.get("message") or "").strip()
    if not message:
        return
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "success":
        st.success(message)
    else:
        st.info(message)


# ── discovery / picker helpers ────────────────────────────────────────────────


def _transcript_paths_for_speaker_views() -> list:
    """Cached discovery; kept as a page-local alias for tests/signals."""
    return cached_transcript_paths_for_speaker_views()


def _preferred_transcript_path() -> str | None:
    """Path from identity navigation, page selection, last import, or subject."""
    for key in (
        WORKFLOW_NAV_TRANSCRIPT_PATH,
        _SPEAKER_ID_SELECTED_PATH,
        IMPORT_LAST_TRANSCRIPT_PATH,
    ):
        raw = st.session_state.get(key)
        if raw:
            try:
                if Path(raw).is_file():
                    return str(raw)
            except OSError:
                continue
    return SubjectService.current_transcript_path(st.session_state)


def _paths_with_current_subject(paths: list[Path]) -> list[Path]:
    """Ensure navigated subject is listed even if discovery briefly lags import."""
    current = _preferred_transcript_path()
    if not current:
        return list(paths)
    current_path = Path(current)
    try:
        if not current_path.is_file():
            return list(paths)
    except OSError:
        return list(paths)
    if any(paths_match(p, current_path) for p in paths):
        return list(paths)
    return sorted([*paths, current_path], key=lambda p: str(p.resolve()))


def _bind_transcript_picker_index(options: list, default_idx: int) -> None:
    """Force selectbox value when key was cleared or reset to placeholder."""
    key = "speaker_id_transcript"
    n = len(options)
    if key in st.session_state:
        current = st.session_state.get(key)
        if not isinstance(current, int) or current < 0 or current > n:
            if 0 <= default_idx <= n:
                st.session_state[key] = default_idx
            else:
                st.session_state[key] = 0
            return
        if current == 0 and default_idx > 0:
            st.session_state[key] = default_idx
        return
    if 0 <= default_idx <= n:
        st.session_state[key] = default_idx


def _cached_transcripts_for_paths(paths_key: tuple[str, ...]) -> list:
    """Deprecated heavy path — retained for tests; prefer path+label listing."""
    from transcriptx.web.cache_helpers import cached_get_transcript_summaries_for_paths

    return cached_get_transcript_summaries_for_paths(paths_key)


def _cached_fallback_transcripts() -> list:
    """Deprecated heavy fallback — retained for tests."""
    from transcriptx.web.cache_helpers import cached_list_all_transcript_summaries

    return cached_list_all_transcript_summaries()


def _light_transcript_picker_rows(paths: list[Path]) -> tuple[list[Path], list[str]]:
    """Build picker options/labels without parsing segments for every path."""
    options = list(paths)
    labels = [p.stem or str(p) for p in options]
    return options, labels


def _rerun_app() -> None:
    """Full-app rerun (completion only on ordinary action paths)."""
    st.rerun()


def _rerun_ui() -> None:
    """Legacy fragment-scope rerun helper retained for illegal-scope fallback tests.

    Ordinary Save/Ignore/Nav/Voice paths must not call this — callbacks + the
    natural fragment rerun are the single paint. Completion still uses
    ``_rerun_app_for_completion``.
    """
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        _rerun_app()


def _rerun_app_for_completion() -> None:
    """Single intentional full-app rerun: completion paint + picker label refresh."""
    st.session_state[_SPEAKER_ID_COMPLETION_APP_RERUN] = True
    _rerun_app()


def _load_cached_segments(transcript_path: str | Path) -> List[SegmentInfo]:
    """Load segments from the path+mtime_ns+size cache; fail closed on missing files."""
    try:
        path_str = str(Path(transcript_path).resolve())
    except OSError as exc:
        raise FileNotFoundError(f"Transcript unavailable: {transcript_path}") from exc
    signature = transcript_segments_signature(path_str)
    return list(cached_speaker_id_segments(path_str, signature))


# ── navigation helpers ────────────────────────────────────────────────────────


def navigate_to_speaker(
    target_idx: int,
    *,
    transcript_path: str | Path,
    speaker_count: int,
    clear_playback_if_changed: bool = True,
) -> int:
    """Canonical speaker navigation: index, lines reset, optional playback clear.

    Does **not** write the jump widget key (use ``sync_jump_widget`` from Prev/Next).
    """
    sanitized = sanitize_play_index(target_idx, speaker_count)
    if sanitized is None:
        sanitized = 0
    idx_key = speaker_idx_key(transcript_path)
    prev = sanitize_play_index(st.session_state.get(idx_key, 0), speaker_count)
    changed = prev != sanitized
    st.session_state[idx_key] = sanitized
    st.session_state[lines_key(transcript_path)] = _LINES_PER_PAGE
    if clear_playback_if_changed and changed:
        clear_playback_session_keys(play_key(transcript_path))
    return sanitized


def sync_jump_widget(
    speaker_idx: int,
    *,
    transcript_path: str | Path,
) -> None:
    """Update the jump selectbox session value to match canonical index (Prev/Next)."""
    st.session_state[jump_key(transcript_path)] = speaker_idx


def _set_active_speaker(
    target_idx: int,
    *,
    speaker_count: int,
    clear_playback_if_changed: bool = True,
    transcript_path: str | Path | None = None,
) -> int:
    """Backward-compatible wrapper: navigate + sync jump when path is known."""
    path = transcript_path or st.session_state.get(_SPEAKER_ID_SELECTED_PATH)
    if not path:
        # Legacy tests without transcript path use global keys.
        sanitized = sanitize_play_index(target_idx, speaker_count)
        if sanitized is None:
            sanitized = 0
        prev = sanitize_play_index(
            st.session_state.get("speaker_id_speaker_idx", 0), speaker_count
        )
        changed = prev != sanitized
        st.session_state["speaker_id_speaker_idx"] = sanitized
        st.session_state["sid_jump"] = sanitized
        st.session_state[_LINES_KEY] = _LINES_PER_PAGE
        if clear_playback_if_changed and changed:
            clear_playback_session_keys(_PLAY_KEY)
        return sanitized
    idx = navigate_to_speaker(
        target_idx,
        transcript_path=path,
        speaker_count=speaker_count,
        clear_playback_if_changed=clear_playback_if_changed,
    )
    sync_jump_widget(idx, transcript_path=path)
    # Mirror legacy keys for tests that still read them when path is set via selected.
    st.session_state["speaker_id_speaker_idx"] = idx
    return idx


def _speaker_id_transcript_label(t) -> str:
    """Label helper for summary objects; light pickers use path stems instead."""
    return format_transcript_option_with_speaker_status(t)


def _speaker_map_display_name(speaker_map: Dict[str, str], sid: str) -> str:
    nid = normalize_diarized_id(sid)
    if nid:
        v = speaker_map.get(nid)
        if is_effective_speaker_name(nid, v):
            return str(v).strip()
    v = speaker_map.get(sid)
    if is_effective_speaker_name(sid, v):
        return str(v).strip()
    return ""


def _is_speaker_ignored(ignored: List[str], sid: str) -> bool:
    nid = normalize_diarized_id(sid)
    if not nid and not sid:
        return False
    for ig in ignored or []:
        if ig is None or not str(ig).strip():
            continue
        raw = str(ig).strip()
        if sid == raw or (nid and nid == raw):
            return True
        if nid and normalize_diarized_id(raw) == nid:
            return True
    return False


def _group_by_diarized_id(
    segments: List[SegmentInfo],
) -> Dict[str, List[SegmentInfo]]:
    """Return ordered dict: diarized_id → list of SegmentInfo (legacy helper)."""
    from collections import defaultdict

    groups: Dict[str, List[SegmentInfo]] = defaultdict(list)
    seen_order: List[str] = []
    for seg in segments:
        did = seg.speaker_diarized_id or seg.speaker
        if did and did not in groups:
            seen_order.append(did)
        if did:
            groups[did].append(seg)
    return {k: groups[k] for k in seen_order}


def _voice_analyse_segment_dicts(segments: List[SegmentInfo]) -> list[dict]:
    """Build segment dicts for voice analyse using diarized IDs."""
    out: list[dict] = []
    for s in segments:
        did = s.speaker_diarized_id or s.speaker
        out.append(
            {
                "speaker": did,
                "speaker_diarized_id": did,
                "start": s.start,
                "end": s.end,
                "text": s.text or "",
            }
        )
    return out


def _latest_run_summary_for_transcript(transcript_path: Path) -> RunSummary | None:
    resolution = resolve_transcript_context(
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )
    subject_id = resolution.subject_id
    run_id = resolution.run_id
    if not subject_id or not run_id:
        return None
    if "/" in subject_id or "\\" in subject_id or Path(subject_id).suffix:
        return None
    run_dir = Path(OUTPUTS_DIR) / subject_id / run_id
    if not run_dir.is_dir():
        return None
    try:
        created_at = datetime.fromtimestamp(run_dir.stat().st_mtime)
    except OSError:
        created_at = datetime.now()
    return RunSummary(
        run_dir=run_dir,
        transcript_path=Path(transcript_path),
        run_id=run_id,
        created_at=created_at,
        selected_modules=[],
    )


def _render_post_speaker_id_actions(transcript_path: Path) -> None:
    """Configured action strip under Speaker ID completion."""
    run = _latest_run_summary_for_transcript(transcript_path)
    if run is not None:
        render_recent_run_actions(
            run,
            row_index=0,
            key_prefix="speaker_id_run",
            section=SectionId.SPEAKER_ID_COMPLETE,
            nav_style=NavStyle.CLICK_RERUN,
        )
        return

    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id=transcript_path.stem,
        transcript_path=transcript_path,
    )
    ctx = ActionContext(
        identity=identity,
        widget_identity=f"speaker_id_{transcript_path.stem}",
        nav_style=NavStyle.CLICK_RERUN,
        instance_prefix="speaker_id",
        rename_supported=True,
        run_completed=False,
    )
    render_configured_actions(SectionId.SPEAKER_ID_COMPLETE, ctx)


def _remaining_count(
    speaker_ids: Sequence[str],
    speaker_map: Dict[str, str],
    ignored: List[str],
) -> tuple[int, int, int]:
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = len(speaker_ids) - named - n_ignored
    return named, n_ignored, remaining


def _speaker_label(
    sid: str,
    idx: int,
    speaker_map: Dict[str, str],
    ignored: List[str],
) -> str:
    name = _speaker_map_display_name(speaker_map, sid)
    if _is_speaker_ignored(ignored, sid):
        return f"{idx + 1}. {sid} 🔇"
    if name:
        return f"{idx + 1}. {sid} → {name}"
    return f"{idx + 1}. {sid} ❓"


def _next_unnamed_idx(
    speaker_ids: List[str],
    speaker_map: Dict[str, str],
    ignored: List[str],
    current: int,
) -> int:
    """Advance to the next unnamed, non-ignored speaker after a successful mutation."""
    if 0 <= current < len(speaker_ids):
        sid = speaker_ids[current]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return current
    for i in range(current + 1, len(speaker_ids)):
        sid = speaker_ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    for i in range(0, current):
        sid = speaker_ids[i]
        if not _is_speaker_ignored(ignored, sid) and not _speaker_map_display_name(
            speaker_map, sid
        ):
            return i
    return current


def _apply_mapping_advance(
    *,
    transcript_path: str | Path,
    speaker_ids: Sequence[str],
    new_state,
    speaker_idx: int,
    summary_sig_before: tuple[int, int, int],
) -> None:
    """Invalidate summary, advance speaker; completion may full-app rerun.

    Does **not** call ``_rerun_ui`` — the natural fragment rerun paints.
    """
    invalidate_transcript_summary_for_path(
        transcript_path, signature=summary_sig_before
    )
    speaker_map = dict(new_state.speaker_map or {})
    ignored = list(new_state.ignored_speakers or [])
    next_idx = _next_unnamed_idx(list(speaker_ids), speaker_map, ignored, speaker_idx)
    idx = navigate_to_speaker(
        next_idx,
        transcript_path=transcript_path,
        speaker_count=len(speaker_ids),
    )
    sync_jump_widget(idx, transcript_path=transcript_path)
    st.session_state["speaker_id_speaker_idx"] = idx
    _, _, remaining = _remaining_count(speaker_ids, speaker_map, ignored)
    if remaining == 0 and len(speaker_ids) > 0:
        _rerun_app_for_completion()


# Backward-compatible name used by tests.
def _after_mapping_mutation(
    *,
    transcript_path: str | Path,
    speaker_ids: Sequence[str],
    new_state,
    speaker_idx: int,
    summary_sig_before: tuple[int, int, int],
) -> None:
    """Advance after mutation without a second fragment ``_rerun_ui``."""
    _apply_mapping_advance(
        transcript_path=transcript_path,
        speaker_ids=speaker_ids,
        new_state=new_state,
        speaker_idx=speaker_idx,
        summary_sig_before=summary_sig_before,
    )


def _validate_callback_identity(
    transcript_path: str,
    *,
    expected_speaker_id: str | None = None,
) -> tuple[list[str], int, str] | None:
    """Recompute index + active speaker; return None if identity is stale."""
    try:
        index = load_speaker_identification_index(transcript_path)
    except FileNotFoundError:
        _set_flash(transcript_path, level="error", message="Transcript file is missing.")
        return None
    speaker_ids = list(index.ordered_speaker_ids)
    if not speaker_ids:
        _set_flash(transcript_path, level="error", message="No speakers found.")
        return None
    idx = sanitize_play_index(
        st.session_state.get(speaker_idx_key(transcript_path), 0),
        len(speaker_ids),
    )
    if idx is None:
        idx = 0
    active_id = speaker_ids[idx]
    if expected_speaker_id is not None and active_id != expected_speaker_id:
        _set_flash(
            transcript_path,
            level="warning",
            message="Active speaker changed; action was not applied. Try again.",
        )
        return None
    # Soft-check transcript still readable (signature race handled in loaders).
    try:
        transcript_segments_signature(transcript_path)
    except FileNotFoundError:
        _set_flash(transcript_path, level="error", message="Transcript file is missing.")
        return None
    return speaker_ids, idx, active_id


# ── module-level callbacks ────────────────────────────────────────────────────


def _cb_save_name(transcript_path: str, expected_speaker_id: str) -> None:
    identity = _validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, active_id = identity
    name = str(st.session_state.get(name_widget_key(transcript_path, active_id)) or "").strip()
    if not name:
        _set_flash(transcript_path, level="warning", message="Enter a name before saving.")
        return
    link_profile = bool(
        st.session_state.get(link_profile_key(transcript_path, active_id), False)
    )
    controller = get_shared_speaker_studio_controller()
    profile_ctx = _resolve_profile_context(transcript_path)
    try:
        summary_sig = transcript_summary_signature(transcript_path)
        if link_profile and profile_ctx.is_managed:
            from transcriptx.services.speaker_profiles.create_and_name import (
                create_profile_link_and_name,
            )

            partial = create_profile_link_and_name(
                transcript_path=transcript_path,
                raw_speaker=active_id,
                display_name=name,
                controller=controller,
                create_profile=True,
                apply_sidecar_name=True,
                method="web",
            )
            consume_cache_invalidation_signal(partial.effective_signal)
            if partial.is_partial:
                _set_flash(
                    transcript_path,
                    level="warning",
                    message=(
                        "Profile link saved, but local naming failed: "
                        f"{partial.naming_error}"
                    ),
                )
            new_state = controller.get_mapping_status(transcript_path)
        else:
            new_state = controller.apply_mapping_mutation(
                transcript_path, active_id, name, method="web"
            )
        _apply_mapping_advance(
            transcript_path=transcript_path,
            speaker_ids=speaker_ids,
            new_state=new_state,
            speaker_idx=speaker_idx,
            summary_sig_before=summary_sig,
        )
    except Exception as exc:
        _set_flash(transcript_path, level="error", message=str(exc))


def _cb_ignore_toggle(transcript_path: str, expected_speaker_id: str) -> None:
    identity = _validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, active_id = identity
    controller = get_shared_speaker_studio_controller()
    try:
        summary_sig = transcript_summary_signature(transcript_path)
        map_state = controller.get_mapping_status(transcript_path)
        ignored = list(getattr(map_state, "ignored_speakers", None) or [])
        if _is_speaker_ignored(ignored, active_id):
            new_state = controller.unignore_speaker(
                transcript_path, active_id, method="web"
            )
        else:
            new_state = controller.ignore_speaker(
                transcript_path, active_id, method="web"
            )
        _apply_mapping_advance(
            transcript_path=transcript_path,
            speaker_ids=speaker_ids,
            new_state=new_state,
            speaker_idx=speaker_idx,
            summary_sig_before=summary_sig,
        )
    except Exception as exc:
        _set_flash(transcript_path, level="error", message=str(exc))


def _cb_prev(transcript_path: str, expected_speaker_id: str) -> None:
    identity = _validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, _ = identity
    if speaker_idx <= 0:
        return
    idx = navigate_to_speaker(
        speaker_idx - 1,
        transcript_path=transcript_path,
        speaker_count=len(speaker_ids),
    )
    sync_jump_widget(idx, transcript_path=transcript_path)
    st.session_state["speaker_id_speaker_idx"] = idx


def _cb_next(transcript_path: str, expected_speaker_id: str) -> None:
    identity = _validate_callback_identity(
        transcript_path, expected_speaker_id=expected_speaker_id
    )
    if identity is None:
        return
    speaker_ids, speaker_idx, _ = identity
    if speaker_idx >= len(speaker_ids) - 1:
        return
    idx = navigate_to_speaker(
        speaker_idx + 1,
        transcript_path=transcript_path,
        speaker_count=len(speaker_ids),
    )
    sync_jump_widget(idx, transcript_path=transcript_path)
    st.session_state["speaker_id_speaker_idx"] = idx


def _cb_jump_change(transcript_path: str) -> None:
    """Jump selectbox on_change: update canonical index only — do not rewrite jump key."""
    try:
        index = load_speaker_identification_index(transcript_path)
    except FileNotFoundError:
        return
    speaker_ids = list(index.ordered_speaker_ids)
    if not speaker_ids:
        return
    jump = sanitize_play_index(
        st.session_state.get(jump_key(transcript_path)),
        len(speaker_ids),
    )
    if jump is None:
        return
    navigate_to_speaker(
        jump,
        transcript_path=transcript_path,
        speaker_count=len(speaker_ids),
    )
    st.session_state["speaker_id_speaker_idx"] = jump


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
        result_key = voice_session_key(
            resolved.managed_transcript_id, lsk, "result"
        )
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
        result_key = voice_session_key(
            resolved.managed_transcript_id, lsk, "result"
        )
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
            operation_idempotency_key=ensure_idempotency_key(
                st.session_state, rej_key
            ),
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
        result_key = voice_session_key(
            resolved.managed_transcript_id, lsk, "result"
        )
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


# ── voice conditional block ───────────────────────────────────────────────────


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
                key=widget_key(path_str, f"voice_confirm_{active_id}_{pid}"),
                on_click=_cb_voice_confirm,
                args=(path_str, active_id, pid),
            )
            cols[1].button(
                "Reject suggestion",
                key=widget_key(path_str, f"voice_reject_{active_id}_{pid}"),
                on_click=_cb_voice_reject,
                args=(path_str, active_id, pid),
            )
            cols[2].button(
                "Leave unlinked",
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
            on_click=_cb_load_voice,
            args=(path_str,),
            help="Prepare local voice matching controls for this transcript.",
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
        key=widget_key(path_str, f"voice_analyse_{active_id}"),
        help="Embed this speaker and rank local profile suggestions.",
        on_click=_cb_voice_analyse_one,
        args=(path_str, active_id),
    )
    btn_all.button(
        "Analyse all speakers",
        key=widget_key(path_str, "voice_analyse_all"),
        help=(
            "Run voice matching for every non-ignored speaker so "
            "suggestions are ready as you step through the list."
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
        result_key = voice_session_key(
            resolved.managed_transcript_id, lsk, "result"
        )

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
                targets = [
                    sid
                    for sid in speaker_ids
                    if not _is_speaker_ignored(ignored, sid)
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


# ── workspace fragment ────────────────────────────────────────────────────────


@st.fragment
def _speaker_id_workspace_fragment(
    transcript_path: str,
    controller: SpeakerStudioController,
) -> None:
    """Post-picker workspace: reload map every run; index from cache."""
    _consume_flash(transcript_path)

    try:
        index = load_speaker_identification_index(transcript_path)
        map_state = controller.get_mapping_status(transcript_path)
    except FileNotFoundError as exc:
        st.error(f"Transcript file is missing or unreadable: {exc}")
        return
    except Exception as exc:
        st.error(
            f"Speaker mapping file is corrupt for this transcript: {exc}. "
            "Please re-identify speakers or delete the sidecar."
        )
        return

    speaker_ids = list(index.ordered_speaker_ids)
    total_speakers = len(speaker_ids)
    if total_speakers == 0:
        st.info("No speaker IDs found in this transcript.")
        return

    speaker_map: Dict[str, str] = map_state.speaker_map or {}
    ignored: List[str] = getattr(map_state, "ignored_speakers", None) or []
    named, n_ignored, remaining = _remaining_count(speaker_ids, speaker_map, ignored)
    playback_ctx = resolve_playback_context(controller, transcript_path)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Speakers", total_speakers)
    col_b.metric("Named", named)
    col_c.metric("Ignored", n_ignored)
    col_d.metric("Remaining", remaining)

    if remaining == 0 and total_speakers > 0:
        st.success("All speakers identified!")
        _render_post_speaker_id_actions(Path(transcript_path))

    st.divider()

    idx_key = speaker_idx_key(transcript_path)
    j_key = jump_key(transcript_path)
    raw_speaker_idx = st.session_state.get(idx_key, 0)
    speaker_idx = sanitize_play_index(raw_speaker_idx, total_speakers)
    if speaker_idx is None:
        speaker_idx = navigate_to_speaker(
            0, transcript_path=transcript_path, speaker_count=total_speakers
        )
        sync_jump_widget(speaker_idx, transcript_path=transcript_path)
    else:
        st.session_state[idx_key] = speaker_idx
        if j_key not in st.session_state:
            st.session_state[j_key] = speaker_idx
    st.session_state["speaker_id_speaker_idx"] = speaker_idx

    active_id = speaker_ids[speaker_idx]
    active_segs = list(index.segments_by_speaker[active_id])
    current_name = _speaker_map_display_name(speaker_map, active_id)
    is_ignored = _is_speaker_ignored(ignored, active_id)
    total_dur = (
        index.durations[speaker_idx]
        if speaker_idx < len(index.durations)
        else sum(max(0.0, s.end - s.start) for s in active_segs)
    )

    status_badge = (
        "🔇 ignored"
        if is_ignored
        else (f"✅ **{current_name}**" if current_name.strip() else "❓ unnamed")
    )
    st.subheader(
        f"Speaker {speaker_idx + 1} / {total_speakers} — `{active_id}` {status_badge}"
    )
    l_key = lines_key(transcript_path)
    lines_shown = sanitize_lines_shown(
        st.session_state.get(l_key, _LINES_PER_PAGE),
        length=len(active_segs),
        default=_LINES_PER_PAGE,
    )
    st.session_state[l_key] = lines_shown
    st.caption(
        f"{len(active_segs)} segments · {_fmt_time(total_dur)} total · "
        f"showing {min(lines_shown, len(active_segs))} of {len(active_segs)} lines"
    )

    p_key = play_key(transcript_path)
    render_playback_panel_body(
        controller=controller,
        transcript_path=str(transcript_path),
        audio_path=playback_ctx.audio_path,
        all_segs=active_segs,
        active_id=active_id,
        play_key=p_key,
        lines_key=l_key,
        max_lines=_LINES_PER_PAGE,
        autoplay=True,
        include_segment_rows=True,
        playback_context=playback_ctx,
    )

    st.divider()

    profile_ctx = _resolve_profile_context(transcript_path)
    is_managed_for_profiles = profile_ctx.is_managed

    if is_managed_for_profiles and not is_ignored:
        _render_voice_suggestions(
            transcript_path=transcript_path,
            speaker_ids=speaker_ids,
            ignored=ignored,
            active_id=active_id,
            profile_ctx=profile_ctx,
        )

    col_name, col_save, col_ignore = st.columns([3, 1, 1])
    with col_name:
        st.text_input(
            "Assign name",
            value=current_name,
            key=name_widget_key(transcript_path, active_id),
            placeholder="Type speaker name…",
            label_visibility="collapsed",
        )
    if is_managed_for_profiles:
        st.checkbox(
            "Also link to longitudinal speaker profile",
            value=True,
            key=link_profile_key(transcript_path, active_id),
            help=(
                "Creates a durable cross-transcript profile link for this managed "
                "library speaker. Ad-hoc / run-output JSON supports local naming only."
            ),
        )
    else:
        st.caption(
            "Longitudinal profile linking is available for managed library "
            "transcripts only. Local naming still works here."
        )
    with col_save:
        st.button(
            "Save name",
            key=widget_key(transcript_path, "save"),
            type="primary",
            width="stretch",
            on_click=_cb_save_name,
            args=(str(transcript_path), active_id),
        )
    with col_ignore:
        ignore_label = "Unignore" if is_ignored else "Ignore"
        st.button(
            ignore_label,
            key=widget_key(transcript_path, "ignore"),
            width="stretch",
            on_click=_cb_ignore_toggle,
            args=(str(transcript_path), active_id),
        )

    st.divider()
    col_prev, col_jump, col_next = st.columns([1, 3, 1])
    with col_prev:
        st.button(
            "← Prev",
            key=widget_key(transcript_path, "prev"),
            disabled=(speaker_idx == 0),
            width="stretch",
            on_click=_cb_prev,
            args=(str(transcript_path), active_id),
        )
    with col_next:
        st.button(
            "Next →",
            key=widget_key(transcript_path, "next"),
            disabled=(speaker_idx >= total_speakers - 1),
            width="stretch",
            on_click=_cb_next,
            args=(str(transcript_path), active_id),
        )
    with col_jump:
        jump_labels = [
            _speaker_label(sid, i, speaker_map, ignored)
            for i, sid in enumerate(speaker_ids)
        ]
        st.selectbox(
            "Jump to speaker",
            range(total_speakers),
            format_func=lambda i: jump_labels[i],
            key=j_key,
            label_visibility="collapsed",
            on_change=_cb_jump_change,
            args=(str(transcript_path),),
        )


# ── main render ──────────────────────────────────────────────────────────────


def render_speaker_id_page() -> None:
    """Render the speaker-by-speaker identification page."""
    st.session_state.pop(_SPEAKER_ID_COMPLETION_APP_RERUN, None)

    st.markdown(
        '<div class="main-header">Speaker Identification</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Work through each speaker one at a time: review their lines, "
        "play a clip, then assign a name or mark as ignored."
    )

    controller = get_shared_speaker_studio_controller()
    paths = _paths_with_current_subject(_transcript_paths_for_speaker_views())
    if not paths:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    options, labels = _light_transcript_picker_rows(paths)
    n = len(options)
    preferred = _preferred_transcript_path()
    default_idx = 0
    if preferred:
        for i, opt in enumerate(options):
            if paths_match(opt, preferred):
                default_idx = i + 1
                break
    if default_idx == 0:
        default_idx = SubjectService.index_in_path_options(st.session_state, options)
    _bind_transcript_picker_index(options, default_idx)
    st.session_state.pop(WORKFLOW_NAV_TRANSCRIPT_PATH, None)

    idx = st.selectbox(
        "Transcript",
        range(n + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if i == 0 else labels[i - 1]
        ),
        key="speaker_id_transcript",
    )
    if idx == 0:
        st.session_state.pop(_SPEAKER_ID_SELECTED_PATH, None)
        return
    transcript_path = options[idx - 1]
    st.session_state[_SPEAKER_ID_SELECTED_PATH] = str(transcript_path)
    SubjectService.set_transcript_context_from_path(
        st.session_state,
        transcript_path,
        session_resolver=make_session_path_resolver(),
    )
    try:
        summary = cached_transcript_summary_for_path(
            str(transcript_path),
            transcript_summary_signature(transcript_path),
        )
    except Exception:
        summary = None
    if summary is not None:
        st.caption(format_transcript_option_with_speaker_status(summary))

    prev_key = "speaker_id_prev_transcript"
    path_str = str(transcript_path)
    if st.session_state.get(prev_key) != path_str:
        st.session_state[prev_key] = path_str
        st.session_state[speaker_idx_key(path_str)] = 0
        st.session_state[lines_key(path_str)] = _LINES_PER_PAGE
        clear_playback_session_keys(play_key(path_str))
        st.session_state[jump_key(path_str)] = 0
        st.session_state["speaker_id_speaker_idx"] = 0

    _speaker_id_workspace_fragment(path_str, controller)
