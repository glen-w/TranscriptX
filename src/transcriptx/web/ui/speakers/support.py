"""Speakers directory shared helpers and snapshot cache."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    ProfileAggregate,
    ProfileListItem,
)
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.layout import (
    links_dir,
    profiles_dir,
)
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
    build_aggregation_snapshot,
)
from transcriptx.core.speaker_profiles.time_series import (
    DirectoryChartSeries,
)
from transcriptx.web.components.info_tooltip import (
    build_info_tooltip_html,
    build_section_heading_with_info_html,
)
from transcriptx.core.utils.speaker import parse_speaker_name
from transcriptx.io.speaker_map_resolver import (
    normalize_diarized_id,
)
from transcriptx.web.speaker_profile_signals import (
    consume_cache_invalidation_signal,
)

_METHODOLOGY_CAPTIONS: dict[str, str] = {
    "share.duration_only": "Speaking share uses duration only (never turn share).",
    "wpm.weighted_period": "Speaking rate is words ÷ speaking minutes (weighted across sessions).",
    "turn_length.timing_valid_only": "Turn length uses timing-valid turns only (includes zero-duration).",
    "partial.available_while_reporting_missing": "Partial periods sum available timing and note missing evidence.",
    "partners.co_appearance_only": "Partners are co-appearances in shared sessions, not interaction proof.",
    "interactions.from_run_summary": (
        "Interaction and equity metrics come from the newest interactions run "
        "per linked appearance (speaker_summary), not from co-appearance alone."
    ),
    "sentiment.from_run_rows": (
        "Sentiment means come from the newest sentiment run per appearance "
        "(segment rows when available; summary fallback for compound)."
    ),
    "pack.phase16": "Trends are derived from confirmed profile links; not persisted as canonical data.",
    "grain.appearance_date": "Grouped by appearance date.",
    "grain.month": "Grouped by calendar month (YYYY-MM).",
    "grain.quarter": "Grouped by calendar quarter (YYYY-Qn).",
}

_EVIDENCE_CAPTIONS: dict[str, str] = {
    "no_timing_valid_turns": "No timing-valid turns in this period.",
    "denom_unavailable": "Speaking-share denominator unavailable.",
    "missing_timing:all": "No valid timing evidence in this period.",
}


def _evidence_caption(note: str | None) -> str:
    if not note:
        return ""
    if note in _EVIDENCE_CAPTIONS:
        return _EVIDENCE_CAPTIONS[note]
    if note.startswith("missing_timing:"):
        return f"Missing timing for {note.split(':', 1)[1]} sessions."
    if note.startswith("non_finite_metric:"):
        return f"Non-finite {note.split(':', 1)[1]} excluded."
    return note


def _methodology_lines(codes: Sequence[str]) -> list[str]:
    return [
        _METHODOLOGY_CAPTIONS[code]
        for code in codes
        if code in _METHODOLOGY_CAPTIONS and not code.startswith("partners.")
    ]


def _info_tooltip_html(
    lines: Sequence[str],
    *,
    control_id: str,
    aria_label: str,
    test_id: str = "tx-info-tooltip",
) -> str:
    """Build an ⓘ tooltip for multi-line help / notes."""
    return build_info_tooltip_html(
        lines,
        control_id=control_id,
        aria_label=aria_label,
        test_id=test_id,
    )


def _methodology_info_html(
    lines: Sequence[str],
    *,
    control_id: str,
) -> str:
    """Build an ⓘ tooltip for trends methodology notes."""
    return _info_tooltip_html(
        lines,
        control_id=control_id,
        aria_label="Trends methodology",
        test_id="tx-methodology-info",
    )


def _section_heading_with_info_html(title: str, tip_html: str) -> str:
    return build_section_heading_with_info_html(title, tip_html)


_SPEAKERS_DESCRIPTION = (
    "Longitudinal speaker profiles linked across managed library transcripts. "
    "Open a person to edit identity and appearances. "
    "Headline totals exclude needs-review, missing-source, collision, and ignored "
    "appearances (toggle inclusion under Settings → Speakers). "
    "Voice suggestions: enable matching, Enrol trusted voice for all profiles, "
    "then Pre-load voice suggestions — confirm in Speaker Identification."
)

_SELECTED_KEY = "speakers_selected_profile"
_SEARCH_KEY = "speakers_directory_search"


def _service() -> SpeakerProfileService:
    return SpeakerProfileService()


def _idempotency_key(action: str, payload_dict: Mapping[str, Any]) -> str:
    """Session key bound to a canonical payload hash; regenerates when payload changes."""
    digest = _payload_digest(payload_dict)
    store_key = f"speakers_idem_{action}"
    entry = st.session_state.get(store_key)
    if (
        isinstance(entry, dict)
        and entry.get("payload_hash") == digest
        and entry.get("key")
    ):
        return str(entry["key"])
    key = str(uuid4())
    st.session_state[store_key] = {"payload_hash": digest, "key": key}
    return key


def _payload_digest(payload_dict: Mapping[str, Any]) -> str:
    blob = json.dumps(
        dict(payload_dict),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _clear_idempotency(action: str) -> None:
    st.session_state.pop(f"speakers_idem_{action}", None)


def _rerun_ui() -> None:
    """Rerun only the nearest fragment (preview / confirm toggles)."""
    st.rerun(scope="fragment")


def _appearance_samples(
    snap: AggregationSnapshot, row: AppearanceRow, *, limit: int = 2
) -> list[str]:
    bundle = snap.bundles.get(row.managed_transcript_id)
    if bundle is None:
        return []
    lines: list[str] = []
    for segment in bundle.segments:
        key = normalize_diarized_id(segment.get("speaker"))
        if key != row.local_speaker_key:
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        lines.append(text)
        if len(lines) >= limit:
            break
    return lines


def _item_matches_search(item: ProfileListItem, query: str, *, extra: str = "") -> bool:
    needle = " ".join((query or "").split()).casefold()
    if not needle:
        return True
    hay = " ".join([item.display_name, *item.aliases, extra])
    return needle in hay.casefold()


def _gallery_meta(item: ProfileListItem, agg: ProfileAggregate | None) -> str:
    bits = [f"{item.link_count} appearance{'s' if item.link_count != 1 else ''}"]
    if item.status != "active":
        bits.append(item.status)
    if item.needs_repair:
        bits.append("repair")
    if agg is not None and agg.pending_review_count:
        bits.append(f"{agg.pending_review_count} review")
    return " · ".join(bits)


def _surname_sort_key(item: ProfileListItem) -> tuple[str, str, str, str]:
    first_name, surname = parse_speaker_name(item.display_name)
    return (
        (surname or first_name or "").casefold(),
        (first_name or "").casefold(),
        item.display_name.casefold(),
        item.profile_id,
    )


def _directory_chart_frame(
    chart: DirectoryChartSeries,
    *,
    name_by_id: Mapping[str, str],
) -> dict[str, list[Any]]:
    labels: list[str] = []
    seen: set[str] = set()
    for points in chart.series_by_key.values():
        for point in points:
            if point.display_label not in seen:
                seen.add(point.display_label)
                labels.append(point.display_label)
    frame: dict[str, list[Any]] = {"date": labels}
    for key, points in chart.series_by_key.items():
        col = "Other" if key == "Other" else name_by_id.get(key, key)
        by_label = {
            p.display_label: (p.value if p.value is not None else 0.0) for p in points
        }
        frame[col] = [by_label.get(lab, 0.0) for lab in labels]
    return frame


def _render_recovery_banners(root) -> None:
    report = run_integrity_scan(root)
    if report.ok and not report.blocking_operations and not report.blocking_details:
        return

    st.error(
        "Repair required: incomplete or corrupt speaker-profile state is blocking "
        "some records. Review details below or use Diagnostics."
    )
    if (
        report.corrupt_profiles
        or report.corrupt_links
        or report.corrupt_events
        or report.corrupt_operations
    ):
        st.warning(
            "Corrupt records: "
            f"profiles={len(report.corrupt_profiles)}, "
            f"links={len(report.corrupt_links)}, "
            f"events={len(report.corrupt_events)}, "
            f"operations={len(report.corrupt_operations)}."
        )

    svc = _service()
    for detail in report.blocking_details:
        with st.container(border=True):
            st.markdown(f"**Operation** `{detail.operation_id}`")
            st.caption(
                f"recovery_class=`{detail.recovery_class}` · phase=`{detail.phase}`"
            )
            if detail.affected_relpaths:
                st.code("\n".join(detail.affected_relpaths), language=None)
            else:
                st.caption("No affected paths listed.")
            if st.button(
                "Attempt safe recovery",
                key=f"speakers_recover_{detail.operation_id}",
                icon=ic.REPLAY,
                type="primary",
            ):
                try:
                    result = svc.recover_operation(detail.operation_id)
                    consume_cache_invalidation_signal(result.cache_signal)
                    rc = result.report.recovery_class
                    if rc == "complete":
                        st.success(f"Recovery complete for `{detail.operation_id}`.")
                    elif rc == "proven_aborted":
                        st.info(
                            f"Operation `{detail.operation_id}` proven aborted "
                            "(never applied)."
                        )
                    elif rc == "needs_repair" or result.report.blocking:
                        st.warning(
                            f"Operation `{detail.operation_id}` still needs_repair "
                            f"(class=`{rc}`)."
                        )
                    else:
                        st.warning(
                            f"Recovery finished with class `{rc}` for "
                            f"`{detail.operation_id}`."
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Recovery failed: {exc}")


_SPEAKERS_SNAP_CACHE_KEY = "_speakers_aggregation_snap_cache"


def _profiles_store_fingerprint(root: Path) -> tuple[int, int, int, int]:
    """Cheap invalidation key: profile/link counts + max mtimes (ns)."""
    pref = profiles_dir(root)
    lref = links_dir(root)
    p_mtime = p_count = 0
    l_mtime = l_count = 0
    if pref.is_dir():
        for path in pref.glob("*.speaker_profile.json"):
            p_count += 1
            try:
                p_mtime = max(p_mtime, path.stat().st_mtime_ns)
            except OSError:
                pass
    if lref.is_dir():
        for path in lref.glob("*.speaker_link.json"):
            l_count += 1
            try:
                l_mtime = max(l_mtime, path.stat().st_mtime_ns)
            except OSError:
                pass
    return (p_count, p_mtime, l_count, l_mtime)


def _get_speakers_aggregation_snapshot(
    *, root: Path, include_ignored: bool
) -> AggregationSnapshot:
    """Reuse snapshot within a session until profile/link store fingerprint changes."""
    fp = (
        str(root),
        bool(include_ignored),
        _profiles_store_fingerprint(root),
    )
    cached = st.session_state.get(_SPEAKERS_SNAP_CACHE_KEY)
    if (
        isinstance(cached, tuple)
        and len(cached) == 2
        and cached[0] == fp
        and cached[1] is not None
    ):
        return cached[1]
    snap = build_aggregation_snapshot(root=root, include_ignored=include_ignored)
    st.session_state[_SPEAKERS_SNAP_CACHE_KEY] = (fp, snap)
    return snap
