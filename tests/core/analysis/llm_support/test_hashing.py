"""Golden tests for hashing persistence identities."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.hashing import (
    sha256_canonical_json,
    sha256_llm_request,
    sha256_text,
)


@pytest.mark.unit
def test_sha256_text_golden() -> None:
    assert (
        sha256_text("hello world")
        == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


@pytest.mark.unit
def test_sha256_canonical_json_golden() -> None:
    assert (
        sha256_canonical_json({"b": 1, "a": [1, 2]})
        == "94a786c3662bc7beeb598efa7d8cb58d7bea25d6c275ea9785a0230ff1f8c2ba"
    )
    # Key order must not matter (canonical sort).
    assert sha256_canonical_json({"a": [1, 2], "b": 1}) == sha256_canonical_json(
        {"b": 1, "a": [1, 2]}
    )


@pytest.mark.unit
def test_sha256_llm_request_golden_without_system_prompt() -> None:
    assert (
        sha256_llm_request("summarise this")
        == "5061607beea1c747623a65c515dad5868a60665b9f73446a93620cafaa67b218"
    )


@pytest.mark.unit
def test_sha256_llm_request_golden_with_system_prompt() -> None:
    assert (
        sha256_llm_request("summarise this", system_prompt="be brief")
        == "3042580493707bf22039afda5f64952ad59e8e9da24f43e03ff4c46f463061cb"
    )


@pytest.mark.unit
def test_sha256_llm_request_includes_system_prompt() -> None:
    user_only = sha256_llm_request("user")
    with_system = sha256_llm_request("user", system_prompt="sys")
    assert user_only != with_system
