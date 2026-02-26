"""
DB export speaker maps: one-off export of speaker identity from database into transcript JSON.

Pipeline: resolve candidate TranscriptFiles -> for each: load JSON, only-missing check,
Case 1 (TranscriptSpeaker display_name) / Case 2a (alignment by segment_index) /
Case 2b (full reconstruction) -> write speaker_map and optional segment rewrites with provenance.
"""

from __future__ import annotations

import fnmatch
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.utils.speaker_extraction import count_named_speakers
from transcriptx.io.transcript_loader import (
    extract_speaker_map_from_transcript,
    load_segments,
)
from transcriptx.io.speaker_mapping.core import (
    update_transcript_json_with_speaker_names,
)
from transcriptx.utils.text_utils import is_named_speaker


# Strategy labels for report and provenance
STRATEGY_CASE1 = "case1"
STRATEGY_CASE2A = "case2a_alignment"
STRATEGY_CASE2B = "case2b_reconstruction"
STRATEGY_SKIP_ONLY_MISSING = "skip_only_missing"
STRATEGY_SKIP_NO_DATA = "skip_no_data"
STRATEGY_SKIP_FILE_MISSING = "skip_file_missing"
STRATEGY_SKIP_JSON_ERROR = "skip_json_error"
STRATEGY_ERROR = "error"


@dataclass
class ExportRow:
    """One row of the export report."""

    path: str
    strategy: str
    named_before: int
    named_after: int
    would_write: bool
    alignment_ok: Optional[bool] = None
    error: Optional[str] = None
    db_transcript_file_id: Optional[int] = None


def _named_speaker_count_from_file(transcript_path: str) -> int:
    """Named speaker count for file (segments + speaker_map resolution)."""
    segments = load_segments(transcript_path)
    speaker_map = extract_speaker_map_from_transcript(transcript_path)
    resolved = [dict(seg) for seg in segments]
    for seg in resolved:
        speaker = seg.get("speaker")
        if speaker is not None and speaker in speaker_map:
            seg["speaker"] = speaker_map[speaker]
    return count_named_speakers(resolved)


def _named_speaker_count_after_map(
    segments: List[Dict[str, Any]], speaker_map: Dict[str, str]
) -> int:
    """Named speaker count after applying speaker_map to segments (copy)."""
    resolved = [dict(seg) for seg in segments]
    for seg in resolved:
        speaker = seg.get("speaker")
        if speaker is not None and speaker in speaker_map:
            seg["speaker"] = speaker_map[speaker]
    return count_named_speakers(resolved)


def _get_speaker_display_name(speaker: Any) -> str:
    """Display name from Speaker model (display_name or name)."""
    if speaker is None:
        return ""
    if getattr(speaker, "display_name", None):
        return speaker.display_name or ""
    if getattr(speaker, "name", None):
        return speaker.name or ""
    if getattr(speaker, "full_name", None):
        return speaker.full_name or ""
    return str(speaker)


