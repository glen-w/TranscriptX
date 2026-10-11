"""Cache assistive name suggestions per managed transcript and LLM model tag."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from transcriptx.core.speaker_profiles.identify.suggestions.models import (
    NameSuggestionsResult,
)
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.io.atomic_json import write_json_atomic

LLM_OFF_TAG = "llm-off"
LLM_UNRESOLVED_TAG = "llm-unresolved"
_CACHE_SUFFIX = ".name_suggestions.v1.json"


def model_tag_for_cache(llm_model: str | None) -> str:
    """Filesystem-safe tag for a model name (stable, short)."""
    if not llm_model:
        return LLM_OFF_TAG
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", llm_model.strip())[:48]
    digest = hashlib.sha256(llm_model.encode("utf-8")).hexdigest()[:10]
    if slug:
        return f"{slug}-{digest}"
    return digest


def _cache_dir(root: Path | None = None) -> Path:
    base = Path(root) if root is not None else speaker_profiles_dir()
    return base / ".cache" / "identify"


def legacy_suggestions_cache_path(
    managed_transcript_id: str, *, root: Path | None = None
) -> Path:
    return _cache_dir(root) / f"{managed_transcript_id}{_CACHE_SUFFIX}"


def suggestions_cache_path(
    managed_transcript_id: str,
    *,
    model_tag: str,
    root: Path | None = None,
) -> Path:
    base = _cache_dir(root)
    tag = model_tag or LLM_OFF_TAG
    return base / f"{managed_transcript_id}.{tag}{_CACHE_SUFFIX}"


def resolve_assigned_speaker_name_model_tag(*, use_llm: bool) -> str:
    """Model tag for the currently configured speaker-name suggestion consumer."""
    if not use_llm:
        return LLM_OFF_TAG
    try:
        from transcriptx.core.analysis.llm_support.model_selection import (
            resolve_module_llm_model,
        )
        from transcriptx.core.utils.config import get_config

        resolved = resolve_module_llm_model(
            get_config().llm, "speaker_name_suggestions"
        )
        return model_tag_for_cache(resolved.model)
    except Exception:
        return LLM_UNRESOLVED_TAG


def _read_result_file(path: Path) -> NameSuggestionsResult | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return NameSuggestionsResult.from_dict(raw)


def _result_model_tag(result: NameSuggestionsResult) -> str:
    if result.cache_model_tag:
        return result.cache_model_tag
    return model_tag_for_cache(result.llm_model)


def list_suggestion_cache_paths(
    managed_transcript_id: str, *, root: Path | None = None
) -> list[Path]:
    """All on-disk name-suggestion artefacts for a managed transcript."""
    cache_dir = _cache_dir(root)
    paths: list[Path] = []
    legacy = legacy_suggestions_cache_path(managed_transcript_id, root=root)
    if legacy.is_file():
        paths.append(legacy)
    pattern = f"{managed_transcript_id}.*{_CACHE_SUFFIX}"
    for path in sorted(cache_dir.glob(pattern)):
        if path == legacy:
            continue
        paths.append(path)
    return paths


def list_cached_suggestion_variants(
    managed_transcript_id: str,
    *,
    transcript_fingerprint: str,
    root: Path | None = None,
) -> list[NameSuggestionsResult]:
    """Fresh variants for a transcript fingerprint, newest file mtime first."""
    rows: list[tuple[float, NameSuggestionsResult]] = []
    for path in list_suggestion_cache_paths(managed_transcript_id, root=root):
        parsed = _read_result_file(path)
        if parsed is None:
            continue
        if parsed.transcript_fingerprint != transcript_fingerprint:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        rows.append((mtime, parsed))
    rows.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in rows]


def load_suggestions_artefact(
    managed_transcript_id: str,
    *,
    model_tag: str | None = None,
    root: Path | None = None,
) -> NameSuggestionsResult | None:
    if model_tag:
        return _read_result_file(
            suggestions_cache_path(
                managed_transcript_id, model_tag=model_tag, root=root
            )
        )
    legacy = _read_result_file(
        legacy_suggestions_cache_path(managed_transcript_id, root=root)
    )
    if legacy is not None:
        return legacy
    assigned = resolve_assigned_speaker_name_model_tag(use_llm=True)
    tagged = _read_result_file(
        suggestions_cache_path(
            managed_transcript_id, model_tag=assigned, root=root
        )
    )
    if tagged is not None:
        return tagged
    paths = list_suggestion_cache_paths(managed_transcript_id, root=root)
    if not paths:
        return None
    best: NameSuggestionsResult | None = None
    best_mtime = -1.0
    for path in paths:
        parsed = _read_result_file(path)
        if parsed is None:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        if mtime >= best_mtime:
            best_mtime = mtime
            best = parsed
    return best


def load_cached_suggestions(
    managed_transcript_id: str,
    *,
    transcript_fingerprint: str,
    model_tag: str | None = None,
    root: Path | None = None,
) -> NameSuggestionsResult | None:
    if model_tag:
        parsed = _read_result_file(
            suggestions_cache_path(
                managed_transcript_id, model_tag=model_tag, root=root
            )
        )
        if parsed is None or parsed.transcript_fingerprint != transcript_fingerprint:
            return None
        return parsed

    assigned = resolve_assigned_speaker_name_model_tag(use_llm=True)
    tagged = load_cached_suggestions(
        managed_transcript_id,
        transcript_fingerprint=transcript_fingerprint,
        model_tag=assigned,
        root=root,
    )
    if tagged is not None:
        return tagged

    legacy_path = legacy_suggestions_cache_path(managed_transcript_id, root=root)
    if legacy_path.is_file():
        parsed = _read_result_file(legacy_path)
        if (
            parsed is not None
            and parsed.transcript_fingerprint == transcript_fingerprint
        ):
            return parsed

    for result in list_cached_suggestion_variants(
        managed_transcript_id,
        transcript_fingerprint=transcript_fingerprint,
        root=root,
    ):
        return result
    return None


def write_cached_suggestions(
    result: NameSuggestionsResult,
    *,
    model_tag: str | None = None,
    root: Path | None = None,
) -> Path | None:
    if not result.managed_transcript_id:
        return None
    tag = model_tag or _result_model_tag(result)
    path = suggestions_cache_path(
        result.managed_transcript_id, model_tag=tag, root=root
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = result.to_dict()
    payload["cache_model_tag"] = tag
    write_json_atomic(path, payload, indent=2)
    return path


def build_name_suggestions_workspace_payload(
    managed_transcript_id: str,
    *,
    transcript_fingerprint: str,
    selected_model_tag: str | None = None,
    root: Path | None = None,
) -> dict[str, Any] | None:
    """Workspace JSON for Speaker ID, including alternate model runs."""
    variants = list_cached_suggestion_variants(
        managed_transcript_id,
        transcript_fingerprint=transcript_fingerprint,
        root=root,
    )
    if not variants:
        return None

    assigned = resolve_assigned_speaker_name_model_tag(use_llm=True)
    tag_to_variant = {_result_model_tag(v): v for v in variants}
    active_tag = selected_model_tag or assigned
    if active_tag not in tag_to_variant:
        active_tag = _result_model_tag(variants[0])

    active = tag_to_variant[active_tag]
    payload = active.workspace_payload()
    payload["selected_model_tag"] = active_tag
    payload["available_models"] = [
        {
            "model_tag": _result_model_tag(v),
            "llm_model": v.llm_model or LLM_OFF_TAG,
            "status_message": v.status_message,
        }
        for v in variants
    ]
    return payload
