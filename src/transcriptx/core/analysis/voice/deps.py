from __future__ import annotations

import importlib.util
from typing import Iterable


INSTALL_HINT = "pip install transcriptx[voice]"


def _missing_specs(packages: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for pkg in packages:
        try:
            if importlib.util.find_spec(pkg) is None:
                missing.append(pkg)
        except Exception:
            missing.append(pkg)
    return missing


def check_voice_optional_deps(
    *, egemaps_enabled: bool | None = None, required: list[str] | None = None
) -> dict:
    """
    Cheap dependency check for voice modules (no heavy imports).
    Returns structured metadata suitable for skip payloads.
    """
    if required is None:
        required = ["webrtcvad", "librosa", "soundfile"]
        if egemaps_enabled:
            required.append("opensmile")
    missing = _missing_specs(required)
    if missing:
        return {
            "ok": False,
            "missing_optional_deps": missing,
            "install_hint": INSTALL_HINT,
        }
    return {"ok": True, "missing_optional_deps": [], "install_hint": INSTALL_HINT}
