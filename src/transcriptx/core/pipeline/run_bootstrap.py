from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.pipeline.contracts import RunIdentity, TranscriptIdentity
from transcriptx.core.utils._path_core import get_canonical_base_name


class RunBootstrapService:
    def load_segments(self, transcript_path: str) -> List[Dict[str, Any]]:
        from transcriptx.io.transcript_loader import load_canonical_transcript

        canonical = load_canonical_transcript(transcript_path)
        segments = getattr(canonical, "segments", None)
        if segments is not None:
            return segments
        if isinstance(canonical, dict) and isinstance(canonical.get("segments"), list):
            return canonical["segments"]
        raise AttributeError("Loaded transcript payload does not contain segments")

    def compute_identity(
        self, transcript_path: str, segments: List[Dict[str, Any]]
    ) -> TranscriptIdentity:
        from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )
        from transcriptx.core.utils.run_manifest import compute_file_hash

        canonical = CanonicalTranscript.from_segments(segments)
        return TranscriptIdentity(
            transcript_identity_hash=compute_transcript_identity_hash(segments),
            transcript_content_hash_full=canonical.content_hash,
            transcript_file_hash=compute_file_hash(Path(transcript_path)),
        )

    def validate_managed(self, transcript_path: str) -> None:
        from transcriptx.io.import_metadata_sidecar import validate_managed_transcript

        managed_validation = validate_managed_transcript(transcript_path)
        allow_unmanaged = (
            os.getenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "0") == "1"
        )
        if managed_validation.ok:
            return
        if allow_unmanaged:
            return
        raise ValueError(
            "Cannot register non-managed transcript: "
            f"{managed_validation.category.value} ({managed_validation.message})"
        )

    def register(
        self,
        *,
        transcript_path: str,
        transcript_key: str,
        run_id: str,
    ) -> RunIdentity:
        from transcriptx.core.utils.slug_manager import register_transcript

        source_basename = get_canonical_base_name(transcript_path)
        slug = register_transcript(
            transcript_key=transcript_key,
            transcript_path=transcript_path,
            run_id=run_id,
            source_basename=source_basename,
            source_path=transcript_path,
        )
        return RunIdentity(
            transcript_key=transcript_key,
            run_id=run_id,
            source_basename=source_basename,
            slug=slug,
        )
