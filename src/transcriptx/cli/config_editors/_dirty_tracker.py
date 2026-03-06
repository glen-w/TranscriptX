"""Shared dirty tracking for configuration editors."""

_settings_dirty = False


def mark_dirty() -> None:
    """Mark settings as dirty (modified)."""
    global _settings_dirty
    _settings_dirty = True


def is_dirty() -> bool:
    """Check if settings are dirty (modified)."""
    return _settings_dirty


def reset_dirty() -> None:
    """Reset dirty flag."""
    global _settings_dirty
    _settings_dirty = False
