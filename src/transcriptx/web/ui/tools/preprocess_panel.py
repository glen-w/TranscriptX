"""Preprocessing panel — assess and preprocess recordings for transcription."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, List

import streamlit as st

from transcriptx.app.controllers.preprocess_controller import PreprocessController
from transcriptx.app.models.requests import PreprocessRequest
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.paths import RECORDINGS_DIR
from transcriptx.web.components.progress_panel import (
    PREPROCESS_SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.components.rename_form import render_audio_linked_rename_form
from transcriptx.web.navigation import (
    PREPROCESS_SELECTED_FILES_KEY,
    navigate_to_transcribe_with_paths,
)
from transcriptx.web.services.recordings_service import RecordingsService
from transcriptx.web.ui.tools.shared import (
    recordings_path_label,
    render_empty_recordings_hint,
    render_upload_and_refresh,
)
from transcriptx.web.components.info_tooltip import widget_help

_KEY_RUN_IN_PROGRESS = "audio_prep_run_in_progress"
_KEY_RESULT = "audio_prep_run_result"
_KEY_ASSESSMENT = "audio_prep_assessment"
_KEY_SELECTED_FILE = "audio_prep_selected_file"
_KEY_SELECTED_FILES = PREPROCESS_SELECTED_FILES_KEY
_KEY_CONFIG_MODE = "audio_prep_config_mode"  # "suggested" | "custom"

_STEP_LABELS: Dict[str, str] = {
    "resample": "Resample to 16 kHz",
    "mono": "Convert to mono",
    "highpass": "High-pass filter (removes low-frequency rumble)",
    "denoise": "Noise reduction",
    "normalize": "Loudness normalisation",
    "lowpass": "Low-pass filter",
    "bandpass": "Band-pass filter",
}


def resolve_output_dir(audio_path: Path, dest_choice: str) -> Path:
    if dest_choice == "same":
        return audio_path.parent
    if dest_choice == "sub":
        return audio_path.parent / "preprocessed"
    return RECORDINGS_DIR / "preprocessed"


def render_preprocess_panel(*, deps_ready: bool = True) -> None:
    """Render the Preprocessing tool tab."""
    st.caption(
        "Assess noise and compliance, then apply suggested DSP steps before "
        "external transcription."
    )

    recordings = render_upload_and_refresh(
        uploader_key="audio_prep_uploader",
        selected_files_key=_KEY_SELECTED_FILES,
    )
    if not recordings:
        render_empty_recordings_hint()
        return

    paths_str = [str(p) for p in recordings]
    prev_selected = st.session_state.get(_KEY_SELECTED_FILES)
    if prev_selected is None:
        prev = st.session_state.get(_KEY_SELECTED_FILE)
        prev_selected = [prev] if prev is not None else None
    if not prev_selected or not any(p in paths_str for p in prev_selected):
        prev_selected = [paths_str[0]]

    _selection_fragment(paths_str, prev_selected, deps_ready=deps_ready)


@st.fragment
def _selection_fragment(
    paths_str: List[str], prev_selected: List[str], *, deps_ready: bool
) -> None:
    st.subheader("1. Select file(s)")
    selected_paths_str = st.multiselect(
        "Recording — file(s) to process",
        options=paths_str,
        default=[p for p in prev_selected if p in paths_str] or [paths_str[0]],
        format_func=lambda p: recordings_path_label(Path(p)),
        key="audio_prep_file_select",
        help=widget_help((
            "After uploading, your new file appears here — select it to process. "
            "Multiple files use per-file auto steps."
        )),
    )
    if not selected_paths_str:
        st.warning("Select at least one file to continue.")
        return

    selected_paths = [Path(p) for p in selected_paths_str]
    st.session_state[_KEY_SELECTED_FILES] = selected_paths_str

    prev_result_key = st.session_state.get(_KEY_SELECTED_FILE)
    prev_set = (
        set(prev_result_key)
        if isinstance(prev_result_key, list)
        else {prev_result_key}
        if prev_result_key
        else set()
    )
    if set(selected_paths_str) != prev_set:
        st.session_state.pop(_KEY_RESULT, None)
    st.session_state[_KEY_SELECTED_FILE] = (
        selected_paths_str[0] if len(selected_paths_str) == 1 else None
    )

    if len(selected_paths) == 1:
        meta = RecordingsService.get_audio_metadata(selected_paths[0])
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Duration", RecordingsService.format_duration(meta["duration_sec"]))
        col2.metric(
            "Sample rate",
            f"{meta['sample_rate']:,} Hz" if meta["sample_rate"] else "—",
        )
        col3.metric(
            "Channels",
            (
                "Mono"
                if meta["channels"] == 1
                else f"{meta['channels']}ch"
                if meta["channels"]
                else "—"
            ),
        )
        col4.metric("Size", f"{meta['file_size_mb']} MB")
        render_audio_linked_rename_form(
            selected_paths[0],
            form_key="audio_prep_rename_form",
        )
    else:
        total_dur = sum(
            RecordingsService.get_audio_metadata(p)["duration_sec"]
            for p in selected_paths
        )
        st.caption(
            f"{len(selected_paths)} files selected · total duration "
            f"{RecordingsService.format_duration(total_dur)}"
        )

    _render_assess_and_configure(selected_paths, deps_ready=deps_ready)


def _render_assess_and_configure(
    audio_paths: List[Path], *, deps_ready: bool
) -> None:
    st.subheader("2. Assess")

    if len(audio_paths) > 1:
        st.info(
            "Each file will be **assessed** and **preprocessed** with steps "
            "recommended for that file. Output format and advanced settings apply "
            "to all."
        )
        _render_configure(audio_paths, [], deps_ready=deps_ready)
        return

    audio_path = audio_paths[0]
    cache_key = str(audio_path)
    cached = st.session_state.get(_KEY_ASSESSMENT, {}).get(cache_key)

    if cached:
        _render_assessment_result(cached["assessment"], cached["compliance"])
        col_re, _ = st.columns([1, 4])
        if col_re.button("Re-assess", key="audio_prep_reassess"):
            _run_assessment(audio_path, cache_key)
            st.rerun()
    else:
        if st.button("Assess audio", key="audio_prep_assess", type="secondary"):
            _run_assessment(audio_path, cache_key)
            st.rerun()
        st.caption(
            "Run assessment to see noise level, compliance, and suggested steps."
        )

    assessment_data = st.session_state.get(_KEY_ASSESSMENT, {}).get(cache_key)
    suggested_steps: List[str] = []
    if assessment_data:
        suggested_steps = assessment_data["assessment"].get("suggested_steps", [])

    _render_configure(audio_paths, suggested_steps, deps_ready=deps_ready)


def _run_assessment(audio_path: Path, cache_key: str) -> None:
    ctrl = PreprocessController()
    request = PreprocessRequest(input_path=audio_path, operation="assess")
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
    noise_level = assessment.get("noise_level", "unknown")
    noise_colors = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    badge = noise_colors.get(noise_level, "⚪")
    st.markdown(f"**Noise level:** {badge} {noise_level.capitalize()}")

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

    suggested = assessment.get("suggested_steps", [])
    if suggested:
        st.caption(f"Suggested steps: {', '.join(suggested)}")
    else:
        st.caption("No preprocessing steps suggested — audio looks clean.")


def _render_configure(
    audio_paths: List[Path],
    suggested_steps: List[str],
    *,
    deps_ready: bool,
) -> None:
    st.subheader("3. Configure")

    is_batch = len(audio_paths) > 1
    decisions: Dict[str, bool] = {}

    if is_batch:
        mode = "auto"
        config_mode = "suggested"
    else:
        has_assessment = bool(suggested_steps) or bool(
            st.session_state.get(_KEY_ASSESSMENT, {}).get(str(audio_paths[0]))
        )
        config_options = ["Apply suggested", "Custom steps", "Assess only"]
        default_ix = 0 if has_assessment else 0
        choice = st.radio(
            "How to process",
            options=config_options,
            index=default_ix,
            horizontal=True,
            key="audio_prep_how",
            help=widget_help((
                "Apply suggested: run assessment-recommended steps (safe for clean audio). "
                "Custom steps: pick DSP steps manually. "
                "Assess only: no output file."
            )),
        )
        if choice == "Assess only":
            mode = "off"
            config_mode = "off"
        elif choice == "Custom steps":
            mode = "selected"
            config_mode = "custom"
            st.markdown("**Steps to apply:**")
            for step, label in _STEP_LABELS.items():
                decisions[step] = st.checkbox(
                    label,
                    value=step in suggested_steps,
                    key=f"audio_prep_step_{step}",
                )
        else:
            mode = "auto"
            config_mode = "suggested"
            if suggested_steps:
                st.caption(
                    "Will apply: " + ", ".join(suggested_steps)
                    if suggested_steps
                    else "Will apply assessment-recommended steps only."
                )
            elif has_assessment:
                st.caption("Assessment found no required steps — processing may skip.")
            else:
                st.caption(
                    "Without a prior assess, auto mode will assess then apply "
                    "recommended steps."
                )
        st.session_state[_KEY_CONFIG_MODE] = config_mode

    with st.expander("Advanced settings", expanded=False):
        target_lufs = st.slider(
            "Target loudness (LUFS)",
            min_value=-20.0,
            max_value=-16.0,
            value=-18.0,
            step=0.5,
            key="audio_prep_lufs",
            help=widget_help("Integrated loudness target for normalization (broadcast-style LUFS)."),
        )
        denoise_strength = st.selectbox(
            "Denoise strength",
            options=["low", "medium", "high"],
            index=1,
            key="audio_prep_denoise_strength",
            help=widget_help("Higher removes more noise but can soften speech."),
        )
        highpass_cutoff = st.slider(
            "High-pass cutoff (Hz)",
            min_value=70,
            max_value=120,
            value=80,
            step=5,
            key="audio_prep_highpass_cutoff",
            help=widget_help("Remove rumble below this frequency before transcription."),
        )

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
        help=widget_help("Where preprocessed audio files are written relative to the input or app data."),
    )
    output_format = st.radio(
        "Output format",
        options=["wav", "mp3"],
        format_func=str.upper,
        horizontal=True,
        key="audio_prep_output_format",
        help=widget_help("WAV preserves quality for STT; MP3 is smaller for sharing."),
    )
    overwrite = st.checkbox(
        "Overwrite existing file",
        value=False,
        key="audio_prep_overwrite",
        help=widget_help("Replace an existing preprocessed file at the resolved output path."),
    )

    first_path = audio_paths[0]
    output_dir = resolve_output_dir(first_path, output_dest)
    if len(audio_paths) == 1:
        resolved_name = f"{first_path.stem}_preprocessed.{output_format}"
        st.code(str(output_dir / resolved_name), language=None)
    else:
        st.caption(
            f"Outputs: one file per input (e.g. `*_preprocessed.{output_format}`)"
        )
        st.code(str(output_dir), language=None)

    config_override = copy.deepcopy(get_config().audio_preprocessing)
    config_override.target_lufs = target_lufs
    config_override.denoise_strength = denoise_strength
    config_override.highpass_cutoff = highpass_cutoff
    config_override.preprocessing_mode = "selected"

    _render_run(
        audio_paths=audio_paths,
        mode=mode,
        decisions=decisions,
        output_dir=output_dir,
        output_dest=output_dest,
        output_format=output_format,
        overwrite=overwrite,
        config=config_override,
        deps_ready=deps_ready,
    )


def _render_run(
    audio_paths: List[Path],
    mode: str,
    decisions: Dict[str, bool],
    output_dir: Path,
    output_dest: str,
    output_format: str,
    overwrite: bool,
    config: object,
    *,
    deps_ready: bool,
) -> None:
    st.subheader("4. Run")

    if st.session_state.get(_KEY_RUN_IN_PROGRESS, False):
        snapshot = st.session_state.get(PREPROCESS_SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(snapshot)
        else:
            st.info("Processing…")
        return

    last_result = st.session_state.get(_KEY_RESULT)
    if last_result is not None:
        _render_result(last_result, audio_paths)
        with st.expander("Run again", expanded=False):
            _render_run_button(
                audio_paths,
                mode,
                decisions,
                output_dir,
                output_dest,
                output_format,
                overwrite,
                config,
                deps_ready=deps_ready,
            )
    else:
        _render_run_button(
            audio_paths,
            mode,
            decisions,
            output_dir,
            output_dest,
            output_format,
            overwrite,
            config,
            deps_ready=deps_ready,
        )


def _render_run_button(
    audio_paths: List[Path],
    mode: str,
    decisions: Dict[str, bool],
    output_dir: Path,
    output_dest: str,
    output_format: str,
    overwrite: bool,
    config: object,
    *,
    deps_ready: bool,
) -> None:
    n = len(audio_paths)
    if n == 1:
        if mode == "off":
            button_label = "Assess only"
        elif mode == "auto":
            button_label = "Apply suggested"
        else:
            button_label = "Process audio"
        operation = "assess" if mode == "off" else "assess_and_preprocess"
    else:
        button_label = f"Process {n} files (tailored per file)"
        operation = "assess_and_preprocess"

    if not deps_ready and mode != "off":
        st.warning("Install ffmpeg and pydub before processing.")

    disabled = (not deps_ready) and mode != "off"
    if st.button(
        button_label, type="primary", key="audio_prep_run", disabled=disabled
    ):
        st.session_state[PREPROCESS_SNAPSHOT_KEY] = make_initial_snapshot(total=5)
        st.session_state[_KEY_RUN_IN_PROGRESS] = True
        progress = StreamlitProgressCallback(PREPROCESS_SNAPSHOT_KEY)
        ctrl = PreprocessController()

        if n == 1:
            out_dir = resolve_output_dir(audio_paths[0], output_dest)
            request = PreprocessRequest(
                input_path=audio_paths[0],
                operation=operation,
                preprocessing_mode=mode,
                output_dir=out_dir,
                output_format=output_format,
                overwrite=overwrite,
                config=config,
                preprocessing_decisions=decisions if mode == "selected" else None,
            )
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
        else:
            batch_results: List[tuple] = []
            with st.status(f"Processing {n} files…", expanded=True) as status_widget:
                try:
                    for path in audio_paths:
                        out_dir = resolve_output_dir(path, output_dest)
                        request = PreprocessRequest(
                            input_path=path,
                            operation="assess_and_preprocess",
                            preprocessing_mode="auto",
                            output_dir=out_dir,
                            output_format=output_format,
                            overwrite=overwrite,
                            config=config,
                            preprocessing_decisions=None,
                        )
                        result = ctrl.run_preprocess(request, progress=progress)
                        batch_results.append((path, result))
                except Exception as exc:
                    from transcriptx.app.models.results import PreprocessResult

                    batch_results.append(
                        (path, PreprocessResult(success=False, errors=[str(exc)]))
                    )
                finally:
                    st.session_state[_KEY_RUN_IN_PROGRESS] = False
                ok = sum(1 for _, r in batch_results if r.success)
                status_widget.update(
                    label=f"✓ {ok}/{n} complete" if ok == n else f"⚠ {ok}/{n} complete",
                    state="complete" if ok == n else "error",
                )
            st.session_state[_KEY_RESULT] = batch_results
        st.rerun()


def _render_result(result: object, audio_paths: List[Path]) -> None:
    from transcriptx.app.models.results import PreprocessResult

    if isinstance(result, list):
        batch: List[tuple] = result
        ok = sum(1 for _, res in batch if res.success)
        st.caption(f"{ok}/{len(batch)} files processed successfully.")
        handoff_paths: List[Path] = []
        for path, res in batch:
            _render_single_result(res, path)
            if res.output_path:
                handoff_paths.append(Path(res.output_path))
        if handoff_paths:
            _render_transcription_handoff(handoff_paths)
        return

    single_result: PreprocessResult = result  # type: ignore[assignment]
    audio_path = audio_paths[0] if audio_paths else Path(".")
    _render_single_result(single_result, audio_path)
    if single_result.assessment:
        cache_key = str(audio_path)
        cache = st.session_state.get(_KEY_ASSESSMENT, {})
        cache[cache_key] = {
            "assessment": single_result.assessment,
            "compliance": single_result.compliance or {},
        }
        st.session_state[_KEY_ASSESSMENT] = cache
    if single_result.output_path:
        out = Path(single_result.output_path)
        if out.exists():
            try:
                st.audio(out.read_bytes())
            except Exception as exc:
                st.caption(f"Playback unavailable: {exc}")
        _render_transcription_handoff([out])


def _render_single_result(r: object, audio_path: Path) -> None:
    from transcriptx.app.models.results import PreprocessResult

    res: PreprocessResult = r  # type: ignore[assignment]
    name = audio_path.name

    if not res.success:
        st.error(f"**{name}** — failed.")
        for err in res.errors:
            st.error(f"  • {err}")
        return

    if res.output_path:
        st.success(f"**{name}** → `{res.output_path}`")
    else:
        st.success(f"**{name}** — assessment complete, no output file.")

    if res.applied_steps:
        steps_clean = [s for s in res.applied_steps if s != "skipped_already_compliant"]
        if "skipped_already_compliant" in res.applied_steps:
            st.info("Audio was already compliant — preprocessing was skipped.")
        elif steps_clean:
            st.caption(f"Steps applied: {', '.join(steps_clean)}")

    if res.duration_seconds is not None:
        st.caption(f"Completed in {res.duration_seconds:.1f}s")

    if res.warnings:
        for w in res.warnings:
            st.warning(w)


def _render_transcription_handoff(output_paths: List[Path]) -> None:
    st.markdown("**Next step**")
    st.caption(
        "Transcription runs outside the app. Open Transcribe Audio for host "
        "commands, then import JSON via Import Transcript."
    )
    if st.button(
        "Open Transcribe Audio",
        type="primary",
        key="audio_prep_transcribe_handoff",
    ):
        navigate_to_transcribe_with_paths(st.session_state, output_paths)
        st.rerun()
