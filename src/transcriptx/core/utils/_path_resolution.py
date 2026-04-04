"""
Public path resolution API.

Implementation is delegated to :class:`transcriptx.core.utils.path_resolver.PathResolver`.
"""

from __future__ import annotations

from typing import Literal


def resolve_file_path(
    file_path: str,
    file_type: Literal["transcript", "audio", "output_dir"] = "transcript",
    validate_state: bool = True,
    use_cache: bool = True,
) -> str:
    """
    Resolve a file path using the default PathResolver.

    This is a thin façade over ``get_default_resolver().resolve``; all strategy
    logic lives in PathResolver and its strategies.
    """
    from transcriptx.core.utils.path_resolver import get_default_resolver

    return get_default_resolver().resolve(
        file_path, file_type, validate_state=validate_state, use_cache=use_cache
    )
