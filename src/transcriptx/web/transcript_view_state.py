"""Transcript viewer data pipeline helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.web.models.search import NavRequest


@dataclass(frozen=True)
class TranscriptViewerContextResult:
    ok: bool
    reason: str | None = None
    session_slug: str | None = None
    run_id: str | None = None
    selected_session: str | None = None
    run_root: Path | None = None


@dataclass(frozen=True)
class TranscriptArtifactsResult:
    txt_file: Path | None
    csv_file: Path | None
    srt_file: Path | None
    json_file: Path | None


@dataclass(frozen=True)
class TranscriptNavigationResult:
    guard_failed: bool
    highlight_query: str | None
    jump_index: int | None
    clear_nav_request: bool = False


def transcript_context_result(
    *,
    ok: bool,
    reason: str | None = None,
    session_slug: str | None = None,
    run_id: str | None = None,
    run_root: Path | None = None,
) -> TranscriptViewerContextResult:
    selected_session = None
    if session_slug and run_id:
        selected_session = f"{session_slug}/{run_id}"
    return TranscriptViewerContextResult(
        ok=ok,
        reason=reason,
        session_slug=session_slug,
        run_id=run_id,
        selected_session=selected_session,
        run_root=run_root,
    )


def resolve_transcript_artifacts(
    *, run_root: Path, selected_session: str, run_id: str
) -> TranscriptArtifactsResult:
    transcripts_dir = run_root / "transcripts"
    manifest_path = run_root / ".transcriptx" / "manifest.json"
    manifest_transcript_path = None
    base_name = None
    if manifest_path.exists():
        try:
            from transcriptx.core.pipeline.manifest_loader import load_run_manifest

            manifest = load_run_manifest(manifest_path)
            manifest_transcript_path = manifest.get("transcript_path")
            if manifest_transcript_path:
                base_name = Path(manifest_transcript_path).stem
        except Exception:
            pass

    if base_name is None:
        base_name = f"{selected_session}/{run_id}".split("/", 1)[-1]

    json_file = None
    json_paths = []
    if manifest_transcript_path:
        json_paths.append(Path(manifest_transcript_path))
    json_paths.extend(
        [
            Path(DIARISED_TRANSCRIPTS_DIR) / f"{base_name}.json",
            Path(DIARISED_TRANSCRIPTS_DIR) / f"{base_name}_transcript_diarised.json",
        ]
    )
    for candidate in json_paths:
        if candidate.exists():
            json_file = candidate
            break

    txt_file = None
    csv_file = None
    srt_file = None
    if transcripts_dir.exists():
        txt_files = list(transcripts_dir.glob(f"{base_name}-transcript.txt"))
        csv_files = list(transcripts_dir.glob(f"{base_name}-transcript.csv"))
        srt_files = list(transcripts_dir.glob(f"{base_name}-transcript.srt"))
        if txt_files:
            txt_file = txt_files[0]
        if csv_files:
            csv_file = csv_files[0]
        if srt_files:
            srt_file = srt_files[0]
    return TranscriptArtifactsResult(
        txt_file=txt_file,
        csv_file=csv_file,
        srt_file=srt_file,
        json_file=json_file,
    )


def consume_nav_request(session_state: dict[str, Any]) -> TranscriptNavigationResult:
    nav_request = session_state.get("nav_request")
    highlight_query = None
    jump_index = None
    clear_nav_request = False
    if isinstance(nav_request, NavRequest):
        highlight_query = nav_request.highlight_query
        segment_ref = nav_request.segment_ref
        if segment_ref.segment_index is not None:
            jump_index = segment_ref.segment_index
        clear_nav_request = True
    return TranscriptNavigationResult(
        guard_failed=False,
        highlight_query=highlight_query,
        jump_index=jump_index,
        clear_nav_request=clear_nav_request,
    )


def filtered_display_segments(
    *,
    segments: list[dict[str, Any]],
    search_text: str,
    jump_index: int | None,
) -> tuple[list[tuple[int, dict[str, Any]]], str | None]:
    display_segments: list[tuple[int, dict[str, Any]]] = list(enumerate(segments))
    if search_text:
        filtered = [
            (idx, segment)
            for idx, segment in display_segments
            if search_text.lower() in str(segment.get("text", "")).lower()
        ]
        return filtered, f"Showing {len(filtered)} of {len(segments)} segments"
    if jump_index is not None:
        start_idx = max(0, jump_index - 2)
        end_idx = min(len(segments) - 1, jump_index + 2)
        context = [(idx, segments[idx]) for idx in range(start_idx, end_idx + 1)]
        return context, "Showing context around selected segment."
    return display_segments, None
