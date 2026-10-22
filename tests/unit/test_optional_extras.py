"""Unit tests for optional-extra distribution probes (no heavy imports)."""

from __future__ import annotations

import importlib.metadata

import pytest

from transcriptx.core.pipeline.optional_extras import (
    EXTRA_DISTRIBUTION_NAME,
    distribution_name_for_extra,
    is_extra_distribution_present,
    resolve_extra_dependency_reason,
)


@pytest.mark.unit
def test_distribution_name_for_extra_known() -> None:
    assert distribution_name_for_extra("nlp") == "spacy"
    assert distribution_name_for_extra("bertopic") == "bertopic"


@pytest.mark.unit
def test_distribution_name_for_extra_unknown() -> None:
    assert distribution_name_for_extra("not_an_extra") is None


@pytest.mark.unit
def test_extra_distribution_catalogue_is_non_empty() -> None:
    assert "voice" in EXTRA_DISTRIBUTION_NAME
    assert EXTRA_DISTRIBUTION_NAME["emotion_lexical"] == "nrclex"


@pytest.mark.unit
def test_is_extra_distribution_present_true(monkeypatch) -> None:
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda _name: "1.0.0",
    )
    assert is_extra_distribution_present("nlp")


@pytest.mark.unit
def test_is_extra_distribution_present_missing(monkeypatch) -> None:
    def _missing(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", _missing)
    assert not is_extra_distribution_present("nlp")


@pytest.mark.unit
def test_is_extra_distribution_present_unknown_extra() -> None:
    assert not is_extra_distribution_present("unknown_extra_key")


@pytest.mark.unit
def test_resolve_extra_dependency_reason_present(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.optional_extras.is_extra_distribution_present",
        lambda _extra: True,
    )
    assert resolve_extra_dependency_reason("nlp") is None


@pytest.mark.unit
def test_resolve_extra_dependency_reason_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.pipeline.optional_extras.is_extra_distribution_present",
        lambda _extra: False,
    )
    assert resolve_extra_dependency_reason("nlp") == "missing_extra:nlp"
