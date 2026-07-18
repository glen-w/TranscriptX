"""Generational artifact index: current complete vs latest attempt."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.emotion_family.canonical_hash import canonical_json_hash
from transcriptx.core.analysis.emotion_family.errors import (
    EmotionFamilyGenerationConflictError,
    EmotionFamilyGenerationIncompleteError,
    EmotionFamilyGenerationValidationError,
    EmotionFamilyPersistError,
    EmotionFamilySchemaError,
    EmotionFamilyUnsafeIdentifierError,
)
from transcriptx.core.analysis.emotion_family.safe_ids import (
    assert_generation_id,
    assert_path_under_root,
    assert_safe_token,
)
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.io.atomic_json import write_json_atomic as shared_write_json_atomic

INDEX_FILENAME = "artifact_index.json"
GENERATIONS_DIRNAME = "generations"
ORPHANED_DIRNAME = "orphaned"
CANONICAL_ROWS_FILENAME = "canonical_rows.json"
GENERATION_MANIFEST_FILENAME = "generation_manifest.json"

INDEX_SCHEMA_VERSION = "emotion_family_artifact_index_v1"
MANIFEST_SCHEMA_VERSION = "emotion_family_generation_manifest_v1"
ATTEMPT_HISTORY_CAP = 50
GENERATION_KEEP_RECENT = 50
ORPHAN_GRACE_SECONDS = 60.0

_TEMP_PREFIXES = (".emotion_json_", ".emotion_idx_", ".inference_", ".aggregation_")


@dataclass
class ArtifactGenerationIndex:
    module_id: str
    current_complete_generation: str | None = None
    latest_attempt_generation: str | None = None
    attempt_history: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = INDEX_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = self.schema_version or INDEX_SCHEMA_VERSION
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactGenerationIndex":
        schema = str(data.get("schema_version") or INDEX_SCHEMA_VERSION)
        if schema != INDEX_SCHEMA_VERSION:
            raise EmotionFamilySchemaError(
                f"unsupported artifact index schema: {schema!r}"
            )
        module_id = str(data.get("module_id") or "")
        if not module_id:
            raise EmotionFamilyGenerationValidationError(
                "artifact index missing module_id"
            )
        return cls(
            module_id=module_id,
            current_complete_generation=data.get("current_complete_generation"),
            latest_attempt_generation=data.get("latest_attempt_generation"),
            attempt_history=list(data.get("attempt_history") or []),
            schema_version=schema,
        )


def load_index(path: Path) -> ArtifactGenerationIndex | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError, TypeError) as exc:
        raise EmotionFamilyPersistError(f"corrupt artifact index: {path}") from exc
    if not isinstance(raw, dict):
        raise EmotionFamilyPersistError(f"corrupt artifact index: {path}")
    return ArtifactGenerationIndex.from_dict(raw)


def save_index_atomic(path: Path, index: ArtifactGenerationIndex) -> None:
    write_json_atomic(path, index.to_dict())


def write_json_atomic(final_path: Path, payload: Any) -> None:
    """Strict crash-safe JSON write (shared atomic_json primitive)."""
    shared_write_json_atomic(final_path, payload, indent=2)


def record_attempt(
    index: ArtifactGenerationIndex,
    *,
    generation_id: str,
    run_status: str,
    usable_output: bool,
    extra: dict[str, Any] | None = None,
) -> ArtifactGenerationIndex:
    """Update latest_attempt; never clears current_complete on failure/partial."""
    index.latest_attempt_generation = generation_id
    entry = {
        "artifact_generation_id": generation_id,
        "run_status": run_status,
        "usable_output": usable_output,
    }
    if extra:
        entry.update(extra)
    index.attempt_history.append(entry)
    if len(index.attempt_history) > ATTEMPT_HISTORY_CAP:
        index.attempt_history = index.attempt_history[-ATTEMPT_HISTORY_CAP:]
    return index


def activate_complete_generation(
    index: ArtifactGenerationIndex,
    *,
    generation_id: str,
    usable_output: bool,
) -> ArtifactGenerationIndex:
    """Point current_complete at generation only when usable_output is true."""
    index.latest_attempt_generation = generation_id
    if usable_output:
        index.current_complete_generation = generation_id
    return index


def should_activate_generation(*, run_status: str, usable_output: bool) -> bool:
    """Only complete + usable generations become current_complete_generation."""
    return str(run_status) == "complete" and bool(usable_output)


def generation_dir_path(module_dir: Path | str, generation_id: str) -> Path:
    gid = assert_generation_id(generation_id)
    module_path = Path(module_dir)
    path = module_path / GENERATIONS_DIRNAME / gid
    # Validate only after parents exist / on resolve during persist
    return path


def generation_rows_path(module_dir: Path | str, generation_id: str) -> Path:
    return generation_dir_path(module_dir, generation_id) / CANONICAL_ROWS_FILENAME


def generation_manifest_path(module_dir: Path | str, generation_id: str) -> Path:
    return generation_dir_path(module_dir, generation_id) / GENERATION_MANIFEST_FILENAME


def row_integrity_checksum(row: Mapping[str, Any]) -> str:
    return canonical_json_hash(dict(row))


def ordered_segment_ids_from_rows(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(r.get("segment_id") or "") for r in rows]


def _count_evaluation_states(rows: Sequence[Mapping[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        state = str(row.get("evaluation_state") or "")
        if state:
            counts[state] += 1
    return counts


def build_generation_manifest(
    *,
    module_id: str,
    artifact_generation_id: str,
    inference_generation_id: str | None,
    schema_version: str | None,
    semantics_version: str | None,
    compatibility_fingerprint: str | None,
    run_status: str,
    usable_output: bool,
    canonical_rows: Sequence[Mapping[str, Any]],
    expected_segment_ids: Sequence[str] | None = None,
    segments_scored: int | None = None,
    segments_skipped: int | None = None,
    segments_empty: int | None = None,
    segments_failed: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    assert_safe_token(module_id, what="module_id")
    assert_generation_id(artifact_generation_id)
    if inference_generation_id:
        assert_generation_id(inference_generation_id)

    ordered_ids = ordered_segment_ids_from_rows(canonical_rows)
    if expected_segment_ids is not None:
        ordered_ids = [str(s) for s in expected_segment_ids]
    row_checksums = [
        {
            "segment_id": str(row.get("segment_id") or ""),
            "integrity_checksum": row_integrity_checksum(row),
            "scored_text_hash": row.get("scored_text_hash"),
        }
        for row in canonical_rows
    ]
    rows_digest = canonical_json_hash(row_checksums)
    state_counts = _count_evaluation_states(canonical_rows)
    if segments_scored is None:
        segments_scored = int(state_counts.get("scored", 0))
    if segments_skipped is None:
        segments_skipped = int(state_counts.get("skipped", 0))
    if segments_empty is None:
        segments_empty = int(state_counts.get("empty", 0))
    if segments_failed is None:
        segments_failed = int(state_counts.get("failed", 0))

    manifest: dict[str, Any] = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "module_id": module_id,
        "artifact_generation_id": artifact_generation_id,
        "inference_generation_id": inference_generation_id,
        "schema_version": schema_version,
        "semantics_version": semantics_version,
        "compatibility_fingerprint": compatibility_fingerprint,
        "run_status": run_status,
        "usable_output": usable_output,
        "ordered_segment_ids": ordered_ids,
        "row_count": len(canonical_rows),
        "segments_scored": segments_scored,
        "segments_skipped": segments_skipped,
        "segments_empty": segments_empty,
        "segments_failed": segments_failed,
        "row_checksums": row_checksums,
        "rows_integrity_digest": rows_digest,
    }
    if extra:
        manifest.update(dict(extra))
    manifest["manifest_integrity_checksum"] = canonical_json_hash(
        {k: v for k, v in manifest.items() if k != "manifest_integrity_checksum"}
    )
    return manifest


def write_canonical_rows_atomic(
    final_path: Path,
    rows: list[dict[str, Any]],
    *,
    validate_count: int | None = None,
) -> None:
    """Write rows to temp, validate, atomically promote."""
    if validate_count is not None and len(rows) != validate_count:
        raise ValueError(
            f"canonical row count mismatch: got {len(rows)}, expected {validate_count}"
        )
    write_json_atomic(final_path, rows)


def load_generation_rows(
    module_dir: Path | str, generation_id: str
) -> list[dict[str, Any]]:
    """Read and return canonical rows for a generation; raises on missing/invalid."""
    rows_path = generation_rows_path(module_dir, generation_id)
    if not rows_path.is_file():
        raise FileNotFoundError(f"canonical rows missing: {rows_path}")
    with rows_path.open("r", encoding="utf-8") as fh:
        rows = json.load(fh)
    if not isinstance(rows, list):
        raise ValueError(f"canonical rows must be a list: {rows_path}")
    return rows


def load_generation_manifest(
    module_dir: Path | str, generation_id: str
) -> dict[str, Any]:
    path = generation_manifest_path(module_dir, generation_id)
    if not path.is_file():
        raise FileNotFoundError(f"generation manifest missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    if not isinstance(manifest, dict):
        raise ValueError(f"generation manifest must be an object: {path}")
    return manifest


def generation_is_complete(module_dir: Path | str, generation_id: str) -> bool:
    gen_dir = generation_dir_path(module_dir, generation_id)
    return (
        gen_dir.is_dir()
        and (gen_dir / CANONICAL_ROWS_FILENAME).is_file()
        and (gen_dir / GENERATION_MANIFEST_FILENAME).is_file()
    )


def validate_generation_readable(
    module_dir: Path | str,
    generation_id: str,
    *,
    expected_count: int | None = None,
) -> list[dict[str, Any]]:
    """Read-back validation before activating a generation."""
    rows = load_generation_rows(module_dir, generation_id)
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(
            f"canonical row count mismatch after persist: "
            f"got {len(rows)}, expected {expected_count}"
        )
    return rows


def validate_generation_integrity(
    module_dir: Path | str,
    generation_id: str,
    *,
    expected_manifest: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Full pre-activation validation: ordered segment IDs, uniqueness,
    scored_text_hash presence where required, row checksums, metadata.
    """
    assert_generation_id(generation_id)
    rows = load_generation_rows(module_dir, generation_id)
    manifest = load_generation_manifest(module_dir, generation_id)

    manifest_schema = str(
        manifest.get("manifest_schema_version") or MANIFEST_SCHEMA_VERSION
    )
    if manifest_schema != MANIFEST_SCHEMA_VERSION:
        raise EmotionFamilySchemaError(
            f"unsupported generation manifest schema: {manifest_schema!r}"
        )

    required_fields = (
        "module_id",
        "artifact_generation_id",
        "schema_version",
        "semantics_version",
        "run_status",
        "usable_output",
        "ordered_segment_ids",
        "row_count",
        "row_checksums",
        "rows_integrity_digest",
        "manifest_integrity_checksum",
    )
    for key in required_fields:
        if key not in manifest:
            raise EmotionFamilyGenerationValidationError(
                f"manifest missing required field {key!r}"
            )

    if expected_manifest is not None:
        for key in (
            "module_id",
            "artifact_generation_id",
            "schema_version",
            "semantics_version",
            "compatibility_fingerprint",
            "run_status",
            "usable_output",
            "ordered_segment_ids",
            "row_count",
            "rows_integrity_digest",
        ):
            if key in expected_manifest and manifest.get(key) != expected_manifest.get(
                key
            ):
                raise EmotionFamilyGenerationValidationError(
                    f"manifest field mismatch for {key!r}: "
                    f"got {manifest.get(key)!r}, expected {expected_manifest.get(key)!r}"
                )

    if str(manifest.get("artifact_generation_id") or "") != generation_id:
        raise EmotionFamilyGenerationValidationError(
            "manifest artifact_generation_id does not match directory"
        )

    ordered = list(manifest.get("ordered_segment_ids") or [])
    if not isinstance(ordered, list):
        raise EmotionFamilyGenerationValidationError(
            "ordered_segment_ids must be a list"
        )
    row_count = manifest.get("row_count")
    if row_count is None:
        raise EmotionFamilyGenerationValidationError("manifest missing row_count")
    if len(rows) != int(row_count):
        raise EmotionFamilyGenerationValidationError(
            f"row_count mismatch: rows={len(rows)} manifest={row_count}"
        )
    if len(ordered) != len(rows):
        raise EmotionFamilyGenerationValidationError(
            "ordered_segment_ids length does not match row count"
        )

    checksums = manifest.get("row_checksums")
    if not isinstance(checksums, list):
        raise EmotionFamilyGenerationValidationError("row_checksums must be a list")
    if len(checksums) != len(rows):
        raise EmotionFamilyGenerationValidationError(
            "row_checksums length does not match row count"
        )

    state_counts = _count_evaluation_states(rows)
    for field_name, state in (
        ("segments_scored", "scored"),
        ("segments_skipped", "skipped"),
        ("segments_empty", "empty"),
        ("segments_failed", "failed"),
    ):
        declared = manifest.get(field_name)
        if declared is None:
            continue
        actual = int(state_counts.get(state, 0))
        if int(declared) != actual:
            raise EmotionFamilyGenerationValidationError(
                f"{field_name} mismatch: declared={declared} actual={actual}"
            )

    if should_activate_generation(
        run_status=str(manifest.get("run_status") or ""),
        usable_output=bool(manifest.get("usable_output")),
    ):
        if int(manifest.get("segments_scored") or 0) < 1 and len(rows) > 0:
            # usable complete with rows must have scored count agreeing; empty
            # complete+usable is rejected by consumers separately.
            pass
        if not bool(manifest.get("usable_output")):
            raise EmotionFamilyGenerationValidationError(
                "complete+usable invariant violated"
            )

    # Empty generations are valid (failed/skipped attempts with no rows).
    if not rows:
        recomputed = canonical_json_hash(manifest.get("row_checksums") or [])
        if recomputed != manifest.get("rows_integrity_digest"):
            raise EmotionFamilyGenerationValidationError(
                "rows_integrity_digest mismatch"
            )
        stored_manifest_checksum = manifest.get("manifest_integrity_checksum")
        body = {k: v for k, v in manifest.items() if k != "manifest_integrity_checksum"}
        if stored_manifest_checksum != canonical_json_hash(body):
            raise EmotionFamilyGenerationValidationError(
                "manifest_integrity_checksum mismatch"
            )
        return rows, manifest

    seen: set[str] = set()
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise EmotionFamilyGenerationValidationError(
                f"canonical row at index {idx} must be an object"
            )
        sid = str(row.get("segment_id") or "")
        if not sid.strip():
            raise EmotionFamilyGenerationValidationError(
                f"empty segment_id at row index {idx}"
            )
        if sid in seen:
            raise EmotionFamilyGenerationValidationError(f"duplicate segment_id: {sid}")
        seen.add(sid)
        if ordered[idx] != sid:
            raise EmotionFamilyGenerationValidationError(
                f"ordered segment_id mismatch at {idx}: "
                f"row={sid!r} manifest={ordered[idx]!r}"
            )
        checksum_entry = checksums[idx]
        if not isinstance(checksum_entry, dict):
            raise EmotionFamilyGenerationValidationError(
                f"row_checksums[{idx}] must be an object"
            )
        if str(checksum_entry.get("segment_id") or "") != sid:
            raise EmotionFamilyGenerationValidationError(
                f"row_checksums segment_id mismatch at {idx}"
            )
        expected_hash = checksum_entry.get("integrity_checksum")
        actual = row_integrity_checksum(row)
        if expected_hash is not None and expected_hash != actual:
            raise EmotionFamilyGenerationValidationError(
                f"row integrity mismatch for {sid}"
            )
        state = str(row.get("evaluation_state") or "")
        if state in {"scored", "skipped", "empty", "failed"}:
            if not str(row.get("scored_text_hash") or "").strip():
                raise EmotionFamilyGenerationValidationError(
                    f"missing scored_text_hash for segment {sid}"
                )

    recomputed = canonical_json_hash(manifest.get("row_checksums") or [])
    if recomputed != manifest.get("rows_integrity_digest"):
        raise EmotionFamilyGenerationValidationError("rows_integrity_digest mismatch")

    stored_manifest_checksum = manifest.get("manifest_integrity_checksum")
    body = {k: v for k, v in manifest.items() if k != "manifest_integrity_checksum"}
    if stored_manifest_checksum != canonical_json_hash(body):
        raise EmotionFamilyGenerationValidationError(
            "manifest_integrity_checksum mismatch"
        )

    return rows, manifest


