"""Offline unit tests for HF text-classification profiles and pure runtime helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.hf_text_classification.profiles import (
    BUILTIN_PROFILES,
    CONTEXTUAL_HARTMANN_V1,
    FINE_GRAINED_GOEMOTIONS_V1,
    get_builtin_profile,
)
from transcriptx.core.analysis.hf_text_classification.runtime import (
    ModelProfile,
    assert_revision_pinned,
    device_class_for,
    resolve_usable_max_length,
)


@pytest.mark.unit
def test_get_builtin_profile_returns_pinned_builtins():
    hartmann = get_builtin_profile(CONTEXTUAL_HARTMANN_V1.profile_id)
    goemo = get_builtin_profile(FINE_GRAINED_GOEMOTIONS_V1.profile_id)
    assert hartmann is CONTEXTUAL_HARTMANN_V1
    assert goemo is FINE_GRAINED_GOEMOTIONS_V1
    assert hartmann.activation == "softmax"
    assert goemo.activation == "sigmoid"
    # Hartmann pin ships pytorch_model.bin only; GoEmotions has safetensors.
    assert hartmann.prefer_safetensors is False
    assert goemo.prefer_safetensors is True
    assert set(BUILTIN_PROFILES) == {
        CONTEXTUAL_HARTMANN_V1.profile_id,
        FINE_GRAINED_GOEMOTIONS_V1.profile_id,
    }


@pytest.mark.unit
def test_get_builtin_profile_unknown_raises_keyerror():
    with pytest.raises(KeyError, match="Unknown emotion model profile"):
        get_builtin_profile("not_a_real_profile_id")


@pytest.mark.unit
def test_builtin_profiles_reject_floating_revisions():
    assert_revision_pinned(CONTEXTUAL_HARTMANN_V1)
    assert_revision_pinned(FINE_GRAINED_GOEMOTIONS_V1)
    assert len(CONTEXTUAL_HARTMANN_V1.model_revision) == 40
    assert len(FINE_GRAINED_GOEMOTIONS_V1.model_revision) == 40


@pytest.mark.unit
def test_model_profile_label_map_hash_stable_and_activation_sensitive():
    a = ModelProfile(
        profile_id="p",
        model_id="m",
        model_revision="0" * 40,
        tokenizer_id="m",
        tokenizer_revision="0" * 40,
        activation="sigmoid",
        labels=("joy", "anger"),
        threshold_profile_version="t0",
    )
    b = ModelProfile(
        profile_id="p2",
        model_id="m2",
        model_revision="1" * 40,
        tokenizer_id="m2",
        tokenizer_revision="1" * 40,
        activation="sigmoid",
        labels=("joy", "anger"),
        threshold_profile_version="t0",
    )
    soft = ModelProfile(
        profile_id="p3",
        model_id="m",
        model_revision="0" * 40,
        tokenizer_id="m",
        tokenizer_revision="0" * 40,
        activation="softmax",
        labels=("joy", "anger"),
        threshold_profile_version="t0",
    )
    assert a.num_labels == 2
    assert a.label_map_hash == b.label_map_hash
    assert a.label_map_hash != soft.label_map_hash


@pytest.mark.unit
@pytest.mark.parametrize(
    "device,expected",
    [
        ("cuda:0", "cuda"),
        ("CUDA", "cuda"),
        ("mps", "mps"),
        ("cpu", "cpu"),
        ("cpu:0", "cpu"),
        ("tpu", "other"),
    ],
)
def test_device_class_for_normalizes_device_strings(device, expected):
    assert device_class_for(device) == expected


@pytest.mark.unit
def test_resolve_usable_max_length_respects_model_positional_limit():
    tok = MagicMock()
    tok.model_max_length = 512
    model = MagicMock()
    model.config = MagicMock()
    model.config.max_position_embeddings = 64
    model.config.n_positions = None
    model.config.max_sequence_length = None
    assert resolve_usable_max_length(tok, 256, model=model) == 64
    # Degenerate/missing positional attrs fall back to tokenizer/profile min.
    model.config.max_position_embeddings = None
    assert resolve_usable_max_length(tok, 256, model=model) == 256
    assert resolve_usable_max_length(tok, 0, model=None) == 1
