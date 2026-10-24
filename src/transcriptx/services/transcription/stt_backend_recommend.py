"""Hardware-aware STT backend recommendations (Theme E).

Hints only — never mutate the operator's selection silently.

Lives under services/transcription (not core/) so analysis-only invariants
stay clean: core must not mention WhisperX or host STT orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from transcriptx.core.observability.hardware_probe import HardwareSnapshot


@dataclass(frozen=True)
class SttBackendRecommendation:
    provider_id: str
    device: str  # cpu | cuda
    reason: str
    caption: str


def recommend_stt_backend(
    hardware: HardwareSnapshot,
    *,
    available_provider_ids: Sequence[str],
) -> SttBackendRecommendation:
    """Recommend STT provider + device from this process snapshot.

    STT engines run on the host (or a separate Docker recipe), not in the
    analysis image. When ``in_container`` is True we still prefer whispermlx
    on Darwin hosts by os_family, but caption that CUDA visibility is a host
    concern.
    """
    ids = {str(p) for p in available_provider_ids}
    os_f = hardware.os_family
    in_container = hardware.in_container

    if os_f == "darwin" and "whispermlx" in ids:
        return SttBackendRecommendation(
            provider_id="whispermlx",
            device="cpu",
            reason="apple_silicon_mlx",
            caption=(
                "Recommended: whispermlx on this Mac (MLX). "
                "WhisperX Docker on Apple Silicon is usually CPU-only."
            ),
        )

    if "whisperx_docker" in ids:
        # Prefer cuda when this process can see CUDA *and* we are not forced
        # to CPU. Inside an analysis container without GPU, stay on cpu and say so.
        if hardware.acceleration == "cuda" and not hardware.force_cpu:
            return SttBackendRecommendation(
                provider_id="whisperx_docker",
                device="cuda",
                reason="cuda_visible",
                caption=(
                    "Recommended: WhisperX Docker with cuda (--gpus all). "
                    "Confirm the host GPU is passed into the STT container."
                ),
            )
        caption = "Recommended: WhisperX Docker on cpu for this environment."
        if in_container:
            caption += (
                " Analysis runs in a container without CUDA — host STT may "
                "still use a GPU via a separate recipe."
            )
        elif os_f == "darwin":
            caption += " On Apple Silicon prefer whispermlx when available."
        return SttBackendRecommendation(
            provider_id="whisperx_docker",
            device="cpu",
            reason="cpu_fallback",
            caption=caption,
        )

    if "parakeet_docker" in ids:
        device = (
            "cuda"
            if hardware.acceleration == "cuda" and not hardware.force_cpu
            else "cpu"
        )
        return SttBackendRecommendation(
            provider_id="parakeet_docker",
            device=device,
            reason="parakeet_available",
            caption=(
                f"Parakeet Docker available; default device={device}. "
                "Intended for CUDA Linux hosts."
            ),
        )

    # Fallback: first available id or whisperx_docker label.
    fallback = next(iter(available_provider_ids), "whisperx_docker")
    return SttBackendRecommendation(
        provider_id=str(fallback),
        device="cpu",
        reason="default",
        caption="Use the available STT provider; device defaults to cpu.",
    )
