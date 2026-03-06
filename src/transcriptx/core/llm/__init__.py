"""
LLM integration for TranscriptX.

This module provides a pluggable interface for LLM providers, enabling
future integration with OpenAI, Ollama, and other LLM services.

Note: This is infrastructure-only. No UI integration yet. Future modules
(summarization, action items, speaker briefs) will use this interface
with strict provenance and caching.
"""

from .llm_client import LLMClient, NullLLMClient

__all__ = ["LLMClient", "NullLLMClient"]
