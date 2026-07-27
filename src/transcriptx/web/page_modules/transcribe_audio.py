"""
Transcribe Audio — parameterised command generator for external transcription.

Commands are copyable only; Streamlit never executes transcription for 1.0.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.core.utils.paths import PATHS
from transcriptx.services.transcription.command_gen import (
    DEFAULT_TRANSCRIPTION_MODEL,
    TRANSCRIPTION_MODEL_OPTIONS,
    CommandGenParams,
    TranscriptionTool,
    default_host_env_file,
    default_host_script_ref,
    generate_preview_lines,
    generate_transcription_command,
    looks_like_container_install_path,
)
from transcriptx.web.navigation import consume_transcription_nav_paths
from transcriptx.web.state import PAGE_KEY

_ENV_FILE_DEFAULT = default_host_env_file(PATHS.project_root)
_SCRIPT_REF = default_host_script_ref(PATHS.project_root)

_TOOL_LABELS = {
    TranscriptionTool.WHISPERMLX_SINGLE: "whispermlx (macOS host)",
    TranscriptionTool.WHISPERMLX_MISSING: "whispermlx-missing (skip existing JSON)",
    TranscriptionTool.WHISPERX_DOCKER: "WhisperX Docker (external recipe)",
    TranscriptionTool.WHISPER_WEBUI_DOCKER: "Whisper-WebUI Docker (Gradio)",
}

_DEFAULT_WEBUI_IMAGE = "jhj0517/whisper-webui:v1.0.8-4def223"
_DEFAULT_WHISPERX_IMAGE = "ghcr.io/m-bain/whisperx:latest"


def render_transcribe_audio_page() -> None:
    """Render external transcription command generator (copy-only)."""
    st.markdown(
        '<div class="main-header">Transcribe Audio</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Transcription runs **outside** the TranscriptX web app. "
        "Generate a copyable command below, run it on the **host** terminal "
        "(not inside the Linux analysis container for whispermlx), "
        "then open **Import Transcript** to add JSON to your library."
    )

    hint_paths = consume_transcription_nav_paths(st.session_state)
    default_input = ""
    if hint_paths:
        st.markdown("**Audio file(s) suggested from navigation**")
        for path_str in hint_paths:
            st.code(path_str, language=None)
        default_input = hint_paths[0]
        st.caption("These paths are prefilled below when present. Adjust as needed.")

    st.subheader("Command generator")
    st.caption(
        "Copy and paste only — TranscriptX does not execute these commands from Streamlit."
    )

    tool_label = st.selectbox(
        "Tool",
        options=list(_TOOL_LABELS.values()),
        index=1 if not default_input else 0,
        key="tx_cmdgen_tool",
    )
    tool = next(t for t, label in _TOOL_LABELS.items() if label == tool_label)
    if tool is TranscriptionTool.WHISPERMLX_MISSING:
        st.caption(
            "Host install once: "
            "`install -m 755 scripts/whispermlx-missing.py ~/.local/bin/whispermlx-missing` "
            "(needs `~/.local/bin` on PATH). Or run "
            "`python3 scripts/whispermlx-missing.py …`. "
            "See Bulk helper below / `docs/runtime/transcription.md`."
        )
    if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER:
        st.caption(
            "Optional third-party recipe: "
            "[jhj0517/Whisper-WebUI](https://github.com/jhj0517/Whisper-WebUI) "
            "(Apache-2.0). TranscriptX does not own or guarantee the service — see "
            "`docs/recipes/whisper-webui/README.md`. "
            "**Apple Silicon: expect CPU inference** (prefer whispermlx for MLX speed). "
            "Export **SRT/VTT** → **Import Transcript**."
        )

    col_a, col_b = st.columns(2)
    with col_a:
        input_help = (
            "Not used for Whisper-WebUI deploy (upload audio in the Gradio UI). "
            "Kept for navigation hints."
            if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER
            else "Absolute path preferred. Spaces are quoted in the generated command."
        )
        input_path = st.text_input(
            "Input file or folder",
            value=default_input or "/path/to/audio",
            key="tx_cmdgen_input",
            help=input_help,
            disabled=tool is TranscriptionTool.WHISPER_WEBUI_DOCKER,
        )
        output_label = (
            "Output folder (SRT/VTT downloads)"
            if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER
            else "Output folder (JSON)"
        )
        output_dir = st.text_input(
            output_label,
            value="/path/to/transcript/output",
            key="tx_cmdgen_output",
        )
        env_file = _ENV_FILE_DEFAULT
        if tool is not TranscriptionTool.WHISPER_WEBUI_DOCKER:
            # Drop stale session values that pointed at the Docker install tree.
            existing_env = st.session_state.get("tx_cmdgen_env")
            if isinstance(existing_env, str) and looks_like_container_install_path(
                existing_env
            ):
                st.session_state["tx_cmdgen_env"] = _ENV_FILE_DEFAULT
            env_file = st.text_input(
                "Env file (host)",
                value=_ENV_FILE_DEFAULT,
                key="tx_cmdgen_env",
                help=(
                    "Host path to repo-root whisperx.env for the Mac terminal command. "
                    "Do not use container paths under /opt/venv — those do not exist on the host. "
                    "Relative whisperx.env works when you run the command from the git clone."
                ),
            )
            if looks_like_container_install_path(env_file):
                st.warning(
                    "Env file looks like a Docker/venv path. Use the host repo "
                    "`whisperx.env` (absolute host path, or `whisperx.env` from the clone)."
                )
        audio_glob = st.text_input(
            "Audio glob (folder loop)",
            value="*.mp3",
            key="tx_cmdgen_glob",
            disabled=tool is not TranscriptionTool.WHISPERMLX_SINGLE,
        )
    with col_b:
        model_help = (
            "Suggested Gradio UI model (written as a comment in the deploy snippet). "
            "Actual selection is in the browser after launch."
            if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER
            else (
                "Whisper model size for the host command. "
                "Pick a listed option or type another engine-supported name."
            )
        )
        model = st.selectbox(
            "Model",
            options=list(TRANSCRIPTION_MODEL_OPTIONS),
            index=TRANSCRIPTION_MODEL_OPTIONS.index(DEFAULT_TRANSCRIPTION_MODEL),
            key="tx_cmdgen_model",
            accept_new_options=True,
            help=model_help,
        )
        language = st.text_input("Language", value="en", key="tx_cmdgen_language")
        diarize = st.checkbox("Diarize", value=True, key="tx_cmdgen_diarize")
        dry_run = st.checkbox(
            "Dry-run / preview flags",
            value=False,
            key="tx_cmdgen_dry",
            disabled=tool is not TranscriptionTool.WHISPERMLX_MISSING,
            help="Adds --dry-run for whispermlx-missing (safe preview).",
        )
        force = st.checkbox(
            "Force / overwrite existing JSON",
            value=False,
            key="tx_cmdgen_force",
            disabled=tool is not TranscriptionTool.WHISPERMLX_MISSING,
        )
        fuzzy = st.checkbox(
            "Fuzzy JSON match (skip variants)",
            value=False,
            key="tx_cmdgen_fuzzy",
            disabled=tool is not TranscriptionTool.WHISPERMLX_MISSING,
        )

    whispermlx_binary = "whispermlx"
    device = "cpu"
    compute_type = "float16"
    batch_size = 16
    min_speakers: int | None = None
    max_speakers: int | None = None
    docker_image = _DEFAULT_WHISPERX_IMAGE
    webui_port = 7860
    webui_clone_dir = "$HOME/Whisper-WebUI"
    expected_output_format = "whisperx_json"
    if tool is TranscriptionTool.WHISPERMLX_SINGLE:
        whispermlx_binary = st.text_input(
            "whispermlx binary",
            value="whispermlx",
            key="tx_cmdgen_bin",
            help="PATH name or absolute path. Overridden by WHISPERMLX in the env file when set.",
        )
    if tool is TranscriptionTool.WHISPERX_DOCKER:
        device = st.selectbox(
            "Device",
            options=["cpu", "cuda"],
            index=0,
            key="tx_cmdgen_device",
        )
        compute_type = st.selectbox(
            "Compute type",
            options=["float16", "int8", "float32"],
            index=0 if device == "cuda" else 1,
            key="tx_cmdgen_compute",
        )
        batch_size = int(
            st.number_input(
                "Batch size",
                min_value=1,
                max_value=64,
                value=16,
                key="tx_cmdgen_batch",
            )
        )
        use_speaker_bounds = st.checkbox(
            "Set min/max speakers",
            value=False,
            key="tx_cmdgen_speaker_bounds",
        )
        if use_speaker_bounds:
            min_speakers = int(
                st.number_input(
                    "Min speakers",
                    min_value=1,
                    max_value=50,
                    value=1,
                    key="tx_cmdgen_min_spk",
                )
            )
            max_speakers = int(
                st.number_input(
                    "Max speakers",
                    min_value=1,
                    max_value=50,
                    value=20,
                    key="tx_cmdgen_max_spk",
                )
            )
    if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER:
        expected_output_format = "srt_vtt"
        docker_image = st.text_input(
            "Docker image",
            value=_DEFAULT_WEBUI_IMAGE,
            key="tx_cmdgen_webui_image",
            help="Pre-built Hub image, or build from the clone with docker compose.",
        )
        webui_port = int(
            st.number_input(
                "Host port",
                min_value=1,
                max_value=65535,
                value=7860,
                key="tx_cmdgen_webui_port",
            )
        )
        webui_clone_dir = st.text_input(
            "Clone directory (host)",
            value="$HOME/Whisper-WebUI",
            key="tx_cmdgen_webui_clone",
            help="Where to git clone jhj0517/Whisper-WebUI for models/configs volumes.",
        )
        device = st.selectbox(
            "Device",
            options=["cpu", "cuda"],
            index=0,
            key="tx_cmdgen_webui_device",
            help="cuda adds --gpus all to docker run.",
        )

    if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER:
        st.caption(
            "Expected output format: **SRT / WebVTT** "
            "(Import Transcript). Configure model/language/diarization in the Gradio UI."
        )
    else:
        st.caption(
            "Expected output format: **WhisperX / whispermlx JSON** "
            "(Import Transcript). Alternate formats are not generated here."
        )

    params = CommandGenParams(
        tool=tool,
        input_path=input_path.strip(),
        output_dir=output_dir.strip(),
        model=(str(model).strip() if model else "") or DEFAULT_TRANSCRIPTION_MODEL,
        language=language.strip() or "en",
        diarize=bool(diarize),
        env_file=env_file.strip() or "whisperx.env",
        whispermlx_binary=whispermlx_binary.strip() or "whispermlx",
        audio_glob=audio_glob.strip() or "*.mp3",
        force=bool(force),
        dry_run=bool(dry_run),
        fuzzy_json_match=bool(fuzzy),
        device=device,
        compute_type=compute_type,
        batch_size=batch_size,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        docker_image=docker_image.strip()
        or (
            _DEFAULT_WEBUI_IMAGE
            if tool is TranscriptionTool.WHISPER_WEBUI_DOCKER
            else _DEFAULT_WHISPERX_IMAGE
        ),
        webui_port=webui_port,
        webui_clone_dir=webui_clone_dir.strip() or "$HOME/Whisper-WebUI",
        expected_output_format=expected_output_format,
    )

    generated = generate_transcription_command(params)

    with st.expander("Preview", expanded=True):
        for line in generate_preview_lines(params):
            st.write(f"- {line}")

    st.markdown(f"**{generated.title}**")
    st.code(generated.shell, language="bash")
    for note in generated.notes:
        st.caption(f"• {note}")
    st.success(generated.next_step)

    st.subheader("Bulk helper reference")
    st.markdown(
        f"`whispermlx-missing` is **not** on PATH until you install "
        f"`{_SCRIPT_REF}` once from the **host** git clone. "
        "Or run `python3 scripts/whispermlx-missing.py …` from the repo root."
    )
    st.code(
        """mkdir -p ~/.local/bin
