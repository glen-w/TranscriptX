"""Lexical emotion preflight — fail before emitting zero profiles."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from transcriptx.core.analysis.emotion.lexical_pipeline import NRC_LEXICAL_PIPELINE_V1
from transcriptx.core.utils.downloads import downloads_disabled

# Minimum compatible nrclex major.minor for pipeline v1
PINNED_NRCLEX_MIN = (3, 0)


@dataclass
class LexicalPreflightResult:
    ok: bool
    reason: str
    nrclex_version: str | None = None
    details: dict[str, Any] | None = None


def _parse_version(ver: str) -> tuple[int, ...]:
    parts = []
    for p in ver.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def run_lexical_preflight() -> LexicalPreflightResult:
    """Verify nrclex, lexicon, and TextBlob resources before scoring."""
    if NRC_LEXICAL_PIPELINE_V1 != "nrc_lexical_pipeline_v1":
        return LexicalPreflightResult(
            False, "lexical_preflight_failed", details={"pipeline": "mismatch"}
        )

    try:
        ver = version("nrclex")
    except PackageNotFoundError:
        return LexicalPreflightResult(
            False, "lexical_preflight_failed", details={"error": "nrclex_not_installed"}
        )

    parsed = _parse_version(ver)
    if parsed[:2] < PINNED_NRCLEX_MIN:
        return LexicalPreflightResult(
            False,
            "lexical_preflight_failed",
            nrclex_version=ver,
            details={"error": "nrclex_version_too_old", "got": ver},
        )

    try:
        from nrclex import NRCLex
    except Exception as exc:
        return LexicalPreflightResult(
            False,
            "lexical_preflight_failed",
            nrclex_version=ver,
            details={"error": "nrclex_import", "message": str(exc)},
        )

    try:
        if hasattr(NRCLex, "load_raw_text"):
            try:
                probe = NRCLex()
                probe.load_raw_text("happy joy good")
            except TypeError:
                probe = NRCLex("happy joy good")
        else:
            probe = NRCLex("happy joy good")
        # Lexicon must yield some affect signal on positive probe text
        raw = getattr(probe, "raw_emotion_scores", None) or getattr(
            probe, "affect_frequencies", None
        )
        lexicon = getattr(probe, "lexicon", None)
        if (not isinstance(raw, dict) or not raw) and (
            not isinstance(lexicon, dict) or not lexicon
        ):
            affect = getattr(probe, "AffectDict", None) or getattr(
                probe, "affect_dict", None
            )
            if not isinstance(affect, dict) or not affect:
                return LexicalPreflightResult(
                    False,
                    "lexical_preflight_failed",
                    nrclex_version=ver,
                    details={"error": "lexicon_unavailable"},
                )
    except Exception as exc:
        return LexicalPreflightResult(
            False,
            "lexical_preflight_failed",
            nrclex_version=ver,
            details={"error": "lexicon_probe", "message": str(exc)},
        )

    # TextBlob corpora — required by some nrclex paths
    try:
        import nltk

        for resource in ("tokenizers/punkt", "corpora/wordnet"):
            try:
                nltk.data.find(resource)
            except LookupError:
                if downloads_disabled():
                    # punkt may be punkt_tab on newer nltk
                    try:
                        nltk.data.find("tokenizers/punkt_tab")
                        continue
                    except LookupError:
                        return LexicalPreflightResult(
                            False,
                            "lexical_preflight_failed",
                            nrclex_version=ver,
                            details={
                                "error": "tokenizer_resources_missing",
                                "resource": resource,
                            },
                        )
    except Exception as exc:
        return LexicalPreflightResult(
            False,
            "lexical_preflight_failed",
            nrclex_version=ver,
            details={"error": "nltk_check", "message": str(exc)},
        )

    return LexicalPreflightResult(True, "ok", nrclex_version=ver)
