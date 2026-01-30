from __future__ import annotations

from typing import TYPE_CHECKING

from transcriptx.core.utils.config import get_config

from .controller import (
    ENGINE_AUTO,
    ENGINE_WHISPERCPP,
    ENGINE_WHISPERX,
    list_recordings,
    run_transcription,
)

if TYPE_CHECKING:
    import gradio as gr


def _model_choices() -> list[str]:
    config = get_config()
    default_model = getattr(config.transcription, "model_name", "large-v2")
    candidates = [
        default_model,
        "large-v2",
        "medium",
        "small",
        "base",
        "tiny",
    ]
    seen = set()
    choices = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            choices.append(item)
    return choices


def build_app() -> "gr.Blocks":
    # Lazy import: TranscriptX should be usable without UI deps installed.
    import gradio as gr

    with gr.Blocks(title="TranscriptX UI") as demo:
        gr.Markdown("# TranscriptX Local UI")
        gr.Markdown(
            "Upload an audio file or select one from `data/recordings`, then start transcription."
        )

        with gr.Row():
            upload = gr.File(label="Upload audio file", file_count="single")
            recordings = gr.Dropdown(
                label="Select from recordings",
                choices=list_recordings(),
                interactive=True,
            )

        refresh = gr.Button("Refresh recordings")

        with gr.Row():
            engine = gr.Dropdown(
                label="Engine",
                choices=[ENGINE_AUTO, ENGINE_WHISPERX, ENGINE_WHISPERCPP],
                value=ENGINE_AUTO,
            )
            model = gr.Dropdown(
                label="Model (optional)",
                choices=_model_choices(),
                value=None,
                allow_custom_value=True,
            )
            language = gr.Dropdown(
                label="Language (optional)",
                choices=["Auto", "en", "fr", "es", "de", "it", "pt", "nl"],
                value="Auto",
            )

        start = gr.Button("Start Transcription", variant="primary")

        logs = gr.Textbox(label="Logs", lines=14, interactive=False)
        transcript_path = gr.Textbox(
            label="Transcript JSON Path", interactive=False
        )
        preview = gr.Textbox(label="Preview", lines=12, interactive=False)
        notes = gr.Textbox(label="Notes", lines=4, interactive=False)

        refresh.click(
            fn=lambda: gr.Dropdown.update(choices=list_recordings()),
            inputs=[],
            outputs=[recordings],
        )

        start.click(
            fn=run_transcription,
            inputs=[upload, recordings, engine, model, language],
            outputs=[logs, transcript_path, preview, notes],
        )

    return demo


def main(host: str = "127.0.0.1", port: int = 7860, open_browser: bool = True) -> None:
    app = build_app()
    app.launch(server_name=host, server_port=port, inbrowser=open_browser)
