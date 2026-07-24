"""Pinned SpeechBrain ECAPA embedding runtime (optional ``speaker_match`` extra)."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from transcriptx.core.speaker_profiles.voice.errors import VoiceFeatureError
from transcriptx.core.speaker_profiles.voice.vectors import (
    EXPECTED_DIM,
    l2_normalize,
    validate_embedding_vector,
)
from transcriptx.core.speaker_profiles.voice.versioning import (
    EMBEDDING_SCHEMA_VERSION,
    PREPROCESSING_POLICY_ID,
)

# Pinned profile — never silently substitute another model.
MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
# Hub commit SHA for speechbrain/spkrec-ecapa-voxceleb (main @ 0f99f2d, 2025-02-18).
MODEL_REVISION_PIN = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
LOADER_PROFILE_ID = "speechbrain_ecapa_voxceleb_v1"
SPEECHBRAIN_PKG_PIN = "speechbrain==1.0.2"
EMBEDDING_DIM = EXPECTED_DIM


class ModelUnavailable(VoiceFeatureError):
    """``[speaker_match]`` extra or SpeechBrain import missing."""


class ModelDownloadRequired(VoiceFeatureError):
    """Weights not present locally and downloads are disabled."""


class UnsupportedPlatform(VoiceFeatureError):
    """Torch/device placement failed before batching."""


@dataclass(frozen=True)
class EmbeddingRuntimeMeta:
    model_id: str
    model_revision: str
    loader_profile_id: str
    device_class: str
    embedding_schema_version: str
    preprocessing_policy_id: str
    speechbrain_version: str | None
    torch_version: str | None


@dataclass(frozen=True)
class EmbeddingBatchResult:
    vectors: tuple[np.ndarray, ...]
    meta: EmbeddingRuntimeMeta


_CACHE_LOCK = threading.RLock()


def speaker_match_deps_available() -> bool:
    try:
        import speechbrain  # noqa: F401
        import torch  # noqa: F401

        return True
    except Exception:
        return False


def resolve_torch_device(torch_mod: Any) -> tuple[Any, str]:
    """Select device before any batch; no mid-batch silent downgrade."""
    try:
        if torch_mod.cuda.is_available():
            return torch_mod.device("cuda"), "cuda"
    except Exception:
        pass
    try:
        if (
            getattr(torch_mod.backends, "mps", None)
            and torch_mod.backends.mps.is_available()
        ):
            return torch_mod.device("mps"), "mps"
    except Exception:
        pass
    return torch_mod.device("cpu"), "cpu"


class SpeakerEmbeddingRuntime:
    """Lazy SpeechBrain ECAPA loader. No network fallback after local failure."""

    def __init__(
        self,
        *,
        model_id: str = MODEL_ID,
        model_revision: str = MODEL_REVISION_PIN,
        savedir: Path | None = None,
    ) -> None:
        if model_revision != MODEL_REVISION_PIN and model_id == MODEL_ID:
            # Allow tests to pass alternate only when model_id also changes —
            # never silently use a different revision for the production model.
            raise ModelUnavailable(
                f"refusing unpinned revision for {MODEL_ID}: {model_revision!r}"
            )
        self.model_id = model_id
        self.model_revision = model_revision
        self.savedir = savedir
        self._classifier: Any | None = None
        self._device: Any | None = None
        self._device_class: str | None = None

    def ensure_loaded(self) -> EmbeddingRuntimeMeta:
        if not speaker_match_deps_available():
            raise ModelUnavailable(
                "Install transcriptx[speaker_match] for local voice embeddings"
            )
        import torch

        from transcriptx.core.utils.downloads import downloads_disabled

        with _CACHE_LOCK:
            if self._classifier is not None and self._device_class is not None:
                return self._meta()

            device, device_class = resolve_torch_device(torch)
            try:
                from speechbrain.inference.speaker import EncoderClassifier
            except Exception as exc:
                raise ModelUnavailable(str(exc)) from exc

            local_only = bool(downloads_disabled())
            # Force Hub local-only when downloads disabled; never fall back to network.
            if local_only:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

            savedir = (
                self.savedir
                or Path(
                    os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")
                )
                / "transcriptx_speaker_match"
                / self.model_revision
            )

            try:
                kwargs: dict[str, Any] = {
                    "source": self.model_id,
                    "savedir": str(savedir),
                    "run_opts": {"device": str(device)},
                }
                # Prefer revision when SpeechBrain/HF stack supports it.
                try:
                    self._classifier = EncoderClassifier.from_hparams(
                        **kwargs,
                        revisions={"hyperparams": self.model_revision},
                    )
                except TypeError:
                    # Older SpeechBrain: no revisions kw — still pin via savedir name.
                    if local_only and not Path(savedir).exists():
                        raise ModelDownloadRequired(
                            f"SpeechBrain weights missing offline at {savedir}"
                        )
                    self._classifier = EncoderClassifier.from_hparams(**kwargs)
            except ModelDownloadRequired:
                raise
            except Exception as exc:
                if local_only:
                    raise ModelDownloadRequired(
                        f"SpeechBrain weights unavailable offline: {exc}"
                    ) from exc
                raise ModelUnavailable(str(exc)) from exc

            self._device = device
            self._device_class = device_class
            return self._meta()

    def _meta(self) -> EmbeddingRuntimeMeta:
        sb_ver = None
        torch_ver = None
        try:
            import speechbrain
            import torch

            sb_ver = getattr(speechbrain, "__version__", None)
            torch_ver = getattr(torch, "__version__", None)
        except Exception:
            pass
        return EmbeddingRuntimeMeta(
            model_id=self.model_id,
            model_revision=self.model_revision,
            loader_profile_id=LOADER_PROFILE_ID,
            device_class=self._device_class or "unknown",
            embedding_schema_version=EMBEDDING_SCHEMA_VERSION,
            preprocessing_policy_id=PREPROCESSING_POLICY_ID,
            speechbrain_version=sb_ver,
            torch_version=torch_ver,
        )

    def embed_wav_paths(self, paths: list[Path]) -> EmbeddingBatchResult:
        meta = self.ensure_loaded()
        assert self._classifier is not None
        vectors: list[np.ndarray] = []
        for path in paths:
            waveform = self._classifier.load_audio(str(path))
            emb = self._classifier.encode_batch(waveform)
            arr = emb.squeeze().detach().cpu().numpy()
            arr = l2_normalize(arr)
            arr = validate_embedding_vector(arr, expected_dim=EXPECTED_DIM)
            vectors.append(arr)
        return EmbeddingBatchResult(vectors=tuple(vectors), meta=meta)
