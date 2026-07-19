"""BERTopic optional-dependency and model preflight (execution-time)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

from transcriptx.core.pipeline.optional_dep_outcomes import (
    broken_extra_reason,
    install_hint_for_extra,
    missing_extra_reason,
)
from transcriptx.core.pipeline.optional_extras import is_extra_distribution_present
from transcriptx.core.utils.downloads import (
    downloads_disabled_failfast_message,
)
from transcriptx.core.utils.lazy_imports import optional_import

EXTRA_NAME = "bertopic"


def classify_bertopic_package_state() -> Tuple[str, Optional[str]]:
    """
    Classify bertopic package readiness.

    Returns ``(state, reason)`` where state is one of:
    ``missing``, ``present``, or (after import attempt) ``broken`` / ``import_ok``.
    Non-importing probe first; import verification is separate.
    """
    if not is_extra_distribution_present(EXTRA_NAME):
        return "missing", missing_extra_reason(EXTRA_NAME)
    return "present", None


def import_bertopic(*, auto_install: bool = False) -> Any:
    """Import bertopic with auto-install disabled by policy."""
    return optional_import(
        "bertopic",
        "BERTopic topic modeling",
        EXTRA_NAME,
        auto_install=auto_install,
    )


def verify_bertopic_import(*, auto_install: bool = False) -> Tuple[Any, Optional[str]]:
    """
    Execution-time import verification.

    Returns ``(module, None)`` on success, or ``(None, reason)`` on failure.
    Distinguishes missing vs broken when distribution metadata is present.
    """
    state, missing_reason = classify_bertopic_package_state()
    if state == "missing":
        return None, missing_reason
    try:
        mod = import_bertopic(auto_install=auto_install)
        return mod, None
    except ImportError:
        return None, broken_extra_reason(EXTRA_NAME)
    except Exception:
        return None, broken_extra_reason(EXTRA_NAME)


def redact_path_for_diagnostics(path: Optional[str]) -> Optional[str]:
    """Redact sensitive absolute paths to basename for provenance/diagnostics."""
    if not path:
        return None
    try:
        return Path(path).name
    except Exception:
        return "<redacted>"


def embedding_model_policy_check(embedding_model: str) -> Optional[str]:
    """
    Offline / path policy for the configured embedding model identity.

    - Local paths: require existence (strict).
    - Hub IDs: syntax-only check — do **not** claim existence without network/load.
      Real usability is known only during load/fit.
    Returns a stable reason string or None when OK to attempt.
    """
    model = (embedding_model or "").strip()
    if not model:
        return "config:empty_embedding_model"

    looks_like_path = (
        model.startswith("/")
        or model.startswith(".")
        or model.startswith("~")
        or "\\" in model
        or Path(model).suffix in {".bin", ".safetensors", ".pt", ".pth"}
    )
    if looks_like_path:
        path = Path(model).expanduser()
        if not path.exists():
            return "model_unavailable:local_path"
        return None

    # Hub-style id: require org/name or short name with alnum/_-
    if "/" in model:
        parts = model.split("/")
        if len(parts) != 2 or not all(parts):
            return "config:invalid_hub_id"
    elif not model.replace("-", "").replace("_", "").isalnum():
        return "config:invalid_hub_id"

    return None


def offline_block_message(embedding_model: str) -> str:
    return downloads_disabled_failfast_message(
        f"BERTopic embedding model '{embedding_model}'",
        extra_hint=install_hint_for_extra(EXTRA_NAME),
    )
