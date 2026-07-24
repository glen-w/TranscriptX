"""Packaging contracts for optional extras (metadata-only; no heavy installs)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


def _parse_optional_extra(name: str) -> list[str]:
    text = PYPROJECT.read_text(encoding="utf-8")
    # Match [project.optional-dependencies] block for `name = [ ... ]`
    pattern = rf"(?ms)^{re.escape(name)}\s*=\s*\[(.*?)\]"
    # Prefer scanning after optional-dependencies header
    opt_idx = text.find("[project.optional-dependencies]")
    assert opt_idx >= 0
    section = text[opt_idx:]
    match = re.search(pattern, section)
    assert match, f"extra {name!r} not found in pyproject.toml"
    body = match.group(1)
    reqs = []
    for line in body.splitlines():
        line = line.strip().strip(",").strip()
        if not line or line.startswith("#"):
            continue
        reqs.append(line.strip('"').strip("'"))
    return reqs


def _normalize_req(req: str) -> str:
    # Drop environment markers; keep name+specifier for subset compare.
    return req.split(";")[0].strip()


@pytest.mark.unit
def test_bertopic_extra_is_subset_of_full() -> None:
    bertopic = {_normalize_req(r) for r in _parse_optional_extra("bertopic")}
    full = {_normalize_req(r) for r in _parse_optional_extra("full")}
    missing = bertopic - full
    assert not missing, f"bertopic extra deps missing from full: {sorted(missing)}"


@pytest.mark.unit
def test_keyphrases_extra_is_subset_of_full() -> None:
    keyphrases = {_normalize_req(r) for r in _parse_optional_extra("keyphrases")}
    full = {_normalize_req(r) for r in _parse_optional_extra("full")}
    missing = keyphrases - full
    assert not missing, f"keyphrases extra deps missing from full: {sorted(missing)}"


@pytest.mark.unit
def test_bertopic_extra_is_compat_alias_for_base_stack() -> None:
    """``[bertopic]`` remains installable; packages are owned by base for now."""
    reqs = _parse_optional_extra("bertopic")
    joined = " ".join(reqs).lower()
    for forbidden in (
        "scikit-learn",
        "numpy",
        "scipy",
        "torch",
        "transformers",
        "sentence-transformers",
    ):
        assert forbidden not in joined, f"bertopic extra must not pin {forbidden}"
    assert any(r.startswith("bertopic") for r in reqs)
    assert any(r.startswith("hdbscan") for r in reqs)
    assert any(r.startswith("umap-learn") for r in reqs)


@pytest.mark.unit
def test_sentence_transformers_owned_by_base() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    deps_match = re.search(
        r"(?ms)^dependencies\s*=\s*\[(.*?)\]\s*\n\n\[project",
        text,
    )
    assert deps_match, "base dependencies block not found"
    body = deps_match.group(1).lower()
    assert "sentence-transformers" in body


@pytest.mark.unit
def test_bertopic_stack_owned_by_base() -> None:
    """Temporary default install: bertopic/hdbscan/umap-learn live in base deps."""
    text = PYPROJECT.read_text(encoding="utf-8")
    deps_match = re.search(
        r"(?ms)^dependencies\s*=\s*\[(.*?)\]\s*\n\n\[project",
        text,
    )
    assert deps_match, "base dependencies block not found"
    body = deps_match.group(1).lower()
    assert "bertopic" in body
    assert "hdbscan" in body
    assert "umap-learn" in body
