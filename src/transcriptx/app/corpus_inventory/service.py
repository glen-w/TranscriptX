"""Application-level corpus inventory read model.

No Streamlit. Incremental per-row cache keyed by explicit file fingerprints.
Discovery is best-effort per transcript: one corrupt file never empties the list.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from transcriptx.app.corpus_inventory.mapping import (
    analysis_state_from_run_results,
    corrections_state_from_session,
    datetime_from_mtime,
    listing_from_document,
    max_datetime,
    parse_iso_datetime,
    speaker_state_from_map,
)
from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    FieldIntegrity,
    FileStamp,
    InventoryBuildStats,
    InventoryFingerprint,
    InventoryRow,
    SpeakerIdState,
    SpeakerIdStatus,
    TranscriptRef,
)
from transcriptx.core.utils._path_core import get_canonical_base_name, get_transcript_dir
from transcriptx.core.utils.transcript_picker import list_transcript_picker_options
from transcriptx.io.import_metadata.paths import (
    find_existing_import_sidecar,
    legacy_flat_sidecar_path_for_transcript,
    mirrored_import_sidecar_path_for_transcript,
)
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    speaker_map_sidecar_candidates,
)


def _stamp(path: Path) -> FileStamp:
    try:
        stats = path.stat()
    except OSError:
        return FileStamp(path=str(path), mtime_ns=0, size=-1)
    return FileStamp(
        path=str(path),
        mtime_ns=int(getattr(stats, "st_mtime_ns", int(stats.st_mtime * 1e9))),
        size=int(stats.st_size),
    )


def _dir_child_names_stamp(path: Path) -> FileStamp:
    """Stamp a directory by mtime plus a stable child-name digest (new run dirs)."""
    try:
        stats = path.stat()
        mtime_ns = int(getattr(stats, "st_mtime_ns", int(stats.st_mtime * 1e9)))
        children = tuple(
            sorted(
                child.name for child in path.iterdir() if not child.name.startswith(".")
            )
        )
    except OSError:
        return FileStamp(path=str(path), mtime_ns=0, size=-1)
    digest = int(hashlib.sha1("\n".join(children).encode("utf-8")).hexdigest()[:8], 16)
    return FileStamp(path=str(path), mtime_ns=mtime_ns, size=digest)


def import_sidecar_candidates(transcript_path: Path) -> list[Path]:
    seen: list[Path] = []
    for candidate in (
        find_existing_import_sidecar(transcript_path),
        mirrored_import_sidecar_path_for_transcript(transcript_path),
        legacy_flat_sidecar_path_for_transcript(transcript_path),
        transcript_path.with_name(f"{transcript_path.stem}.import_meta.json"),
    ):
        if candidate is None:
            continue
        if candidate not in seen:
            seen.append(candidate)
    return seen


def _legacy_corrections_session_path(transcript_path: Path) -> Path:
    from transcriptx.core.store.corrections_session_store import (
        session_path_for_transcript,
    )

    return session_path_for_transcript(transcript_path)


def corrections_paths_by_transcript() -> dict[str, list[Path]]:
    """Map resolved transcript path → session.json paths (one index read)."""
    from transcriptx.core.store.corrections_session_store import (
        CorrectionsSessionStore,
        sessions_layout_root,
    )

    mapping: dict[str, list[Path]] = {}
    try:
        idx = CorrectionsSessionStore()._load_index()
    except Exception:
        return mapping
    for entry in (idx.get("entries") or {}).values():
        tp = entry.get("transcript_path")
        rel = entry.get("rel_path")
        if not tp or not rel:
            continue
        try:
            key = str(Path(tp).expanduser().resolve())
        except OSError:
            continue
        session_json = sessions_layout_root() / rel / "session.json"
        mapping.setdefault(key, []).append(session_json)
    return mapping


def corrections_session_candidates(
    transcript_path: Path, *, extra: list[Path] | None = None
) -> list[Path]:
    paths = [_legacy_corrections_session_path(transcript_path)]
    if extra:
        paths.extend(extra)
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def output_root_for(ref: TranscriptRef) -> Path:
    if ref.slug:
        from transcriptx.core.utils.paths import OUTPUTS_DIR

        return Path(OUTPUTS_DIR) / ref.slug
    return Path(get_transcript_dir(str(ref.path)))


def newest_run_dir(output_root: Path) -> Path | None:
    try:
        children = [
            child
            for child in output_root.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
    except OSError:
        return None
    if not children:
        return None
    dated: list[tuple[int, Path]] = []
    for child in children:
        try:
            dated.append((child.stat().st_mtime_ns, child))
        except OSError:
            dated.append((0, child))
    dated.sort(key=lambda item: item[0], reverse=True)
    return dated[0][1]


def fingerprint_contributors(
    ref: TranscriptRef, *, corrections_extra: list[Path] | None = None
) -> list[Path]:
    """Paths whose mtime/size participate in this row's fingerprint."""
    paths: list[Path] = [ref.path]
    paths.extend(import_sidecar_candidates(ref.path))
    paths.extend(speaker_map_sidecar_candidates(ref.path))
    output_root = output_root_for(ref)
    paths.append(output_root)
    run_dir = newest_run_dir(output_root)
    if run_dir is not None:
        paths.append(run_dir)
        paths.append(run_dir / "run_results.json")
        paths.append(run_dir / "manifest.json")
        paths.append(run_dir / ".transcriptx" / "manifest.json")
    paths.extend(
        corrections_session_candidates(ref.path, extra=corrections_extra)
    )
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def fingerprint_for(
    ref: TranscriptRef, *, corrections_extra: list[Path] | None = None
) -> InventoryFingerprint:
    stamps: list[FileStamp] = []
    output_root = output_root_for(ref)
    for path in fingerprint_contributors(ref, corrections_extra=corrections_extra):
        if path == output_root:
            stamps.append(_dir_child_names_stamp(path))
        else:
            stamps.append(_stamp(path))
    return InventoryFingerprint(stamps=tuple(stamps))


