"""Voice evidence ownership transfer for profile merge (same journal)."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.operations import PlannedDelete, PlannedWrite
from transcriptx.core.speaker_profiles.operations import (
    relative_voice_embedding_path,
    relative_voice_sample_path,
)
from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.models import VoiceEmbeddingV1, VoiceSampleV1


def plan_voice_transfer_on_merge(
    *,
    root: Path,
    source_profile_id: str,
    target_profile_id: str,
) -> tuple[list[PlannedWrite], list[PlannedDelete]]:
    """Retarget voice samples/embeddings from source → target within merge plan.

    Vectors keep the same embedding_id paths; metadata profile_id is rewritten.
    Derived suggestion/summary caches must be invalidated by the caller after merge.
    """
    writes: list[PlannedWrite] = []
    deletes: list[PlannedDelete] = []
    now = utc_now_iso()
    samples_dir = root / "voice" / "samples"
    emb_dir = root / "voice" / "embeddings"
    if samples_dir.is_dir():
        for path in samples_dir.glob("*.voice_sample.json"):
            try:
                sample = VoiceSampleV1.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except Exception:
                continue
            if sample.profile_id != source_profile_id:
                continue
            updated = sample.model_copy(
                update={
                    "profile_id": target_profile_id,
                    "ownership_provenance": {
                        **dict(sample.ownership_provenance or {}),
                        "merged_from_profile_id": source_profile_id,
                        "merged_at": now,
                    },
                }
            )
            writes.append(
                PlannedWrite(
                    relpath=relative_voice_sample_path(sample.sample_id),
                    data=dumps_model(updated),
                )
            )
    if emb_dir.is_dir():
        for path in emb_dir.glob("*.voice_embedding.json"):
            try:
                emb = VoiceEmbeddingV1.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except Exception:
                continue
            if emb.profile_id != source_profile_id:
                continue
            updated = emb.model_copy(update={"profile_id": target_profile_id})
            writes.append(
                PlannedWrite(
                    relpath=relative_voice_embedding_path(emb.embedding_id),
                    data=dumps_model(updated),
                )
            )
    return writes, deletes
