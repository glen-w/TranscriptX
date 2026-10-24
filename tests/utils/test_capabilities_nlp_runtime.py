"""``has_nlp_runtime`` must require a spaCy *model*, not just ``import spacy``."""

from __future__ import annotations

import sys
import types

import pytest

from tests import capabilities


@pytest.fixture(autouse=True)
def _clear_cache():
    capabilities.has_nlp_runtime.cache_clear()
    yield
    capabilities.has_nlp_runtime.cache_clear()


def _fake_spacy(monkeypatch, installed: set[str]) -> None:
    util = types.ModuleType("spacy.util")
    util.is_package = lambda name: name in installed  # type: ignore[attr-defined]
    spacy = types.ModuleType("spacy")
    spacy.util = util  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setitem(sys.modules, "spacy.util", util)


def test_false_when_spacy_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", None)
    assert capabilities.has_nlp_runtime() is False


def test_false_when_spacy_importable_but_no_model(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_SPACY_MODEL", raising=False)
    _fake_spacy(monkeypatch, installed=set())
    assert capabilities.has_nlp_runtime() is False


@pytest.mark.parametrize("model", ["en_core_web_md", "en_core_web_sm"])
def test_true_when_fallback_model_installed(monkeypatch, model: str) -> None:
    monkeypatch.delenv("TRANSCRIPTX_SPACY_MODEL", raising=False)
    _fake_spacy(monkeypatch, installed={model})
    assert capabilities.has_nlp_runtime() is True


def test_true_when_configured_model_installed(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_SPACY_MODEL", "en_core_web_lg")
    _fake_spacy(monkeypatch, installed={"en_core_web_lg"})
    assert capabilities.has_nlp_runtime() is True
