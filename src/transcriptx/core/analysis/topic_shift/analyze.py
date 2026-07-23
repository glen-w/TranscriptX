"""Orchestrate topic_shift analysis (pure compute + envelope assembly)."""

from __future__ import annotations

import statistics
import time
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.topic_shift.detector import (
    DetectorThresholds,
    detect_peaks,
    reconcile_chunk_peaks,
)
from transcriptx.core.analysis.topic_shift.embed import (
    TopicShiftEmbedder,
    model_weights_locally_available,
)
from transcriptx.core.analysis.topic_shift.keywords import keyword_hints_for_segments
from transcriptx.core.analysis.topic_shift.language import (
    resolve_transcript_language,
    select_backend,
)
from transcriptx.core.analysis.topic_shift.semantics import (
    BACKEND_THRESHOLDS,
    DEFAULT_CENTROID_RADIUS,
    DEFAULT_CENTROID_THRESHOLD,
    DEFAULT_CHUNK_OVERLAP_WINDOWS,
    DEFAULT_EDGE_EXCLUDE,
    DEFAULT_EN_MODEL,
    DEFAULT_MAX_SHIFTS,
    DEFAULT_MAX_WINDOWS_PER_CHUNK,
    DEFAULT_MIN_DURATION_FOR_RATE_SECONDS,
    DEFAULT_MIN_GAP_SECONDS,
    DEFAULT_MIN_GAP_WINDOWS,
    DEFAULT_MIN_TEXT_CHARS,
    DEFAULT_MIN_WINDOWS,
    DEFAULT_MULTI_MODEL,
    DEFAULT_SMOOTH_WIDTH,
    DEFAULT_STRIDE,
    DEFAULT_WINDOW_SIZE,
    ENGLISH_CODES,
    SCHEMA_VERSION,
    SEMANTICS_BY_BACKEND,
)
from transcriptx.core.analysis.topic_shift.segments import canonicalise_segments
from transcriptx.core.analysis.topic_shift.spans import (
    build_coverage_and_events,
    transcript_identity_for_segments,
)
from transcriptx.core.analysis.topic_shift.windowing import (
    TopicWindow,
    build_rolling_windows,
    partition_overlapping_chunks,
)


def _thresholds_for(backend: str, overrides: Mapping[str, Any] | None) -> DetectorThresholds:
    base = dict(BACKEND_THRESHOLDS.get(backend) or BACKEND_THRESHOLDS["tfidf"])
    if overrides:
        for key in ("k_mad", "absolute_floor", "min_prominence"):
            if key in overrides:
                base[key] = float(overrides[key])
    return DetectorThresholds(
        k_mad=float(base["k_mad"]),
        absolute_floor=float(base["absolute_floor"]),
        min_prominence=float(base["min_prominence"]),
    )


def _transformers_probe(
    allow_downloads: bool,
    *,
    en_model: str,
    multi_model: str,
) -> tuple[bool, bool]:
    """Return (en_available, multi_available). Offline probes local weights only."""
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except Exception:
        return False, False
    if allow_downloads:
        return True, True
    return (
        model_weights_locally_available(en_model),
        model_weights_locally_available(multi_model),
    )


def _texts_for_backend(
    windows: Sequence[TopicWindow], backend: str
) -> list[str]:
    """Transformers use raw_text; TF-IDF paths use lexical_text (raw fallback)."""
    if backend in ("tfidf", "tfidf_char"):
        return [
            (w.lexical_text.strip() if w.lexical_text and w.lexical_text.strip() else w.raw_text)
            for w in windows
        ]
    return [w.raw_text for w in windows]


def _embed_failed_status(
    *,
    preferred: str,
    limited: bool,
    lang_code: str | None,
) -> str:
    """unsupported_language when non-English path cannot embed; else backend_unavailable.

    Do not use post-fallback ``limited`` (e.g. English transformers → tfidf_char):
    that flag means lexical fallback was attempted, not that the language is unsupported.
    """
    del limited  # retained for call-site stability; classification uses preferred/lang only
    code = (lang_code or "en").lower()
    non_english = preferred == "transformers_multi" or code not in ENGLISH_CODES
    return "unsupported_language" if non_english else "backend_unavailable"