def _validate_alignment(
    json_segments: List[Dict[str, Any]],
    db_segments: List[Any],
    tolerance: float = 1e-3,
    sample_size: int = 5,
) -> bool:
    """Check segment count and sample of start/end/text between JSON and DB."""
    if len(json_segments) != len(db_segments):
        return False
    n = len(json_segments)
    if n == 0:
        return True
    indices = []
    if n <= sample_size:
        indices = list(range(n))
    else:
        indices = [0, n // 2, n - 1]
        if sample_size > 3:
            step = max(1, (n - 1) // (sample_size - 1))
            indices = list(set(min(i, n - 1) for i in range(0, n, step)))[:sample_size]
    for i in indices:
        js = json_segments[i]
        ds = db_segments[i]
        start_js = float(js.get("start", 0))
        end_js = float(js.get("end", 0))
        if abs(start_js - float(ds.start_time)) > tolerance:
            return False
        if abs(end_js - float(ds.end_time)) > tolerance:
            return False
        text_js = (js.get("text") or "")[:50]
        text_db = (ds.text or "")[:50]
        if text_js != text_db:
            return False
    return True


def _case1_speaker_map(
    session: Any,
    transcript_file_id: int,
    TranscriptSpeaker: Any,
) -> Optional[Tuple[Dict[str, str], Dict[str, int]]]:
    """Build speaker_map from TranscriptSpeaker rows with named display_name."""
    rows = (
        session.query(TranscriptSpeaker)
        .filter(TranscriptSpeaker.transcript_file_id == transcript_file_id)
        .all()
    )
    speaker_map: Dict[str, str] = {}
    label_to_db_id: Dict[str, int] = {}
    has_named = False
    for row in rows:
        label = row.speaker_label
        display = (row.display_name or row.speaker_label or "").strip()
        if display and is_named_speaker(display) and display != label:
            has_named = True
        speaker_map[label] = display or label
        # TranscriptSpeaker does not store global Speaker id; only label->display
        # So we don't set label_to_db_id for Case 1 unless we had a join to Speaker
    if not has_named:
        return None
    return speaker_map, label_to_db_id


def _case2a_speaker_map(
    session: Any,
    transcript_file_id: int,
    json_segments: List[Dict[str, Any]],
    db_segments: List[Any],
    TranscriptSegment: Any,
    Speaker: Any,
) -> Optional[Tuple[Dict[str, str], Dict[str, int], bool]]:
    """Build speaker_map from alignment: json label -> db speaker_id -> name. Returns (map, label_to_db_id, alignment_ok)."""
    if not _validate_alignment(json_segments, db_segments):
        return None
    # label -> list of (segment_index, speaker_id) for majority vote
    label_to_ids: Dict[str, List[Tuple[int, Optional[int]]]] = defaultdict(list)
    for i, db_seg in enumerate(db_segments):
        if i >= len(json_segments):
            break
        json_label = json_segments[i].get("speaker")
        if json_label is None:
            json_label = ""
        speaker_id = getattr(db_seg, "speaker_id", None)
        label_to_ids[json_label].append((i, speaker_id))
    speaker_map: Dict[str, str] = {}
    label_to_db_id: Dict[str, int] = {}
    speaker_ids_to_resolve: set = set()
    for label, pairs in label_to_ids.items():
        ids = [sid for _, sid in pairs if sid is not None]
        if not ids:
            speaker_map[label] = label
            continue
        # Majority vote: most common speaker_id for this label
        most_common = Counter(ids).most_common(1)[0][0]
        label_to_db_id[label] = most_common
        speaker_ids_to_resolve.add(most_common)
        speaker_map[label] = label  # placeholder
    if not speaker_ids_to_resolve:
        return speaker_map, label_to_db_id, True
    # Resolve names from Speaker table
    speakers = (
        session.query(Speaker).filter(Speaker.id.in_(speaker_ids_to_resolve)).all()
    )
    id_to_name: Dict[int, str] = {
        s.id: _get_speaker_display_name(s) or s.name for s in speakers
    }
    for label, db_id in label_to_db_id.items():
        speaker_map[label] = id_to_name.get(db_id, label)
    return speaker_map, label_to_db_id, True


def _case2b_speaker_map(
    session: Any,
    db_segments: List[Any],
    Speaker: Any,
) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Full reconstruction: order speaker_ids by min(segment_index), assign SPEAKER_00, SPEAKER_01, ..."""
    # speaker_id -> min(segment_index)
    order_map: Dict[Optional[int], int] = {}
    for seg in db_segments:
        sid = getattr(seg, "speaker_id", None)
        idx = getattr(seg, "segment_index", 0)
        if sid not in order_map or idx < order_map[sid]:
            order_map[sid] = idx
    # Sort by min index, exclude None
    sorted_ids: List[Optional[int]] = [
        sid
        for sid, _ in sorted(order_map.items(), key=lambda x: (x[1], x[0] or -1))
        if sid is not None
    ]
    speaker_map: Dict[str, str] = {}
    label_to_db_id: Dict[str, int] = {}
    speakers = session.query(Speaker).filter(Speaker.id.in_(sorted_ids)).all()
    id_to_name: Dict[int, str] = {
        s.id: _get_speaker_display_name(s) or s.name for s in speakers
    }
    for i, sid in enumerate(sorted_ids):
        label = f"SPEAKER_{i:02d}"
        speaker_map[label] = id_to_name.get(sid, label)
        label_to_db_id[label] = sid
    return speaker_map, label_to_db_id


def _process_one_file(
    transcript_path: str,
    transcript_file_id: int,
    session: Any,
    *,
    only_missing: bool,
    rewrite_segment_speakers: bool,
    dry_run: bool,
    TranscriptFile: Any,
    TranscriptSpeaker: Any,
    TranscriptSegment: Any,
    Speaker: Any,
    TranscriptSegmentRepository: Any,
) -> ExportRow:
    """Process a single transcript file; return report row. Does not write if dry_run."""
    path_str = str(Path(transcript_path).resolve())
    if not Path(transcript_path).exists():
        return ExportRow(
            path=path_str,
            strategy=STRATEGY_SKIP_FILE_MISSING,
            named_before=0,
            named_after=0,
            would_write=False,
            db_transcript_file_id=transcript_file_id,
        )
    try:
        with open(transcript_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return ExportRow(
            path=path_str,
            strategy=STRATEGY_SKIP_JSON_ERROR,
            named_before=0,
            named_after=0,
            would_write=False,
            error=str(e),
            db_transcript_file_id=transcript_file_id,
        )
    json_segments = data.get("segments") or []
    if not isinstance(json_segments, list):
        json_segments = []
    named_before = _named_speaker_count_from_file(transcript_path)

    if only_missing and named_before > 0:
        return ExportRow(
            path=path_str,
            strategy=STRATEGY_SKIP_ONLY_MISSING,
            named_before=named_before,
            named_after=named_before,
            would_write=False,
            db_transcript_file_id=transcript_file_id,
        )

    speaker_map: Optional[Dict[str, str]] = None
    label_to_db_id: Dict[str, int] = {}
    strategy = STRATEGY_SKIP_NO_DATA
    alignment_ok: Optional[bool] = None

    # Case 1: TranscriptSpeaker with named display_name
    result1 = _case1_speaker_map(session, transcript_file_id, TranscriptSpeaker)
    if result1 is not None:
        speaker_map, label_to_db_id = result1
        strategy = STRATEGY_CASE1

    # Case 2a/2b: segments with speaker_id
    if speaker_map is None:
        db_segments = TranscriptSegmentRepository.get_segments_by_file(
            transcript_file_id, order_by_index=True
        )
        if not db_segments:
            return ExportRow(
                path=path_str,
                strategy=STRATEGY_SKIP_NO_DATA,
                named_before=named_before,
                named_after=named_before,
                would_write=False,
                db_transcript_file_id=transcript_file_id,
            )
        result2a = _case2a_speaker_map(
            session,
            transcript_file_id,
            json_segments,
            db_segments,
            TranscriptSegment,
            Speaker,
        )
        if result2a is not None:
            speaker_map, label_to_db_id, alignment_ok = result2a
            strategy = STRATEGY_CASE2A
        else:
            speaker_map, label_to_db_id = _case2b_speaker_map(
                session, db_segments, Speaker
            )
            strategy = STRATEGY_CASE2B
            alignment_ok = False

    if not speaker_map:
        return ExportRow(
            path=path_str,
            strategy=STRATEGY_SKIP_NO_DATA,
            named_before=named_before,
            named_after=named_before,
            would_write=False,
            db_transcript_file_id=transcript_file_id,
        )

    named_after = _named_speaker_count_after_map(json_segments, speaker_map)
    would_write = bool(speaker_map)

    if not dry_run and would_write:
        provenance = {
            "type": "db_export",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy,
            "db_transcript_file_id": transcript_file_id,
        }
        # Case 2b: segment speakers are keyed by reconstructed SPEAKER_00, etc. We must assign
        # each segment index the correct label before the helper can replace with names.
        if strategy == STRATEGY_CASE2B and rewrite_segment_speakers:
            db_segments = TranscriptSegmentRepository.get_segments_by_file(
                transcript_file_id, order_by_index=True
            )
            id_to_label = {v: k for k, v in label_to_db_id.items()}
            try:
                with open(transcript_path, "r") as f:
                    data_patch = json.load(f)
                segs = data_patch.get("segments") or []
                if isinstance(segs, list) and len(segs) == len(db_segments):
                    for i, db_seg in enumerate(db_segments):
                        if i < len(segs):
                            sid = getattr(db_seg, "speaker_id", None)
                            segs[i]["speaker"] = id_to_label.get(
                                sid, segs[i].get("speaker")
                            )
                    data_patch["segments"] = segs
                    with open(transcript_path, "w") as f:
                        json.dump(data_patch, f, indent=2)
            except (json.JSONDecodeError, OSError):
                pass
        update_transcript_json_with_speaker_names(
            transcript_path,
            speaker_map,
            speaker_id_to_db_id=label_to_db_id if rewrite_segment_speakers else None,
            rewrite_segment_speakers=rewrite_segment_speakers,
            speaker_map_source=provenance,
        )

    return ExportRow(
        path=path_str,
        strategy=strategy,
        named_before=named_before,
        named_after=named_after,
        would_write=would_write,
        alignment_ok=alignment_ok,
        db_transcript_file_id=transcript_file_id,
    )


def get_candidate_transcript_files(
    session: Any,
    TranscriptFile: Any,
    path_like_glob: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Tuple[Any, str]]:
    """Return list of (TranscriptFile, resolved_path) for existing files, optionally filtered by path glob and limit."""
    query = session.query(TranscriptFile).order_by(TranscriptFile.id)
    rows = query.all()
    out: List[Tuple[Any, str]] = []
    for tf in rows:
        path = getattr(tf, "file_path", None) or ""
        if path_like_glob and not fnmatch.fnmatch(path, path_like_glob):
            continue
        resolved = str(Path(path).resolve())
        if Path(resolved).exists():
            out.append((tf, resolved))
        if limit is not None and len(out) >= limit:
            break
    return out


def run_export_speaker_maps(
    dry_run: bool = True,
    write: bool = False,
    only_missing: bool = False,
    limit: Optional[int] = None,
    path_like: Optional[str] = None,
    rewrite_segment_speakers: bool = False,
) -> List[ExportRow]:
    """
    Run the export-speaker-maps pipeline. If write is False (default), no files are modified.

    Returns list of ExportRow for reporting.
    """
    from transcriptx.database.database import get_session
    from transcriptx.database.models import (
        TranscriptFile,
        TranscriptSpeaker,
        TranscriptSegment,
        Speaker,
    )
    from transcriptx.database.repositories import TranscriptSegmentRepository

    session = get_session()
    segment_repo = TranscriptSegmentRepository(session)
    actually_write = write and not dry_run
    candidates = get_candidate_transcript_files(
        session, TranscriptFile, path_like_glob=path_like, limit=limit
    )
    rows: List[ExportRow] = []
    for tf, path in candidates:
        file_id = getattr(tf, "id", 0)
        row = _process_one_file(
            path,
            file_id,
            session,
            only_missing=only_missing,
            rewrite_segment_speakers=rewrite_segment_speakers,
            dry_run=not actually_write,
            TranscriptFile=TranscriptFile,
            TranscriptSpeaker=TranscriptSpeaker,
            TranscriptSegment=TranscriptSegment,
            Speaker=Speaker,
            TranscriptSegmentRepository=segment_repo,
        )
        rows.append(row)
    return rows
