from __future__ import annotations

import os
import shutil
from typing import Any, Dict


def has_models() -> bool:
    """Check if model-heavy tests are enabled."""
    return os.getenv("TRANSCRIPTX_TEST_MODELS") == "1"


def has_docker() -> bool:
    """Check if Docker is available."""
    if shutil.which("docker") is None:
        return False
    if os.getenv("DOCKER_HOST"):
        return True
    return os.path.exists("/var/run/docker.sock")


def has_ffmpeg() -> bool:
    """Check if ffmpeg/ffprobe are available."""
    return shutil.which("ffprobe") is not None or shutil.which("ffmpeg") is not None


def has_package(module_name: str) -> bool:
    """Check if a Python package can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def get_optional_packages() -> Dict[str, bool]:
    """Return availability for common optional packages."""
    return {
        "pandas": has_package("pandas"),
        "plotly": has_package("plotly"),
        "librosa": has_package("librosa"),
        "webrtcvad": has_package("webrtcvad"),
        "opensmile": has_package("opensmile"),
        "matplotlib": has_package("matplotlib"),
        "seaborn": has_package("seaborn"),
        "wordcloud": has_package("wordcloud"),
        "folium": has_package("folium"),
        "geopy": has_package("geopy"),
        "playwright": has_package("playwright"),
        "torch": has_package("torch"),
        "transformers": has_package("transformers"),
        "spacy": has_package("spacy"),
        "numpy": has_package("numpy"),
    }


def get_capabilities_snapshot() -> Dict[str, Any]:
    """Return a deterministic snapshot of runtime and package capabilities."""
    return {
        "runtime": {
            "has_models": has_models(),
            "has_docker": has_docker(),
            "has_ffmpeg": has_ffmpeg(),
        },
        "packages": get_optional_packages(),
        "environment": {
            "TRANSCRIPTX_TEST_MODELS": os.getenv("TRANSCRIPTX_TEST_MODELS"),
            "TRANSCRIPTX_DISABLE_DOWNLOADS": os.getenv("TRANSCRIPTX_DISABLE_DOWNLOADS"),
            "DOCKER_HOST": os.getenv("DOCKER_HOST"),
        },
    }