def run_topic_shift_analysis(
    segments: Sequence[Mapping[str, Any]],
    *,
    metadata: Mapping[str, Any] | None = None,
    settings: Mapping[str, Any] | None = None,
    generation_id: str = "pending",
    allow_downloads: bool = True,
) -> dict[str, Any]:
    """
    Compute deterministic topic_shift payloads.

    Returns dict with keys: analytical_status, spans_envelope, events_envelope,
    stats_envelope, events (Event list), operational (volatile diagnostics).
    """
    cfg = dict(settings or {})
    raw_segments = [dict(s) for s in segments if isinstance(s, Mapping)]
    identity = transcript_identity_for_segments(raw_segments)

    canon = canonicalise_segments(
        raw_segments,
        min_text_chars=int(cfg.get("min_text_chars", DEFAULT_MIN_TEXT_CHARS)),
    )
    if canon.analytical_status:
        return _empty_result(
            identity=identity,
            generation_id=generation_id,
            analytical_status=canon.analytical_status,
            backend="tfidf",
            reason=canon.analytical_status,
        )

    segs = canon.segments
    lang_code, lang_tag = resolve_transcript_language(raw_segments, metadata)
    en_model = str(cfg.get("en_model", DEFAULT_EN_MODEL))
    multi_model = str(cfg.get("multi_model", DEFAULT_MULTI_MODEL))
    en_ok, multi_ok = _transformers_probe(
        allow_downloads, en_model=en_model, multi_model=multi_model
    )
    preferred, limited = select_backend(
        lang_code,
        lang_tag,
        transformers_available=en_ok,
        multilingual_available=multi_ok,
    )

    window_size = int(cfg.get("window_size", DEFAULT_WINDOW_SIZE))
    stride = int(cfg.get("stride", DEFAULT_STRIDE))
    windows = build_rolling_windows(segs, window_size=window_size, stride=stride)
    min_windows = int(cfg.get("min_windows_for_detection", DEFAULT_MIN_WINDOWS))
    if len(windows) < min_windows:
        return _empty_result(
            identity=identity,
            generation_id=generation_id,
            analytical_status="insufficient_content",
            backend=preferred,
            reason="insufficient_windows",
            language_code=lang_code,
            language_resolution=lang_tag,
            limited_language_support=limited,
        )

    chunks, coverage = partition_overlapping_chunks(
        windows,
        max_windows_per_chunk=int(
            cfg.get("max_windows_per_chunk", DEFAULT_MAX_WINDOWS_PER_CHUNK)
        ),
        overlap_windows=int(
            cfg.get("chunk_overlap_windows", DEFAULT_CHUNK_OVERLAP_WINDOWS)
        ),
    )
    if not coverage.complete:
        return _empty_result(
            identity=identity,
            generation_id=generation_id,
            analytical_status="invalid_input",
            backend=preferred,
            reason="incomplete_coverage",
        )

    timeout_seconds = float(cfg.get("timeout_seconds", 600.0) or 600.0)
    deadline = time.perf_counter() + max(1.0, timeout_seconds)
    embedder = TopicShiftEmbedder(
        en_model=en_model,
        multi_model=multi_model,
        batch_size=int(cfg.get("batch_size", 32)),
        allow_downloads=allow_downloads,
        lru_size=int(cfg.get("lru_size", 4096)),
        deadline_monotonic=deadline,
    )

    backend = preferred
    semantics = SEMANTICS_BY_BACKEND[backend]
    texts = _texts_for_backend(windows, backend)
    embed = embedder.embed(texts, backend=backend, semantics_version=semantics)
    if embed is None and backend.startswith("transformers"):
        # Full corpus TF-IDF restart (lexical channel)
        backend = "tfidf"
        semantics = SEMANTICS_BY_BACKEND[backend]
        texts = _texts_for_backend(windows, backend)
        embed = embedder.embed(texts, backend=backend, semantics_version=semantics)
        if embed is None:
            backend = "tfidf_char"
            semantics = SEMANTICS_BY_BACKEND[backend]
            texts = _texts_for_backend(windows, backend)
            embed = embedder.embed(texts, backend=backend, semantics_version=semantics)
            limited = True
    elif embed is None and backend == "tfidf":
        backend = "tfidf_char"
        semantics = SEMANTICS_BY_BACKEND[backend]
        texts = _texts_for_backend(windows, backend)
        embed = embedder.embed(texts, backend=backend, semantics_version=semantics)
        limited = True

    if embed is None:
        return _empty_result(
            identity=identity,
            generation_id=generation_id,
            analytical_status=_embed_failed_status(
                preferred=preferred, limited=limited, lang_code=lang_code
            ),
            backend=preferred,
            reason="embed_failed",
            language_code=lang_code,
            language_resolution=lang_tag,
            limited_language_support=limited,
        )

    backend = embed.backend
    semantics = embed.semantics_version
    thr = _thresholds_for(backend, cfg.get("thresholds"))

    # Detect per chunk then reconcile
    chunk_accepted = []
    for chunk in chunks:
        # Map chunk windows to embedding rows via global_index
        idxs = [w.global_index for w in chunk.windows]
        if len(idxs) < 2:
            continue
        sub_emb = embed.vectors[idxs]
        sub_windows = list(chunk.windows)
        # Remap distance indices to global: local i → global idxs[i]
        peaks, _raw, _sm, _thr = detect_peaks(
            sub_emb,
            sub_windows,
            thresholds=thr,
            smooth_width=int(cfg.get("smooth_width", DEFAULT_SMOOTH_WIDTH)),
            edge_exclude=int(cfg.get("edge_exclude", DEFAULT_EDGE_EXCLUDE)),
            centroid_radius=int(cfg.get("centroid_radius", DEFAULT_CENTROID_RADIUS)),
            centroid_threshold=float(
                cfg.get("centroid_threshold", DEFAULT_CENTROID_THRESHOLD)
            ),
            min_gap_windows=int(cfg.get("min_gap_windows", DEFAULT_MIN_GAP_WINDOWS)),
            min_gap_seconds=float(cfg.get("min_gap_seconds", DEFAULT_MIN_GAP_SECONDS)),
            max_shifts=int(cfg.get("max_shifts", DEFAULT_MAX_SHIFTS)),
        )
        # Rewrite distance_index to global window boundary index
        remapped = []
        for p in peaks:
            if not p.accepted:
                continue
            global_i = idxs[p.distance_index]
            from transcriptx.core.analysis.topic_shift.detector import PeakCandidate

            remapped.append(
                PeakCandidate(
                    distance_index=global_i,
                    raw_distance=p.raw_distance,
                    smoothed_distance=p.smoothed_distance,
                    local_prominence=p.local_prominence,
                    decision_threshold=p.decision_threshold,
                    normalized_strength=p.normalized_strength,
                    time=p.time,
                    accepted=True,
                    reject_reason=None,
                )
            )
        chunk_accepted.append(remapped)

    accepted = reconcile_chunk_peaks(
        chunk_accepted,
        min_gap_windows=int(cfg.get("min_gap_windows", DEFAULT_MIN_GAP_WINDOWS)),
        min_gap_seconds=float(cfg.get("min_gap_seconds", DEFAULT_MIN_GAP_SECONDS)),
        max_shifts=int(cfg.get("max_shifts", DEFAULT_MAX_SHIFTS)),
    )

    analytical_status = "success" if accepted else "no_shift_detected"

    # Keyword hints per span: build temporary ranges via build then refresh
    spans, events, _meta = build_coverage_and_events(
        segments=segs,
        windows=windows,
        accepted_peaks=accepted,
        transcript_identity=identity,
        semantics_version=semantics,
        backend=backend,
        analytical_status=analytical_status,
        keyword_hints_by_span=None,
    )
    # Fill keyword hints
    for span in spans:
        c_segs = [
            s
            for s in segs
            if span["segment_start_idx"] <= s.source_index <= span["segment_end_idx"]
            or s.canonical_position
            >= next(
                (
                    x.canonical_position
                    for x in segs
                    if x.source_index == span["segment_start_idx"]
                ),
                0,
            )
        ]
        # Prefer canonical range from time order membership
        members = [
            s
            for s in segs
            if s.start >= span["time_start"] - 1e-9 and s.end <= span["time_end"] + 1e-9
        ]
        if not members:
            members = [
                s
                for s in segs
                if span["segment_start_idx"]
                <= s.source_index
                <= span["segment_end_idx"]
            ]
        span["keyword_hints"] = keyword_hints_for_segments(members)

    durations = [float(s["time_end"] - s["time_start"]) for s in spans]
    valid_duration = sum(float(s.end - s.start) for s in segs)
    min_dur = float(
        cfg.get("min_duration_for_rate_seconds", DEFAULT_MIN_DURATION_FOR_RATE_SECONDS)
    )
    n_shifts = len(events)
    shifts_per_hour = None
    if valid_duration >= min_dur and valid_duration > 0:
        shifts_per_hour = (n_shifts / valid_duration) * 3600.0

    provenance_key = f"{backend}|{embed.model_name or 'none'}|{semantics}"
    stats = {
        "schema_version": SCHEMA_VERSION,
        "semantics_version": semantics,
        "transcript_identity": identity,
        "deterministic_generation_id": generation_id,
        "analytical_status": analytical_status,
        "backend": backend,
        "model_name": embed.model_name,
        "n_shifts": n_shifts,
        "shifts_per_hour": shifts_per_hour,
        "median_span_duration": (
            float(statistics.median(durations)) if durations else None
        ),
        "longest_span_duration": (max(durations) if durations else None),
        "valid_duration_seconds": valid_duration,
        "language_resolution": lang_tag,
        "language_code": lang_code,
        "limited_language_support": limited
        or backend in ("tfidf", "tfidf_char")
        and not (lang_code in ("en", None) and lang_tag == "assumed_english"),
        "windowing": {
            "window_size": window_size,
            "stride": stride,
            "n_windows": len(windows),
            "n_chunks": len(chunks),
        },
        "thresholds": {
            "k_mad": thr.k_mad,
            "absolute_floor": thr.absolute_floor,
            "min_prominence": thr.min_prominence,
        },
        "coverage_map": {
            "n_canonical_segments": coverage.n_canonical_segments,
            "n_windows": coverage.n_windows,
            "n_chunks": coverage.n_chunks,
            "complete": coverage.complete,
            "covered_canonical_positions": list(coverage.covered_canonical_positions),
        },
        "provenance_compatibility_key": provenance_key,
    }

    spans_envelope = {
        "schema_version": SCHEMA_VERSION,
        "semantics_version": semantics,
        "transcript_identity": identity,
        "deterministic_generation_id": generation_id,
        "analytical_status": analytical_status,
        "backend": backend,
        "coverage_spans": spans,
        "span_count": len(spans),
    }
    events_envelope = {
        "schema_version": SCHEMA_VERSION,
        "semantics_version": semantics,
        "transcript_identity": identity,
        "deterministic_generation_id": generation_id,
        "analytical_status": analytical_status,
        "backend": backend,
        "event_count": len(events),
        "events": [e.to_dict() for e in events],
    }

    return {
        "analytical_status": analytical_status,
        "spans_envelope": spans_envelope,
        "events_envelope": events_envelope,
        "stats_envelope": stats,
        "events": events,
        "operational": {
            "skipped_invalid": canon.skipped_invalid,
            "skipped_empty": canon.skipped_empty,
            "used_fallback": embed.used_fallback,
        },
    }


