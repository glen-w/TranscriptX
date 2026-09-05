"""Transcript library tags — organisation metadata, not group membership.

Persists ``tags`` / ``tag_details`` (and optional conversation type) on
``processing_state.json`` entries. Auto-extraction never overwrites an
explicitly saved tag list (including an empty list after the user cleared tags).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from transcriptx.core.utils.processing_state import (
    find_processed_entry_for_path,
    load_processing_state,
    save_processing_state,
)
from transcriptx.io.tag_validation import (
    build_tag_details,
    sanitize_tag_list,
    validate_tag,
)


def _speaker_count(segments: List[Dict[str, Any]]) -> int:
    speakers = {
        seg.get("speaker")
        for seg in segments
        if isinstance(seg, dict) and seg.get("speaker")
    }
    return len(speakers)


def _detect_kind(
    segments: List[Dict[str, Any]],
) -> tuple[Optional[str], Optional[float]]:
    from transcriptx.core.analysis.conversation_type import detect_conversation_type

    try:
        info = detect_conversation_type(segments, _speaker_count(segments))
    except Exception:
        return None, None
    return info.get("type"), info.get("confidence")


class TranscriptTagService:
    """Read/write library tags for a transcript path."""

    def get_record(self, transcript_path: str | Path) -> dict[str, Any]:
        """Return stored tag fields; ``tags`` is None when never initialized."""
        _, entry = find_processed_entry_for_path(str(transcript_path))
        if not entry:
            return {
                "tags": None,
                "tag_details": {},
                "conversation_type": None,
                "type_confidence": None,
            }
        tags = entry.get("tags")
        return {
            "tags": None if tags is None else sanitize_tag_list(tags),
            "tag_details": dict(entry.get("tag_details") or {}),
            "conversation_type": entry.get("conversation_type"),
            "type_confidence": entry.get("type_confidence"),
        }

    def get_tags(self, transcript_path: str | Path) -> list[str]:
        record = self.get_record(transcript_path)
        return list(record["tags"] or [])

    def save_tags(
        self,
        transcript_path: str | Path,
        tags: List[str],
        tag_details: Optional[Dict[str, Any]] = None,
        *,
        conversation_type: Optional[str] = None,
        type_confidence: Optional[float] = None,
    ) -> dict[str, Any]:
        """Persist a reviewed tag list (may be empty)."""
        safe_tags = sanitize_tag_list(tags)
        details = build_tag_details(
            safe_tags,
            auto_tags=[
                name
                for name, meta in (tag_details or {}).items()
                if isinstance(meta, dict) and meta.get("source") == "auto"
            ],
            existing_details=tag_details or {},
        )
        payload: dict[str, Any] = {
            "tags": safe_tags,
            "tag_details": details,
        }
        if conversation_type is not None:
            payload["conversation_type"] = conversation_type
        if type_confidence is not None:
            payload["type_confidence"] = type_confidence
        self._upsert_entry(str(transcript_path), payload)
        return {"tags": safe_tags, "tag_details": details}

    def initialize_from_extraction(
        self,
        transcript_path: str | Path,
        extraction: Dict[str, Any],
        *,
        conversation_type: Optional[str] = None,
        type_confidence: Optional[float] = None,
    ) -> dict[str, Any]:
        """Write auto tags only when this transcript has no saved tag list yet."""
        record = self.get_record(transcript_path)
        if record["tags"] is not None:
            return {
                "tags": record["tags"],
                "tag_details": record["tag_details"],
                "initialized": False,
            }
        auto_tags = sanitize_tag_list(extraction.get("tags") or [])
        details = build_tag_details(
            auto_tags,
            auto_tags=auto_tags,
            existing_details=extraction.get("tag_details") or {},
        )
        saved = self.save_tags(
            transcript_path,
            auto_tags,
            details,
            conversation_type=conversation_type
            if conversation_type is not None
            else record.get("conversation_type"),
            type_confidence=type_confidence
            if type_confidence is not None
            else record.get("type_confidence"),
        )
        saved["initialized"] = True
        return saved

    def suggest_auto_tags(
        self,
        transcript_path: str | Path,
        segments: List[Dict[str, Any]],
    ) -> dict[str, Any]:
        """Add auto-extracted tags without removing existing ones."""
        from transcriptx.core.analysis.tag_extraction import TagExtractor

        extraction = TagExtractor().extract_tags(segments)
        conversation_type, type_confidence = _detect_kind(segments)
        record = self.get_record(transcript_path)
        current = list(record["tags"] or [])
        auto = sanitize_tag_list(extraction.get("tags") or [])
        merged = list(dict.fromkeys([*current, *auto]))
        details = build_tag_details(
            merged,
            auto_tags=auto,
            existing_details={
                **(extraction.get("tag_details") or {}),
                **(record.get("tag_details") or {}),
            },
        )
        return self.save_tags(
            transcript_path,
            merged,
            details,
            conversation_type=conversation_type,
            type_confidence=type_confidence,
        )

    def extract_and_persist(
        self,
        transcript_path: str | Path,
        segments: List[Dict[str, Any]],
        *,
        batch_mode: bool = True,
    ) -> dict[str, Any]:
        """Run tag extraction (and optional CLI review) then persist."""
        from transcriptx.core.analysis.tag_extraction import TagExtractor
        from transcriptx.io.tag_management import manage_tags_interactive

        extraction = TagExtractor().extract_tags(segments)
        conversation_type, type_confidence = _detect_kind(segments)

        record = self.get_record(transcript_path)
        current_tags = record["tags"]
        auto_tags = sanitize_tag_list(extraction.get("tags") or [])
        auto_details = extraction.get("tag_details") or {}

        if batch_mode:
            if current_tags is None:
                return self.initialize_from_extraction(
                    transcript_path,
                    extraction,
                    conversation_type=conversation_type,
                    type_confidence=type_confidence,
                )
            return {
                "tags": current_tags,
                "tag_details": record["tag_details"],
                "initialized": False,
            }

        reviewed = manage_tags_interactive(
            str(transcript_path),
            auto_tags,
            auto_details,
            current_tags=current_tags,
            batch_mode=False,
        )
        return self.save_tags(
            transcript_path,
            reviewed.get("tags") or [],
            reviewed.get("tag_details") or {},
            conversation_type=conversation_type,
            type_confidence=type_confidence,
        )

    def tags_by_transcript_path(
        self, state: Optional[Dict[str, Any]] = None
    ) -> dict[str, tuple[str, ...]]:
        """Map resolved transcript path → tags for inventory/filtering."""
        current = state if state is not None else load_processing_state(validate=False)
        mapping: dict[str, tuple[str, ...]] = {}
        for entry in (current.get("processed_files") or {}).values():
            if not isinstance(entry, dict):
                continue
            tags = entry.get("tags")
            if tags is None:
                continue
            safe = tuple(sanitize_tag_list(tags))
            for key in (
                "current_transcript_path",
                "transcript_path",
                "original_transcript_path",
                "file_path",
            ):
                path = entry.get(key)
                if path:
                    mapping[str(Path(path).expanduser())] = safe
                    try:
                        mapping[str(Path(path).expanduser().resolve())] = safe
                    except OSError:
                        pass
        return mapping

    def corpus_tag_names(self, rows_tags: Iterable[Iterable[str]] | None = None) -> list[str]:
        names: set[str] = set()
        if rows_tags is None:
            for tags in self.tags_by_transcript_path().values():
                names.update(tags)
        else:
            for tags in rows_tags:
                names.update(tags)
        return sorted(names)

    def add_manual_tag(self, transcript_path: str | Path, raw: str) -> tuple[bool, str | None]:
        is_valid, err = validate_tag(raw)
        if not is_valid:
            return False, err
        current = self.get_tags(transcript_path)
        record = self.get_record(transcript_path)
        details = dict(record["tag_details"] or {})
        normalized = sanitize_tag_list([raw])[0]
        if normalized not in current:
            current.append(normalized)
            details[normalized] = {"source": "manual", "confidence": 1.0}
        self.save_tags(transcript_path, current, details)
        return True, None

    def _upsert_entry(self, transcript_path: str, payload: Dict[str, Any]) -> None:
        state = load_processing_state(validate=False)
        key, entry = find_processed_entry_for_path(transcript_path, state)
        processed = state.setdefault("processed_files", {})
        now = datetime.now().isoformat()
        try:
            normalized = str(Path(transcript_path).expanduser().resolve())
        except OSError:
            normalized = str(Path(transcript_path).expanduser())

        if key is None or not isinstance(entry, dict):
            from uuid import NAMESPACE_URL, uuid5

            key = str(uuid5(NAMESPACE_URL, normalized))
            entry = {
                "processed_at": now,
                "status": "pending",
                "transcript_path": normalized,
                "current_transcript_path": normalized,
                "original_transcript_path": normalized,
                "transcript_uuid": key,
            }
        updated = dict(entry)
        updated.update(payload)
        updated["last_updated"] = now
        processed[key] = updated
        save_processing_state(state)
