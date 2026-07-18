"""Compatibility and source-identity digests for emotion-family modules."""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.emotion_family.canonical_hash import (
    canonical_json_hash,
    quantize_float_str,
)


def segment_text_hash(text: str | None) -> str:
    """SHA-256 of UTF-8(NFC(strip(text)))."""
    raw = "" if text is None else str(text)
    normalized = unicodedata.normalize("NFC", raw.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_text_source_payload(
    segments: Sequence[Mapping[str, Any]],
    *,
    transcript_revision: str | None = None,
) -> list[dict[str, str]]:
    """Exact stored sequence — never sort segment IDs lexically."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for seg in segments:
        sid = seg.get("id") or seg.get("segment_id")
        if sid is None or str(sid).strip() == "":
            raise ValueError(
                "segment_id missing; unique non-empty segment ids required"
            )
        sid_s = str(sid)
        if sid_s in seen:
            raise ValueError(f"duplicate segment_id: {sid_s}")
        seen.add(sid_s)
        rows.append(
            {
                "segment_id": sid_s,
                "text_hash": segment_text_hash(seg.get("text")),
            }
        )
    return rows


def text_source_digest(
    segments: Sequence[Mapping[str, Any]],
    *,
    transcript_revision: str | None = None,
) -> str:
    payload = {
        "segment_rows": build_text_source_payload(segments),
        "transcript_revision": transcript_revision,
    }
    return canonical_json_hash(payload)


def _resolved_speaker_grouping_key(seg: Mapping[str, Any]) -> str:
    """Same grouping key aggregation uses via extract_speaker_info."""
    from transcriptx.core.utils.speaker_extraction import extract_speaker_info

    info = extract_speaker_info(dict(seg))
    if info is None:
        return ""
    return str(info.grouping_key)


def speaker_identity_digest(segments: Sequence[Mapping[str, Any]]) -> str:
    """Hash resolved aggregation grouping keys in transcript order."""
    rows = []
    for seg in segments:
        sid = str(seg.get("id") or seg.get("segment_id") or "")
        rows.append(
            {
                "segment_id": sid,
                "speaker_grouping_key": _resolved_speaker_grouping_key(seg),
            }
        )
    return canonical_json_hash(rows)


def timeline_identity_digest(segments: Sequence[Mapping[str, Any]]) -> str:
    """
    Hash the ordered timeline inputs aggregation consumes: transcript order,
    segment ids, and start/end timestamps (quantized).
    """
    rows = []
    for order_index, seg in enumerate(segments):
        sid = str(seg.get("id") or seg.get("segment_id") or "")
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        rows.append(
            {
                "order_index": order_index,
                "segment_id": sid,
                "start": quantize_float_str(float(start) if start is not None else 0.0),
                "end": quantize_float_str(float(end) if end is not None else 0.0),
            }
        )
    return canonical_json_hash(rows)


def build_compatibility_payload(
    *,
    schema_version: str,
    semantics_version: str,
    profile_id: str | None = None,
    model_id: str | None = None,
    tokenizer_id: str | None = None,
    model_revision: str | None = None,
    tokenizer_revision: str | None = None,
    label_map_hash: str | None = None,
    activation: str | None = None,
    effective_max_length: int | None = None,
    long_text_policy_version: str | None = None,
    language_policy_version: str | None = None,
    lexical_pipeline_version: str | None = None,
    padding_policy_version: str | None = None,
    numerical_dtype: str = "float32",
    device_class: str | None = None,
    transformers_version: str | None = None,
    torch_version: str | None = None,
    lexicon_digest: str | None = None,
    nrclex_version: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Inference-layer compatibility payload.

    Thresholds and aggregation caps belong in aggregation_settings, not here.
    """
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "semantics_version": semantics_version,
        "profile_id": profile_id,
        "model_id": model_id,
        "tokenizer_id": tokenizer_id,
        "model_revision": model_revision,
        "tokenizer_revision": tokenizer_revision,
        "label_map_hash": label_map_hash,
        "activation": activation,
        "effective_max_length": effective_max_length,
        "long_text_policy_version": long_text_policy_version,
        "language_policy_version": language_policy_version,
        "lexical_pipeline_version": lexical_pipeline_version,
        "padding_policy_version": padding_policy_version,
        "numerical_dtype": numerical_dtype,
        "device_class": device_class,
        "transformers_version": transformers_version,
        "torch_version": torch_version,
        "lexicon_digest": lexicon_digest,
        "nrclex_version": nrclex_version,
    }
    if extra:
        payload.update(dict(extra))
    return payload


