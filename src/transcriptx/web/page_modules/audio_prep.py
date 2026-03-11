"""
Audio Prep page — assess and preprocess audio files for transcription.

Layout:
    A. File Selection       — browse recordings dir or upload
    B. Assessment           — on-demand noise + compliance analysis
    C. Configuration        — mode, per-step options, output settings
    D. Run & Result         — process with live progress, then result + handoff
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import streamlit as st

from transcriptx.app.controllers.preprocess_controller import PreprocessController
from transcriptx.app.models.requests import PreprocessRequest
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.utils.paths import RECORDINGS_DIR
from transcriptx.web.components.progress_panel import (
    PREPROCESS_SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.services.recordings_service import RecordingsService

# ---------------------------------------------------------------------------
# Session-state key constants
# ---------------------------------------------------------------------------
_KEY_RUN_IN_PROGRESS = "audio_prep_run_in_progress"
_KEY_RESULT = "audio_prep_run_result"
_KEY_ASSESSMENT = "audio_prep_assessment"  # dict keyed by str(path)
_KEY_SELECTED_FILE = "audio_prep_selected_file"

# Steps that have per-step checkboxes in "selected" mode
_STEP_LABELS: Dict[str, str] = {
    "resample": "Resample to 16 kHz",
    "mono": "Convert to mono",
    "highpass": "High-pass filter (removes low-frequency rumble)",
    "denoise": "Noise reduction",
    "normalize": "Loudness normalisation",
    "lowpass": "Low-pass filter",
    "bandpass": "Band-pass filter",
}


def render_audio_prep_page() -> None:
    """Render the Audio Prep page."""
    st.markdown(
        '<div class="main-header">🎛️ Audio Prep</div>',
        unsafe_allow_html=True,
    )

    _render_section_a()


# ---------------------------------------------------------------------------
# Section A — File Selection
# ---------------------------------------------------------------------------


def _render_section_a() -> None:
    st.subheader("1. Select audio file")

    recordings = RecordingsService.list_recordings(RECORDINGS_DIR)

    # File uploader — saved immediately to imports/ for stability
    uploaded = st.file_uploader(
        "Upload audio file",
        type=["mp3", "wav", "m4a", "flac", "ogg", "aac"],
        help="Uploaded files are saved to the recordings imports folder and persist across reruns.",
        key="audio_prep_uploader",
    )
    if uploaded is not None:
        saved_path = RecordingsService.save_uploaded_file(uploaded, RECORDINGS_DIR)
        st.success(f"Saved to `{saved_path.relative_to(RECORDINGS_DIR)}`")
        # Clear cache so the new file appears in the selectbox
        RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]
        recordings = RecordingsService.list_recordings(RECORDINGS_DIR)

    if not recordings:
        st.info(
            f"No audio files found in `{RECORDINGS_DIR}`. "
            "Upload a file above or add files to the recordings directory."
        )
        return

    # Build display labels relative to RECORDINGS_DIR when possible
    def _label(p: Path) -> str:
        try:
            return str(p.relative_to(RECORDINGS_DIR))
        except ValueError:
            return p.name

    labels = [_label(p) for p in recordings]
    paths_str = [str(p) for p in recordings]

    # Preserve previously selected file across reruns
    prev_selection = st.session_state.get(_KEY_SELECTED_FILE)
    default_idx = 0
    if prev_selection and prev_selection in paths_str:
        default_idx = paths_str.index(prev_selection)

    choice_idx = st.selectbox(
        "Recording",
        range(len(recordings)),
        format_func=lambda i: labels[i],
        index=default_idx,
        key="audio_prep_file_select",
    )
    selected_path = recordings[choice_idx]

    # Invalidate cached assessment when the file changes
    if st.session_state.get(_KEY_SELECTED_FILE) != str(selected_path):
        st.session_state.pop(_KEY_RESULT, None)
        st.session_state[_KEY_SELECTED_FILE] = str(selected_path)

    # File metadata row
    meta = RecordingsService.get_audio_metadata(selected_path)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Duration", RecordingsService.format_duration(meta["duration_sec"]))
    col2.metric(
        "Sample rate", f"{meta['sample_rate']:,} Hz" if meta["sample_rate"] else "—"
    )
    col3.metric(
        "Channels",
        (
            "Mono"
            if meta["channels"] == 1
            else f"{meta['channels']}ch" if meta["channels"] else "—"
        ),
    )
    col4.metric("Size", f"{meta['file_size_mb']} MB")

    _render_section_b(selected_path)


# ---------------------------------------------------------------------------
# Section B — Assessment
# ---------------------------------------------------------------------------


def _render_section_b(audio_path: Path) -> None:
    st.subheader("2. Assess audio")

    cache_key = str(audio_path)
    cached = st.session_state.get(_KEY_ASSESSMENT, {}).get(cache_key)

    if cached:
        _render_assessment_result(cached["assessment"], cached["compliance"])
        col_re, _ = st.columns([1, 4])
        if col_re.button("🔄 Re-assess", key="audio_prep_reassess"):
            _run_assessment(audio_path, cache_key)
            st.rerun()
    else:
        if st.button("🔍 Assess Audio", key="audio_prep_assess", type="secondary"):
            _run_assessment(audio_path, cache_key)
            st.rerun()
        st.caption(
            "Run assessment to see noise level, compliance, and suggested steps."
        )

    # Pass cached (or freshly computed) assessment into section C
    assessment_data = st.session_state.get(_KEY_ASSESSMENT, {}).get(cache_key)
    suggested_steps: List[str] = []
    if assessment_data:
        suggested_steps = assessment_data["assessment"].get("suggested_steps", [])

    _render_section_c(audio_path, suggested_steps)


def _run_assessment(audio_path: Path, cache_key: str) -> None:
    """Run assess-only preprocessing and cache the result."""
    ctrl = PreprocessController()
    request = PreprocessRequest(
        input_path=audio_path,
        operation="assess",
    )
    with st.spinner("Assessing audio…"):
        result = ctrl.run_preprocess(request)

    cache = st.session_state.get(_KEY_ASSESSMENT, {})
    cache[cache_key] = {
        "assessment": result.assessment or {},
        "compliance": result.compliance or {},
    }
    st.session_state[_KEY_ASSESSMENT] = cache

    if result.errors:
        for err in result.errors:
            st.error(err)


def _render_assessment_result(assessment: dict, compliance: dict) -> None:  # type: ignore[type-arg]
    """Render noise level badge, compliance row, metrics, and suggested steps."""
    noise_level = assessment.get("noise_level", "unknown")
    noise_colors = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    badge = noise_colors.get(noise_level, "⚪")

    st.markdown(f"**Noise level:** {badge} {noise_level.capitalize()}")

    # Compliance checklist
    missing = compliance.get("missing_requirements", [])
    compliance_items = {
        "16kHz": "16 kHz sample rate",
        "mono": "Mono channel",
        "normalized": "Loudness normalised",
    }
    cols = st.columns(len(compliance_items))
    for col, (key, label) in zip(cols, compliance_items.items()):
        icon = "❌" if key in missing else "✅"
        col.markdown(f"{icon} {label}")

    # Metrics table
    metrics = assessment.get("metrics", {})
    if metrics:
        with st.expander("Raw metrics", expanded=False):
            rows = {}
            if metrics.get("rms_db") is not None:
                rows["RMS level"] = f"{metrics['rms_db']:.1f} dB"
            if metrics.get("peak_db") is not None:
                rows["Peak level"] = f"{metrics['peak_db']:.1f} dB"
            if metrics.get("clipping_percentage") is not None:
                rows["Clipping"] = f"{metrics['clipping_percentage']:.3f}%"
            if metrics.get("snr_proxy_db") is not None:
                rows["SNR proxy"] = f"{metrics['snr_proxy_db']:.1f} dB"
            if metrics.get("speech_ratio") is not None:
                rows["Speech ratio"] = f"{metrics['speech_ratio']:.0%}"
            if metrics.get("dc_offset_db") is not None:
                rows["DC offset"] = f"{metrics['dc_offset_db']:.1f} dB"
            for label, value in rows.items():
                st.text(f"  {label}: {value}")

    # Suggested steps
    suggested = assessment.get("suggested_steps", [])
    if suggested:
        st.caption(f"Suggested steps: {', '.join(suggested)}")
    else:
        st.caption("No preprocessing steps suggested — audio looks clean.")


# ---------------------------------------------------------------------------
# Section C — Configuration
# ---------------------------------------------------------------------------


def _render_section_c(audio_path: Path, suggested_steps: List[str]) -> None:
    st.subheader("3. Configure preprocessing")

    mode = st.radio(
        "Preprocessing mode",
        options=["off", "auto", "selected"],
        format_func=lambda m: {
            "off": "Off — skip all processing (assess only)",
            "auto": "Auto — apply steps recommended by assessment",
            "selected": "Selected — choose steps manually below",
        }[m],
        index=1,
        horizontal=True,
        key="audio_prep_mode",
        help=(
            "Off: no output file is produced. "
            "Auto: only assessment-suggested steps run — will not degrade already-clean audio. "
            "Selected: you control exactly which steps run."
        ),
    )

    # Per-step checkboxes — only shown in "selected" mode
    decisions: Dict[str, bool] = {}
    if mode == "selected":
        st.markdown("**Steps to apply:**")
        for step, label in _STEP_LABELS.items():
            default = step in suggested_steps
            decisions[step] = st.checkbox(
                label, value=default, key=f"audio_prep_step_{step}"
            )

    # Advanced settings
    with st.expander("Advanced settings", expanded=False):
        target_lufs = st.slider(
            "Target loudness (LUFS)",
            min_value=-20.0,
            max_value=-16.0,
            value=-18.0,
            step=0.5,
            key="audio_prep_lufs",
        )
        denoise_strength = st.selectbox(
            "Denoise strength",
            options=["low", "medium", "high"],
            index=1,
            key="audio_prep_denoise_strength",
        )
        highpass_cutoff = st.slider(
            "High-pass cutoff (Hz)",
            min_value=70,
            max_value=120,
            value=80,
            step=5,
            key="audio_prep_highpass_cutoff",
        )

    # Output settings
    st.markdown("**Output**")
    output_dest = st.radio(
        "Save output to",
        options=["same", "sub", "app"],
        format_func=lambda d: {
            "same": "Same folder as input",
            "sub": "preprocessed/ subfolder",
            "app": f"App output dir ({RECORDINGS_DIR / 'preprocessed'})",
        }[d],
        horizontal=True,
        key="audio_prep_output_dest",
    )
    output_format = st.radio(
        "Output format",
        options=["wav", "mp3"],
        format_func=str.upper,
        horizontal=True,
        key="audio_prep_output_format",
    )
    overwrite = st.checkbox(
        "Overwrite existing file", value=False, key="audio_prep_overwrite"
    )

    # Resolve and show output path read-only
    output_dir = _resolve_output_dir(audio_path, output_dest)
    resolved_name = f"{audio_path.stem}_preprocessed.{output_format}"
    st.code(str(output_dir / resolved_name), language=None)

    # Build config override with advanced settings
    from transcriptx.core.utils.config import get_config
    from dataclasses import replace as dc_replace

    base_config = get_config().audio_preprocessing
    config_override = dc_replace(
        base_config,
        target_lufs=target_lufs,
        denoise_strength=denoise_strength,
        highpass_cutoff=highpass_cutoff,
        # Keep preprocessing_mode at "selected" so apply_preprocessing respects decisions
        preprocessing_mode="selected",
    )

    _render_section_d(
        audio_path=audio_path,
        mode=mode,
        decisions=decisions,
        output_dir=output_dir,
        output_format=output_format,
        overwrite=overwrite,
        config=config_override,
    )


def _resolve_output_dir(audio_path: Path, dest_choice: str) -> Path:
    if dest_choice == "same":
        return audio_path.parent
    if dest_choice == "sub":
        return audio_path.parent / "preprocessed"
    return RECORDINGS_DIR / "preprocessed"


# ---------------------------------------------------------------------------
# Section D — Run & Result
# ---------------------------------------------------------------------------


def _render_section_d(
    audio_path: Path,
    mode: str,
    decisions: Dict[str, bool],
    output_dir: Path,
    output_format: str,
    overwrite: bool,
    config: object,
) -> None:
    st.subheader("4. Run")

    # If a run is in progress, show the progress panel and return
    if st.session_state.get(_KEY_RUN_IN_PROGRESS, False):
        snapshot = st.session_state.get(PREPROCESS_SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(snapshot)
        else:
            st.info("Processing…")
        return

    # Show last run result if available (collapsed so it doesn't dominate)
    last_result = st.session_state.get(_KEY_RESULT)
    if last_result is not None:
        _render_result(last_result, audio_path)
        with st.expander("Run again", expanded=False):
            _render_run_button(
                audio_path,
                mode,
                decisions,
                output_dir,
                output_format,
                overwrite,
                config,
            )
    else:
        _render_run_button(
            audio_path, mode, decisions, output_dir, output_format, overwrite, config
        )


def _render_run_button(
    audio_path: Path,
    mode: str,
    decisions: Dict[str, bool],
    output_dir: Path,
    output_format: str,
    overwrite: bool,
    config: object,
) -> None:
    button_label = "🔍 Assess Only" if mode == "off" else "▶ Process Audio"
    operation = "assess" if mode == "off" else "assess_and_preprocess"

    if st.button(button_label, type="primary", key="audio_prep_run"):
        request = PreprocessRequest(
            input_path=audio_path,
            operation=operation,
            preprocessing_mode=mode,
            output_dir=output_dir,
            output_format=output_format,
            overwrite=overwrite,
            config=config,
            preprocessing_decisions=decisions if mode == "selected" else None,
        )

        st.session_state[PREPROCESS_SNAPSHOT_KEY] = make_initial_snapshot(total=5)
        st.session_state[_KEY_RUN_IN_PROGRESS] = True

        progress = StreamlitProgressCallback(PREPROCESS_SNAPSHOT_KEY)
        ctrl = PreprocessController()

        with st.status(
            "Assessing audio…" if mode == "off" else "Processing audio…",
            expanded=True,
        ) as status_widget:
            try:
                result = ctrl.run_preprocess(request, progress=progress)
            except Exception as exc:
                from transcriptx.app.models.results import PreprocessResult

                result = PreprocessResult(success=False, errors=[str(exc)])
            finally:
                st.session_state[_KEY_RUN_IN_PROGRESS] = False

            if result.success:
                status_widget.update(label="✓ Complete", state="complete")
            else:
                status_widget.update(label="✗ Failed", state="error")

        st.session_state[_KEY_RESULT] = result
        st.rerun()


def _render_result(result: object, audio_path: Path) -> None:
    """Render the outcome of the last run."""
    from transcriptx.app.models.results import PreprocessResult

    r: PreprocessResult = result  # type: ignore[assignment]

    if not r.success:
        st.error("Processing failed.")
        for err in r.errors:
            st.error(f"  • {err}")
        return

    if r.output_path:
        st.success(f"Output saved: `{r.output_path}`")
    else:
        st.success("Assessment complete — no output file produced.")

    if r.applied_steps:
        steps_clean = [s for s in r.applied_steps if s != "skipped_already_compliant"]
        if "skipped_already_compliant" in r.applied_steps:
            st.info("Audio was already compliant — preprocessing was skipped.")
        elif steps_clean:
            st.caption(f"Steps applied: {', '.join(steps_clean)}")

    if r.duration_seconds is not None:
        st.caption(f"Completed in {r.duration_seconds:.1f}s")

    if r.warnings:
        for w in r.warnings:
            st.warning(w)

    # Update the cached assessment from the result (if a fresh one was run)
    if r.assessment:
        cache_key = str(audio_path)
        cache = st.session_state.get(_KEY_ASSESSMENT, {})
        cache[cache_key] = {
            "assessment": r.assessment,
            "compliance": r.compliance or {},
        }
        st.session_state[_KEY_ASSESSMENT] = cache

    # Transcription handoff
    if r.output_path:
        _render_transcription_handoff(r.output_path)


def _render_transcription_handoff(output_path: Path) -> None:
    """Show the WhisperX Docker command pre-filled with the output path."""
    with st.expander("Next step: transcribe with WhisperX", expanded=False):
        st.markdown(
            "Run the following command to transcribe the preprocessed file. "
            "Adjust the volume mount paths to match your environment."
        )
        input_dir = output_path.parent
        filename = output_path.name
        cmd = (
            "docker run --rm \\\n"
            f'  -v "{input_dir}:/data/input:ro" \\\n'
            '  -v "/path/to/transcripts:/data/output" \\\n'
            "  --env-file whisperx.env \\\n"
            "  ghcr.io/jim60105/whisperx:no_model \\\n"
            f'  -c "whisperx /data/input/{filename} '
            '--output_dir /data/output --language en --diarize"'
        )
        st.code(cmd, language="bash")
        st.caption(
            "Edit `whisperx.env` to change the model, language, or diarisation settings. "
            "Once transcription is complete, load the resulting JSON via the Library page."
        )
