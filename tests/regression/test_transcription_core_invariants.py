"""Regression: transcription-related forbidden strings must not appear in core/."""

from __future__ import annotations

import os

import pytest


def _collect_py_files(root: str, exclude_dirs: frozenset):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for f in filenames:
            if f.endswith(".py"):
                out.append(os.path.join(dirpath, f))
    return out


@pytest.mark.unit
def test_no_hf_token_or_whisperx_or_docker_in_core():
    base = os.path.join(
        os.path.dirname(__file__), "..", "..", "src", "transcriptx", "core"
    )
    exclude = frozenset({"__pycache__", ".mypy_cache"})
    files = _collect_py_files(base, exclude)
    docker_patterns = ("docker exec", "docker cp", "docker compose", "docker run")
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
        content = raw.lower()
        rel = os.path.relpath(path, base)
        assert "hf_token" not in content, f"hf_token found in core/{rel}"
        assert "HF_TOKEN" not in raw, f"HF_TOKEN found in core/{rel}"
        assert "whisperx" not in content, f"whisperx found in core/{rel}"
        for pat in docker_patterns:
            assert pat not in content, f"{pat!r} found in core/{rel}"