def resolve_canonical_ref(
    module_dir: Path | str,
    canonical_ref: Mapping[str, Any],
    *,
    expected_module_id: str | None = None,
    expected_scored_text_hash: str | None = None,
) -> dict[str, Any] | None:
    """
    Resolve a canonical_ref against generation manifest + row integrity.
    Returns the matching row or None when validation fails.
    """
    generation_id = str(canonical_ref.get("artifact_generation_id") or "")
    row_key = str(canonical_ref.get("row_key") or "")
    if not generation_id or not row_key:
        return None
    try:
        assert_generation_id(generation_id)
        rows, manifest = validate_generation_integrity(module_dir, generation_id)
    except (
        OSError,
        ValueError,
        EmotionFamilyGenerationValidationError,
        EmotionFamilySchemaError,
        EmotionFamilyUnsafeIdentifierError,
        FileNotFoundError,
    ):
        return None
    if expected_module_id and manifest.get("module_id") != expected_module_id:
        return None
    if canonical_ref.get("module_id") and canonical_ref.get(
        "module_id"
    ) != manifest.get("module_id"):
        return None
    if canonical_ref.get("schema_version") and canonical_ref.get(
        "schema_version"
    ) != manifest.get("schema_version"):
        return None
    if canonical_ref.get("semantics_version") and canonical_ref.get(
        "semantics_version"
    ) != manifest.get("semantics_version"):
        return None
    ordered = list(manifest.get("ordered_segment_ids") or [])
    if row_key not in ordered:
        return None
    for row in rows:
        if str(row.get("segment_id") or "") != row_key:
            continue
        expected = canonical_ref.get("integrity_checksum")
        if expected and expected != row_integrity_checksum(row):
            return None
        if expected_scored_text_hash is not None:
            if str(row.get("scored_text_hash") or "") != str(expected_scored_text_hash):
                return None
        ref_hash = canonical_ref.get("scored_text_hash")
        if ref_hash and str(row.get("scored_text_hash") or "") != str(ref_hash):
            return None
        return dict(row)
    return None


