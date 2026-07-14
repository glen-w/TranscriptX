"""Resolve transcript / summary inputs for export index pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

from transcriptx.export.summary_bodies import (
    strip_summary_markdown,
    summary_text_from_payload,
)
from transcriptx.export.types import ExportTextSummary
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    SpeakerMapState,
    normalize_diarized_id,
    normalize_display_name,
)

_TRANSCRIPT_SIDECAR_MARKERS = (
    "_summary.json",
    ".speaker_map.json",
    "_simplified_transcript_summary.json",
)
_ENRICHED_TRANSCRIPT_MARKER = "_with_"
_SUMMARY_JSON_SUFFIX = ".json"
_SUMMARY_MD_SUFFIX = ".md"
_SUMMARY_KIND_ORDER = {
    "executive": 0,
    "llm_summary": 1,
    "narrative_summary": 2,
    "llm_speaker_summary": 3,
    "llm_action_items": 4,
    "run_report": 5,
}


def _is_transcript_sidecar(rel_path: str) -> bool:
    lowered = rel_path.lower()
    return any(marker in lowered for marker in _TRANSCRIPT_SIDECAR_MARKERS)


def normalize_transcript_payload(raw: Any) -> Optional[dict[str, Any]]:
    """Normalize transcript JSON shapes to a dict with a non-empty ``segments`` list."""
    if isinstance(raw, list):
        segments: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            segments.append(
                {
                    "speaker": item.get("speaker")
                    or item.get("speaker_display")
                    or "Unknown",
                    "text": text,
                    "start": item.get("start", 0),
                    "end": item.get("end", 0),
                }
            )
        if not segments:
            return None
        return {"segments": segments, "metadata": {}}

    if not isinstance(raw, dict):
        return None

    segments = raw.get("segments")
    if not isinstance(segments, list) or not segments:
        return None
    return raw


def _try_load_transcript_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return normalize_transcript_payload(raw)


def _run_root_transcript_candidates(run_root: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        candidates.append(path)

    report_path = run_root / "report.json"
    if report_path.is_file():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            meta = payload.get("meta") or payload.get("metadata") or {}
            base_name = meta.get("base_name")
            if base_name:
                from transcriptx.core.utils.paths import PATHS

                transcripts_dir = PATHS.transcripts_dir
                _add(transcripts_dir / f"{base_name}.json")
                _add(transcripts_dir / f"{base_name}_transcript_diarised.json")
        except Exception:
            pass

    manifest_path = run_root / ".transcriptx" / "manifest.json"
    if manifest_path.is_file():
        try:
            from transcriptx.core.pipeline.manifest_loader import load_run_manifest

            manifest = load_run_manifest(manifest_path)
            transcript_path = manifest.get("transcript_path")
            if transcript_path:
                _add(Path(str(transcript_path)))
            source_basename = manifest.get("source_basename")
            if source_basename:
                from transcriptx.core.utils.paths import PATHS

                _add(PATHS.transcripts_dir / f"{source_basename}.json")
        except Exception:
            pass

    return candidates


def _speaker_map_state_from_export_copies(
    staging_dir: Path,
    copied: Sequence[tuple[Any, Path]],
) -> Optional[SpeakerMapState]:
    """Load speaker-map state from a copied ``.speaker_map.json`` export artifact."""
    for _artifact, rel in copied:
        rel_posix = rel.as_posix()
        if not rel_posix.endswith(".speaker_map.json"):
            continue
        path = staging_dir / rel
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        speaker_map_raw = raw.get("speaker_map") or {}
        if not isinstance(speaker_map_raw, dict) or not speaker_map_raw:
            continue
        normalized_map = {
            normalize_diarized_id(speaker_id): normalize_display_name(display_name)
            for speaker_id, display_name in speaker_map_raw.items()
            if normalize_diarized_id(speaker_id)
        }
        if not normalized_map:
            continue
        ignored_raw = raw.get("ignored_speakers") or []
        ignored = (
            [
                normalize_diarized_id(speaker_id)
                for speaker_id in ignored_raw
                if normalize_diarized_id(speaker_id)
            ]
            if isinstance(ignored_raw, list)
            else []
        )
        return SpeakerMapState(
            has_sidecar=True,
            speaker_map=normalized_map,
            ignored_speakers=ignored,
        )
    return None


def _resolve_speaker_map_transcript_path(
    *,
    run_root: Optional[Path],
    loaded_from: Optional[Path],
) -> Optional[Path]:
    """Pick the canonical on-disk transcript path for sidecar speaker-map lookup."""
    if run_root is not None:
        for candidate in _run_root_transcript_candidates(run_root):
            if candidate.is_file():
                return candidate

    if loaded_from is not None and loaded_from.is_file():
        return loaded_from
    return None


def _apply_export_speaker_names(
    transcript_data: dict[str, Any],
    *,
    run_root: Optional[Path] = None,
    loaded_from: Optional[Path] = None,
    staging_dir: Optional[Path] = None,
    copied: Optional[Sequence[tuple[Any, Path]]] = None,
) -> dict[str, Any]:
    """Resolve diarized speaker IDs to mapped display names for export rendering."""
    segments = transcript_data.get("segments")
    if not isinstance(segments, list) or not segments:
        return transcript_data

    resolver = SpeakerMapResolver()
    state: Optional[SpeakerMapState] = None

    transcript_path = _resolve_speaker_map_transcript_path(
        run_root=run_root,
        loaded_from=loaded_from,
    )
    if transcript_path is not None:
        try:
            candidate_state = resolver.load_mapping(transcript_path)
            if candidate_state.speaker_map:
                state = candidate_state
        except Exception:
            state = None

    if state is None and staging_dir is not None and copied:
        state = _speaker_map_state_from_export_copies(staging_dir, copied)

    if state is None or not state.speaker_map:
        return transcript_data

    resolved_segments = resolver.resolve_segments(segments, state)
    for segment in resolved_segments:
        if not isinstance(segment, dict):
            continue
        speaker = segment.get("speaker")
        if speaker and not segment.get("speaker_display"):
            segment["speaker_display"] = str(speaker)

    updated = dict(transcript_data)
    updated["segments"] = resolved_segments
    return updated


def resolve_export_page_title(
    *,
    staging_dir: Path,
    run_root: Optional[Path] = None,
    fallback: str,
) -> str:
    """Resolve the user-facing page title from transcript metadata when available."""
    for base_dir in (staging_dir, run_root):
        if base_dir is None:
            continue
        report_path = base_dir / "report.json"
        if report_path.is_file():
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                meta = payload.get("meta") or payload.get("metadata") or {}
                base_name = meta.get("base_name")
                if base_name:
                    return str(base_name)
            except Exception:
                pass

    if run_root is not None:
        manifest_path = run_root / ".transcriptx" / "manifest.json"
        if manifest_path.is_file():
            try:
                from transcriptx.core.pipeline.manifest_loader import load_run_manifest

                manifest = load_run_manifest(manifest_path)
                source_basename = manifest.get("source_basename")
                if source_basename:
                    return str(source_basename)
                transcript_path = manifest.get("transcript_path")
                if transcript_path:
                    from transcriptx.core.utils._path_core import (
                        get_canonical_base_name,
                    )

                    return get_canonical_base_name(str(transcript_path))
            except Exception:
                pass

    return fallback


def resolve_export_transcript_data(
    *,
    staging_dir: Path,
    run_root: Optional[Path] = None,
    copied: Sequence[tuple[Any, Path]],
) -> Optional[dict[str, Any]]:
    """Pick the best available transcript payload for the export index page."""
    if run_root is not None:
        for candidate in _run_root_transcript_candidates(run_root):
            normalized = _try_load_transcript_json(candidate)
            if normalized is not None:
                return _apply_export_speaker_names(
                    normalized,
                    run_root=run_root,
                    loaded_from=candidate,
                    staging_dir=staging_dir,
                    copied=copied,
                )

    best: Optional[dict[str, Any]] = None
    best_count = 0
    best_source: Optional[Path] = None

    def _consider(path: Path, raw: Any) -> None:
        nonlocal best, best_count, best_source
        normalized = normalize_transcript_payload(raw)
        if normalized is None:
            return
        count = len(normalized.get("segments") or [])
        if count > best_count:
            best = normalized
            best_count = count
            best_source = path

    for _artifact, rel in copied:
        rel_posix = rel.as_posix()
        path = staging_dir / rel
        if not path.is_file() or not rel_posix.endswith(".json"):
            continue

        artifact = _artifact
        kind = getattr(artifact, "kind", None)
        if kind == "transcript":
            if _is_transcript_sidecar(rel_posix):
                continue
        elif kind == "data_json":
            if _ENRICHED_TRANSCRIPT_MARKER not in Path(rel_posix).name:
                continue
        else:
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        _consider(path, raw)

    if best is None:
        return None
    return _apply_export_speaker_names(
        best,
        run_root=run_root,
        loaded_from=best_source,
        staging_dir=staging_dir,
        copied=copied,
    )


def _summary_kind_from_rel_path(
    rel_posix: str,
    *,
    module: Optional[str],
) -> Optional[str]:
    name = Path(rel_posix).name.lower()
    if name == "report.md":
        return "run_report"
    if name.endswith("_llm_summary.json") or name.endswith("_llm_summary.md"):
        return "llm_summary"
    if name.endswith("_narrative_summary.json") or name.endswith(
        "_narrative_summary.md"
    ):
        return "narrative_summary"
    if name.endswith("_llm_speaker_summary.json") or name.endswith(
        "_llm_speaker_summary.md"
    ):
        return "llm_speaker_summary"
    if name.endswith("_llm_action_items.json") or name.endswith("_llm_action_items.md"):
        return "llm_action_items"
    if (
        module == "summary"
        and (name.endswith("_summary.json") or name.endswith("_summary.md"))
        and "_llm_" not in name
        and "_narrative_" not in name
        and "_simplified_transcript_" not in name
    ):
        return "executive"
    return None


def _default_summary_title(kind: str, *, rel_posix: str) -> str:
    if kind == "executive":
        return "Executive Summary"
    if kind == "llm_summary":
        return "LLM Transcript Summary"
    if kind == "narrative_summary":
        return "Narrative Summary"
    if kind == "run_report":
        return "Run Report"
    if kind == "llm_speaker_summary":
        stem = Path(rel_posix).stem
        marker = "_llm_speaker_summary"
        if stem.endswith(marker):
            speaker_token = stem[: -len(marker)].rsplit("_", 1)[-1]
            if speaker_token:
                return f"Speaker Summary — {speaker_token.replace('_', ' ')}"
        return "Speaker Summary"
    if kind == "llm_action_items":
        return "Action Items"
    return "Summary"


def _summary_section_id(kind: str, rel_posix: str) -> str:
    stem = Path(rel_posix).stem.replace("_", "-")
    return f"summary-{kind}-{stem}"


def _load_summary_body(
    *,
    json_path: Optional[Path],
    md_path: Optional[Path],
    kind: str,
) -> tuple[str, dict[str, Any]]:
    payload: Optional[dict[str, Any]] = None
    if json_path is not None and json_path.is_file():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload = raw
        except Exception:
            payload = None

    body = ""
    if payload:
        body = summary_text_from_payload(payload, kind=kind)
    if not body and md_path is not None and md_path.is_file():
        try:
            body = strip_summary_markdown(md_path.read_text(encoding="utf-8"))
        except Exception:
            body = ""

    provenance = payload.get("provenance") if isinstance(payload, dict) else {}
    if kind == "llm_speaker_summary" and isinstance(payload, dict):
        speaker = payload.get("speaker")
        if speaker:
            provenance = {**provenance, "speaker": speaker}
    return body, provenance if isinstance(provenance, dict) else {}


def resolve_export_text_summaries(
    *,
    staging_dir: Path,
    copied: Sequence[tuple[Any, Path]],
) -> list[ExportTextSummary]:
    """Load prose summaries from copied export artifacts for the index page."""
    grouped: dict[str, dict[str, Any]] = {}

    for artifact, rel in copied:
        rel_posix = rel.as_posix()
        module = getattr(artifact, "module", None)
        kind = _summary_kind_from_rel_path(rel_posix, module=module)
        if kind is None:
            continue
        if kind == "llm_speaker_summary" and rel_posix.endswith(
            "_llm_speaker_summary_index.json"
        ):
            continue

        stem = Path(rel_posix).stem
        group_key = f"{kind}|{stem}"
        entry = grouped.setdefault(
            group_key,
            {
                "kind": kind,
                "rel_posix": rel_posix,
                "title": getattr(artifact, "title", None),
                "json_path": None,
                "md_path": None,
            },
        )
        path = staging_dir / rel
        if rel_posix.endswith(_SUMMARY_JSON_SUFFIX):
            entry["json_path"] = path
        elif rel_posix.endswith(_SUMMARY_MD_SUFFIX):
            entry["md_path"] = path

    summaries: list[ExportTextSummary] = []
    ordered = sorted(
        grouped.values(),
        key=lambda item: (
            _SUMMARY_KIND_ORDER.get(str(item["kind"]), 99),
            str(item["rel_posix"]),
        ),
    )
    for entry in ordered:
        kind = str(entry["kind"])
        rel_posix = str(entry["rel_posix"])
        body, provenance = _load_summary_body(
            json_path=entry.get("json_path"),
            md_path=entry.get("md_path"),
            kind=kind,
        )
        if not body:
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            title = _default_summary_title(kind, rel_posix=rel_posix)
        if kind == "llm_speaker_summary":
            speaker = provenance.get("speaker")
            if speaker:
                title = f"Speaker Summary — {speaker}"
        summaries.append(
            ExportTextSummary(
                section_id=_summary_section_id(kind, rel_posix),
                title=title,
                body=body,
                provenance=provenance,
            )
        )
    return summaries


def resolve_export_llm_summary(
    *,
    staging_dir: Path,
    copied: Sequence[tuple[Any, Path]],
) -> Optional[ExportTextSummary]:
    """Backward-compatible helper returning the first LLM transcript summary."""
    for summary in resolve_export_text_summaries(
        staging_dir=staging_dir, copied=copied
    ):
        if summary.get("title") == "LLM Transcript Summary":
            return summary
    return None
