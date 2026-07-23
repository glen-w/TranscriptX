"""Bounded crash-safe voice wipe protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from transcriptx.core.speaker_profiles.layout import speaker_profiles_project_lock
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedDelete,
    relative_event_path,
)
from transcriptx.core.speaker_profiles.path_safety import assert_safe_relpath
from transcriptx.core.speaker_profiles.store_io import dumps_model, ensure_layout, utc_now_iso
from transcriptx.core.speaker_profiles.voice.caches import VoiceSuggestionCache
from transcriptx.core.speaker_profiles.voice.excerpt_cache import VoiceExcerptStore
from transcriptx.core.utils.paths import PATHS

WIPE_RECEIPT_REL = "voice/wipe_receipt.json"
MAX_PATHS_PER_CHUNK = 40


@dataclass(frozen=True)
class WipeProgress:
    complete: bool
    deleted: int
    remaining: int
    chunk_operation_id: str | None


def _list_voice_canonical_paths(root: Path) -> list[str]:
    rels: list[str] = []
    voice = root / "voice"
    if not voice.is_dir():
        return rels
    for sub in ("samples", "embeddings", "vectors", "decisions", "generations"):
        d = voice / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                rels.append(p.relative_to(root).as_posix())
    # Keep privacy settings unless full wipe includes consent clear (caller decides)
    return rels


def list_voice_paths_for_profile(root: Path, profile_id: str) -> list[str]:
    """Canonical voice paths owned by ``profile_id`` (samples/embeddings/vectors)."""
    rels: list[str] = []
    samples_dir = root / "voice" / "samples"
    emb_dir = root / "voice" / "embeddings"
    sample_ids: set[str] = set()
    if samples_dir.is_dir():
        for path in sorted(samples_dir.glob("*.voice_sample.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if payload.get("profile_id") != profile_id:
                continue
            sample_ids.add(str(payload.get("sample_id") or path.name.split(".")[0]))
            rels.append(path.relative_to(root).as_posix())
    if emb_dir.is_dir():
        for path in sorted(emb_dir.glob("*.voice_embedding.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if payload.get("profile_id") != profile_id and payload.get(
                "sample_id"
            ) not in sample_ids:
                continue
            rels.append(path.relative_to(root).as_posix())
            emb_id = payload.get("embedding_id")
            if emb_id:
                vec = root / "voice" / "vectors" / f"{emb_id}.npy"
                if vec.is_file():
                    rels.append(vec.relative_to(root).as_posix())
    return rels


class VoiceWipeService:
    """Chunked journalled deletes — never one unbounded recursive plan."""

    def __init__(self, root: Path | None = None, state_dir: Path | None = None) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.engine = OperationEngine(self.root)

    def _receipt_path(self) -> Path:
        assert_safe_relpath(WIPE_RECEIPT_REL)
        return self.root / WIPE_RECEIPT_REL

    def read_receipt(self) -> dict | None:
        path = self._receipt_path()
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def start_or_resume_global_wipe(
        self,
        *,
        operation_idempotency_key: str,
        include_privacy: bool = False,
        actor: str = "user",
    ) -> WipeProgress:
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            receipt = self.read_receipt()
            pending = list(_list_voice_canonical_paths(self.root))
            if include_privacy:
                pending.append("voice/privacy.voice_settings.json")
                pending.append("voice/active_generation.json")
            # Deduplicate preserve order
            seen: set[str] = set()
            paths = []
            for r in pending:
                if r not in seen:
                    seen.add(r)
                    paths.append(r)

            if receipt and receipt.get("pending_paths"):
                paths = list(receipt["pending_paths"])

            if not paths:
                # Clear disposable caches even when canonical empty
                VoiceExcerptStore(self.root).clear_all()
                VoiceSuggestionCache(self.root).invalidate_all()
                q = self.root / ".cache" / "voice" / "query"
                if q.is_dir():
                    for p in q.rglob("*"):
                        if p.is_file():
                            p.unlink(missing_ok=True)
                if self._receipt_path().exists():
                    self._receipt_path().unlink(missing_ok=True)
                return WipeProgress(
                    complete=True, deleted=0, remaining=0, chunk_operation_id=None
                )

            chunk = paths[:MAX_PATHS_PER_CHUNK]
            rest = paths[MAX_PATHS_PER_CHUNK:]
            deletes: list[PlannedDelete] = []
            for rel in chunk:
                abs_path = self.root / rel
                if abs_path.is_file():
                    deletes.append(PlannedDelete(relpath=rel))

            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_wipe_chunk",
                created_at=utc_now_iso(),
                actor=actor,
                payload={
                    "deleted_count": len(deletes),
                    "remaining_after": len(rest),
                },
            )
            from transcriptx.core.speaker_profiles.operations import PlannedWrite

            writes = [
                PlannedWrite(
                    relpath=relative_event_path(event_id),
                    data=dumps_model(event),
                )
            ]
            # Update wipe receipt as after-image
            new_receipt = {
                "schema_id": "voice_wipe_receipt.v1",
                "pending_paths": rest,
                "updated_at": utc_now_iso(),
                "include_privacy": include_privacy,
            }
            writes.append(
                PlannedWrite(
                    relpath=WIPE_RECEIPT_REL,
                    data=(json.dumps(new_receipt, indent=2) + "\n").encode("utf-8"),
                )
            )

            if not rest:
                VoiceExcerptStore(self.root).clear_all()
                VoiceSuggestionCache(self.root).invalidate_all()
                q = self.root / ".cache" / "voice" / "query"
                if q.is_dir():
                    for p in q.rglob("*"):
                        if p.is_file():
                            p.unlink(missing_ok=True)
                # Do not persist an empty wipe receipt on the final chunk.
                writes = [w for w in writes if w.relpath != WIPE_RECEIPT_REL]
                if self._receipt_path().is_file():
                    deletes.append(PlannedDelete(relpath=WIPE_RECEIPT_REL))
                outcome = self.engine.run(
                    op_type="voice_wipe_chunk",
                    operation_idempotency_key=operation_idempotency_key,
                    writes=writes,
                    deletes=deletes,
                    receipt_extra={
                        "scopes": ["speaker_voice"],
                        "deleted": [d.relpath for d in deletes],
                        "remaining": 0,
                        "wipe_complete": True,
                    },
                )
                return WipeProgress(
                    complete=True,
                    deleted=len(deletes),
                    remaining=0,
                    chunk_operation_id=outcome.operation_id,
                )
            outcome = self.engine.run(
                op_type="voice_wipe_chunk",
                operation_idempotency_key=operation_idempotency_key,
                writes=writes,
                deletes=deletes,
                receipt_extra={
                    "scopes": ["speaker_voice"],
                    "deleted": [d.relpath for d in deletes],
                    "remaining": len(rest),
                },
            )
            return WipeProgress(
                complete=False,
                deleted=len(deletes),
                remaining=len(rest),
                chunk_operation_id=outcome.operation_id,
            )

    def wipe_until_complete(
        self, *, base_idempotency_key: str, include_privacy: bool = False
    ) -> WipeProgress:
        """Run chunks until complete (tests / CLI)."""
        i = 0
        last = WipeProgress(complete=False, deleted=0, remaining=-1, chunk_operation_id=None)
        while True:
            last = self.start_or_resume_global_wipe(
                operation_idempotency_key=f"{base_idempotency_key}:chunk:{i}",
                include_privacy=include_privacy,
            )
            i += 1
            if last.complete:
                return last
            if i > 10_000:
                raise RuntimeError("wipe did not complete within chunk budget")

    def wipe_profile_voice(
        self,
        *,
        operation_idempotency_key: str,
        profile_id: str,
        actor: str = "user",
    ) -> WipeProgress:
        """Delete voice artefacts owned by one profile (single chunked plan)."""
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            paths = list_voice_paths_for_profile(self.root, profile_id)
            if not paths:
                return WipeProgress(
                    complete=True, deleted=0, remaining=0, chunk_operation_id=None
                )
            deletes = [
                PlannedDelete(relpath=rel)
                for rel in paths
                if (self.root / rel).is_file()
            ]
            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1
            from transcriptx.core.speaker_profiles.operations import PlannedWrite

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_wipe_profile",
                created_at=utc_now_iso(),
                actor=actor,
                payload={
                    "profile_id": profile_id,
                    "deleted_count": len(deletes),
                },
            )
            outcome = self.engine.run(
                op_type="voice_wipe_profile",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    )
                ],
                deletes=deletes,
                receipt_extra={
                    "scopes": ["speaker_voice"],
                    "profile_id": profile_id,
                    "deleted": [d.relpath for d in deletes],
                },
            )
            return WipeProgress(
                complete=True,
                deleted=len(deletes),
                remaining=0,
                chunk_operation_id=outcome.operation_id,
            )