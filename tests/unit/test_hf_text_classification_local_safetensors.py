"""Regression: HF classifier load must use local safetensors path on torch<2.6."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.hf_text_classification import runtime as rt
from transcriptx.core.analysis.hf_text_classification.runtime import (
    ModelProfile,
    load_classifier,
)

_SHA = "0" * 40


def _clear_classifier_cache() -> None:
    with rt._CACHE_LOCK:
        rt._MODEL_CACHE.clear()
        rt._LOADING_LOCKS.clear()


@pytest.mark.unit
def test_load_classifier_uses_local_safetensors_path(tmp_path: Path) -> None:
    """prefer_safetensors=False (bin-only Hub pin) still loads via converted local path."""
    torch = pytest.importorskip("torch")

    profile = ModelProfile(
        profile_id="test_bin_only_local",
        model_id="org/bin-only-emotion",
        model_revision=_SHA,
        tokenizer_id="org/bin-only-emotion",
        tokenizer_revision=_SHA,
        activation="softmax",
        labels=("anger", "joy", "neutral"),
        threshold_profile_version="t0",
        prefer_safetensors=False,
        max_length=16,
    )
    local_root = tmp_path / "snap"
    local_root.mkdir()

    param = MagicMock()
    param.dtype = torch.float32

    model = MagicMock()
    model.config.id2label = {0: "anger", 1: "joy", 2: "neutral"}
    model.parameters.return_value = iter([param])
    model.to.return_value = model

    tokenizer = MagicMock()
    tokenizer.model_max_length = 512

    transformers = MagicMock()
    transformers.AutoTokenizer.from_pretrained.return_value = tokenizer
    transformers.AutoModelForSequenceClassification.from_pretrained.return_value = model

    torch_mod = MagicMock()
    torch_mod.float32 = torch.float32
    torch_mod.device.return_value = torch.device("cpu")
    torch_mod.cuda.is_available.return_value = False
    torch_mod.backends.mps.is_available.return_value = False

    _clear_classifier_cache()
    try:
        with (
            patch(
                "transcriptx.core.utils.lazy_imports.get_torch",
                return_value=torch_mod,
            ),
            patch(
                "transcriptx.core.utils.lazy_imports.get_transformers",
                return_value=transformers,
            ),
            patch(
                "transcriptx.core.analysis.hf_safetensors.ensure_local_safetensors",
                return_value=local_root,
            ),
            patch(
                "transcriptx.core.utils.downloads.downloads_disabled",
                return_value=True,
            ),
        ):
            loaded = load_classifier(profile)
    finally:
        _clear_classifier_cache()

    assert loaded.model is model
    call_kw = transformers.AutoModelForSequenceClassification.from_pretrained.call_args
    assert call_kw.args[0] == str(local_root)
    assert call_kw.kwargs.get("use_safetensors") is True
    assert "revision" not in call_kw.kwargs
    # Must not load via Hub repo id after local conversion.
    assert call_kw.args[0] != profile.model_id
