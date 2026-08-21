"""Settings panel for the directory watcher (roadmap G2)."""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.services.watcher import (
    DirectoryWatcherSettings,
    get_watcher_service,
    load_watcher_settings,
)
from transcriptx.web.components.info_tooltip import widget_help


def render_watcher_panel() -> None:
    """Render enable/path/mode controls and recent watcher activity."""
    st.subheader("Directory watcher")
    st.caption(
        "Default-off. When enabled, new transcript files in a watched inbox can be "
        "auto-imported into the managed library. Audio files are queued (offer) until "
        "host STT is available. Inbox sources are never deleted. The watcher runs only "
        "while TranscriptX is running."
    )

    service = get_watcher_service()
    current = load_watcher_settings()
    status = service.status()

    enabled = st.checkbox(
        "Enable directory watcher",
        value=bool(current.enabled),
        key="watcher_enabled",
        help=widget_help(
            "Explicit opt-in. Leave off on shared machines unless you intend auto-import."
        ),
    )
    paths_text = st.text_area(
        "Watch paths (one absolute path per line)",
        value="\n".join(current.watch_paths),
        key="watcher_paths",
        help=widget_help(
            (
                "Example: /mnt/transcript-inbox (Docker) or "
                "/Users/you/Documents/transcripts-inbox. "
                "Must not be under the managed transcripts library."
            )
        ),
    )
    col_a, col_b = st.columns(2)
    with col_a:
        transcript_mode = st.selectbox(
            "Transcript mode",
            options=["auto_import", "offer", "ignore"],
            index=["auto_import", "offer", "ignore"].index(current.transcript_mode),
            key="watcher_transcript_mode",
            help=widget_help(
                (
                    "auto_import: admit new transcript files into the library. "
                    "offer: queue for review. ignore: skip transcript files."
                )
            ),
        )
    with col_b:
        audio_mode = st.selectbox(
            "Audio mode",
            options=["offer", "ignore", "auto_transcribe"],
            index=(
                ["offer", "ignore", "auto_transcribe"].index(current.audio_mode)
                if current.audio_mode in {"offer", "ignore", "auto_transcribe"}
                else 0
            ),
            key="watcher_audio_mode",
            help=widget_help(
                "auto_transcribe requires a host STT provider (theme H) and is rejected for now."
            ),
        )

    recursive = st.checkbox(
        "Watch subdirectories",
        value=bool(current.recursive),
        key="watcher_recursive",
        help=widget_help(
            "When on, files in nested folders under each watch path are also considered."
        ),
    )
    debounce_ms = st.number_input(
        "Debounce (ms)",
        min_value=100,
        max_value=120_000,
        value=int(current.debounce_ms),
        step=100,
        key="watcher_debounce_ms",
        help=widget_help(
            "Wait this long after the last write before treating a file as complete."
        ),
    )

    if st.button(
        "Save watcher settings", type="primary", key="watcher_save_btn", icon=ic.SAVE
    ):
        paths = [line.strip() for line in paths_text.splitlines() if line.strip()]
        settings = DirectoryWatcherSettings(
            enabled=bool(enabled),
            watch_paths=paths,
            recursive=bool(recursive),
            debounce_ms=int(debounce_ms),
            stability_checks=current.stability_checks,
            stability_interval_ms=current.stability_interval_ms,
            transcript_mode=transcript_mode,  # type: ignore[arg-type]
            audio_mode=audio_mode,  # type: ignore[arg-type]
            on_success=current.on_success,
            transcription_profile=current.transcription_profile,
            poll_fallback_seconds=current.poll_fallback_seconds,
            extensions_transcript=current.extensions_transcript,
            extensions_audio=current.extensions_audio,
        )
        try:
            service.configure(settings, persist=True)
            st.success("Watcher settings saved.")
            if settings.enabled:
                errs = service.status().last_errors
                if errs:
                    st.warning("Watcher started with notes: " + "; ".join(errs))
                else:
                    st.info("Watcher is running.")
            else:
                st.info("Watcher is stopped.")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Could not apply watcher settings: {exc}")

    status = service.status()
    st.markdown("**Status**")
    st.text(
        f"running={status.running} enabled={status.enabled} "
        f"observer={status.observer_alive} "
        f"transcript_mode={status.transcript_mode} audio_mode={status.audio_mode}"
    )
    if status.watch_paths:
        st.text("paths: " + ", ".join(status.watch_paths))
    if status.job_counts:
        st.text(
            "jobs: "
            + ", ".join(f"{k}={v}" for k, v in sorted(status.job_counts.items()))
        )
    if status.last_errors:
        st.warning("; ".join(status.last_errors))

    st.markdown("**Recent activity**")
    activity = service.store.recent_activity(limit=25)
    if not activity:
        st.caption("No watcher activity yet.")
    else:
        rows = [
            {
                "time": a.get("ts", ""),
                "state": a.get("state", ""),
                "file": (a.get("path") or "").rsplit("/", 1)[-1],
                "detail": a.get("detail", ""),
            }
            for a in activity
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
