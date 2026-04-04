"""
Transcribe Audio — informational page (external transcription; no built-in engine).
"""

from __future__ import annotations

import streamlit as st

# Mirrors docs/transcription.md — WhisperX (optional reference example) subsection.
_WHISPERX_RECIPE_FROM_DOCS = """WhisperX is one example of an external transcription workflow. The recipe below is a standalone reference — optional, not required. Run WhisperX yourself (container or local), then feed the output into TranscriptX.

Copy-paste workflow: Use the reference recipe in docs/recipes/whisperx/README.md. From that directory:

cp whisperx.env.example whisperx.env
# Edit whisperx.env and set HF_TOKEN
# Start the stack (see README for the exact compose invocation; often docker-compose -f docker-compose.whisperx.yml up -d).

Single-container example (snippet; align flags with README):

# Run the image with --rm and the volume/env flags from docs/recipes/whisperx/README.md
# ghcr.io/jim60105/whisperx:no_model … whisperx /data/input/your_audio.wav --output_dir /data/output

WhisperX writes JSON with segments (often with words arrays). TranscriptX can load that format directly for analysis; for full canonical metadata, run import_transcript() (see below in docs/transcription.md)."""


def render_transcribe_audio_page() -> None:
    """Render guidance for obtaining transcript JSON via external tools (e.g. WhisperX)."""
    st.markdown(
        '<div class="main-header">🎙️ Transcribe Audio</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "TranscriptX does not currently provide integrated audio transcription. "
        "The recommended method is **WhisperX** (run separately), then import the "
        "resulting JSON into TranscriptX. Other tools that emit compatible JSON also work."
    )

    st.text(_WHISPERX_RECIPE_FROM_DOCS)
