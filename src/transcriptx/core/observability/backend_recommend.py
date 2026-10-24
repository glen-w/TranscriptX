"""Hardware-aware analysis model hints (Theme E).

Hints only — never mutate the operator's selection silently.

STT provider recommendations live under services/transcription so core/
stays free of host-STT engine names (analysis-only invariants).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from transcriptx.core.observability.hardware_probe import HardwareSnapshot


@dataclass(frozen=True)
class AnalysisModelHint:
    message: str
    prefer_light: bool


def analysis_model_hint(
    hardware: HardwareSnapshot,
    *,
    preset: Optional[str] = None,
) -> AnalysisModelHint:
    """Hint whether to stay on light analysis models (md + MiniLM)."""
    band = hardware.memory_band
    prefer_light = band in {"low", "mid", "unknown"}
    parts: list[str] = []
    if prefer_light:
        parts.append(
            "Constrained RAM band — stay on spaCy md + MiniLM defaults; "
            "avoid en_core_web_trf / mpnet unless you have headroom."
        )
    elif band == "high":
        parts.append(
            "Mid-high RAM — defaults are fine; mpnet/lg upgrades are optional."
        )
    else:
        parts.append(
            "High RAM — higher-accuracy English models (lg/mpnet) are reasonable."
        )

    preset_k = (preset or "").strip().lower()
    if preset_k == "thorough" and hardware.install_profile == "core":
        parts.append(
            "Thorough + install profile core: heavy extras (BERTopic, voice) "
            "may be unavailable or skip."
        )
    return AnalysisModelHint(
        message=" ".join(parts),
        prefer_light=prefer_light,
    )