def _quarantine_generation_dir(module_path: Path, generation_dir: Path) -> Path | None:
    orphan_root = module_path / ORPHANED_DIRNAME
    orphan_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    target = (
        orphan_root / f"{generation_dir.name}-{stamp}-{int(time.time() * 1000) % 1000}"
    )
    try:
        shutil.move(str(generation_dir), str(target))
        return target
    except OSError:
        return None


def _cleanup_temp_files(module_path: Path) -> int:
    removed = 0
    for path in module_path.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if any(name.startswith(prefix) for prefix in _TEMP_PREFIXES):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def quarantine_orphaned_generations(
    module_dir: Path | str,
    *,
    grace_seconds: float = ORPHAN_GRACE_SECONDS,
    keep_recent: int = GENERATION_KEEP_RECENT,
) -> dict[str, Any]:
    """
    Quarantine incomplete/unindexed generation dirs and wipe abandoned temps.

    Must be called under the index lock (or before concurrent writers start).
    Never quarantines current_complete_generation.
    """
    module_path = Path(module_dir)
    index_path = module_path / INDEX_FILENAME
    try:
        index = load_index(index_path)
    except EmotionFamilyPersistError:
        corrupt_backup = module_path / f"{INDEX_FILENAME}.corrupt-{int(time.time())}"
        try:
            shutil.move(str(index_path), str(corrupt_backup))
        except OSError:
            pass
        index = None

    protected: set[str] = set()
    if index is not None:
        if index.current_complete_generation:
            protected.add(str(index.current_complete_generation))
        if index.latest_attempt_generation:
            protected.add(str(index.latest_attempt_generation))
        for entry in index.attempt_history[-keep_recent:]:
            gid = str(entry.get("artifact_generation_id") or "")
            if gid:
                protected.add(gid)

    generations_root = module_path / GENERATIONS_DIRNAME
    quarantined: list[str] = []
    now = time.time()
    if generations_root.is_dir():
        for child in list(generations_root.iterdir()):
            if not child.is_dir():
                continue
            gid = child.name
            try:
                assert_generation_id(gid)
            except ValueError:
                moved = _quarantine_generation_dir(module_path, child)
                if moved:
                    quarantined.append(gid)
                continue
            if gid in protected:
                # Still quarantine incomplete protected dirs after grace.
                if not generation_is_complete(module_path, gid):
                    age = now - child.stat().st_mtime
                    if age >= grace_seconds:
                        moved = _quarantine_generation_dir(module_path, child)
                        if moved:
                            quarantined.append(gid)
                continue
            complete = generation_is_complete(module_path, gid)
            age = now - child.stat().st_mtime
            if not complete and age >= grace_seconds:
                moved = _quarantine_generation_dir(module_path, child)
                if moved:
                    quarantined.append(gid)
            elif complete and gid not in protected and age >= grace_seconds:
                # Complete but unreferenced beyond retention window.
                moved = _quarantine_generation_dir(module_path, child)
                if moved:
                    quarantined.append(gid)

    # Repair dangling current_complete pointer.
    dangling_cleared = False
    if index is not None and index.current_complete_generation:
        gid = str(index.current_complete_generation)
        try:
            validate_generation_integrity(module_path, gid)
        except Exception:
            index.current_complete_generation = None
            dangling_cleared = True
            save_index_atomic(index_path, index)

    temps_removed = _cleanup_temp_files(module_path)
    return {
        "quarantined": quarantined,
        "temps_removed": temps_removed,
        "dangling_cleared": dangling_cleared,
    }