def _empty_result(
    *,
    identity: str,
    generation_id: str,
    analytical_status: str,
    backend: str,
    reason: str,
    language_code: str | None = None,
    language_resolution: str | None = None,
    limited_language_support: bool = False,
) -> dict[str, Any]:
    if analytical_status == "error_internal":
        analytical_status = "invalid_input"
    semantics = SEMANTICS_BY_BACKEND.get(backend, SEMANTICS_BY_BACKEND["tfidf"])
    # No spans when cannot analyse
    spans: list[dict] = []
    stats = {
        "schema_version": SCHEMA_VERSION,
        "semantics_version": semantics,
        "transcript_identity": identity,
        "deterministic_generation_id": generation_id,
        "analytical_status": analytical_status,
        "backend": backend,
        "model_name": None,
        "n_shifts": 0,
        "shifts_per_hour": None,
        "median_span_duration": None,
        "longest_span_duration": None,
        "valid_duration_seconds": None,
        "language_resolution": language_resolution,
        "language_code": language_code,
        "limited_language_support": limited_language_support,
        "windowing": {},
        "thresholds": {},
        "coverage_map": {"complete": False, "reason": reason},
        "provenance_compatibility_key": f"{backend}|none|{semantics}",
    }
    return {
        "analytical_status": analytical_status,
        "spans_envelope": {
            "schema_version": SCHEMA_VERSION,
            "semantics_version": semantics,
            "transcript_identity": identity,
            "deterministic_generation_id": generation_id,
            "analytical_status": analytical_status,
            "backend": backend,
            "coverage_spans": spans,
            "span_count": 0,
        },
        "events_envelope": {
            "schema_version": SCHEMA_VERSION,
            "semantics_version": semantics,
            "transcript_identity": identity,
            "deterministic_generation_id": generation_id,
            "analytical_status": analytical_status,
            "backend": backend,
            "event_count": 0,
            "events": [],
        },
        "stats_envelope": stats,
        "events": [],
        "operational": {"reason": reason},
    }