def build_aggregation_settings(
    *,
    threshold_profile_version: str | None = None,
    effective_threshold: float | None = None,
    max_labels: int | None = None,
    aggregation_semantics: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregation-layer settings (thresholds, caps) — never partition inference."""
    settings: dict[str, Any] = {
        "threshold_profile_version": threshold_profile_version,
        "effective_threshold": (
            None
            if effective_threshold is None
            else quantize_float_str(float(effective_threshold))
        ),
        "max_labels": max_labels,
        "aggregation_semantics": aggregation_semantics,
    }
    if extra:
        settings.update(dict(extra))
    return settings


def compatibility_fingerprint(payload: Mapping[str, Any]) -> str:
    return canonical_json_hash(dict(payload))


def build_display_fingerprint(
    *,
    family_ontology_version: str | None = None,
    display_cap: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> str:
    """UI/grouping fingerprint — never partitions analytical compatibility."""
    payload: dict[str, Any] = {
        "family_ontology_version": family_ontology_version,
        "display_cap": display_cap,
    }
    if extra:
        payload.update(dict(extra))
    return canonical_json_hash(payload)


def library_versions() -> dict[str, str | None]:
    """Best-effort Transformers / Torch version strings for provenance."""
    transformers_version = None
    torch_version = None
    try:
        import transformers  # type: ignore

        transformers_version = getattr(transformers, "__version__", None)
    except Exception:
        pass
    try:
        import torch  # type: ignore

        torch_version = getattr(torch, "__version__", None)
    except Exception:
        pass
    return {
        "transformers_version": transformers_version,
        "torch_version": torch_version,
    }


def build_runtime_metadata(
    *,
    activation: str | None = None,
    label_map_hash: str | None = None,
    model_id: str | None = None,
    tokenizer_id: str | None = None,
    model_revision: str | None = None,
    tokenizer_revision: str | None = None,
    device_class: str | None = None,
    numerical_dtype: str | None = None,
    language_policy_version: str | None = None,
    long_text_policy_version: str | None = None,
    effective_max_length: int | None = None,
    effective_threshold: float | None = None,
    threshold_profile_version: str | None = None,
    batch_size: int | None = None,
    padding_policy_version: str | None = None,
    lexicon_digest: str | None = None,
    nrclex_version: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    libs = library_versions()
    meta: dict[str, Any] = {
        "activation": activation,
        "label_map_hash": label_map_hash,
        "model_id": model_id,
        "tokenizer_id": tokenizer_id,
        "model_revision": model_revision,
        "tokenizer_revision": tokenizer_revision,
        "device_class": device_class,
        "numerical_dtype": numerical_dtype,
        "language_policy_version": language_policy_version,
        "long_text_policy_version": long_text_policy_version,
        "effective_max_length": effective_max_length,
        "effective_threshold": effective_threshold,
        "threshold_profile_version": threshold_profile_version,
        "batch_size": batch_size,
        "padding_policy_version": padding_policy_version,
        "lexicon_digest": lexicon_digest,
        "nrclex_version": nrclex_version,
        "transformers_version": libs.get("transformers_version"),
        "torch_version": libs.get("torch_version"),
    }
    if extra:
        meta.update(dict(extra))
    return meta
