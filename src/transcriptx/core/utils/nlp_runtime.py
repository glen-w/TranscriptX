"""
Centralized spaCy model runtime loading with thread-safe caching.
"""

from __future__ import annotations

import os
import threading
from typing import Optional, Any

_nlp_model: Optional[Any] = None
_nlp_model_name: Optional[str] = None
_nlp_lock = threading.Lock()

_DISABLE_DOWNLOADS_ENV = "TRANSCRIPTX_DISABLE_DOWNLOADS"


def _downloads_disabled() -> bool:
    value = os.getenv(_DISABLE_DOWNLOADS_ENV, "").strip().lower()
    if value == "":
        # Default to downloads disabled unless explicitly opted in.
        return True
    return value in {"1", "true", "yes", "on"}


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


def _ensure_spacy_model(model_name: str) -> None:
    """Ensure spaCy model is available before loading."""
    spacy = _import_spacy()
    try:
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            spacy.load(model_name)
        return
    except OSError:
        pass

    if _downloads_disabled():
        # CI/offline mode: avoid network calls. Caller will fall back to blank("en").
        return

    try:
        from transcriptx.core.utils.notifications import notify_user

        notify_user(
            f"📥 Downloading spaCy model '{model_name}' (required for NLP analysis)...",
            technical=True,
            section="ner",
        )
    except Exception:
        print(
            f"📥 Downloading spaCy model '{model_name}' (required for NLP analysis)..."
        )

    try:
        from transcriptx.core.utils.output import suppress_stdout_stderr

        with suppress_stdout_stderr():
            spacy.cli.download(model_name)
    except Exception as exc:
        error_msg = (
            f"⚠️ Could not download spaCy model '{model_name}': {exc}. "
            f"Please run: python -m spacy download {model_name}"
        )
        try:
            from transcriptx.core.utils.notifications import notify_user

            notify_user(error_msg, technical=True, section="ner")
        except Exception:
            print(error_msg)
        raise


def _import_spacy():
    import spacy

    return spacy


def get_nlp_model(model_name: Optional[str] = None):
    """Get spaCy model with thread-safe lazy loading."""
    global _nlp_model, _nlp_model_name

    if _nlp_model is not None:
        return _nlp_model

    with _nlp_lock:
        if _nlp_model is not None:
            return _nlp_model

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

