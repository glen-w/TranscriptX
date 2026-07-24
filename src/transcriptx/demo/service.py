"""Transactional demo project install / remove service."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from transcriptx.core.store.group_manifest_store import GroupManifestStore
from transcriptx.core.utils import paths as paths_mod
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.schema_epoch import CURRENT_SCHEMA_EPOCH
from transcriptx.core.utils.slug_manager import (
    INDEX_FILE,
    load_index,
    save_index,
)
from transcriptx.demo.pack_loader import (
    DemoPack,
    PackValidationError,
    extract_transcript_to_temp,
    load_and_validate_pack,
)
from transcriptx.io.admit_and_register import AdmitOutcomeKind, admit_and_register
from transcriptx.io.atomic_json import locked_path, write_bytes_atomic
from transcriptx.io.managed_import_workflow import StagingCleanupPolicy

INVENTORY_FILENAME = "demo_project.json"
JOURNAL_FILENAME = "demo_project.journal.json"
INVENTORY_SCHEMA = 1
DEMO_BUSY_LOCK = "demo_project.lock"


class DemoStatusKind(str, Enum):
    MISSING = "missing"
    INSTALLING = "installing"
    INSTALLED = "installed"
    STALE = "stale"
    PARTIAL = "partial"
    CORRUPT = "corrupt"
    BUSY = "busy"


@dataclass
class DemoStatus:
    kind: DemoStatusKind
    detail: str = ""
    inventory: dict[str, Any] | None = None


@dataclass
class DemoPlan:
    operation: Literal["install", "remove"]
    steps: list[str] = field(default_factory=list)
    pack_id: str | None = None
    pack_version: str | None = None


@dataclass
class DemoResult:
    ok: bool
    status: DemoStatusKind
    detail: str = ""
    errors: list[str] = field(default_factory=list)
    inventory: dict[str, Any] | None = None
    partial: bool = False


def inventory_path() -> Path:
    return Path(paths_mod.CONFIG_DIR) / INVENTORY_FILENAME


def journal_path() -> Path:
    return Path(paths_mod.CONFIG_DIR) / JOURNAL_FILENAME


def busy_lock_path() -> Path:
    return Path(paths_mod.PATHS.state_dir) / DEMO_BUSY_LOCK


def clear_demo_ui_caches() -> None:
    try:
        from transcriptx.web.cache_helpers import (
            clear_group_workspace_cache,
            clear_run_listing_caches,
            clear_transcript_listing_caches,
        )
    except Exception:
        return

    try:
        clear_transcript_listing_caches()
        clear_run_listing_caches()
        clear_group_workspace_cache()
    except Exception:
        return


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_inventory(payload: dict[str, Any]) -> None:
    target = inventory_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with locked_path(target):
        write_bytes_atomic(target, raw)


def _write_journal(payload: dict[str, Any]) -> None:
    target = journal_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with locked_path(target):
        write_bytes_atomic(target, raw)


def _acquire_demo_busy_lock() -> FileLock | None:
    """Non-blocking exclusive lock; lock file is ``demo_project.lock`` itself."""
    lock_path = busy_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    file_lock = FileLock(lock_path.with_suffix(""), timeout=1, blocking=False)
    file_lock.lock_file = lock_path
    if not file_lock.acquire():
        return None
    return file_lock


def status_demo_project(*, ignore_busy: bool = False) -> DemoStatus:
    if not ignore_busy and busy_lock_path().exists():
        return DemoStatus(DemoStatusKind.BUSY, "Demo install/remove in progress")
    inv = _read_json(inventory_path())
    journal = _read_json(journal_path())
    if journal and not inv:
        return DemoStatus(DemoStatusKind.PARTIAL, "Interrupted install/remove journal present")
    if inv is None:
        if inventory_path().exists():
            return DemoStatus(DemoStatusKind.CORRUPT, "Inventory unreadable")
        return DemoStatus(DemoStatusKind.MISSING, "Demo project not installed")
    if inv.get("schema_version") != INVENTORY_SCHEMA:
        return DemoStatus(DemoStatusKind.CORRUPT, "Unsupported inventory schema", inv)
    try:
        pack = load_and_validate_pack()
    except PackValidationError as exc:
        return DemoStatus(DemoStatusKind.CORRUPT, f"Pack invalid: {exc}", inv)
    if (
        inv.get("pack_hash") != pack.pack_hash
        or inv.get("schema_epoch") != CURRENT_SCHEMA_EPOCH
        or inv.get("pack_version") != pack.pack_version
    ):
        return DemoStatus(DemoStatusKind.STALE, "Demo pack or schema epoch mismatch", inv)
    if inv.get("data_root") != str(Path(paths_mod.PATHS.data_dir).resolve()):
        return DemoStatus(DemoStatusKind.CORRUPT, "Inventory bound to a different data root", inv)
    return DemoStatus(DemoStatusKind.INSTALLED, "Demo project installed", inv)


def plan_install() -> DemoPlan:
    pack = load_and_validate_pack()
    return DemoPlan(
        operation="install",
        pack_id=pack.pack_id,
        pack_version=pack.pack_version,
        steps=[
            "validate pack",
            "preflight collisions",
            "admit transcripts",
            "create owned demo group",
            "generate deterministic runs",
            "commit inventory",
        ],
    )


def plan_remove() -> DemoPlan:
    return DemoPlan(
        operation="remove",
        steps=[
            "load inventory",
            "delete owned runs (identity-verified)",
            "compare-and-delete index entries",
            "delete managed paths",
            "delete owned group",
            "clear inventory/journal",
        ],
    )


def _segments_identity(data: bytes) -> str:
    payload = json.loads(data.decode("utf-8"))
    segments = payload.get("segments")
    if not isinstance(segments, list):
        raise ValueError("segments missing")
    return compute_transcript_identity_hash(segments)


def _preflight_collisions(pack: DemoPack) -> list[str]:
    errors: list[str] = []
    index = load_index()
    slug_to_key = index.get("slug_to_key") or {}
    transcripts = index.get("transcripts") or {}
    known_identities = {
        str(k): v for k, v in transcripts.items() if isinstance(v, dict)
    }
    transcripts_dir = Path(paths_mod.PATHS.transcripts_dir)
    for tx in pack.transcripts:
        if tx.slug in slug_to_key:
            errors.append(f"Slug already registered: {tx.slug}")
        identity = _segments_identity(tx.bytes)
        if identity in known_identities:
            errors.append(f"Content identity already registered: {tx.slug}")
        managed = transcripts_dir / tx.basename
        if managed.exists():
            errors.append(f"Managed path already occupied: {managed}")
    # Same-members group conflict checked after admit (paths are real then).
    return errors


def _preflight_group_collision(members: list[str]) -> str | None:
    intended = [str(Path(m).resolve()) for m in members]
    store = GroupManifestStore()
    for existing in store.list_groups_best_effort()[0]:
        existing_members = [str(Path(m).resolve()) for m in existing.members]
        if existing_members == intended:
            return (
                f"A group with the same members already exists ({existing.group_id}); "
                "refusing unsafe reuse"
            )
    return None


def _create_owned_demo_group(name: str, description: str, members: list[str]) -> str:
    store = GroupManifestStore()
    group = store.create_group(name=name, members=members, description=description)
    return group.group_id


def _generate_demo_run(slug: str, run_id: str, transcript_path: Path, label: str) -> Path:
    """Write a minimal viewable synthetic run (no network / Ollama)."""
    run_root = Path(paths_mod.OUTPUTS_DIR) / slug / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    tx_meta = run_root / ".transcriptx"
    tx_meta.mkdir(exist_ok=True)
    (tx_meta / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_type": "run_manifest",
                "schema_version": 1,
                "transcript_path": str(transcript_path),
                "demo": True,
                "provenance_label": label,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    overview = {
        "title": "Demo example overview",
        "summary": "Synthetic/authored demo placeholder — not model output.",
        "demo": True,
        "provenance_label": label,
    }
    overview_name = "demo_overview.json"
    (run_root / overview_name).write_text(
        json.dumps(overview, indent=2) + "\n", encoding="utf-8"
    )
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_type": "artifact_manifest",
                "schema_version": 1,
                "demo": True,
                "provenance_label": label,
                "artifacts": [
                    {
                        "rel_path": overview_name,
                        "kind": "overview",
                        "module_id": "demo_placeholder",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_root / "run_results.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "demo": True,
                "modules": [],
                "base_install_modules": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return run_root


def install_demo_project() -> DemoResult:
    lock = _acquire_demo_busy_lock()
    if lock is None:
        return DemoResult(False, DemoStatusKind.BUSY, "Demo operation busy")

    try:
        try:
            pack = load_and_validate_pack()
        except PackValidationError as exc:
            return DemoResult(False, DemoStatusKind.CORRUPT, str(exc), errors=[str(exc)])

        existing = status_demo_project(ignore_busy=True)
        if existing.kind == DemoStatusKind.INSTALLED:
            return DemoResult(
                True,
                DemoStatusKind.INSTALLED,
                "Already installed",
                inventory=existing.inventory,
            )
        if existing.kind in {DemoStatusKind.PARTIAL, DemoStatusKind.CORRUPT}:
            return DemoResult(
                False,
                existing.kind,
                "Resolve partial/corrupt demo state (remove) before reinstall",
                inventory=existing.inventory,
            )

        collisions = _preflight_collisions(pack)
        if collisions:
            return DemoResult(
                False,
                DemoStatusKind.MISSING,
                "Collision preflight failed",
                errors=collisions,
            )

        journal = {
            "operation": "install",
            "started_at": _now(),
            "pack_id": pack.pack_id,
            "pack_version": pack.pack_version,
            "data_root": str(Path(paths_mod.PATHS.data_dir).resolve()),
            "steps_done": [],
        }
        _write_journal(journal)

        owned: list[dict[str, Any]] = []
        group_id = ""
        run_ids: list[dict[str, str]] = []
        with tempfile.TemporaryDirectory(prefix="tx_demo_") as tmp:
            tmp_path = Path(tmp)
            for tx in pack.transcripts:
                src = extract_transcript_to_temp(tx, tmp_path)
                outcome = admit_and_register(
                    src,
                    logical_basename=tx.basename,
                    staging_cleanup=StagingCleanupPolicy.NEVER,
                )
                if outcome.kind == AdmitOutcomeKind.ALREADY_MANAGED:
                    return DemoResult(
                        False,
                        DemoStatusKind.PARTIAL,
                        "Refusing to claim ALREADY_MANAGED artifact as demo-owned",
                        errors=[outcome.user_safe_detail],
                        partial=True,
                    )
                if outcome.transcript_path is None or outcome.slug is None:
                    return DemoResult(
                        False,
                        DemoStatusKind.PARTIAL,
                        f"Admit failed for {tx.slug}: {outcome.kind.value}",
                        errors=[outcome.user_safe_detail or ""],
                        partial=True,
                    )
                if outcome.slug != tx.slug:
                    return DemoResult(
                        False,
                        DemoStatusKind.PARTIAL,
                        f"Slug mismatch: expected {tx.slug}, got {outcome.slug}",
                        partial=True,
                    )
                identity = _segments_identity(tx.bytes)
                owned.append(
                    {
                        "slug": outcome.slug,
                        "identity": identity,
                        "managed_path": str(Path(outcome.transcript_path).resolve()),
                        "basename": tx.basename,
                        "content_sha256": tx.content_sha256,
                        "provenance_label": tx.provenance_label,
                    }
                )
                journal["steps_done"].append(f"admit:{tx.slug}")
                _write_journal(journal)

            members = [o["managed_path"] for o in owned]
            group_collision = _preflight_group_collision(members)
            if group_collision:
                return DemoResult(
                    False,
                    DemoStatusKind.PARTIAL,
                    group_collision,
                    errors=[group_collision],
                    partial=True,
                )
            group_id = _create_owned_demo_group(
                pack.group_name, pack.group_description, members
            )
            journal["steps_done"].append(f"group:{group_id}")
            journal["group_id"] = group_id
            _write_journal(journal)

            for o in owned:
                _generate_demo_run(
                    o["slug"],
                    pack.deterministic_run_id,
                    Path(o["managed_path"]),
                    o["provenance_label"],
                )
                run_ids.append({"slug": o["slug"], "run_id": pack.deterministic_run_id})
                journal["steps_done"].append(f"run:{o['slug']}")
                _write_journal(journal)

        inventory = {
            "schema_version": INVENTORY_SCHEMA,
            "status": "installed",
            "installed_at": _now(),
            "pack_id": pack.pack_id,
            "pack_version": pack.pack_version,
            "pack_hash": pack.pack_hash,
            "schema_epoch": CURRENT_SCHEMA_EPOCH,
            "data_root": str(Path(paths_mod.PATHS.data_dir).resolve()),
            "group": {
                "group_id": group_id,
                "ownership": "owned",
            },
            "transcripts": owned,
            "runs": run_ids,
            "base_install_modules": list(pack.base_install_modules),
        }
        _write_inventory(inventory)
        if journal_path().exists():
            journal_path().unlink()
        clear_demo_ui_caches()
        return DemoResult(
            True, DemoStatusKind.INSTALLED, "Demo project installed", inventory=inventory
        )
    finally:
        try:
            lock.release()
        except Exception:
            pass
        try:
            if busy_lock_path().exists():
                busy_lock_path().unlink()
        except OSError:
            pass


def _path_under_approved_root(path: Path, roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
        if resolved.is_symlink() or path.is_symlink():
            return False
        for root in roots:
            root_r = root.resolve()
            try:
                resolved.relative_to(root_r)
                return True
            except ValueError:
                continue
    except OSError:
        return False
    return False


def _bounded_delete(path: Path, roots: list[Path]) -> tuple[bool, str]:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return True, "already absent"
    except OSError as exc:
        return False, str(exc)
    if path.is_symlink() or (hasattr(st, "st_mode") and False):
        return False, "symlink rejected"
    if not _path_under_approved_root(path, roots):
        return False, "path escapes approved roots"
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as exc:
        return False, str(exc)
    return True, "deleted"


def compare_and_delete_slug(
    *,
    slug: str,
    identity: str,
    source_path: str,
) -> tuple[bool, str]:
    """Remove index entry only when slug + identity key + source path still match."""
    index_path = Path(INDEX_FILE)
    with FileLock(index_path, timeout=30):
        index = load_index()
        slug_to_key = index.setdefault("slug_to_key", {})
        transcripts = index.setdefault("transcripts", {})
        key = slug_to_key.get(slug)
        if key is None:
            return True, "slug absent"
        if key != identity:
            return False, "stale mapping: identity mismatch"
        entry = transcripts.get(key)
        if not isinstance(entry, dict):
            return False, "stale mapping: missing entry"
        if entry.get("slug") != slug:
            return False, "stale mapping: slug mismatch"
        entry_path = entry.get("source_path")
        if entry_path is None:
            return False, "stale mapping: missing source_path"
        try:
            if str(Path(entry_path).resolve()) != str(Path(source_path).resolve()):
                return False, "stale mapping: source path mismatch"
        except OSError:
            return False, "stale mapping: path resolve failed"
        slug_to_key.pop(slug, None)
        transcripts.pop(key, None)
        save_index(index)
        return True, "unregistered"


def remove_demo_project() -> DemoResult:
    lock = _acquire_demo_busy_lock()
    if lock is None:
        return DemoResult(False, DemoStatusKind.BUSY, "Demo operation busy")

    errors: list[str] = []
    try:
        inv = _read_json(inventory_path())
        if inv is None:
            return DemoResult(True, DemoStatusKind.MISSING, "Nothing to remove")
        if inv.get("data_root") != str(Path(paths_mod.PATHS.data_dir).resolve()):
            return DemoResult(
                False,
                DemoStatusKind.CORRUPT,
                "Wrong data root — refusing removal",
                inventory=inv,
            )

        _write_journal({"operation": "remove", "started_at": _now(), "inventory": inv})
        roots = [
            Path(paths_mod.PATHS.transcripts_dir),
            Path(paths_mod.PATHS.transcripts_metadata_dir),
            Path(paths_mod.OUTPUTS_DIR),
            Path(paths_mod.PATHS.data_dir) / "groups",
        ]
        # Delete runs attached to owned demo transcript identities.
        for run in inv.get("runs") or []:
            slug = run.get("slug")
            run_id = run.get("run_id")
            if not slug or not run_id:
                continue
            run_dir = Path(paths_mod.OUTPUTS_DIR) / slug / run_id
            ok, msg = _bounded_delete(run_dir, roots)
            if not ok:
                errors.append(f"run {slug}/{run_id}: {msg}")
            # Also remove other runs under owned slug dirs after identity check.
            slug_dir = Path(paths_mod.OUTPUTS_DIR) / slug
            if slug_dir.is_dir():
                for child in list(slug_dir.iterdir()):
                    if child.name.startswith("."):
                        continue
                    ok, msg = _bounded_delete(child, roots)
                    if not ok:
                        errors.append(f"run-extra {child}: {msg}")
                ok, msg = _bounded_delete(slug_dir, roots)
                if not ok:
                    errors.append(f"slug-dir {slug}: {msg}")

        for tx in inv.get("transcripts") or []:
            slug = tx.get("slug")
            identity = tx.get("identity")
            managed = tx.get("managed_path")
            if slug and identity and managed:
                ok, msg = compare_and_delete_slug(
                    slug=slug, identity=identity, source_path=managed
                )
                if not ok:
                    errors.append(f"index {slug}: {msg}")
            if managed:
                ok, msg = _bounded_delete(Path(managed), roots)
                if not ok:
                    errors.append(f"managed {managed}: {msg}")
                stem = Path(managed).stem
                meta_root = Path(paths_mod.PATHS.transcripts_metadata_dir)
                for kind in ("imports", "originals", "readable"):
                    meta = meta_root / kind
                    if not meta.exists():
                        continue
                    for candidate in meta.rglob(f"{stem}*"):
                        ok, msg = _bounded_delete(candidate, roots)
                        if not ok and "already absent" not in msg:
                            errors.append(f"meta {candidate}: {msg}")

        group = inv.get("group") or {}
        if group.get("ownership") == "owned" and group.get("group_id"):
            store = GroupManifestStore()
            try:
                store.delete(str(group["group_id"]))
            except Exception as exc:
                errors.append(f"group delete: {exc}")

        if inventory_path().exists():
            inventory_path().unlink()
        if journal_path().exists():
            journal_path().unlink()
        clear_demo_ui_caches()
        if errors:
            return DemoResult(
                False,
                DemoStatusKind.PARTIAL,
                "Removal completed with partial errors",
                errors=errors,
                partial=True,
            )
        return DemoResult(True, DemoStatusKind.MISSING, "Demo project removed")
    finally:
        try:
            lock.release()
        except Exception:
            pass
        try:
            if busy_lock_path().exists():
                busy_lock_path().unlink()
        except OSError:
            pass