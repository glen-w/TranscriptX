"""Workflow 4: Local AI synthesis — Run Analysis LLM setup surface (offline-honest)."""

from __future__ import annotations

import pytest

from tests.e2e_gui.helpers import (
    goto_app,
    nav,
    page_text,
    select_transcript,
    wait,
)

pytestmark = [pytest.mark.gui_e2e, pytest.mark.heavy]


def test_local_ai_synthesis_surface(seeded_run_app, page) -> None:
    """
    Confirm Run Analysis exposes Local AI / LLM setup honestly when Ollama
    is unavailable (default CI / disable-downloads environment).

    Does not require a live Ollama daemon: asserts the readiness surface and
    that LLM module labels are discoverable for Custom / preset flows.
    """
    goto_app(page, seeded_run_app.base_url)
    select_transcript(page, needle="planning")

    nav(page, "Run Analysis")
    wait(page, 3000)
    body = page_text(page)
    assert "Run Analysis" in body or "Analysis preset" in body

    # Expand LLM setup if collapsed (expander / button).
    for label in ("LLM setup", "Local AI", "LLM"):
        ctrl = page.get_by_text(label, exact=False)
        if ctrl.count():
            try:
                ctrl.first.click(force=True)
                wait(page, 1500)
            except Exception:
                pass
            break

    body = page_text(page)
    llm_signals = (
        "LLM",
        "Ollama",
        "Local AI",
        "llm_summary",
        "LLM summary",
        "disabled",
        "not set",
        "Settings →",
        "Models",
        "provider",
    )
    assert any(s in body for s in llm_signals), (
        f"Expected LLM/Local AI readiness copy on Run Analysis; got head={body[:800]!r}"
    )
