"""
Configuration provider system for dependency injection.

This module provides a flexible configuration system that supports:
- Thread-local configuration (for backward compatibility)
- Dependency injection (for testing and multi-tenant scenarios)
- Context managers for temporary configuration
"""

import threading
from contextlib import contextmanager
from typing import Optional, Protocol

from transcriptx.core.utils.config import TranscriptXConfig


class ConfigProvider(Protocol):
    """
    Protocol for configuration providers.

    This allows any object that provides a get_config() method
    to be used as a configuration source.
    """

    def get_config(self) -> TranscriptXConfig:
        """Get the current configuration."""
        ...


class ThreadLocalConfigProvider:
    """
    Configuration provider that uses thread-local storage.

    This provides backward compatibility with the global config
    while supporting per-thread configuration.
    """

    def __init__(self):
        """Initialize thread-local storage."""
        self._local = threading.local()
        self._default_config: Optional[TranscriptXConfig] = None

    def get_config(self) -> TranscriptXConfig:
        """
        Get configuration for current thread.

        Returns:
            Thread-local config if set, otherwise default/global config
        """
        # Check thread-local storage first
        if hasattr(self._local, "config") and self._local.config is not None:
            return _ensure_dashboard_config(self._local.config)

        # Fall back to default/global config
        if self._default_config is None:
            from transcriptx.core.utils.config import get_config as get_global_config

            self._default_config = get_global_config()

        return _ensure_dashboard_config(self._default_config)


def _ensure_dashboard_config(config: TranscriptXConfig) -> TranscriptXConfig:
    if hasattr(config, "dashboard"):
        return config
    from transcriptx.core.utils.config.workflow import DashboardConfig

    config.dashboard = DashboardConfig()
    return config

    def set_config(self, config: TranscriptXConfig) -> None:
        """
        Set configuration for current thread.

        Args:
            config: Configuration to set for current thread
        """
        self._local.config = config

    def clear_config(self) -> None:
        """Clear thread-local configuration (revert to default)."""
        if hasattr(self._local, "config"):
            delattr(self._local, "config")

    @contextmanager
    def with_config(self, config: TranscriptXConfig):
        """
        Context manager for temporary configuration.

        Useful for testing or temporarily overriding configuration.

        Args:
            config: Configuration to use within context

        Example:
            with provider.with_config(test_config):
                # Use test_config here
                result = some_function()
        """
        old_config = getattr(self._local, "config", None)
        try:
            self.set_config(config)
            yield config
        finally:
            if old_config is None:
                self.clear_config()
            else:
                self.set_config(old_config)


# Global thread-local provider instance
_thread_local_provider: Optional[ThreadLocalConfigProvider] = None


def get_config_provider() -> ThreadLocalConfigProvider:
    """Get the global thread-local config provider."""
    global _thread_local_provider
    if _thread_local_provider is None:
        _thread_local_provider = ThreadLocalConfigProvider()
    return _thread_local_provider


def get_config() -> TranscriptXConfig:
    """
    Get configuration using thread-local provider.

    This function maintains backward compatibility with the old
    global config while supporting thread-local configuration.

    Returns:
        Current thread's configuration
    """
    return get_config_provider().get_config()


def set_config(config: TranscriptXConfig) -> None:
    """
    Set configuration for current thread.

    Args:
        config: Configuration to set
    """
    get_config_provider().set_config(config)


@contextmanager
def with_config(config: TranscriptXConfig):
    """
    Context manager for temporary configuration.

    This is the main API for dependency injection in tests.

    Args:
        config: Configuration to use within context

    Example:
        test_config = TranscriptXConfig()
        with with_config(test_config):
            # Use test_config here
            result = some_function()
    """
    provider = get_config_provider()
    with provider.with_config(config):
        yield config