def _intended_digests(
    *,
    canonical_rows: list[dict[str, Any]],
    manifest: Mapping[str, Any],
) -> tuple[str, str]:
    return (
        str(manifest.get("rows_integrity_digest") or ""),
        str(manifest.get("manifest_integrity_checksum") or ""),
    )


def _existing_matches_intended(
    module_path: Path,
    generation_id: str,
    *,
    intended_rows_digest: str,
    intended_manifest_checksum: str,
) -> bool:
    if not generation_is_complete(module_path, generation_id):
        return False
    try:
        _rows, manifest = validate_generation_integrity(module_path, generation_id)
    except Exception:
        return False
    return (
        str(manifest.get("rows_integrity_digest") or "") == intended_rows_digest
        and str(manifest.get("manifest_integrity_checksum") or "")
        == intended_manifest_checksum
    )


def persist_generation(
    module_dir: Path | str,
    *,
    module_id: str,
    generation_id: str,
    run_status: str,
    usable_output: bool,
    canonical_rows: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
    inference_generation_id: str | None = None,
    schema_version: str | None = None,
    semantics_version: str | None = None,
    compatibility_fingerprint: str | None = None,
    expected_segment_ids: Sequence[str] | None = None,
    segments_scored: int | None = None,
    segments_skipped: int | None = None,
    segments_empty: int | None = None,
    segments_failed: int | None = None,
) -> Path:
    """
    Persist one generation under module_dir and update the artifact index.

    Write order: exclusive generation dir → rows → manifest → validate →
    locked index update. Only complete+usable becomes current_complete.

    Idempotent: an existing complete generation with matching content hashes
    succeeds without overwrite. Conflicting reuse raises.
    """
    try:
        assert_safe_token(module_id, what="module_id")
        assert_generation_id(generation_id)
    except ValueError as exc:
        raise EmotionFamilyUnsafeIdentifierError(str(exc)) from exc

    module_path = Path(module_dir)
    module_path.mkdir(parents=True, exist_ok=True)
    generations_root = module_path / GENERATIONS_DIRNAME
    generations_root.mkdir(parents=True, exist_ok=True)

    generation_dir = generation_dir_path(module_path, generation_id)
    try:
        assert_path_under_root(generation_dir, module_path)
    except ValueError as exc:
        raise EmotionFamilyUnsafeIdentifierError(str(exc)) from exc

    ordered_ids = (
        [str(s) for s in expected_segment_ids]
        if expected_segment_ids is not None
        else ordered_segment_ids_from_rows(canonical_rows)
    )
    manifest = build_generation_manifest(
        module_id=module_id,
        artifact_generation_id=generation_id,
        inference_generation_id=inference_generation_id,
        schema_version=schema_version,
        semantics_version=semantics_version,
        compatibility_fingerprint=compatibility_fingerprint,
        run_status=run_status,
        usable_output=usable_output,
        canonical_rows=canonical_rows,
        expected_segment_ids=ordered_ids,
        segments_scored=segments_scored,
        segments_skipped=segments_skipped,
        segments_empty=segments_empty,
        segments_failed=segments_failed,
        extra=extra,
    )
    intended_rows_digest, intended_manifest_checksum = _intended_digests(
        canonical_rows=canonical_rows, manifest=manifest
    )

    created = False
    try:
        generation_dir.mkdir(parents=True, exist_ok=False)
        created = True
    except FileExistsError:
        if _existing_matches_intended(
            module_path,
            generation_id,
            intended_rows_digest=intended_rows_digest,
            intended_manifest_checksum=intended_manifest_checksum,
        ):
            # Idempotent success — still ensure index records the attempt.
            index_path = module_path / INDEX_FILENAME
            with FileLock(index_path, timeout=30, blocking=True):
                quarantine_orphaned_generations(module_path)
                index = load_index(index_path) or ArtifactGenerationIndex(
                    module_id=module_id
                )
                record_attempt(
                    index,
                    generation_id=generation_id,
                    run_status=run_status,
                    usable_output=usable_output,
                    extra={
                        "compatibility_fingerprint": compatibility_fingerprint,
                        "segments_scored": segments_scored,
                        "inference_generation_id": inference_generation_id,
                        "idempotent_reuse": True,
                    },
                )
                if should_activate_generation(
                    run_status=run_status, usable_output=usable_output
                ):
                    activate_complete_generation(
                        index, generation_id=generation_id, usable_output=True
                    )
                else:
                    index.latest_attempt_generation = generation_id
                save_index_atomic(index_path, index)
            return generation_dir

        if generation_is_complete(module_path, generation_id):
            raise EmotionFamilyGenerationConflictError(
                f"generation directory already exists with conflicting contents: "
                f"{generation_dir}"
            )
        # Incomplete existing dir: if young, another writer may still be active.
        try:
            age = time.time() - generation_dir.stat().st_mtime
        except OSError:
            age = ORPHAN_GRACE_SECONDS
        if age < ORPHAN_GRACE_SECONDS:
            raise EmotionFamilyGenerationIncompleteError(
                f"generation directory write in progress: {generation_dir}"
            )
        # Stale incomplete dir: quarantine then retry once.
        _quarantine_generation_dir(module_path, generation_dir)
        try:
            generation_dir.mkdir(parents=True, exist_ok=False)
            created = True
        except FileExistsError as exc:
            raise EmotionFamilyGenerationIncompleteError(
                f"generation directory remains incomplete after quarantine: "
                f"{generation_dir}"
            ) from exc

    try:
        write_canonical_rows_atomic(
            generation_dir / CANONICAL_ROWS_FILENAME, list(canonical_rows)
        )
        write_json_atomic(generation_dir / GENERATION_MANIFEST_FILENAME, manifest)
        validate_generation_integrity(
            module_path, generation_id, expected_manifest=manifest
        )
    except Exception:
        if created:
            _quarantine_generation_dir(module_path, generation_dir)
        raise

    index_path = module_path / INDEX_FILENAME
    with FileLock(index_path, timeout=30, blocking=True):
        quarantine_orphaned_generations(module_path)
        index = load_index(index_path) or ArtifactGenerationIndex(module_id=module_id)
        record_attempt(
            index,
            generation_id=generation_id,
            run_status=run_status,
            usable_output=usable_output,
            extra={
                "compatibility_fingerprint": compatibility_fingerprint,
                "segments_scored": segments_scored,
                "inference_generation_id": inference_generation_id,
            },
        )
        if should_activate_generation(
            run_status=run_status, usable_output=usable_output
        ):
            activate_complete_generation(
                index, generation_id=generation_id, usable_output=True
            )
        else:
            index.latest_attempt_generation = generation_id
        save_index_atomic(index_path, index)
    return generation_dir


