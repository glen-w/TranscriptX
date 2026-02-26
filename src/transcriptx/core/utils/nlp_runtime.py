"""
Centralized spaCy model runtime loading with thread-safe caching.

spaCy model auto-download is allowed by default when not in core mode, unless
TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1. Model name is resolved via TRANSCRIPTX_SPACY_MODEL
(default en_core_web_md) or config (e.g. ner_use_light_model).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional, Any

logger = logging.getLogger(__name__)

_nlp_model: Optional[Any] = None


def _patch_transformers_for_spacy() -> None:
    """Patch transformers so spacy_transformers entry point can load on transformers 5.x.

    When spaCy loads any model, it loads all registered pipeline entry points, including
    spacy_transformers. spacy_transformers 1.x imports BatchEncoding from
    transformers.tokenization_utils, but in transformers 5.x that class lives in
    tokenization_utils_base. This patch adds the alias so the import succeeds.
    """
    try:
        import transformers.tokenization_utils as tu  # noqa: PLC0415

        if not hasattr(tu, "BatchEncoding"):
            from transformers.tokenization_utils_base import (
                BatchEncoding,
            )  # noqa: PLC0415

            tu.BatchEncoding = BatchEncoding
    except Exception:
        pass


_nlp_model_name: Optional[str] = None
_nlp_lock = threading.Lock()

_DISABLE_DOWNLOADS_ENV = "TRANSCRIPTX_DISABLE_DOWNLOADS"
_DISABLE_SPACY_DOWNLOAD_ENV = "TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD"


def _downloads_disabled() -> bool:
    value = os.getenv(_DISABLE_DOWNLOADS_ENV, "").strip().lower()
    if value == "":
        # Default to downloads disabled unless explicitly opted in.
        return True
    return value in {"1", "true", "yes", "on"}


def _spacy_download_disabled() -> bool:
    """True only when TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD is set to 1/true/yes/on. Unset = allow."""
    value = os.getenv(_DISABLE_SPACY_DOWNLOAD_ENV, "").strip().lower()
    if value == "":
        return False
    return value in {"1", "true", "yes", "on"}


def _core_mode() -> bool:
    """True if core mode is on (no download, hint only)."""
    env_val = os.getenv("TRANSCRIPTX_CORE")
    if env_val is not None:
        return str(env_val).strip().lower() in ("1", "true", "yes", "on")
    try:
        from transcriptx.core.utils.config import get_config

        return get_config().core_mode
    except Exception:
        return True


def _resolve_model_name(preferred: Optional[str] = None) -> str:
    if preferred:
        return preferred

    env_model = os.getenv("TRANSCRIPTX_SPACY_MODEL")
    if env_model:
        return env_model

    try:
        from transcriptx.core.utils.config import get_config

        config = get_config()
        if getattr(config.analysis, "ner_use_light_model", False):
            return "en_core_web_sm"
    except Exception:
        pass

    return "en_core_web_md"


def ensure_spacy_model(model_name: Optional[str] = None) -> None:
    """
    Ensure the given spaCy model is available. Single helper for the nlp layer.

    Model name is resolved via _resolve_model_name (TRANSCRIPTX_SPACY_MODEL, config;
    default en_core_web_md). We only hard-fail before attempting download when
    TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1 or core_mode; otherwise we try download
    and raise only if download fails (e.g. offline), with a message including
    the manual command and how to disable.
    """
    resolved = _resolve_model_name(model_name)
    spacy = _import_spacy()
    try:
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            spacy.load(resolved)
        return
    except OSError:
        pass

    if _core_mode():
        raise OSError(
            f"spaCy model '{resolved}' is not installed. "
            f"Install NLP extra and download the model: pip install 'transcriptx[nlp]' && python -m spacy download {resolved}"
        )

    if _spacy_download_disabled():
        raise OSError(
            f"spaCy model '{resolved}' is not installed and auto-download is disabled "
            f"(TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1). "
            f"Install manually: python -m spacy download {resolved}"
        )

    try:
        from transcriptx.core.utils.notifications import notify_user

        notify_user(
            f"📥 Downloading spaCy model '{resolved}' (required for NLP analysis)...",
            technical=True,
            section="ner",
        )
    except Exception:
        print(f"📥 Downloading spaCy model '{resolved}' (required for NLP analysis)...")

    try:
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            spacy.cli.download(resolved)
    except Exception as exc:
        error_msg = (
            f"spaCy model '{resolved}' auto-download was attempted but failed: {exc}. "
            f"To install manually run: python -m spacy download {resolved} "
            f"(to disable auto-download set TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1)."
        )
        try:
            from transcriptx.core.utils.notifications import notify_user

            notify_user(error_msg, technical=True, section="ner")
        except Exception:
            print(error_msg)
        raise OSError(error_msg) from exc


def _ensure_spacy_model(model_name: Optional[str] = None) -> None:
    """Internal: ensure model available; logs and returns when TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1 (caller may fall back to blank('en'))."""
    resolved = _resolve_model_name(model_name)
    spacy = _import_spacy()
    try:
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            spacy.load(resolved)
        return
    except OSError:
        pass

    if _core_mode():
        raise OSError(
            f"spaCy model '{resolved}' is not installed. "
            f"Install NLP extra and download the model: pip install 'transcriptx[nlp]' && python -m spacy download {resolved}"
        )

    if _spacy_download_disabled():
        logger.info(
            "spaCy model auto-download skipped (TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1). "
            "Install manually: python -m spacy download %s",
            resolved,
        )
        return

    try:
        from transcriptx.core.utils.notifications import notify_user

        notify_user(
            f"📥 Downloading spaCy model '{resolved}' (required for NLP analysis)...",
            technical=True,
            section="ner",
        )
    except Exception:
        print(f"📥 Downloading spaCy model '{resolved}' (required for NLP analysis)...")

    try:
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            spacy.cli.download(resolved)
    except Exception as exc:
        error_msg = (
            f"spaCy model '{resolved}' auto-download was attempted but failed: {exc}. "
            f"To install manually run: python -m spacy download {resolved} "
            f"(to disable auto-download set TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD=1)."
        )
        try:
            from transcriptx.core.utils.notifications import notify_user

            notify_user(error_msg, technical=True, section="ner")
        except Exception:
            print(error_msg)
        raise OSError(error_msg) from exc


def _import_spacy():
    from transcriptx.core.utils.lazy_imports import optional_import

    return optional_import("spacy", "NLP (NER, etc.)", "nlp", auto_install=True)


def get_nlp_model(model_name: Optional[str] = None):
    """Get spaCy model with thread-safe lazy loading."""
    global _nlp_model, _nlp_model_name

    if _nlp_model is not None:
        return _nlp_model

    with _nlp_lock:
        if _nlp_model is not None:
            return _nlp_model

        _patch_transformers_for_spacy()
        resolved = _resolve_model_name(model_name)
        _ensure_spacy_model(resolved)

        spacy = _import_spacy()
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            try:
                _nlp_model = spacy.load(resolved)
                _nlp_model_name = resolved
            except OSError:
                _nlp_model = spacy.blank("en")
                _nlp_model_name = "blank:en"
        return _nlp_model


def get_nlp_model_name() -> Optional[str]:
    return _nlp_model_name
