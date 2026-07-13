"""Tests for summary precedence helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from transcriptx.web.summary_precedence import (
    quiet_unavailable_message,
    resolve_primary_summary,
)


def test_llm_summary_wins_over_narrative() -> None:
    loader = MagicMock()
    loader.load_text.side_effect = lambda module, suffix, **kw: (
        "# LLM"
        if module == "llm_summary"
        else ("# Narr" if module == "narrative_summary" else None)
    )
    loader.load_json.return_value = {"summary": "x", "narrative": "y"}
    result = resolve_primary_summary(loader, run_root=None)
    assert result.primary is not None
    assert result.primary.kind == "llm_summary"
    assert any(c.kind == "narrative_summary" for c in result.others)


def test_falls_back_to_executive() -> None:
    loader = MagicMock()

    def _text(module, suffix, **kw):
        if module == "summary" and suffix.endswith(".md"):
            return "# Exec"
        return None

    def _json(module, suffix, **kw):
        if module == "summary":
            return {"summary": "exec"}
        return None

    loader.load_text.side_effect = _text
    loader.load_json.side_effect = _json
    result = resolve_primary_summary(loader, run_root=Path("/tmp"))
    assert result.primary is not None
    assert result.primary.kind == "executive_summary"


def test_unavailable_when_empty() -> None:
    loader = MagicMock()
    loader.load_text.return_value = None
    loader.load_json.return_value = None
    result = resolve_primary_summary(loader)
    assert result.primary is None


def test_none_loader_returns_unavailable() -> None:
    result = resolve_primary_summary(None)
    assert result.primary is None
    assert result.others == ()


def test_narrative_wins_when_llm_empty() -> None:
    loader = MagicMock()

    def _text(module, suffix, **kw):
        if module == "narrative_summary":
            return "# Narr"
        return None

    def _json(module, suffix, **kw):
        if module == "narrative_summary":
            return {"narrative": "story"}
        return None

    loader.load_text.side_effect = _text
    loader.load_json.side_effect = _json
    result = resolve_primary_summary(loader)
    assert result.primary is not None
    assert result.primary.kind == "narrative_summary"


def test_failed_module_not_chosen_as_primary() -> None:
    loader = MagicMock()

    def _text(module, suffix, **kw):
        if module == "llm_summary":
            return "# LLM"
        if module == "summary":
            return "# Exec"
        return None

    def _json(module, suffix, **kw):
        if module in {"llm_summary", "summary"}:
            return {"summary": "x"}
        return None

    loader.load_text.side_effect = _text
    loader.load_json.side_effect = _json
    with patch(
        "transcriptx.web.summary_precedence.module_outcome_state",
        side_effect=lambda _root, module, **kw: (
            "failed" if module == "llm_summary" else "succeeded"
        ),
    ):
        result = resolve_primary_summary(loader, run_root=Path("/tmp"))
    assert result.primary is not None
    assert result.primary.kind == "executive_summary"
    assert any(c.kind == "llm_summary" and c.outcome == "failed" for c in result.others)


def test_payload_without_text_field_still_available() -> None:
    loader = MagicMock()
    loader.load_text.return_value = None
    loader.load_json.side_effect = lambda module, suffix, **kw: (
        {"unexpected": "blob"} if module == "llm_summary" else None
    )
    result = resolve_primary_summary(loader)
    assert result.primary is not None
    assert result.primary.kind == "llm_summary"
    assert result.primary.available is True


def test_quiet_unavailable_message_for_outcomes() -> None:
    # Failed uses the same quiet unavailable wording as the default path.
    assert quiet_unavailable_message("Key themes", outcome="failed") == (
        "Key themes were unavailable for this run."
    )
    assert (
        "skipped" in quiet_unavailable_message("Key themes", outcome="skipped").lower()
    )
    assert (
        "blocked" in quiet_unavailable_message("Key themes", outcome="blocked").lower()
    )
    assert "unavailable" in quiet_unavailable_message("Key themes").lower()
