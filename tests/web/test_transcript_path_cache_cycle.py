"""FileService must not import cache_helpers (breaks the listing/resolve cycle)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


@pytest.mark.unit
def test_file_service_does_not_import_cache_helpers() -> None:
    path = Path("src/transcriptx/web/services/file_service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module != "transcriptx.web.cache_helpers"
            assert not node.module.startswith("transcriptx.web.cache_helpers.")
            assert node.module != "transcriptx.web.services.transcript_path_cache"


@pytest.mark.unit
def test_cache_helpers_reexports_path_cache() -> None:
    from transcriptx.web.cache_helpers import cached_resolve_transcript_path
    from transcriptx.web import transcript_path_cache

    assert (
        cached_resolve_transcript_path
        is transcript_path_cache.cached_resolve_transcript_path
    )
