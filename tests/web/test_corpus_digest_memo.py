"""Corpus inventory fingerprint is memoised between reruns."""

from __future__ import annotations

import pytest

from transcriptx.web import cache_helpers as ch


@pytest.fixture(autouse=True)
def _reset_memo():
    ch._CORPUS_DIGEST_MEMO = None
    yield
    ch._CORPUS_DIGEST_MEMO = None


def _patch_discover(monkeypatch, calls: list[int]) -> None:
    def _discover():
        calls.append(1)
        return ["ref"]

    def _digest(refs):
        return ("digest", tuple(refs))

    import transcriptx.app.corpus_inventory.service as svc

    monkeypatch.setattr(svc, "discover_transcript_refs", _discover)
    monkeypatch.setattr(svc, "corpus_fingerprint_digest", _digest)


@pytest.mark.unit
def test_digest_walk_runs_once_within_window(monkeypatch) -> None:
    calls: list[int] = []
    _patch_discover(monkeypatch, calls)
    monkeypatch.setattr(ch, "_transcripts_dir_scandir_stamp", lambda: ("dir", 1, 1))

    assert ch._corpus_digest(now=100.0) == ("digest", ("ref",))
    assert ch._corpus_digest(now=100.0 + ch.CORPUS_DIGEST_MEMO_SECONDS - 0.1) == (
        "digest",
        ("ref",),
    )
    assert len(calls) == 1
    ch._corpus_digest(now=100.0 + ch.CORPUS_DIGEST_MEMO_SECONDS + 0.1)
    assert len(calls) == 1  # same scandir stamp; skip discover after window


@pytest.mark.unit
def test_digest_walks_again_when_scandir_stamp_changes(monkeypatch) -> None:
    calls: list[int] = []
    _patch_discover(monkeypatch, calls)
    stamps = [("dir", 1, 1), ("dir", 2, 2)]

    def _stamp():
        return stamps.pop(0) if stamps else ("dir", 2, 2)

    monkeypatch.setattr(ch, "_transcripts_dir_scandir_stamp", _stamp)
    ch._corpus_digest(now=100.0)
    ch._corpus_digest(now=100.0 + ch.CORPUS_DIGEST_MEMO_SECONDS + 0.1)
    assert len(calls) == 2


@pytest.mark.unit
def test_clear_cache_drops_memo(monkeypatch) -> None:
    ch._CORPUS_DIGEST_MEMO = (0.0, ("stamp",), ("stale",))
    monkeypatch.setattr(
        ch._cached_corpus_inventory_rows, "clear", lambda: None, raising=False
    )
    ch.clear_corpus_inventory_cache()
    assert ch._CORPUS_DIGEST_MEMO is None


@pytest.mark.unit
def test_search_service_does_not_rediscover_transcript_refs() -> None:
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "services"
        / "search_service.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "discover_transcript_refs" not in text
    assert "cached_list_available_sessions" in text
