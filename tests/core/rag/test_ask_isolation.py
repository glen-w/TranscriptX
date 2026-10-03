"""Ask isolation: live RagAPI.search path with a fake embedder."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from transcriptx.core.rag.api import RagAPI
from transcriptx.core.rag.embed import _normalize
from transcriptx.core.rag.index import Index, RagScopeMissing
from transcriptx.core.rag.settings import RagSettings

pytest.importorskip("lancedb")

DIM = 8


class FakeEmbedder:
    dim = DIM

    def embed_query(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        lower = text.lower()
        if "alpha" in lower:
            vec[0] = 1.0
        if "beta" in lower:
            vec[1] = 1.0
        if "widget" in lower:
            vec[2] = 1.0
        vec[-1] = 0.01
        return _normalize(vec)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]


def _settings(tmp_path: Path) -> RagSettings:
    return RagSettings(
        data_dir=tmp_path,
        enabled=True,
        embed_model="fake-embed",
        embed_dim=DIM,
        ollama_base_url="http://example.invalid",
        chunk_chars=80,
        min_chunk_chars=8,
    )


def _api(tmp_path: Path) -> RagAPI:
    return RagAPI(_settings(tmp_path), embedder=FakeEmbedder())


def _segments(*texts: str) -> list[dict]:
    segs = []
    t = 0.0
    for i, text in enumerate(texts):
        segs.append(
            {
                "speaker": "A",
                "text": text,
                "start": t,
                "end": t + 1.0,
            }
        )
        t += 1.0
    return segs


def _write_json(path: Path, texts: tuple[str, ...]) -> None:
    path.write_text("\n".join(texts), encoding="utf-8")


def test_twin_session_scoped_search_returns_only_own(tmp_path: Path) -> None:
    api = _api(tmp_path)
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    _write_json(a_path, ("alpha widget",))
    _write_json(b_path, ("beta widget",) * 20)
    api.ingest(a_path, "sess-a", "run-a", "A", _segments("alpha widget in session A"))
    api.ingest(
        b_path,
        "sess-b",
        "run-b",
        "B",
        _segments(*(["beta widget in session B"] * 20)),
    )

    hits = api.search("widget", session_slug="sess-a", run_id="run-a", k=5)
    assert hits
    assert all(h.session_slug == "sess-a" and h.run_id == "run-a" for h in hits)
    assert not any("session B" in h.text for h in hits)

    b_hits = api.search("beta", session_slug="sess-b", run_id="run-b", k=5)
    assert b_hits
    assert all(h.session_slug == "sess-b" for h in b_hits)

    # Filter-removed regression: unscoped search would surface the dominant foreign session.
    embedder = FakeEmbedder()
    index = Index.open(api.settings, create=False)
    unscoped = index.search(embedder.embed_query("widget"), k=5)
    assert any(row.get("session_slug") == "sess-b" for row in unscoped)


def test_missing_scope_raises_and_does_not_open_index(tmp_path: Path, monkeypatch) -> None:
    api = _api(tmp_path)
    opened = {"called": False}

    def boom(*_a, **_k):
        opened["called"] = True
        raise AssertionError("Index.open should not run without scope")

    monkeypatch.setattr("transcriptx.core.rag.api.Index.open", boom)
    with pytest.raises(RagScopeMissing, match="Ask requires session_slug and run_id"):
        api.search("anything")
    assert opened["called"] is False

    with pytest.raises(RagScopeMissing):
        api.answer("anything", session_slug="only-slug")


def test_search_backend_error_propagates(tmp_path: Path, monkeypatch) -> None:
    api = _api(tmp_path)
    path = tmp_path / "a.json"
    _write_json(path, ("alpha",))
    api.ingest(path, "sess-a", "run-a", "A", _segments("alpha widget"))

    def explode(self, *args, **kwargs):
        raise RuntimeError("lance down")

    monkeypatch.setattr("transcriptx.core.rag.api.Index.search", explode)
    with pytest.raises(RuntimeError, match="lance down"):
        api.search("alpha", session_slug="sess-a", run_id="run-a")


def test_reingest_does_not_duplicate_chunks(tmp_path: Path) -> None:
    api = _api(tmp_path)
    path = tmp_path / "a.json"
    _write_json(path, ("alpha-v1",))
    segs = _segments("alpha widget first")
    api.ingest(path, "sess-a", "run-a", "A", segs)
    index = Index.open(api.settings, create=False)
    first = index.count_rows()
    assert first > 0

    _write_json(path, ("alpha-v2",))
    api.ingest(path, "sess-a", "run-a", "A", _segments("alpha widget second"))
    index = Index.open(api.settings, create=False)
    assert index.count_rows() == first


def test_purge_drops_session_chunks(tmp_path: Path, monkeypatch) -> None:
    from transcriptx.core.rag.purge import purge_transcript_from_index

    api = _api(tmp_path)
    path = tmp_path / "keep.json"
    _write_json(path, ("alpha",))
    api.ingest(path, "sess-a", "run-a", "A", _segments("alpha widget"))
    other = tmp_path / "other.json"
    _write_json(other, ("beta",))
    api.ingest(other, "sess-b", "run-b", "B", _segments("beta widget"))
    assert Index.open(api.settings, create=False).count_rows() == 2

    monkeypatch.setenv("TRANSCRIPTX_RAG_ENABLED", "1")
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRANSCRIPTX_RAG_EMBED_MODEL", "fake-embed")
    monkeypatch.setattr(
        "transcriptx.core.rag.purge._slugs_for_path",
        lambda _p: ["sess-a"],
    )
    purge_transcript_from_index(path)
    remaining = Index.open(api.settings, create=False)
    assert remaining.count_rows() == 1
    hits = api.search("widget", session_slug="sess-b", run_id="run-b", k=5)
    assert hits
    assert all(h.session_slug == "sess-b" for h in hits)
