"""
Combined Overview-export index page builder.

Builds a single self-contained ``index.html`` for the Overview artifact export
that approximates the GUI: a basic server-rendered transcript displayer, optional
LLM transcript summary, and an unfiltered charts gallery (all charts in the
selection). Rendering is done server-side (not client-side JS) so the page works
when opened directly from disk over ``file://``, where browsers block ``fetch()``
of local JSON.

The transcript, LLM summary, and charts sections fail independently: a malformed
transcript drops only the transcript section, and a charts render failure drops
only the gallery. ``build_export_index_html`` returns ``None`` only when no section
could be produced, so the caller can skip writing the file entirely.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Optional, Sequence, TypedDict

from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    SpeakerMapState,
    normalize_diarized_id,
    normalize_display_name,
)
from transcriptx.utils.charts_export import (
    _EXPORT_INDEX_CSS,
    _ExportableItem,
    render_chart_sections,
)
from transcriptx.utils.text_utils import format_time_detailed

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


class ExportTextSummary(TypedDict, total=False):
    section_id: str
    title: str
    body: str
    provenance: dict[str, Any]


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


def _strip_summary_markdown(md: str) -> str:
    """Drop generated markdown titles and provenance footers when JSON is absent."""
    lines = md.splitlines()
    body_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("# "):
            continue
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def _summary_text_from_payload(payload: dict[str, Any], *, kind: str) -> str:
    if kind == "narrative_summary":
        return str(payload.get("narrative") or payload.get("summary") or "").strip()
    if kind == "llm_speaker_summary":
        return str(payload.get("summary") or "").strip()
    if kind == "llm_action_items":
        items = payload.get("items") or []
        if not isinstance(items, list) or not items:
            return "No action items found."
        lines: list[str] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            lines.append(f"{index}. {text}")
            status = item.get("status")
            if status:
                lines.append(f"   Status: {status}")
            owner = item.get("owner")
            if owner:
                lines.append(f"   Owner: {owner}")
            deadline = item.get("deadline")
            if deadline:
                lines.append(f"   Deadline: {deadline}")
            quote = item.get("quote")
            if quote:
                lines.append(f'   Quote: "{quote}"')
        return "\n".join(lines).strip()
    return str(payload.get("summary") or payload.get("narrative") or "").strip()


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
        body = _summary_text_from_payload(payload, kind=kind)
    if not body and md_path is not None and md_path.is_file():
        try:
            if kind == "run_report":
                body = md_path.read_text(encoding="utf-8").strip()
            else:
                body = _strip_summary_markdown(md_path.read_text(encoding="utf-8"))
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


def render_summaries_section(summaries: Sequence[ExportTextSummary]) -> str:
    """Render a grouped summaries block for the export index page."""
    blocks = "".join(render_text_summary_section(summary) for summary in summaries)
    return f'<section id="summaries"><h2>Summaries</h2>{blocks}</section>'


def _strip_llm_summary_markdown(md: str) -> str:
    return _strip_summary_markdown(md)


def render_text_summary_section(summary: ExportTextSummary) -> str:
    """Render a prose summary block for the export index page."""
    section_id = summary.get("section_id") or "summary"
    title = summary.get("title") or "Summary"
    body = summary.get("body") or ""
    provenance = summary.get("provenance") or {}

    meta_bits: list[str] = []
    model = provenance.get("model")
    provider = provenance.get("provider")
    if model:
        meta_bits.append(f"Model: {model}")
    if provider:
        meta_bits.append(f"Provider: {provider}")
    if provenance.get("truncated"):
        meta_bits.append("Input truncated")

    meta_html = ""
    if meta_bits:
        meta_line = " · ".join(html.escape(str(bit)) for bit in meta_bits)
        meta_html = f'<p class="meta">{meta_line}</p>'

    return (
        f'<section id="{html.escape(section_id)}">'
        f"<h2>{html.escape(title)}</h2>"
        '<div class="tx-summary">'
        f'<p class="tx-text">{html.escape(body)}</p>'
        "</div>"
        f"{meta_html}"
        "</section>"
    )


def _segment_speaker_label(segment: dict[str, Any]) -> str:
    return str(segment.get("speaker_display") or segment.get("speaker") or "Unknown")


def _group_contiguous_segments_by_speaker(
    segments: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group contiguous transcript segments by resolved speaker label."""
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    current_speaker: str | None = None
    current_group: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        speaker = _segment_speaker_label(segment)
        if speaker != current_speaker:
            if current_group:
                groups.append((str(current_speaker), current_group))
            current_speaker = speaker
            current_group = [segment]
        else:
            current_group.append(segment)
    if current_group:
        groups.append((str(current_speaker), current_group))
    return groups


def _format_timestamp_range(start: Any, end: Any) -> str:
    try:
        return (
            f"{format_time_detailed(float(start))} - {format_time_detailed(float(end))}"
        )
    except (TypeError, ValueError):
        return ""