def update_enriched_projection_status(
    module_dir: Path | str,
    *,
    module_id: str,
    generation_id: str,
    enriched_projection_status: str,
    secondary_output_status: str | None = None,
) -> None:
    """Persist durable projection/secondary status on the latest matching attempt."""
    try:
        assert_generation_id(generation_id)
    except ValueError as exc:
        raise EmotionFamilyUnsafeIdentifierError(str(exc)) from exc
    module_path = Path(module_dir)
    index_path = module_path / INDEX_FILENAME
    with FileLock(index_path, timeout=30, blocking=True):
        index = load_index(index_path) or ArtifactGenerationIndex(module_id=module_id)
        updated = False
        for entry in reversed(index.attempt_history):
            if str(entry.get("artifact_generation_id") or "") == generation_id:
                entry["enriched_projection_status"] = enriched_projection_status
                if secondary_output_status is not None:
                    entry["secondary_output_status"] = secondary_output_status
                updated = True
                break
        if not updated:
            record_attempt(
                index,
                generation_id=generation_id,
                run_status="complete",
                usable_output=True,
                extra={
                    "enriched_projection_status": enriched_projection_status,
                    "secondary_output_status": secondary_output_status,
                },
            )
        save_index_atomic(index_path, index)


def record_attempt_only(
    module_dir: Path | str,
    *,
    module_id: str,
    generation_id: str,
    run_status: str,
    usable_output: bool,
    extra: dict[str, Any] | None = None,
) -> None:
    """Update artifact index without writing a generation directory."""
    module_path = Path(module_dir)
    index_path = module_path / INDEX_FILENAME
    with FileLock(index_path, timeout=30, blocking=True):
        quarantine_orphaned_generations(module_path)
        index = load_index(index_path) or ArtifactGenerationIndex(module_id=module_id)
        record_attempt(
            index,
            generation_id=generation_id,
            run_status=run_status,
            usable_output=usable_output,
            extra=extra,
        )
        save_index_atomic(index_path, index)


