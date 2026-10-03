"""RAG feature-flag and embed URL parsing (no LanceDB)."""

from __future__ import annotations

from transcriptx.core.rag.flags import ollama_base_url_from_env, parse_rag_enabled
from transcriptx.core.rag.index import sql_string


def test_parse_rag_enabled_accepts_truthy_set() -> None:
    for raw in ("1", "true", "TRUE", "yes", "on", " On "):
        assert parse_rag_enabled(raw) is True


def test_parse_rag_enabled_rejects_other_values() -> None:
    for raw in (None, "", "0", "false", "off", "2", "enabled"):
        assert parse_rag_enabled(raw) is False


def test_ollama_url_falls_back_to_llm_then_localhost(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSCRIPTX_LLM_BASE_URL", raising=False)
    assert ollama_base_url_from_env() == "http://localhost:11434"

    monkeypatch.setenv("TRANSCRIPTX_LLM_BASE_URL", "http://llm.example:11434")
    assert ollama_base_url_from_env() == "http://llm.example:11434"

    monkeypatch.setenv("TRANSCRIPTX_OLLAMA_BASE_URL", "http://embed.example:11434")
    assert ollama_base_url_from_env() == "http://embed.example:11434"


def test_sql_string_escapes_quotes_and_backslashes() -> None:
    assert sql_string("plain") == "'plain'"
    assert sql_string("o'clock") == "'o''clock'"
    assert sql_string("a\\b") == "'a\\\\b'"
