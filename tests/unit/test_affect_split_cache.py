"""Split inference vs aggregation cache layer tests."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.emotion_family.fingerprints import (
    speaker_identity_digest,
    text_source_digest,
    timeline_identity_digest,
)
from transcriptx.core.analysis.emotion_family.split_cache import (
    InferenceCacheStore,
    aggregation_cache_key,
    inference_cache_key,
    module_cache_fingerprint,
)


@pytest.mark.unit
def test_inference_key_stable_when_speaker_or_timing_changes():
    """Speaker/timing edits must not bust the inference key."""
    text_a = [
        {"id": "s1", "text": "hello", "speaker": "Alice", "start": 0.0, "end": 1.0},
        {"id": "s2", "text": "world", "speaker": "Bob", "start": 1.0, "end": 2.0},
    ]
    text_b = [
        {"id": "s1", "text": "hello", "speaker": "Carol", "start": 10.0, "end": 11.0},
        {"id": "s2", "text": "world", "speaker": "Dave", "start": 20.0, "end": 21.0},
    ]
    digest_a = text_source_digest(text_a)
    digest_b = text_source_digest(text_b)
    assert digest_a == digest_b
    key_a = inference_cache_key(
        compatibility_fingerprint="compat", text_source_digest=digest_a
    )
    key_b = inference_cache_key(
        compatibility_fingerprint="compat", text_source_digest=digest_b
    )
    assert key_a == key_b


@pytest.mark.unit
def test_aggregation_key_busts_on_speaker_or_timing_edit():
    segs = [
        {"id": "s1", "text": "hello", "speaker": "Alice", "start": 0.0, "end": 1.0},
        {"id": "s2", "text": "world", "speaker": "Bob", "start": 1.0, "end": 2.0},
    ]
    renamed = [
        {"id": "s1", "text": "hello", "speaker": "Carol", "start": 0.0, "end": 1.0},
        {"id": "s2", "text": "world", "speaker": "Bob", "start": 1.0, "end": 2.0},
    ]
    retimed = [
        {"id": "s1", "text": "hello", "speaker": "Alice", "start": 0.0, "end": 1.0},
        {"id": "s2", "text": "world", "speaker": "Bob", "start": 5.0, "end": 6.0},
    ]
    base = aggregation_cache_key(
        inference_generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        speaker_identity_digest=speaker_identity_digest(segs),
        timeline_identity_digest=timeline_identity_digest(segs),
        aggregation_semantics_version="v1",
    )
    renamed_key = aggregation_cache_key(
        inference_generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        speaker_identity_digest=speaker_identity_digest(renamed),
        timeline_identity_digest=timeline_identity_digest(renamed),
        aggregation_semantics_version="v1",
    )
    retimed_key = aggregation_cache_key(
        inference_generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        speaker_identity_digest=speaker_identity_digest(retimed),
        timeline_identity_digest=timeline_identity_digest(retimed),
        aggregation_semantics_version="v1",
    )
    assert base != renamed_key
    assert base != retimed_key


@pytest.mark.unit
def test_text_edit_busts_inference_key():
    a = [{"id": "s1", "text": "hello"}]
    b = [{"id": "s1", "text": "goodbye"}]
    key_a = inference_cache_key(
        compatibility_fingerprint="compat",
        text_source_digest=text_source_digest(a),
    )
    key_b = inference_cache_key(
        compatibility_fingerprint="compat",
        text_source_digest=text_source_digest(b),
    )
    assert key_a != key_b


@pytest.mark.unit
def test_inference_store_roundtrip(tmp_path):
    store = InferenceCacheStore(tmp_path)
    key = inference_cache_key(compatibility_fingerprint="c", text_source_digest="t")
    store.store(
        key,
        inference_generation_id="0120a4f9196a5f9eb9f523f31f914da7",
        rows_by_segment={"s1": {"scores": {"joy": 0.9}, "truncated": False}},
    )
    loaded = store.load(key)
    assert loaded is not None
    assert loaded["inference_generation_id"] == "0120a4f9196a5f9eb9f523f31f914da7"
    assert loaded["rows_by_segment"]["s1"]["scores"]["joy"] == 0.9


@pytest.mark.unit
def test_module_cache_fingerprint_combines_layers():
    i = inference_cache_key(compatibility_fingerprint="c", text_source_digest="t")
    a = aggregation_cache_key(
        inference_generation_id="b2f5ff47436671b6e533d8dc3614845d",
        speaker_identity_digest="s",
        timeline_identity_digest="tl",
        aggregation_semantics_version="v1",
    )
    fp = module_cache_fingerprint(inference_key=i, aggregation_key=a)
    assert isinstance(fp, str) and len(fp) == 64


@pytest.mark.unit
def test_old_inference_cache_version_rejected(tmp_path):
    import json

    from transcriptx.core.analysis.emotion_family.split_cache import (
        INFERENCE_CACHE_VERSION,
    )

    store = InferenceCacheStore(tmp_path)
    key = inference_cache_key(compatibility_fingerprint="c", text_source_digest="t")
    path = tmp_path / f"{key}.json"
    path.write_text(
        json.dumps(
            {
                "version": "emotion_family_inference_cache_v1",
                "inference_generation_id": "g1",
                "rows_by_segment": {"s1": {"scores": {"joy": 1.0}}},
            }
        ),
        encoding="utf-8",
    )
    assert store.load(key) is None
    assert INFERENCE_CACHE_VERSION == "emotion_family_inference_cache_v3"


@pytest.mark.unit
def test_cache_hit_preserves_distinct_generation_ids(tmp_path):
    """Inference cache stamps inference_generation_id, not artifact_generation_id."""
    store = InferenceCacheStore(tmp_path)
    key = inference_cache_key(compatibility_fingerprint="c", text_source_digest="t")
    inference_id = "inf-gen-stable"
    artifact_id = "artifact-gen-fresh"
    store.store(
        key,
        inference_generation_id=inference_id,
        rows_by_segment={"s1": {"scores": {"joy": 0.5}, "truncated": False}},
    )
    loaded = store.load(key)
    assert loaded is not None
    assert loaded["inference_generation_id"] == inference_id
    assert "artifact_generation_id" not in loaded
    assert loaded["inference_generation_id"] != artifact_id


@pytest.mark.unit
def test_aggregation_key_changes_when_speaker_digest_changes():
    key_a = aggregation_cache_key(
        inference_generation_id="7050838f0b07c5a6354fbfdecf9c958d",
        speaker_identity_digest="spk-alice",
        timeline_identity_digest="tl",
        aggregation_semantics_version="v1",
    )
    key_b = aggregation_cache_key(
        inference_generation_id="7050838f0b07c5a6354fbfdecf9c958d",
        speaker_identity_digest="spk-bob",
        timeline_identity_digest="tl",
        aggregation_semantics_version="v1",
    )
    assert key_a != key_b
