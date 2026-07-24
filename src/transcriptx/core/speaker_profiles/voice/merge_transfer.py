"""Voice evidence ownership transfer for profile merge (chunked journals)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedDelete,
    PlannedWrite,
    relative_voice_embedding_path,
    relative_voice_sample_path,
)
from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.models import (
    VoiceEmbeddingV1,
    VoiceSampleV1,
)

# Cap PlannedWrite entries per continuation journal (sample + embedding rows).
VOICE_TRANSFER_CHUNK_SIZE = 32


def plan_voice_transfer_on_merge(
    *,
    root: Path,
    source_profile_id: str,
    target_profile_id: str,
) -> tuple[list[PlannedWrite], list[PlannedDelete]]:
    """Retarget voice samples/embeddings from source → target.

    Vectors keep the same embedding_id paths; metadata profile_id is rewritten.
    Derived suggestion/summary caches must be invalidated by the caller after merge.
    """
    writes: list[PlannedWrite] = []
    deletes: list[PlannedDelete] = []
    now = utc_now_iso()
    samples_dir = root / "voice" / "samples"
    emb_dir = root / "voice" / "embeddings"
    if samples_dir.is_dir():
        for path in sorted(samples_dir.glob("*.voice_sample.json")):
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
        for path in sorted(emb_dir.glob("*.voice_embedding.json")):
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


def chunk_planned_writes(
    writes: list[PlannedWrite],
    *,
    chunk_size: int = VOICE_TRANSFER_CHUNK_SIZE,
) -> list[list[PlannedWrite]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not writes:
        return []
    return [writes[i : i + chunk_size] for i in range(0, len(writes), chunk_size)]


def voice_chunk_idempotency_key(
    base_key: str, chunk_index: int, writes: list[PlannedWrite]
) -> str:
    """Stable key for a chunk of relpaths (survives replan of remaining work)."""
    payload = json.dumps(
        [w.relpath for w in writes],
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{base_key}:voice_chunk:{chunk_index}:{digest}"


@dataclass(frozen=True)
class VoiceTransferChunkReceipt:
    chunks_total: int
    chunks_complete: int
    write_count: int
    replayed_chunks: tuple[int, ...]


def apply_chunked_voice_transfer(
    *,
    root: Path,
    engine: OperationEngine,
    operation_idempotency_key: str,
    source_profile_id: str,
    target_profile_id: str,
    chunk_size: int = VOICE_TRANSFER_CHUNK_SIZE,
) -> VoiceTransferChunkReceipt:
    """Journal voice ownership rewrite in digestible continuation receipts.

    Safe to re-enter after crash: completed chunk keys replay as no-ops.
    Replans from current source-owned rows so partial transfers continue.
    """
    writes, _deletes = plan_voice_transfer_on_merge(
        root=root,
        source_profile_id=source_profile_id,
        target_profile_id=target_profile_id,
    )
    chunks = chunk_planned_writes(writes, chunk_size=chunk_size)
    replayed: list[int] = []
    for index, chunk in enumerate(chunks):
        key = voice_chunk_idempotency_key(operation_idempotency_key, index, chunk)
        prior = engine.find_complete(key)
        if prior is not None:
            replayed.append(index)
            continue
        engine.run(
            op_type="voice_merge_transfer_chunk",
            operation_idempotency_key=key,
            writes=chunk,
            deletes=[],
            receipt_extra={
                "source_profile_id": source_profile_id,
                "target_profile_id": target_profile_id,
                "chunk_index": index,
                "chunks_total": len(chunks),
                "write_count": len(chunk),
                "scopes": ["speaker_voice"],
            },
        )
    return VoiceTransferChunkReceipt(
        chunks_total=len(chunks),
        chunks_complete=len(chunks),
        write_count=len(writes),
        replayed_chunks=tuple(replayed),
    )
