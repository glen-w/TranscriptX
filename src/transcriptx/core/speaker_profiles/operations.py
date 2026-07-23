"""Portable multi-file operation protocol for speaker profiles."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from transcriptx.core.speaker_profiles.hashing import sha256_bytes, sha256_file
from transcriptx.core.speaker_profiles.layout import (
    operation_backup_dir,
    operation_staging_dir,
)
from transcriptx.core.speaker_profiles.models import (
    OperationPlanActionV1,
    OperationPlanV1,
    SpeakerProfileOperationV1,
)
from transcriptx.core.speaker_profiles.store_io import (
    delete_under_root,
    find_operations_by_idempotency_key,
    utc_now_iso,
    write_bytes_under_root,
    write_operation,
)
from transcriptx.io.atomic_json import write_bytes_atomic


@dataclass(frozen=True)
class PlannedWrite:
    """A planned write of known after-image bytes."""

    relpath: str
    data: bytes
    expected_before_sha256: str | None = None


@dataclass(frozen=True)
class PlannedDelete:
    relpath: str
    expected_before_sha256: str | None = None


@dataclass(frozen=True)
class OperationOutcome:
    operation_id: str
    operation_idempotency_key: str
    op_type: str
    replayed: bool
    receipt: dict[str, Any]


class OperationEngine:
    """Execute journalled multi-file mutations under speaker_profiles root."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def find_complete(self, operation_idempotency_key: str) -> OperationOutcome | None:
        existing_ops = find_operations_by_idempotency_key(
            operation_idempotency_key, root=self.root
        )
        if not existing_ops:
            return None

        from transcriptx.core.speaker_profiles.recovery import (
            PROVEN_ABORTED,
            classify_operation,
        )

        # Prefer completed receipt for idempotent replay.
        for existing in existing_ops:
            if existing.phase == "complete" and existing.receipt is not None:
                return OperationOutcome(
                    operation_id=existing.operation_id,
                    operation_idempotency_key=existing.operation_idempotency_key,
                    op_type=existing.op_type,
                    replayed=True,
                    receipt=dict(existing.receipt),
                )

        # Any blocking non-proven-aborted attempt blocks a new start.
        blocking: list[str] = []
        for existing in existing_ops:
            report = classify_operation(self.root, existing)
            if report.recovery_class == "proven_aborted" or (
                existing.phase == "failed"
                and (existing.receipt or {}).get("abort_class") == PROVEN_ABORTED
            ):
                continue
            blocking.append(
                f"{existing.operation_id}:{existing.phase}/{report.recovery_class}"
            )
        if blocking:
            from transcriptx.core.speaker_profiles.errors import ActiveOperationError

            raise ActiveOperationError(
                f"operation key {operation_idempotency_key} blocked by "
                f"{', '.join(blocking)}"
            )
        return None

    def run(
        self,
        *,
        op_type: str,
        operation_idempotency_key: str,
        writes: list[PlannedWrite],
        deletes: list[PlannedDelete],
        receipt_extra: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> OperationOutcome:
        replay = self.find_complete(operation_idempotency_key)
        if replay is not None:
            return replay

        op_id = operation_id or str(uuid4())
        staging = operation_staging_dir(op_id, root=self.root)
        backup = operation_backup_dir(op_id, root=self.root)
        staging.mkdir(parents=True, exist_ok=True)
        backup.mkdir(parents=True, exist_ok=True)

        from transcriptx.core.speaker_profiles.path_safety import assert_safe_relpath

        actions: list[OperationPlanActionV1] = []
        staged_payloads: dict[str, bytes] = {}

        for item in writes:
            safe_rel = assert_safe_relpath(item.relpath, what="operation write")
            if safe_rel != item.relpath.replace("\\", "/"):
                from transcriptx.core.speaker_profiles.errors import (
                    SpeakerProfileContractError,
                )

                raise SpeakerProfileContractError(
                    f"operation write path must be normalised POSIX relpath: "
                    f"{item.relpath!r}"
                )
            abs_path = self.root / item.relpath
            before = sha256_file(abs_path)
            if item.expected_before_sha256 is not None and before != item.expected_before_sha256:
                from transcriptx.core.speaker_profiles.errors import StaleUpdateError

                raise StaleUpdateError(
                    f"stale write for {item.relpath}: expected before "
                    f"{item.expected_before_sha256}, found {before}"
                )
            after = sha256_bytes(item.data)
            staging_rel = f"operations/{op_id}/staging/{item.relpath}"
            staging_path = self.root / staging_rel
            staging_path.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_atomic(staging_path, item.data)
            staged_payloads[item.relpath] = item.data
            backup_rel = None
            if before is not None:
                # Crash-safe: keep before-image for overwrite rollback.
                backup_rel = f"operations/{op_id}/backup/{item.relpath}"
                backup_path = self.root / backup_rel
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                write_bytes_atomic(backup_path, abs_path.read_bytes())
            actions.append(
                OperationPlanActionV1(
                    action="write",
                    path=item.relpath,
                    expected_before_sha256=before,
                    after_sha256=after,
                    staging_relpath=staging_rel,
                    backup_relpath=backup_rel,
                )
            )

        for item in deletes:
            assert_safe_relpath(item.relpath, what="operation delete")
            abs_path = self.root / item.relpath
            before = sha256_file(abs_path)
            if before is None:
                from transcriptx.core.speaker_profiles.errors import (
                    SpeakerProfileContractError,
                )

                raise SpeakerProfileContractError(
                    f"delete target missing: {item.relpath}"
                )
            if (
                item.expected_before_sha256 is not None
                and before != item.expected_before_sha256
            ):
                from transcriptx.core.speaker_profiles.errors import StaleUpdateError

                raise StaleUpdateError(
                    f"stale delete for {item.relpath}: expected before "
                    f"{item.expected_before_sha256}, found {before}"
                )
            backup_rel = f"operations/{op_id}/backup/{item.relpath}"
            backup_path = self.root / backup_rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_atomic(backup_path, abs_path.read_bytes())
            actions.append(
                OperationPlanActionV1(
                    action="delete",
                    path=item.relpath,
                    expected_before_sha256=before,
                    after_sha256=None,
                    backup_relpath=backup_rel,
                )
            )

        op = SpeakerProfileOperationV1(
            operation_id=op_id,
            operation_idempotency_key=operation_idempotency_key,
            op_type=op_type,
            phase="prepared",
            plan=OperationPlanV1(actions=actions),
            error_history=[],
            receipt=None,
        )
        write_operation(op, root=self.root)

        op = op.model_copy(update={"phase": "staged"})
        write_operation(op, root=self.root)

        # Apply domain mutations (transaction barrier).
        for action in actions:
            target = self.root / action.path
            if action.action == "write":
                assert action.staging_relpath is not None
                data = staged_payloads[action.path]
                write_bytes_under_root(target, data, root=self.root)
            elif action.action == "delete":
                delete_under_root(target, root=self.root)

        # Verify after-state matches plan before marking committed.
        for action in actions:
            target = self.root / action.path
            if action.action == "write":
                actual = sha256_file(target)
                if actual != action.after_sha256:
                    op = op.model_copy(
                        update={
                            "phase": "needs_repair",
                            "error_history": list(op.error_history)
                            + [
                                {
                                    "at": utc_now_iso(),
                                    "error": f"after_sha256 mismatch for {action.path}",
                                }
                            ],
                        }
                    )
                    write_operation(op, root=self.root)
                    from transcriptx.core.speaker_profiles.errors import (
                        RepairRequiredError,
                    )

                    raise RepairRequiredError(
                        f"after_sha256 mismatch for {action.path}"
                    )
            else:
                if target.exists():
                    op = op.model_copy(
                        update={
                            "phase": "needs_repair",
                            "error_history": list(op.error_history)
                            + [
                                {
                                    "at": utc_now_iso(),
                                    "error": f"delete incomplete for {action.path}",
                                }
                            ],
                        }
                    )
                    write_operation(op, root=self.root)
                    from transcriptx.core.speaker_profiles.errors import (
                        RepairRequiredError,
                    )

                    raise RepairRequiredError(f"delete incomplete for {action.path}")

        op = op.model_copy(update={"phase": "transaction_committed"})
        write_operation(op, root=self.root)

        receipt = {
            "completed_at": utc_now_iso(),
            "action_summaries": [
                {"action": a.action, "path": a.path, "after_sha256": a.after_sha256}
                for a in actions
            ],
            "operation_idempotency_key": operation_idempotency_key,
        }
        if receipt_extra:
            receipt.update(receipt_extra)

        op = op.model_copy(update={"phase": "finalized", "receipt": receipt})
        write_operation(op, root=self.root)

        # Retention: strip staging/backup bytes after complete.
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        # Remove empty operation_id directory if present.
        op_dir = self.root / "operations" / op_id
        if op_dir.is_dir():
            shutil.rmtree(op_dir, ignore_errors=True)

        op = op.model_copy(update={"phase": "complete"})
        write_operation(op, root=self.root)

        return OperationOutcome(
            operation_id=op_id,
            operation_idempotency_key=operation_idempotency_key,
            op_type=op_type,
            replayed=False,
            receipt=receipt,
        )


def relative_profile_path(profile_id: str) -> str:
    return f"profiles/{profile_id}.speaker_profile.json"


def relative_link_path(link_file_key: str) -> str:
    return f"links/{link_file_key}.speaker_link.json"


def relative_event_path(idempotency_id: str) -> str:
    return f"events/{idempotency_id}.speaker_event.json"


def relative_avatar_path(profile_id: str) -> str:
    return f"profiles/assets/{profile_id}/avatar.webp"


def relative_voice_privacy_path() -> str:
    return "voice/privacy.voice_settings.json"


def relative_voice_operator_path() -> str:
    return "voice/operator.voice_settings.json"


def relative_voice_sample_path(sample_id: str) -> str:
    return f"voice/samples/{sample_id}.voice_sample.json"


def relative_voice_embedding_path(embedding_id: str) -> str:
    return f"voice/embeddings/{embedding_id}.voice_embedding.json"


def relative_voice_vector_path(embedding_id: str) -> str:
    return f"voice/vectors/{embedding_id}.npy"


def relative_voice_decision_path(decision_id: str) -> str:
    return f"voice/decisions/{decision_id}.voice_decision.json"


def relative_voice_generation_path(model_generation_id: str) -> str:
    return f"voice/generations/{model_generation_id}.json"


def relative_voice_active_generation_path() -> str:
    return "voice/active_generation.json"