def _corpus_index_stamp() -> FileStamp:
    from transcriptx.core.utils.slug_manager import INDEX_FILE

    return _stamp(Path(INDEX_FILE))


def corpus_fingerprint_digest(refs: Iterable[TranscriptRef]) -> tuple[Any, ...]:
    """Cheap hash inputs for a Streamlit wrapper: index + every row fingerprint."""
    corr_map = corrections_paths_by_transcript()
    row_digests = tuple(
        fingerprint_for(
            ref, corrections_extra=corr_map.get(str(ref.path), [])
        ).digest()
        for ref in refs
    )
    index_stamp = _corpus_index_stamp()
    return ((index_stamp.path, index_stamp.mtime_ns, index_stamp.size), row_digests)


def discover_transcript_refs() -> list[TranscriptRef]:
    from transcriptx.core.utils.slug_manager import list_all_transcripts

    by_path: dict[str, TranscriptRef] = {}
    for entry in list_all_transcripts():
        source_path = entry.get("source_path")
        if not source_path:
            continue
        try:
            path = Path(str(source_path)).expanduser()
            if not path.exists():
                continue
            resolved = path.resolve()
        except OSError:
            continue
        by_path[str(resolved)] = TranscriptRef(
            path=resolved,
            base_name=str(entry.get("source_basename") or resolved.stem),
            slug=entry.get("slug"),
            transcript_key=entry.get("transcript_key"),
        )
    for option in list_transcript_picker_options():
        try:
            path = Path(option.path).expanduser().resolve()
        except OSError:
            continue
        key = str(path)
        if key in by_path:
            continue
        by_path[key] = TranscriptRef(
            path=path,
            base_name=option.label,
            slug=get_canonical_base_name(str(path)),
        )
    return sorted(
        by_path.values(), key=lambda ref: (ref.base_name.casefold(), str(ref.path))
    )


def _sidecar_mtime(paths: Iterable[Path]) -> datetime | None:
    latest: datetime | None = None
    for path in paths:
        stamp = _stamp(path)
        if stamp.size < 0:
            continue
        current = datetime_from_mtime(stamp.mtime_ns / 1e9)
        latest = max_datetime(latest, current)
    return latest


def _default_load_corrections(path: Path) -> dict[str, Any] | None:
    from transcriptx.core.store.corrections_session_store import CorrectionsSessionStore

    return CorrectionsSessionStore().read(path)


