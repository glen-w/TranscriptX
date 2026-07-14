"""Compatibility re-export; canonical implementation lives in transcriptx.io.atomic_json."""

from transcriptx.io.atomic_json import (  # noqa: F401
    write_bytes_atomic,
    write_json_atomic,
)

__all__ = ["write_bytes_atomic", "write_json_atomic"]
