"""Embedding cache and TF-IDF fallback path."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from transcriptx.core.analysis.semantic_similarity_v2.embedding import (
    LRUEmbeddingCache,
    SemanticBatchEmbedder,
)


def test_lru_embedding_cache_evicts_oldest() -> None:
    c = LRUEmbeddingCache(2)
    c.put("a", np.array([1.0]))
    c.put("b", np.array([2.0]))
    c.put("c", np.array([3.0]))
    assert c.get("a") is None
    assert c.get("c") is not None


def test_semantic_batch_embedder_tfidf_fallback_for_missing_dependency(
    monkeypatch,
) -> None:
    def boom(_self, _texts):
        raise ImportError("no torch in test")

    monkeypatch.setattr(
        SemanticBatchEmbedder,
        "_embed_transformer_batches",
        boom,
    )
    manager = SimpleNamespace(
        model=object(),
        tokenizer=object(),
        torch=object(),
        device="cpu",
    )
    emb = SemanticBatchEmbedder("dummy-model", 8, cache=None, model_manager=manager)
    out = emb.embed_unique_texts(["hello world", "hello there"])
    assert out.shape[0] == 2
    assert out.shape[1] >= 1
    assert emb.embedding_backend == "tfidf"
    assert emb.embedding_fallback_reason == "missing_transformer_dependency"
    assert emb.transformer_backend_available is False


def test_semantic_batch_embedder_model_unavailable_fallback() -> None:
    manager = SimpleNamespace(model=None, tokenizer=None, torch=None, device=None)
    emb = SemanticBatchEmbedder("dummy-model", 8, cache=None, model_manager=manager)
    out = emb.embed_unique_texts(["hello world", "hello there"])
    assert out.shape[0] == 2
    assert emb.embedding_backend == "tfidf"
    assert emb.embedding_fallback_reason == "model_unavailable"
    assert emb.transformer_backend_available is False


def test_semantic_batch_embedder_inference_errors_are_not_silent(monkeypatch) -> None:
    def boom(_self, _texts):
        raise RuntimeError("bad model state")

    monkeypatch.setattr(
        SemanticBatchEmbedder,
        "_embed_transformer_batches",
        boom,
    )
    manager = SimpleNamespace(
        model=object(),
        tokenizer=object(),
        torch=object(),
        device="cpu",
    )
    emb = SemanticBatchEmbedder("dummy-model", 8, cache=None, model_manager=manager)
    with pytest.raises(RuntimeError, match="bad model state"):
        emb.embed_unique_texts(["hello world", "hello there"])


class _FakeTensor:
    def __init__(self, arr, tracker):
        self.arr = np.array(arr, dtype=np.float64)
        self.tracker = tracker

    def to(self, device):
        self.tracker["devices"].append(device)
        return self

    def unsqueeze(self, dim):
        return _FakeTensor(np.expand_dims(self.arr, axis=dim), self.tracker)

    def sum(self, dim=None):
        return _FakeTensor(np.sum(self.arr, axis=dim), self.tracker)

    def clamp(self, min):
        return _FakeTensor(np.maximum(self.arr, min), self.tracker)

    def detach(self):
        self.tracker["detach_calls"] += 1
        return self

    def cpu(self):
        self.tracker["cpu_calls"] += 1
        return self

    def numpy(self):
        return self.arr

    def __mul__(self, other):
        return _FakeTensor(self.arr * other.arr, self.tracker)

    def __truediv__(self, other):
        return _FakeTensor(self.arr / other.arr, self.tracker)


class _FakeNoGrad:
    def __init__(self, tracker):
        self.tracker = tracker

    def __enter__(self):
        self.tracker["no_grad_enter"] += 1

    def __exit__(self, exc_type, exc, tb):
        self.tracker["no_grad_exit"] += 1


class _FakeTorch:
    def __init__(self, tracker):
        self.tracker = tracker

    def no_grad(self):
        return _FakeNoGrad(self.tracker)


class _FakeModel:
    def __init__(self, tracker):
        self.tracker = tracker

    def eval(self):
        self.tracker["eval_calls"] += 1

    def __call__(self, **_enc):
        return SimpleNamespace(
            last_hidden_state=_FakeTensor(
                [
                    [[1.0, 0.0], [0.0, 1.0]],
                    [[0.5, 0.5], [1.0, 0.0]],
                ],
                self.tracker,
            )
        )


class _FakeTokenizer:
    def __init__(self, tracker):
        self.tracker = tracker

    def __call__(self, batch, **_kwargs):
        return {
            "input_ids": _FakeTensor(np.ones((len(batch), 2)), self.tracker),
            "attention_mask": _FakeTensor(np.ones((len(batch), 2)), self.tracker),
        }


def test_semantic_batch_embedder_transformer_uses_manager_device_and_no_grad() -> None:
    tracker = {
        "cpu_calls": 0,
        "detach_calls": 0,
        "devices": [],
        "eval_calls": 0,
        "no_grad_enter": 0,
        "no_grad_exit": 0,
    }
    manager = SimpleNamespace(
        model=_FakeModel(tracker),
        tokenizer=_FakeTokenizer(tracker),
        torch=_FakeTorch(tracker),
        device="test-device",
    )
    emb = SemanticBatchEmbedder("dummy-model", 8, cache=None, model_manager=manager)
    out = emb.embed_unique_texts(["hello world", "hello there"])

    assert out.shape == (2, 2)
    assert tracker["eval_calls"] == 1
    assert tracker["no_grad_enter"] == 1
    assert tracker["no_grad_exit"] == 1
    assert tracker["cpu_calls"] == 1
    assert tracker["detach_calls"] == 1
    assert tracker["devices"] == ["test-device", "test-device"]
    assert emb.embedding_backend == "transformer"
    assert emb.embedding_fallback_reason is None
    assert emb.transformer_backend_available is True
    assert emb.embedding_device == "test-device"