install -m 755 scripts/whispermlx-missing.py ~/.local/bin/whispermlx-missing
# ensure ~/.local/bin is on PATH, then:
which whispermlx-missing

cp config/whispermlx-missing.example.json .transcriptx/whispermlx-missing.json
# edit paths, then:
whispermlx-missing --dry-run
whispermlx-missing""",
        language="bash",
    )

    st.subheader("Import into TranscriptX")
    st.markdown(
        "When transcription finishes, open **Import Transcript** and upload the result "
        "(WhisperX / whispermlx JSON, Whisper-WebUI **SRT/VTT**, and other supported formats). "
        "Optionally attach the source recording on that page for speaker ID and "
        "audio-derived features; same-stem audio in the mounted recordings folder "
        "will be linked."
    )
    if st.button(
        "Go to Import Transcript →", type="primary", key="transcribe_goto_import"
    ):
        st.session_state[PAGE_KEY] = "Import Transcript"
        st.rerun()

    with st.expander("Host vs Docker boundaries", expanded=False):
        st.markdown("""
| Where | What runs |
|-------|-----------|
| Host (Mac terminal) | `whispermlx`, `whispermlx-missing` |
| Host (Linux/GPU or Docker Desktop) | WhisperX Docker; Whisper-WebUI Gradio |
| `transcriptx-web` (Docker or native) | Import, library, analysis only |

**whispermlx** needs Apple MLX and cannot run inside the Linux analysis image.
See `docs/runtime/transcription.md`, `docs/recipes/whisperx/README.md`, and
`docs/recipes/whisper-webui/README.md`.
""")
