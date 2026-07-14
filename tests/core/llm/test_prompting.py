"""Unit tests for dependency-neutral prompt-envelope primitives."""

from __future__ import annotations

import pytest

from transcriptx.core.llm.errors import LLMConfigurationError
from transcriptx.core.llm.prompting import (
    DEFAULT_CLOSE_DELIMITER,
    DEFAULT_OPEN_DELIMITER,
    build_prompt_envelope,
    llm_prompt_overhead_chars,
    prompt_envelope_min_chars,
    require_prompt_budget,
)


@pytest.mark.unit
def test_build_prompt_envelope_shape() -> None:
    prefix, suffix = build_prompt_envelope(instruction="Summarise:")
    assert prefix.startswith("Summarise:\n\n")
    assert prefix.endswith(f"{DEFAULT_OPEN_DELIMITER}\n")
    assert suffix == f"\n{DEFAULT_CLOSE_DELIMITER}"


@pytest.mark.unit
def test_overhead_equals_envelope_length() -> None:
    prefix, suffix = build_prompt_envelope(instruction="Do the thing.")
    assert llm_prompt_overhead_chars(instruction="Do the thing.") == len(prefix) + len(
        suffix
    )


@pytest.mark.unit
def test_prompt_envelope_min_chars_is_instructionless_overhead() -> None:
    assert prompt_envelope_min_chars() == llm_prompt_overhead_chars(instruction="")
    # Any non-empty instruction strictly increases the overhead.
    assert (
        llm_prompt_overhead_chars(instruction="x") > prompt_envelope_min_chars()
    )


@pytest.mark.unit
def test_require_prompt_budget_passes_at_exact_overhead() -> None:
    overhead = llm_prompt_overhead_chars(instruction="Summarise:")
    require_prompt_budget(
        max_input_chars=overhead,
        instruction="Summarise:",
        module_name="llm_summary",
    )


@pytest.mark.unit
def test_require_prompt_budget_rejects_below_overhead() -> None:
    overhead = llm_prompt_overhead_chars(instruction="Summarise:")
    with pytest.raises(LLMConfigurationError, match="llm_summary") as exc:
        require_prompt_budget(
            max_input_chars=overhead - 1,
            instruction="Summarise:",
            module_name="llm_summary",
        )
    assert "prompt wrapper overhead" in str(exc.value)