def render_transcript_section(transcript_data: dict[str, Any]) -> str:
    """Render a basic transcript displayer section from transcript JSON.

    Mirrors the GUI segmented view: a metadata summary line followed by one block
    per contiguous speaker run (speaker chip, optional timestamp range, text).
    Every dynamic value is HTML-escaped.
    """
    segments = transcript_data.get("segments") or []
    metadata = transcript_data.get("metadata") or {}

    distinct_speakers: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        speaker = segment.get("speaker_display") or segment.get("speaker")
        if speaker and speaker not in seen:
            seen.add(speaker)
            distinct_speakers.append(speaker)

    duration = metadata.get("duration")
    if duration is None and segments:
        try:
            duration = max(float(s.get("end", 0) or 0) for s in segments)
        except (TypeError, ValueError):
            duration = None

    meta_bits: list[str] = [
        f"{len(segments)} segments",
        f"{len(distinct_speakers)} speakers",
    ]
    if duration:
        try:
            meta_bits.append(f"Duration {format_time_detailed(float(duration))}")
        except (TypeError, ValueError):
            pass
    language = metadata.get("language")
    if language:
        meta_bits.append(f"Language: {language}")
    meta_line = " · ".join(html.escape(str(bit)) for bit in meta_bits)

    blocks: list[str] = []
    for speaker_name, group_segments in _group_contiguous_segments_by_speaker(segments):
        group_start = group_segments[0].get("start", 0)
        group_end = group_segments[-1].get("end", 0)
        timestamp = _format_timestamp_range(group_start, group_end)
        time_html = (
            f'<span class="tx-time">{html.escape(timestamp)}</span>'
            if timestamp
            else ""
        )
        text_blocks = "".join(
            f'<p class="tx-text">{html.escape(str(segment.get("text", "")))}</p>'
            for segment in group_segments
            if str(segment.get("text", "")).strip()
        )
        blocks.append(
            '<div class="tx-segment">'
            f'<span class="tx-speaker-chip">{html.escape(speaker_name)}</span>'
            f"{time_html}"
            f"{text_blocks}"
            "</div>"
        )

    return (
        '<section id="transcript"><h2>Transcript</h2>'
        f'<p class="meta">{meta_line}</p>' + "".join(blocks) + "</section>"
    )


def _render_included_files(included_files: Sequence[str]) -> str:
    items = "".join(f"<li>{html.escape(path)}</li>" for path in sorted(included_files))
    return (
        '<section id="included-files" class="included-files">'
        "<h2>Included files</h2><ul>" + items + "</ul></section>"
    )


def build_export_index_html(
    *,
    page_title: str,
    transcript_data: Optional[dict[str, Any]] = None,
    chart_items: Optional[list[_ExportableItem]] = None,
    text_summaries: Optional[Sequence[ExportTextSummary]] = None,
    llm_summary: Optional[ExportTextSummary] = None,
    omitted_count: int = 0,
    included_files: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Build the combined Overview-export ``index.html``.

    Renders a transcript section, optional summaries, and/or a charts gallery
    section. Each section is produced independently; a failure in one does not drop
    the others. Returns ``None`` when no section could be produced (the caller
    then skips writing the file).
    """
    transcript_section: Optional[str] = None
    normalized_transcript = normalize_transcript_payload(transcript_data)
    if normalized_transcript is not None:
        try:
            transcript_section = render_transcript_section(normalized_transcript)
        except Exception:
            transcript_section = None

    summary_items: list[ExportTextSummary] = []
    if text_summaries:
        summary_items.extend(
            summary for summary in text_summaries if summary.get("body")
        )
    elif llm_summary and llm_summary.get("body"):
        summary_items.append(llm_summary)

    summaries_section: Optional[str] = None
    if summary_items:
        try:
            summaries_section = render_summaries_section(summary_items)
        except Exception:
            summaries_section = None

    chart_toc: list[str] = []
    chart_sections: list[str] = []
    if chart_items:
        try:
            chart_toc, chart_sections = render_chart_sections(chart_items)
        except Exception:
            chart_toc, chart_sections = [], []

    has_transcript = transcript_section is not None
    has_summaries = summaries_section is not None
    has_charts = bool(chart_sections)
    if not has_transcript and not has_summaries and not has_charts:
        return None

    nav_entries: list[str] = []
    if has_transcript:
        nav_entries.append('<li><a href="#transcript">Transcript</a></li>')
    if has_summaries and summary_items:
        nav_entries.append('<li><a href="#summaries">Summaries</a></li>')
        for summary in summary_items:
            section_id = summary.get("section_id") or "summary"
            title = summary.get("title") or "Summary"
            nav_entries.append(
                f'<li><a href="#{html.escape(section_id)}">{html.escape(title)}</a></li>'
            )
    if has_charts:
        nav_entries.append("<li><strong>Charts</strong></li>")
        nav_entries.extend(chart_toc)

    omitted_banner = ""
    if omitted_count > 0:
        plural = "s" if omitted_count != 1 else ""
        omitted_banner = (
            '<div class="notice">'
            f"{omitted_count} chart{plural} were unavailable and omitted from this export."
            "</div>"
        )

    body_sections: list[str] = []
    if has_transcript and transcript_section is not None:
        body_sections.append(transcript_section)
    if has_summaries and summaries_section is not None:
        body_sections.append(summaries_section)
    body_sections.extend(chart_sections)
    if included_files:
        body_sections.append(_render_included_files(included_files))

    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        f"<title>{html.escape(page_title)}</title>"
        "<style>" + _EXPORT_INDEX_CSS + "</style></head><body>"
        "<main><nav><strong>Contents</strong><ul>"
        + "".join(nav_entries)
        + "</ul></nav><div class='content'>"
        f"<h1>{html.escape(page_title)}</h1>"
        + omitted_banner
        + "".join(body_sections)
        + "</div></main></body></html>"
    )
