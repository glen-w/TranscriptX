"""Offline integration: tiny locally constructed classifier fixture (no Hub)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.hf_text_classification.runtime import (
    ModelProfile,
    ScoreResult,
    score_texts,
)


@pytest.mark.unit
def test_score_texts_softmax_with_mock_model():
    torch = pytest.importorskip("torch")

    profile = ModelProfile(
        profile_id="test_softmax",
        model_id="local/test",
        model_revision="0",
        tokenizer_id="local/test",
        tokenizer_revision="0",
        activation="softmax",
        labels=("anger", "joy", "neutral"),
        threshold_profile_version="t0",
        max_length=16,
    )

    class FakeTok:
        def __call__(self, text, **kwargs):
            if isinstance(text, list):
                n = len(text)
                return {
                    "input_ids": torch.ones(n, 4, dtype=torch.long),
                    "attention_mask": torch.ones(n, 4, dtype=torch.long),
                }
            return {"input_ids": [1, 2, 3, 4]}

    class FakeOut:
        def __init__(self, logits):
            self.logits = logits

    class FakeModel:
        def __init__(self):
            self.config = MagicMock()
            self.config.id2label = {0: "anger", 1: "joy", 2: "neutral"}

        def __call__(self, **kwargs):
            b = kwargs["input_ids"].shape[0]
            logits = torch.tensor([[2.0, 0.1, 0.1]] * b)
            return FakeOut(logits)

        def to(self, device):
            return self

        def eval(self):
            return self

    loaded = MagicMock()
    loaded.profile = profile
    loaded.tokenizer = FakeTok()
    loaded.model = FakeModel()
    loaded.device = torch.device("cpu")
    loaded.device_class = "cpu"
    loaded.effective_max_length = 16
    loaded.resolved_id2label = {0: "anger", 1: "joy", 2: "neutral"}

    results = score_texts(loaded, ["hello anger"])
    assert len(results) == 1
    assert isinstance(results[0], ScoreResult)
    assert abs(sum(results[0].scores.values()) - 1.0) < 1e-5
    assert results[0].scores["anger"] > results[0].scores["joy"]


@pytest.mark.unit
def test_score_texts_sigmoid_does_not_sum_to_one():
    torch = pytest.importorskip("torch")

    profile = ModelProfile(
        profile_id="test_sigmoid",
        model_id="local/test",
        model_revision="0",
        tokenizer_id="local/test",
        tokenizer_revision="0",
        activation="sigmoid",
        labels=("joy", "sadness", "neutral"),
        threshold_profile_version="t0",
        max_length=16,
    )

    class FakeTok:
        def __call__(self, text, **kwargs):
            if isinstance(text, list):
                n = len(text)
                return {
                    "input_ids": torch.ones(n, 4, dtype=torch.long),
                    "attention_mask": torch.ones(n, 4, dtype=torch.long),
                }
            return {"input_ids": [1, 2, 3]}

    class FakeOut:
        def __init__(self, logits):
            self.logits = logits

    class FakeModel:
        def __init__(self):
            self.config = MagicMock()
            self.config.id2label = {0: "joy", 1: "sadness", 2: "neutral"}

        def __call__(self, **kwargs):
            b = kwargs["input_ids"].shape[0]
            # High logits → high independent sigmoids
            logits = torch.tensor([[5.0, 5.0, -5.0]] * b)
            return FakeOut(logits)

        def to(self, device):
            return self

        def eval(self):
            return self

    loaded = MagicMock()
    loaded.profile = profile
    loaded.tokenizer = FakeTok()
    loaded.model = FakeModel()
    loaded.device = torch.device("cpu")
    loaded.device_class = "cpu"
    loaded.effective_max_length = 16
    loaded.resolved_id2label = {0: "joy", 1: "sadness", 2: "neutral"}

    results = score_texts(loaded, ["mixed"])
    total = sum(results[0].scores.values())
    assert total > 1.0  # independent sigmoids, not renormalised