class CorpusInventory:
    """Incremental corpus inventory. Independently testable; no Streamlit."""

    def __init__(
        self,
        *,
        load_corrections: Callable[[Path], dict[str, Any] | None] | None = None,
        discover: Callable[[], list[TranscriptRef]] | None = None,
    ) -> None:
        self._cache: dict[str, tuple[InventoryFingerprint, InventoryRow]] = {}
        self._load_corrections = load_corrections or _default_load_corrections
        self._discover = discover or discover_transcript_refs
        self.content_reads = 0
        self.rows_rebuilt = 0
        self.cache_hits = 0

    def reset_counters(self) -> None:
        self.content_reads = 0
        self.rows_rebuilt = 0
        self.cache_hits = 0

    def list_rows(
        self, refs: list[TranscriptRef] | None = None
    ) -> list[InventoryRow]:
        refs = refs if refs is not None else self._discover()
        corr_map = corrections_paths_by_transcript()
        rows: list[InventoryRow] = []
        live_keys: set[str] = set()
        for ref in refs:
            key = str(ref.path)
            live_keys.add(key)
            fp = fingerprint_for(
                ref, corrections_extra=corr_map.get(key, [])
            )
            cached = self._cache.get(key)
            if cached is not None and cached[0].digest() == fp.digest():
                self.cache_hits += 1
                rows.append(cached[1])
                continue
            row = self._build_row(ref, fp)
            self._cache[key] = (fp, row)
            self.rows_rebuilt += 1
            rows.append(row)
        for stale in list(self._cache.keys()):
            if stale not in live_keys:
                del self._cache[stale]
        return rows

    def list_rows_with_stats(
        self, refs: list[TranscriptRef] | None = None
    ) -> tuple[list[InventoryRow], InventoryBuildStats]:
        self.reset_counters()
        rows = self.list_rows(refs)
        stats = InventoryBuildStats(
            row_count=len(rows),
            rows_rebuilt=self.rows_rebuilt,
            content_reads=self.content_reads,
            cache_hits=self.cache_hits,
        )
        return rows, stats

    def _read_json(self, path: Path) -> tuple[Any | None, bool]:
        """Return (payload, unreadable). Missing file is (None, False)."""
        if not path.exists():
            return None, False
        self.content_reads += 1
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None, True
        return payload, False

    def _build_row(
        self, ref: TranscriptRef, fingerprint: InventoryFingerprint
    ) -> InventoryRow:
        duration, speaker_count, word_count, listing_integrity = (
            self._read_listing_stats(ref.path)
        )
        imported_at, source_id = self._read_import_sidecar(ref.path)
        speaker = self._read_speaker(ref.path, speaker_count=speaker_count)
        analysis = self._read_analysis(ref)
        corrections = self._read_corrections(ref.path)
        transcript_mtime = None
        stamp = _stamp(ref.path)
        if stamp.size >= 0:
            transcript_mtime = datetime_from_mtime(stamp.mtime_ns / 1e9)
        last_activity = max_datetime(
            imported_at,
            transcript_mtime,
            _sidecar_mtime(speaker_map_sidecar_candidates(ref.path)),
            analysis.last_analysed_at,
            corrections.updated_at,
        )
        return InventoryRow(
            transcript_path=ref.path,
            transcript_key=ref.transcript_key,
            slug=ref.slug,
            title=ref.base_name,
            imported_at=imported_at,
            duration_seconds=duration,
            speaker_count=speaker_count,
            word_count=word_count,
            source_id=source_id,
            listing_integrity=listing_integrity,
            speaker=speaker,
            corrections=corrections,
            analysis=analysis,
            last_activity_at=last_activity,
            fingerprint=fingerprint,
        )

    def _read_listing_stats(
        self, path: Path
    ) -> tuple[float | None, int | None, int | None, FieldIntegrity]:
        payload, unreadable = self._read_json(path)
        if unreadable:
            return None, None, None, FieldIntegrity.MALFORMED
        if payload is None:
            return None, None, None, FieldIntegrity.MISSING
        if isinstance(payload, dict):
            payload.pop("segments", None)
        return listing_from_document(payload)

    def _read_import_sidecar(self, path: Path) -> tuple[datetime | None, str | None]:
        for candidate in import_sidecar_candidates(path):
            payload, unreadable = self._read_json(candidate)
            if unreadable or not isinstance(payload, dict):
                continue
            imported_at = parse_iso_datetime(payload.get("imported_at"))
            source_id = payload.get("adapter_source_id")
            source = str(source_id) if source_id else None
            if imported_at is not None or source:
                return imported_at, source
        return None, None

    def _read_speaker(
        self, path: Path, *, speaker_count: int | None
    ) -> SpeakerIdState:
        try:
            state = SpeakerMapResolver().load_mapping(path)
        except ValueError:
            return speaker_state_from_map(
                None, speaker_count=speaker_count, malformed=True
            )
        except Exception:
            return SpeakerIdState(
                status=SpeakerIdStatus.UNKNOWN,
                integrity=FieldIntegrity.MALFORMED,
            )
        if state.has_sidecar:
            self.content_reads += 1
        return speaker_state_from_map(state, speaker_count=speaker_count)

    def _read_analysis(self, ref: TranscriptRef) -> AnalysisState:
        run_dir = newest_run_dir(output_root_for(ref))
        if run_dir is None:
            return analysis_state_from_run_results(
                None, run_id=None, last_analysed_at=None, run_present=False
            )
        last_analysed = datetime_from_mtime(_stamp(run_dir).mtime_ns / 1e9)
        results_path = run_dir / "run_results.json"
        payload, unreadable = self._read_json(results_path)
        if unreadable:
            return analysis_state_from_run_results(
                None,
                run_id=run_dir.name,
                last_analysed_at=last_analysed,
                run_present=True,
                results_unreadable=True,
            )
        if not isinstance(payload, dict):
            payload = None
        return analysis_state_from_run_results(
            payload,
            run_id=run_dir.name,
            last_analysed_at=last_analysed,
            run_present=True,
            results_unreadable=False,
        )

    def _read_corrections(self, path: Path) -> CorrectionsState:
        try:
            payload = self._load_corrections(path)
        except Exception:
            return corrections_state_from_session(None, unreadable=True)
        if payload is None:
            return corrections_state_from_session(None)
        self.content_reads += 1
        return corrections_state_from_session(payload)
