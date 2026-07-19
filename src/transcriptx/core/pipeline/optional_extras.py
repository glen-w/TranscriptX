"""Optional-extra package detection without heavy imports.

Catalogue / UI paths must use non-importing distribution probes.
Execution preflight may use importing checks to distinguish missing vs broken.
"""

from __future__ import annotations

import importlib.metadata
from typing import Dict, Optional

# Extra name -> representative distribution name on PyPI / importlib.metadata.
# Prefer distribution metadata over import names so catalogue never loads natives.
EXTRA_DISTRIBUTION_NAME: Dict[str, str] = {
    "voice": "opensmile",
    "emotion": "transformers",
    "emotion_lexical": "nrclex",
    "emotion_transformers": "transformers",
    "nlp": "spacy",
    "ner": "spacy",
    "bertopic": "bertopic",
    "maps": "folium",
    "visualization": "matplotlib",
    "plotly": "plotly",
}


def distribution_name_for_extra(extra_name: str) -> Optional[str]:
    """Return the representative distribution name for an optional extra."""
    return EXTRA_DISTRIBUTION_NAME.get(extra_name)


def is_extra_distribution_present(extra_name: str) -> bool:
    """
    Return True when package metadata for the extra's representative dist exists.

    Uses ``importlib.metadata`` only — does **not** import the package or its
    native extensions. Suitable for catalogue / UI "apparently available" state.
    """
    dist_name = distribution_name_for_extra(extra_name)
    if not dist_name:
        return False
    try:
        importlib.metadata.version(dist_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False
    except Exception:
        return False


def resolve_extra_dependency_reason(extra_name: str) -> Optional[str]:
    """
    Classify optional-extra readiness without importing.

    Returns:
      - ``None`` when distribution metadata is present (may still fail on import)
      - ``missing_extra:<extra>`` when metadata is absent
    """
    if is_extra_distribution_present(extra_name):
        return None
    return f"missing_extra:{extra_name}"
