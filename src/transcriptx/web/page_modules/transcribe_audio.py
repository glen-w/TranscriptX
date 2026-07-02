"""
Transcribe Audio — instructions for external transcription (whispermlx / CLI).
"""

from __future__ import annotations


import streamlit as st

from transcriptx.core.utils.paths import PATHS
from transcriptx.web.navigation import consume_transcription_nav_paths
from transcriptx.web.state import PAGE_KEY

_REPO_ROOT = PATHS.project_root
_ENV_FILE = _REPO_ROOT / "whisperx.env"
_SCRIPT = _REPO_ROOT / "scripts" / "whispermlx-missing.py"


def _shell_batch_example() -> str:
    return f"""set -a
source "{_ENV_FILE}"
set +a

WHISPERMLX="${{WHISPERMLX:-$(command -v whispermlx)}}"
AUDIO_DIR="/path/to/audio"          # folder of .mp3 (or other) files
OUTDIR="/path/to/transcript/output" # whispermlx JSON output directory

mkdir -p "$OUTDIR"

for f in "$AUDIO_DIR"/*.mp3; do
    echo "Processing: $(basename "$f")"
    "$WHISPERMLX" "$f" \\
        --output_dir "$OUTDIR" \\
        --language en \\
        --model large-v3 \\
        --diarize \\
        --hf_token "$HF_TOKEN"
done"""


def render_transcribe_audio_page() -> None:
    """Render external transcription instructions."""
    st.markdown(
        '<div class="main-header">🎙️ Transcribe Audio</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Transcription runs **outside** the TranscriptX web app. "
        "Run whispermlx on the command line (or use the bulk helper script), "
        "then return here and open **Import Transcript** to add JSON to your library."
    )

    hint_paths = consume_transcription_nav_paths(st.session_state)
    if hint_paths:
        st.markdown("**Audio file(s) to transcribe**")
        for path_str in hint_paths:
            st.code(path_str, language=None)
        st.caption(
            "Use one of the workflows below with these paths, then import the "
            "resulting JSON files."
        )

    st.subheader("1. Transcribe on the command line")
    st.markdown(
        "On **macOS**, use **whispermlx** with your `whisperx.env` at the repo root. "
        "Set `HF_TOKEN` in that file when diarization is enabled. "
        "If `whispermlx` is not on PATH, set `WHISPERMLX` in `whisperx.env` to the full binary path."
    )
    st.code(_shell_batch_example(), language="bash")

    st.subheader("2. Bulk: files missing transcripts")
    st.markdown(
        f"For folders of audio where some files already have JSON transcripts, use "
        f"[`scripts/whispermlx-missing.py`]({_SCRIPT}) (install as `whispermlx-missing`). "
        "It skips stems that already have matching JSON in your transcripts folder."
    )
    st.code(
        """# First-time setup: copy config/whispermlx-missing.example.json to
# .transcriptx/whispermlx-missing.json and edit paths (gitignored).
cp config/whispermlx-missing.example.json .transcriptx/whispermlx-missing.json

# Or save paths once from the CLI:
whispermlx-missing \\
    --source /path/to/audio \\
    --transcripts /path/to/transcripts/originals \\
    --env-file whisperx.env \\
    --save-config

# Normal run (uses .transcriptx/whispermlx-missing.json when run from repo)
whispermlx-missing

# Standalone / custom config path:
whispermlx-missing --config /path/to/whispermlx-missing.json""",
        language="bash",
    )
    st.caption(
        "See `scripts/whispermlx-missing.py --help` for dry-run, fuzzy JSON matching, "
        "and extra whispermlx flags."
    )

    st.subheader("3. Import into TranscriptX")
    st.markdown(
        "When transcription finishes, open **Import Transcript** and upload the JSON "
        "(WhisperX / whispermlx output, SRT, VTT, and other supported formats). "
        "Optionally attach the source recording on that page for speaker ID and "
        "audio-derived features."
    )
    if st.button(
        "Go to Import Transcript →", type="primary", key="transcribe_goto_import"
    ):
        st.session_state[PAGE_KEY] = "Import Transcript"
        st.rerun()

    with st.expander("WhisperX Docker (other platforms)", expanded=False):
        st.markdown(
            "For non-macOS hosts or Docker-based WhisperX, see "
            "`docs/recipes/whisperx/README.md` and `docs/runtime/transcription.md`. "
            "Import the output JSON the same way via **Import Transcript**."
        )
