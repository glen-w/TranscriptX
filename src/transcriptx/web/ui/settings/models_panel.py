"""Settings → Models panel — Ollama refresh, guidance, Model preset CRUD."""

from __future__ import annotations

from transcriptx.web.components.llm_model_selector import render_llm_models_settings_panel


def render_models_panel() -> None:
    """Render the Models settings subview."""
    render_llm_models_settings_panel()
