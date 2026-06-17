"""
Combined Overview-export index page builder.

Builds a single self-contained ``index.html`` for the Overview artifact export
that approximates the GUI: a basic server-rendered transcript displayer plus an
unfiltered charts gallery (all charts in the selection). Rendering is done
server-side (not client-side JS) so the page works when opened directly from
disk over ``file://``, where browsers block ``fetch()`` of local JSON.

The transcript and charts sections fail independently: a malformed transcript
drops only the transcript section, and a charts render failure drops only the
gallery. ``build_export_index_html`` returns ``None`` only when neither section
could be produced, so the caller can skip writing the file entirely.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Optional, Sequence

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
                from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR

                _add(Path(DIARISED_TRANSCRIPTS_DIR) / f"{base_name}.json")
                _add(
                    Path(DIARISED_TRANSCRIPTS_DIR)
                    / f"{base_name}_transcript_diarised.json"
                )
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
                from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR

                _add(Path(DIARISED_TRANSCRIPTS_DIR) / f"{source_basename}.json")
        except Exception:
            pass

    return candidates


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
                return normalized

    best: Optional[dict[str, Any]] = None
    best_count = 0

    def _consider(raw: Any) -> None:
        nonlocal best, best_count
        normalized = normalize_transcript_payload(raw)
        if normalized is None:
            return
        count = len(normalized.get("segments") or [])
        if count > best_count:
            best = normalized
            best_count = count

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
        _consider(raw)

    return best


def _format_timestamp_range(start: Any, end: Any) -> str:
    try:
        return (
            f"{format_time_detailed(float(start))} - {format_time_detailed(float(end))}"
        )
    except (TypeError, ValueError):
        return ""


def render_transcript_section(transcript_data: dict[str, Any]) -> str:
    """Render a basic transcript displayer section from transcript JSON.

    Mirrors the GUI plain view: a metadata summary line followed by one block
    per segment (speaker chip, optional timestamp range, text). Every dynamic
    value is HTML-escaped.
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
    for segment in segments:
        speaker = segment.get("speaker_display") or segment.get("speaker") or "Unknown"
        text = str(segment.get("text", ""))
        timestamp = _format_timestamp_range(
            segment.get("start", 0), segment.get("end", 0)
        )
        time_html = (
            f'<span class="tx-time">{html.escape(timestamp)}</span>'
            if timestamp
            else ""
        )
        blocks.append(
            '<div class="tx-segment">'
            f'<span class="tx-speaker-chip">{html.escape(str(speaker))}</span>'
            f"{time_html}"
            f'<p class="tx-text">{html.escape(text)}</p>'
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
    omitted_count: int = 0,
    included_files: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Build the combined Overview-export ``index.html``.

    Renders a transcript section and/or a charts gallery section. Each section is
    produced independently; a failure in one does not drop the other. Returns
    ``None`` when neither section could be produced (the caller then skips
    writing the file).
    """
    transcript_section: Optional[str] = None
    normalized_transcript = normalize_transcript_payload(transcript_data)
    if normalized_transcript is not None:
        try:
            transcript_section = render_transcript_section(normalized_transcript)
        except Exception:
            transcript_section = None

    chart_toc: list[str] = []
    chart_sections: list[str] = []
    if chart_items:
        try:
            chart_toc, chart_sections = render_chart_sections(chart_items)
        except Exception:
            chart_toc, chart_sections = [], []

    has_transcript = transcript_section is not None
    has_charts = bool(chart_sections)
    if not has_transcript and not has_charts:
        return None

    nav_entries: list[str] = []
    if has_transcript:
        nav_entries.append('<li><a href="#transcript">Transcript</a></li>')
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
