"""Optional live Ollama tests for Corrections Studio LLM discovery.

Skipped unless ``TRANSCRIPTX_LLM_LIVE_TEST=1``. Exercises a diverse installed
model matrix (small/mid/large/thinking) with soft assertions for thinking
models that currently fail closed on empty ``response``.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.services.corrections_studio.llm.contract import (
    SYSTEM_PROMPT,
    build_discovery_instruction,
    parse_discovery_json,
)
from transcriptx.services.corrections_studio.llm.discovery import run_llm_discovery
from transcriptx.core.utils.config.main import TranscriptXConfig
from tests.core.llm.ollama_live_helpers import (
    installed_ollama_models,
    live_base_url,
    select_diverse_models,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_api,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.getenv("TRANSCRIPTX_LLM_LIVE_TEST", "").strip().lower()
        not in ("1", "true", "yes", "on"),
        reason="Set TRANSCRIPTX_LLM_LIVE_TEST=1 to run live Corrections Studio LLM tests",
    ),
]


def _tiny_segments() -> list[dict]:
    return [
        {
            "speaker": "Alice",
            "text": "Welcome to the Riksjokummo announcement today.",
            "start": 0.0,
            "end": 2.0,
        },
        {
            "speaker": "Bob",
            "text": "We use NER for entity recognition at Jukon National.",
            "start": 2.0,
            "end": 5.0,
        },
    ]


def _corrections_llm_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        effort="low",
        request_timeout_seconds=120.0,
        total_wall_clock_seconds=180.0,
        chunk_max_segments=40,
        chunk_overlap_segments=0,
        max_candidates_per_chunk=5,
        max_candidates_per_transcript=20,
        max_chunks=2,
        continue_on_failure=True,
        assess_deterministic=False,
    )


def _llm_cfg(model: str) -> SimpleNamespace:
    base = TranscriptXConfig().llm
    return SimpleNamespace(
        enabled=True,
        provider="ollama",
        model=model,
        base_url=live_base_url(),
        default_temperature=0.0,
        request_timeout=getattr(base, "request_timeout", 120.0),
        availability_timeout=getattr(base, "availability_timeout", 5.0),
        max_input_chars=getattr(base, "max_input_chars", 120000),
        max_output_tokens=getattr(base, "max_output_tokens", 2048),
        seed=42,
    )


@pytest.mark.timeout(1800)
def test_live_corrections_discovery_across_diverse_models() -> None:
    installed = installed_ollama_models(live_base_url())
    assert installed, "Ollama /api/tags returned no models"
    selected_models = select_diverse_models(installed, max_models=4)
    assert selected_models

    segments = _tiny_segments()
    for selected in selected_models:
        result = run_llm_discovery(
            segments=segments,
            transcript_key="live-tk",
            llm_cfg=_llm_cfg(selected.name),
            corrections_llm=_corrections_llm_cfg(),
            speaker_names=["Alice", "Bob"],
            memory_pairs=[],
            known_acronyms=["NER"],
            known_org_phrases={},
        )
        diag = result.diagnostics
        assert diag.enabled is True
        assert diag.attempted is True

        if selected.thinking and diag.outcome in {"failed", "unavailable"}:
            # Thinking models may emit empty response; fail-closed is expected.
            assert diag.error_code in {
                "llm_invalid_response",
                "llm_unavailable",
                "llm_timeout",
                "llm_generation_error",
            }
            continue

        assert diag.available is True, selected.name
        assert diag.outcome in {"success", "partial", "failed"}, selected.name
        if diag.outcome == "failed":
            # Non-thinking models should still be diagnosable; soft-skip only if
            # the model returned unusable JSON after a successful transport.
            assert diag.error_code == "llm_invalid_response", selected.name
            continue

        assert diag.chunks_succeeded >= 1 or diag.chunks_failed >= 1, selected.name
        # Parsed candidates (possibly empty after grounding) are a list.
        assert isinstance(result.candidates, list), selected.name


@pytest.mark.timeout(600)
def test_live_corrections_discovery_generate_and_parse_smoke() -> None:
    """One-chunk generate + parse against preferred non-thinking mid model."""
    from transcriptx.core.analysis.llm_support.runtime import (
        build_ollama_analysis_client,
        resolve_llm_runtime,
    )

    installed = installed_ollama_models(live_base_url())
    preferred = ("gemma3:12b", "qwen2.5:7b", "llama3.2:3b", "mistral:latest")
    model = next((name for name in preferred if name in installed), None)
    if model is None:
        pytest.skip("No preferred non-thinking model installed for discovery smoke")

    llm_cfg = _llm_cfg(model)
    runtime = resolve_llm_runtime(llm_cfg=llm_cfg, effort="low")
    client = build_ollama_analysis_client(llm_cfg=llm_cfg, runtime=runtime)
    if not client.is_available():
        pytest.skip("Ollama unavailable")

    instruction = build_discovery_instruction(max_candidates=3)
    prompt = (
        f"{instruction}\n\n"
        "[0] Alice: Welcome to the Riksjokummo announcement today.\n"
        "[1] Bob: We use NER for entity recognition at Jukon National.\n"
    )
    try:
        raw = client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=runtime.max_output_tokens,
        )
    except LLMResponseError as exc:
        pytest.fail(
            f"Non-thinking model {model!r} returned empty/invalid transport: {exc}"
        )

    assert isinstance(raw, str) and raw.strip()
    parsed = parse_discovery_json(raw)
    assert isinstance(parsed, list)
