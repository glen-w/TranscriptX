"""Corpus inventory fingerprint is memoised for a few seconds between reruns."""

from __future__ import annotations

import pytest

from transcriptx.web import cache_helpers as ch


@pytest.fixture(autouse=True)
def _reset_memo():
    ch._CORPUS_DIGEST_MEMO = None
    yield
    ch._CORPUS_DIGEST_MEMO = None


@pytest.mark.unit
def test_digest_walk_runs_once_within_window(monkeypatch) -> None:
    calls: list[int] = []

    def _discover():
        calls.append(1)
        return ["ref"]

    def _digest(refs):
        return ("digest", tuple(refs))

    import transcriptx.app.corpus_inventory.service as svc

    monkeypatch.setattr(svc, "discover_transcript_refs", _discover)
    monkeypatch.setattr(svc, "corpus_fingerprint_digest", _digest)

    assert ch._corpus_digest(now=100.0) == ("digest", ("ref",))
    assert ch._corpus_digest(now=100.0 + ch.CORPUS_DIGEST_MEMO_SECONDS - 0.1) == (
        "digest",
        ("ref",),
    )
    assert len(calls) == 1
    ch._corpus_digest(now=100.0 + ch.CORPUS_DIGEST_MEMO_SECONDS + 0.1)
    assert len(calls) == 2


@pytest.mark.unit
def test_clear_cache_drops_memo(monkeypatch) -> None:
    ch._CORPUS_DIGEST_MEMO = (0.0, ("stale",))
    monkeypatch.setattr(
        ch._cached_corpus_inventory_rows, "clear", lambda: None, raising=False
    )
    ch.clear_corpus_inventory_cache()
    assert ch._CORPUS_DIGEST_MEMO is None
