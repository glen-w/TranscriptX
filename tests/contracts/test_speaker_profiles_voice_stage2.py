"""Stage 2: .npy vector format, runtime unavailable without extra, export exclude."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from transcriptx.core.speaker_profiles.voice.export_exclude import (
    filter_speaker_profiles_export_paths,
    is_voice_excluded_relpath,
)
from transcriptx.core.speaker_profiles.voice.runtime import (
    ModelUnavailable,
    SpeakerEmbeddingRuntime,
    speaker_match_deps_available,
)
from transcriptx.core.speaker_profiles.voice.vectors import (
    VoiceVectorError,
    load_vector_npy,
    write_vector_npy,
)


@pytest.mark.unit
def test_write_load_round_trip(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    raw = rng.standard_normal(192).astype(np.float32)
    path = tmp_path / "v.npy"
    meta = write_vector_npy(path, raw)
    assert meta["dtype"] == "<f4"
    assert meta["dimension"] == 192
    loaded = load_vector_npy(path, expected_sha256=str(meta["vector_sha256"]))
    assert loaded.shape == (192,)
    assert abs(float(np.linalg.norm(loaded)) - 1.0) < 1e-3


@pytest.mark.unit
def test_reject_wrong_shape(tmp_path: Path) -> None:
    path = tmp_path / "bad.npy"
    np.save(path, np.zeros(10, dtype="<f4"), allow_pickle=False)
    with pytest.raises(VoiceVectorError):
        load_vector_npy(path)


@pytest.mark.unit
def test_reject_pickle_and_hash_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "v.npy"
    meta = write_vector_npy(path, np.ones(192, dtype=np.float32))
    with pytest.raises(VoiceVectorError):
        load_vector_npy(path, expected_sha256="sha256:deadbeef")
    # Trailing data
    path.write_bytes(path.read_bytes() + b"TRAIL")
    with pytest.raises(VoiceVectorError):
        load_vector_npy(path, expected_sha256=str(meta["vector_sha256"]))


@pytest.mark.unit
def test_runtime_unavailable_without_speechbrain() -> None:
    if speaker_match_deps_available():
        pytest.skip("speechbrain installed in this environment")
    runtime = SpeakerEmbeddingRuntime()
    with pytest.raises(ModelUnavailable):
        runtime.ensure_loaded()


@pytest.mark.unit
def test_export_excludes_voice_paths(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    (root / "profiles").mkdir(parents=True)
    (root / "voice" / "samples").mkdir(parents=True)
    (root / ".cache" / "voice" / "excerpts").mkdir(parents=True)
    profile = root / "profiles" / "p.speaker_profile.json"
    sample = root / "voice" / "samples" / "s.voice_sample.json"
    excerpt = root / ".cache" / "voice" / "excerpts" / "x.wav"
    profile.write_text("{}")
    sample.write_text("{}")
    excerpt.write_text("x")
    assert is_voice_excluded_relpath("voice/samples/s.voice_sample.json")
    assert is_voice_excluded_relpath(".cache/voice/excerpts/x.wav")
    assert not is_voice_excluded_relpath("profiles/p.speaker_profile.json")
    kept = filter_speaker_profiles_export_paths(root, [profile, sample, excerpt])
    assert kept == [profile]
