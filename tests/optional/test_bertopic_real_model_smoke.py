"""Optional real-model BERTopic smoke (requires transcriptx[bertopic] + network/cache).

Skipped by default when the bertopic distribution is absent or downloads are
disabled without a usable cache. Not part of the default CI gate.
"""

from __future__ import annotations

import importlib.metadata
import os

import pytest

pytestmark = [
    pytest.mark.requires_models,
]


def _bertopic_installed() -> bool:
    try:
        importlib.metadata.version("bertopic")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


@pytest.mark.skipif(
    not _bertopic_installed(), reason="transcriptx[bertopic] not installed"
)
def test_bertopic_import_and_minimal_fit() -> None:
    """Reproducible smoke: tiny in-memory corpus; uses configured embedding model."""
    if os.environ.get("TRANSCRIPTX_DISABLE_DOWNLOADS", "").strip() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("downloads disabled; provision HF cache for offline smoke")

    from bertopic import BERTopic

    docs = [
        "budget planning meeting about finance",
        "finance and budget discussion continues",
        "sports and football match highlights",
        "football sports game summary",
        "weather forecast rain tomorrow",
        "rain and weather outlook",
    ]
    model = BERTopic(min_topic_size=2, embedding_model="all-MiniLM-L6-v2")
    topics, _probs = model.fit_transform(docs)
    assert len(topics) == len(docs)
