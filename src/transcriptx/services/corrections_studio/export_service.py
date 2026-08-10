"""CorrectionsStudioExportService: same compile as preview, artifacts + provenance + export_completed."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import json

from transcriptx.io import save_json
from transcriptx.io.transcript_schema import compute_metadata_from_segments
from transcriptx.services.corrections_studio.preview_service import (
    CorrectionsStudioPreviewService,
)
from transcriptx.services.corrections_studio.provenance import write_export_provenance
from transcriptx.services.corrections_studio.schema import (
    ExportCompletedPayload,
    ExportProvenance,
    StudioEventEnvelope,
    StudioExportResult,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)


class CorrectionsStudioExportService:
    def __init__(
        self,
        session_service: CorrectionsStudioSessionService,
        preview_service: CorrectionsStudioPreviewService,
    ) -> None:
        self._session = session_service
        self._preview = preview_service

    def apply_and_export(
        self,
        session_id: str,
        export_path: Optional[str] = None,
        *,
        candidate_ids: Optional[List[str]] = None,
        occurrence_keys: Optional[List[str]] = None,
    ) -> StudioExportResult:
        doc = self._session.load_document(session_id)
        preview = self._preview.compute_preview(
            session_id,
            candidate_ids=candidate_ids,
            occurrence_keys=occurrence_keys,
        )
        updated_segments = preview.updated_segments

        transcript_path = doc.transcript_path
        source_path = Path(transcript_path)
        session_short = session_id[:8]
        if export_path is None:
            export_path = str(
                source_path.parent
                / f"{source_path.stem}_corrected_{session_short}.json"
            )

        export_p = Path(export_path)
        tmp_export = export_p.with_suffix(export_p.suffix + ".tmp")
        prov_path = export_p.with_name(export_p.stem + "_export_provenance.json")
        tmp_prov = prov_path.with_suffix(prov_path.suffix + ".tmp")
        gen = doc.current_generation_id or 0
        manifest = (
            doc.current_generation.generation_manifest
            if doc.current_generation
            else None
        )
        mh = (
            doc.current_generation.generation_manifest_hash
            if doc.current_generation
            else ""
        )
        # Mirror compile: only the latest review per candidate counts.
        reviews_cur = [r for r in doc.review_records if r.generation_id == gen]
        latest_by_candidate = {}
        for r in sorted(reviews_cur, key=lambda x: x.event_sequence):
            latest_by_candidate[r.candidate_id] = r
        applied_ids = [
            cid
            for cid, r in latest_by_candidate.items()
            if r.review_action.value in ("accept", "learn")
        ]
        if candidate_ids is not None:
            wanted = set(candidate_ids)
            applied_ids = [cid for cid in applied_ids if cid in wanted]
        llm_influenced = []
        for cid in applied_ids:
            cand = next((c for c in doc.candidates if c.candidate_id == cid), None)
            if cand is None:
                continue
            sources = [
                s.value if hasattr(s, "value") else str(s) for s in (cand.sources or [])
            ]
            if "llm_discovery" in sources or cand.kind == "ner_variant":
                llm_influenced.append(cid)
        llm_fp = ""
        if manifest is not None:
            llm_fp = getattr(manifest, "llm_fingerprint", "") or ""
        prov = ExportProvenance(
            session_id=session_id,
            generation_id=gen,
            transcript_identity_hash=doc.recorded_transcript_identity_hash,
            generation_manifest_hash=mh,
            generation_manifest=manifest,
            studio_schema_version=doc.studio_schema_version,
            detector_version=manifest.detector_version if manifest else "",
            applied_candidate_ids=applied_ids,
            review_summary_counts={},
            review_actions_summary={},
            exported_artifact_paths=[str(export_p.resolve())],
            export_timestamp_utc=datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            llm_influenced_candidate_ids=llm_influenced,
            llm_fingerprint_at_export=llm_fp,
        )
        try:
            # Write a loadable schema v1 artifact (not bare {"segments": ...}).
            try:
                source_doc = json.loads(source_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                source_doc = {}
            if not isinstance(source_doc, dict):
                source_doc = {}
            meta = compute_metadata_from_segments(updated_segments)
            export_doc = {
                "schema_version": source_doc.get("schema_version")
                if source_doc.get("schema_version") is not None
                else 1,
                "source": dict(source_doc.get("source") or {})
                or {
                    "type": "manual",
                    "original_path": str(source_path),
                    "imported_at": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                "metadata": {
                    "duration_seconds": meta.duration_seconds,
                    "segment_count": meta.segment_count,
                    "speaker_count": meta.speaker_count,
                    "word_count": meta.word_count,
                },
                "segments": updated_segments,
                "corrections_lineage": {
                    "parent_transcript_path": str(source_path.resolve()),
                    "parent_session_id": session_id,
                    "parent_transcript_identity_hash": doc.recorded_transcript_identity_hash,
                    "generation_id": gen,
                    "applied_candidate_ids": list(applied_ids),
                    "scoped": candidate_ids is not None,
                },
            }
            # Ensure required source keys exist
            src = export_doc["source"]
            src.setdefault("type", "manual")
            src.setdefault("original_path", str(source_path))
            src.setdefault(
                "imported_at",
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            save_json(export_doc, str(tmp_export))
            os.replace(str(tmp_export), str(export_p))
            write_export_provenance(tmp_prov, prov)
            os.replace(str(tmp_prov), str(prov_path))
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            # Scoped exports do not complete the whole session.
            status_update = {} if candidate_ids is not None else {"status": "completed"}
            doc = doc.model_copy(update={"updated_at": now, **status_update})
            # Sequence allocated under lock by persist(); placeholder 0 is overwritten.
            payload = ExportCompletedPayload(
                generation_id=gen,
                export_paths=[str(export_p.resolve())],
                provenance_path=str(prov_path.resolve()),
                scoped_candidate_ids=list(candidate_ids or []),
            )
            event = StudioEventEnvelope(
                session_id=session_id,
                event_type="export_completed",
                event_sequence=0,
                generation_id=gen,
                payload=payload.model_dump(mode="json"),
            )
            self._session.persist(transcript_path, doc, event)
        except Exception:
            for p in (tmp_export, tmp_prov, export_p, prov_path):
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            raise

        return StudioExportResult(
            export_path=str(export_p),
            provenance_path=str(prov_path),
            applied_count=preview.stats.applied_count,
        )

    def apply_and_export_scoped(
        self,
        session_id: str,
        candidate_ids: List[str],
        occurrence_keys: Optional[List[str]] = None,
        export_path: Optional[str] = None,
    ) -> StudioExportResult:
        """Apply/export only the listed candidates (viewer quick-apply)."""
        if not candidate_ids:
            raise ValueError("candidate_ids must be non-empty for scoped export")
        return self.apply_and_export(
            session_id,
            export_path=export_path,
            candidate_ids=list(candidate_ids),
            occurrence_keys=occurrence_keys,
        )