def persist_generation_from_results(
    results: dict[str, Any],
    output_service: Any,
    module_id: str,
) -> Path:
    """
    Persist the generation described by a module result via its OutputService.

    Fail-closed: raises when generation id or module_dir is missing, or when
    persist/validation fails. Callers must treat failure as module failure
    before writing enriched projections.
    """
    generation_id = str(results.get("artifact_generation_id") or "")
    if not generation_id:
        raise EmotionFamilyPersistError(
            "artifact_generation_id required for generational persist"
        )
    structure = output_service.get_output_structure()
    module_dir = getattr(structure, "module_dir", None)
    if module_dir is None and isinstance(structure, dict):
        module_dir = structure.get("module_dir")
    if not module_dir:
        raise EmotionFamilyPersistError("module_dir required for generational persist")
    rows = list(results.get("canonical_rows") or [])
    if not rows and isinstance(results.get("_canonical_rows"), list):
        rows = list(results["_canonical_rows"])
    expected_ids = results.get("ordered_segment_ids")
    if expected_ids is None:
        expected_ids = ordered_segment_ids_from_rows(rows)
    return persist_generation(
        module_dir,
        module_id=module_id,
        generation_id=generation_id,
        run_status=str(results.get("run_status") or ""),
        usable_output=bool(results.get("usable_output")),
        canonical_rows=rows,
        inference_generation_id=(
            str(results.get("inference_generation_id") or "") or None
        ),
        schema_version=results.get("schema_version"),
        semantics_version=results.get("semantics_version"),
        compatibility_fingerprint=results.get("compatibility_fingerprint"),
        expected_segment_ids=list(expected_ids),
        segments_scored=results.get("segments_scored"),
        segments_skipped=results.get("segments_skipped"),
        segments_empty=results.get("segments_empty"),
        segments_failed=results.get("segments_failed"),
        extra={
            "text_source_digest": results.get("text_source_digest"),
            "speaker_identity_digest": results.get("speaker_identity_digest"),
            "timeline_identity_digest": results.get("timeline_identity_digest"),
            "runtime_metadata": results.get("runtime_metadata"),
        },
    )


def load_current_complete_rows(module_dir: Path | str) -> list[dict[str, Any]] | None:
    """Read canonical rows of the active complete generation, if any."""
    module_path = Path(module_dir)
    try:
        index = load_index(module_path / INDEX_FILENAME)
    except EmotionFamilyPersistError:
        return None
    if index is None or not index.current_complete_generation:
        return None
    try:
        rows, _manifest = validate_generation_integrity(
            module_path, index.current_complete_generation
        )
        return rows
    except (
        OSError,
        ValueError,
        EmotionFamilyGenerationValidationError,
        EmotionFamilySchemaError,
    ):
        return None


def scores_by_segment_from_rows(
    rows: Sequence[dict[str, Any]] | None,
) -> dict[str, dict[str, float]]:
    """Map segment_id → score vector for consumer metrics."""
    out: dict[str, dict[str, float]] = {}
    if not rows:
        return out
    for row in rows:
        sid = str(row.get("segment_id") or "")
        if not sid:
            continue
        scores = row.get("scores")
        if isinstance(scores, dict):
            out[sid] = {str(k): float(v) for k, v in scores.items()}
    return out
