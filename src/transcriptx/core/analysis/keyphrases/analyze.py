"""Keyphrases analyze pipeline."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.keyphrases.contract import (
    ALL_METHODS,
    KeyphrasesResult,
    MethodRankBlock,
    MethodName,
    SCHEMA_ID,
    SEMANTICS_VERSION,
    SkippedMethod,
    empty_result,
)
from transcriptx.core.analysis.keyphrases.noun_chunks import (
    extract_noun_chunk_stores,
    store_to_ranked,
)
from transcriptx.core.analysis.keyphrases.optional_methods import run_keybert, run_yake
from transcriptx.core.analysis.keyphrases.phrase_quality_adapter import (
    KEYPHRASES_ADAPTER_VERSION as ADAPTER_VERSION,
)


def _settings() -> dict[str, Any]:
    try:
        from transcriptx.core.utils.config import get_config

        cfg = get_config().analysis.keyphrases
        enabled = (
            list(cfg.enabled_methods) if cfg.enabled_methods else list(ALL_METHODS)
        )
        return {
            "enabled_methods": [str(m) for m in enabled],
            "max_phrases": int(cfg.max_phrases),
            "min_phrase_tokens": int(cfg.min_phrase_tokens),
            "max_phrase_tokens": int(cfg.max_phrase_tokens),
            "min_occurrences_global": int(cfg.min_occurrences_global),
            "min_occurrences_speaker": int(cfg.min_occurrences_speaker),
            "diversity_jaccard_threshold": float(cfg.diversity_jaccard_threshold),
            "evidence_max_per_phrase": int(cfg.evidence_max_per_phrase),
            "evidence_snippet_max_chars": int(cfg.evidence_snippet_max_chars),
            "keybert_model_id": str(cfg.keybert_model_id),
            "yake_lan": str(cfg.yake_lan),
            "yake_n": int(cfg.yake_n),
            "yake_top": int(cfg.yake_top),
            "yake_window_size": int(cfg.yake_window_size),
            "min_member_sessions": int(cfg.min_member_sessions),
        }
    except Exception:
        return {
            "enabled_methods": list(ALL_METHODS),
            "max_phrases": 40,
            "min_phrase_tokens": 1,
            "max_phrase_tokens": 6,
            "min_occurrences_global": 2,
            "min_occurrences_speaker": 1,
            "diversity_jaccard_threshold": 0.85,
            "evidence_max_per_phrase": 3,
            "evidence_snippet_max_chars": 120,
            "keybert_model_id": "sentence-transformers/all-MiniLM-L6-v2",
            "yake_lan": "en",
            "yake_n": 3,
            "yake_top": 40,
            "yake_window_size": 2,
            "min_member_sessions": 2,
        }


def _language(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    for key in ("language", "lang", "detected_language"):
        val = metadata.get(key)
        if val:
            return str(val)
    return None


def _is_supported_language(language: str | None) -> bool:
    if not language:
        return True
    lang = language.casefold().strip()
    return lang in {"en", "eng", "english", "en-us", "en-gb", "unknown"}


def analyze_keyphrases(
    *,
    filtered_segments: list[dict[str, Any]] | None,
    metadata: dict[str, Any] | None = None,
) -> KeyphrasesResult:
    settings = _settings()
    enabled = set(settings["enabled_methods"])
    skipped: list[SkippedMethod] = []
    methods_run: list[MethodName] = []
    global_by_method: dict[str, MethodRankBlock] = {}
    speakers_by_method: dict[str, dict[str, MethodRankBlock]] = {}

    meta = {
        "schema_id": SCHEMA_ID,
        "semantics_version": SEMANTICS_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "config": {k: settings[k] for k in settings},
        "language": _language(metadata),
    }

    if "noun_chunks" not in enabled:
        skipped.append(
            SkippedMethod(method="noun_chunks", reason_code="disabled_by_config")
        )
        result = empty_result(
            evaluation_state="skipped",
            usable=False,
            skipped_methods=skipped,
            metadata=meta,
        )
        return _run_optionals(
            result,
            filtered_segments or [],
            settings=settings,
            enabled=enabled,
            language=_language(metadata),
        )

    if not filtered_segments:
        skipped.append(
            SkippedMethod(
                method="noun_chunks",
                reason_code="empty_result",
                detail="no insight_eligibility.filtered_segments",
            )
        )
        return empty_result(
            evaluation_state="empty",
            usable=True,
            skipped_methods=skipped,
            metadata=meta,
        )

    language = _language(metadata)
    if not _is_supported_language(language):
        skipped.append(
            SkippedMethod(
                method="noun_chunks",
                reason_code="unsupported_language",
                detail=str(language),
            )
        )
        for method in ("yake", "keybert"):
            if method in enabled:
                skipped.append(
                    SkippedMethod(
                        method=method,  # type: ignore[arg-type]
                        reason_code="unsupported_language",
                        detail=str(language),
                    )
                )
        return empty_result(
            evaluation_state="skipped",
            usable=False,
            skipped_methods=skipped,
            metadata=meta,
        )

    try:
        from transcriptx.core.utils.nlp_runtime import get_nlp_model

        nlp = get_nlp_model()
    except Exception as exc:
        skipped.append(
            SkippedMethod(
                method="noun_chunks",
                reason_code="missing_package",
                detail=str(exc)[:200],
            )
        )
        result = empty_result(
            evaluation_state="failed",
            usable=False,
            skipped_methods=skipped,
            metadata=meta,
        )
        return _run_optionals(
            result,
            filtered_segments,
            settings=settings,
            enabled=enabled,
            language=language,
        )

    try:
        global_store, speaker_stores = extract_noun_chunk_stores(
            filtered_segments,
            nlp=nlp,
            min_phrase_tokens=settings["min_phrase_tokens"],
            max_phrase_tokens=settings["max_phrase_tokens"],
            evidence_max_per_phrase=settings["evidence_max_per_phrase"],
            evidence_snippet_max_chars=settings["evidence_snippet_max_chars"],
        )
        global_phrases = store_to_ranked(
            global_store,
            language=language,
            min_occurrences=settings["min_occurrences_global"],
            max_phrases=settings["max_phrases"],
            diversity_jaccard_threshold=settings["diversity_jaccard_threshold"],
        )
        speaker_blocks: dict[str, MethodRankBlock] = {}
        for speaker, store in sorted(speaker_stores.items()):
            ranked = store_to_ranked(
                store,
                language=language,
                min_occurrences=settings["min_occurrences_speaker"],
                max_phrases=settings["max_phrases"],
                diversity_jaccard_threshold=settings["diversity_jaccard_threshold"],
            )
            speaker_blocks[speaker] = MethodRankBlock(
                method="noun_chunks",
                phrases=ranked,
                evaluation_state="scored" if ranked else "empty",
            )
        state = "scored" if global_phrases else "empty"
        global_by_method["noun_chunks"] = MethodRankBlock(
            method="noun_chunks",
            phrases=global_phrases,
            evaluation_state=state,
        )
        speakers_by_method["noun_chunks"] = speaker_blocks
        methods_run.append("noun_chunks")
    except Exception as exc:
        skipped.append(
            SkippedMethod(
                method="noun_chunks",
                reason_code="inference_failure",
                detail=str(exc)[:200],
            )
        )
        result = empty_result(
            evaluation_state="failed",
            usable=False,
            skipped_methods=skipped,
            metadata=meta,
        )
        return _run_optionals(
            result,
            filtered_segments,
            settings=settings,
            enabled=enabled,
            language=language,
        )

    result = KeyphrasesResult(
        usable=True,
        evaluation_state=global_by_method["noun_chunks"].evaluation_state,
        methods_run=methods_run,
        skipped_methods=skipped,
        global_by_method=global_by_method,
        speakers_by_method=speakers_by_method,
        metadata=meta,
    )
    return _run_optionals(
        result,
        filtered_segments,
        settings=settings,
        enabled=enabled,
        language=language,
    )


def _run_optionals(
    result: KeyphrasesResult,
    filtered_segments: list[dict[str, Any]],
    *,
    settings: dict[str, Any],
    enabled: set[str],
    language: str | None,
) -> KeyphrasesResult:
    skipped = list(result.skipped_methods)
    methods_run = list(result.methods_run)
    global_by_method = dict(result.global_by_method)
    speakers_by_method = dict(result.speakers_by_method)

    if "yake" in enabled:
        if language and not _is_supported_language(language):
            skipped.append(
                SkippedMethod(
                    method="yake",
                    reason_code="unsupported_language",
                    detail=str(language),
                )
            )
        else:
            block, skip = run_yake(
                filtered_segments,
                max_phrases=settings["max_phrases"],
                lan=settings["yake_lan"],
                n=settings["yake_n"],
                top=settings["yake_top"],
                window_size=settings["yake_window_size"],
            )
            if skip:
                skipped.append(skip)
            elif block:
                global_by_method["yake"] = block
                methods_run.append("yake")

    if "keybert" in enabled:
        if language and not _is_supported_language(language):
            skipped.append(
                SkippedMethod(
                    method="keybert",
                    reason_code="unsupported_language",
                    detail=str(language),
                )
            )
        else:
            block, skip = run_keybert(
                filtered_segments,
                max_phrases=settings["max_phrases"],
                model_id=settings["keybert_model_id"],
            )
            if skip:
                skipped.append(skip)
            elif block:
                global_by_method["keybert"] = block
                methods_run.append("keybert")
                meta = dict(result.metadata)
                meta["keybert_model_id"] = settings["keybert_model_id"]
                result = result.model_copy(update={"metadata": meta})

    seen: set[str] = set()
    ordered: list[MethodName] = []
    for m in methods_run:
        if m not in seen:
            seen.add(m)
            ordered.append(m)

    return result.model_copy(
        update={
            "methods_run": ordered,
            "skipped_methods": skipped,
            "global_by_method": global_by_method,
            "speakers_by_method": speakers_by_method,
        }
    )
