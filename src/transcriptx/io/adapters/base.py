"""Base IO adapter errors for unsupported formats."""


class UnsupportedFormatError(ValueError):
    """Raised when no adapter can handle the input file."""


__all__ = ["UnsupportedFormatError"]
