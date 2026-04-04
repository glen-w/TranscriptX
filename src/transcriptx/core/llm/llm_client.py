"""
Abstract LLM client interface for TranscriptX.

This module provides a pluggable abstraction for LLM providers, allowing
future integration with OpenAI, Ollama, and other LLM services without
requiring changes to analysis modules that use LLM capabilities.
"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMClient(ABC):
    """
    Abstract interface for LLM providers.

    This interface allows analysis modules to use LLM capabilities without
    being tied to a specific provider. Implementations should handle:
    - Provider-specific API calls
    - Error handling and retries
    - Rate limiting
    - Token counting
    - Caching (if applicable)
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: User prompt text
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text

        Raises:
            RuntimeError: If LLM client is not configured or available
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if LLM client is configured and available.

        Returns:
            True if client is available, False otherwise
        """
        pass


class NullLLMClient(LLMClient):
    """
    Stub implementation that is always disabled.

    This is the default implementation when no LLM provider is configured.
    All methods raise RuntimeError to prevent accidental usage.
    """

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Raise error - LLM client not configured."""
        raise RuntimeError(
            "LLM client not configured. Please configure an LLM provider in the config file."
        )

    def is_available(self) -> bool:
        """Always returns False - client is not available."""
        return False
