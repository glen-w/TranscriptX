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


def _profile(profile_id: str = "test_bin_only_local") -> ModelProfile:
    return ModelProfile(
        profile_id=profile_id,
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


def _mock_stack(torch, *, transformers):
    param = MagicMock()
    param.dtype = torch.float32
    model = MagicMock()
    model.config.id2label = {0: "anger", 1: "joy", 2: "neutral"}
    model.parameters.return_value = iter([param])
    model.to.return_value = model
    tokenizer = MagicMock()
    tokenizer.model_max_length = 512
    transformers.AutoTokenizer.from_pretrained.return_value = tokenizer
    transformers.AutoModelForSequenceClassification.from_pretrained.return_value = model
    torch_mod = MagicMock()
    torch_mod.float32 = torch.float32
    torch_mod.device.return_value = torch.device("cpu")
    torch_mod.cuda.is_available.return_value = False
    torch_mod.backends.mps.is_available.return_value = False
    return torch_mod, model, tokenizer


def _run_load_classifier(
    profile, *, torch_mod, transformers, local_root, downloads_off
):
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
                return_value=downloads_off,
            ),
            patch(
                "transcriptx.core.utils.hf_hub_load.HUB_RETRY_BACKOFF_SECONDS",
                0,
            ),
        ):
            return load_classifier(profile)
    finally:
        _clear_classifier_cache()


@pytest.mark.unit
def test_load_classifier_uses_local_safetensors_path(tmp_path: Path) -> None:
    """prefer_safetensors=False (bin-only Hub pin) still loads via converted local path."""
    torch = pytest.importorskip("torch")
    profile = _profile()
    local_root = tmp_path / "snap"
    local_root.mkdir()
    transformers = MagicMock()
    torch_mod, model, _tokenizer = _mock_stack(torch, transformers=transformers)

    loaded = _run_load_classifier(
        profile,
        torch_mod=torch_mod,
        transformers=transformers,
        local_root=local_root,
        downloads_off=True,
    )

    assert loaded.model is model
    call_kw = transformers.AutoModelForSequenceClassification.from_pretrained.call_args
    assert call_kw.args[0] == str(local_root)
    assert call_kw.kwargs.get("use_safetensors") is True
    assert "revision" not in call_kw.kwargs
    # Must not load via Hub repo id after local conversion.
    assert call_kw.args[0] != profile.model_id


@pytest.mark.unit
def test_load_classifier_uses_local_cache_when_downloads_enabled(
    tmp_path: Path,
) -> None:
    """Cached weights must not contact the Hub (etag checks hang on bad networks)."""
    torch = pytest.importorskip("torch")
    profile = _profile("test_local_first")
    local_root = tmp_path / "snap"
    local_root.mkdir()
    transformers = MagicMock()
    torch_mod, model, _tokenizer = _mock_stack(torch, transformers=transformers)

    loaded = _run_load_classifier(
        profile,
        torch_mod=torch_mod,
        transformers=transformers,
        local_root=local_root,
        downloads_off=False,
    )

    assert loaded.model is model
    tok_kw = transformers.AutoTokenizer.from_pretrained.call_args.kwargs
    assert tok_kw.get("local_files_only") is True
    assert transformers.AutoTokenizer.from_pretrained.call_count == 1


@pytest.mark.unit
def test_load_classifier_retries_hub_after_local_miss(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    profile = _profile("test_hub_retry")
    local_root = tmp_path / "snap"
    local_root.mkdir()
    transformers = MagicMock()
    torch_mod, model, tokenizer = _mock_stack(torch, transformers=transformers)

    hub_timeout = TimeoutError(
        "HTTPSConnectionPool(host='huggingface.co', port=443): Read timed out."
    )
    attempts = {"tok": 0}

    def from_pretrained(*_args, **kwargs):
        if kwargs.get("local_files_only"):
            raise OSError("not in cache")
        attempts["tok"] += 1
        if attempts["tok"] == 1:
            raise hub_timeout
        return tokenizer

    transformers.AutoTokenizer.from_pretrained.side_effect = from_pretrained

    loaded = _run_load_classifier(
        profile,
        torch_mod=torch_mod,
        transformers=transformers,
        local_root=local_root,
        downloads_off=False,
    )
    assert loaded.model is model
    assert attempts["tok"] == 2


@pytest.mark.unit
def test_load_classifier_raises_after_hub_retries_exhausted(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    profile = _profile("test_hub_exhausted")
    transformers = MagicMock()
    torch_mod, _model, _tokenizer = _mock_stack(torch, transformers=transformers)
    hub_timeout = TimeoutError(
        "HTTPSConnectionPool(host='huggingface.co', port=443): Read timed out."
    )

    def from_pretrained(*_args, **kwargs):
        if kwargs.get("local_files_only"):
            raise OSError("not in cache")
        raise hub_timeout

    transformers.AutoTokenizer.from_pretrained.side_effect = from_pretrained

    with pytest.raises(TimeoutError, match="timed out"):
        _run_load_classifier(
            profile,
            torch_mod=torch_mod,
            transformers=transformers,
            local_root=None,
            downloads_off=False,
        )
