"""Full-workspace backup / restore (ZIP + role-root layout)."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from transcriptx import __version__
from transcriptx.app.models.errors import BackupError
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.paths import PATHS, PathSettings
from transcriptx.io.atomic_json import strict_json_dumps

MANIFEST_NAME = "transcriptx.workspace-backup.json"
FORMAT = "transcriptx.workspace-backup"
SCHEMA_VERSION = 1
ROLE_TOP_LEVEL = frozenset(
    {"transcripts", "config", "data", "wav_backup", "recordings", "outputs"}
)
EXCLUDE_DIR_NAMES = frozenset({".cache", ".staging", "thumbs", "__pycache__"})
# Ephemeral staging under library roots — never pack.
EXCLUDE_REL_PREFIXES = frozenset({"imports", "imports/"})
DURABLE_DATA_SUBDIRS = ("groups", "corrections", "state", "watcher")
MIN_FREE_DISK_BYTES = 256 * 1024 * 1024
_HASH_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class BackupOptions:
    include_recordings: bool = False
    include_outputs: bool = False


@dataclass
class BackupResult:
    archive_path: Path
    manifest: dict[str, Any]
    file_count: int
    uncompressed_bytes: int
    transcript_count: int


@dataclass
class VerifyResult:
    ok: bool
    manifest: dict[str, Any]
    messages: list[str] = field(default_factory=list)


@dataclass
class IntegritySummary:
    """Lightweight post-restore integrity note (speaker profiles when present)."""

    ok: bool
    messages: list[str] = field(default_factory=list)


@dataclass
class RestoreResult:
    ok: bool
    safety_archive: Path | None
    verify: VerifyResult
    integrity: IntegritySummary | None
    messages: list[str] = field(default_factory=list)
    dry_run: bool = False


def default_backup_dest(paths: PathSettings, *, stamp: str | None = None) -> Path:
    when = stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return (
        paths.data_dir / "backups" / "workspace" / f"transcriptx-workspace-{when}.zip"
    )


def default_safety_dest(paths: PathSettings, *, stamp: str | None = None) -> Path:
    when = stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return paths.data_dir / "backups" / "workspace" / f"pre-restore-{when}.zip"


def workspace_backups_dir(paths: PathSettings) -> Path:
    return paths.data_dir / "backups" / "workspace"


def require_workspace_backup_manifest(payload: Any) -> dict[str, Any]:
    """Validate envelope fields for a workspace-backup manifest."""
    if not isinstance(payload, dict):
        raise BackupError("manifest must be a JSON object")
    if payload.get("format") != FORMAT:
        raise BackupError(
            f"unexpected format {payload.get('format')!r}; expected {FORMAT!r}"
        )
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise BackupError(
            f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}"
        )
    return payload


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _sha256_zip_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with zf.open(info, "r") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _free_disk_bytes(path: Path) -> int:
    probe = path if path.exists() else path.parent
    probe.mkdir(parents=True, exist_ok=True)
    return int(shutil.disk_usage(probe).free)


def _ensure_disk_budget(root: Path, *, additional: int = 0) -> None:
    free = _free_disk_bytes(root)
    if free - additional < MIN_FREE_DISK_BYTES:
        raise BackupError(
            f"insufficient free disk space ({free} bytes free; "
            f"need at least {MIN_FREE_DISK_BYTES} bytes headroom"
            + (f" plus {additional} bytes estimated" if additional else "")
            + ")"
        )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


class WorkspaceBackupService:
    """Create, verify, and replace-restore full-workspace ZIP archives."""

    def create_backup(
        self,
        paths: PathSettings,
        dest: Path,
        options: BackupOptions | None = None,
        *,
        force: bool = False,
    ) -> BackupResult:
        options = options or BackupOptions()
        dest = Path(dest)
        self._refuse_busy(paths)

        if dest.suffix.lower() != ".zip":
            raise BackupError("backup destination must be a .zip path")
        if dest.exists() and not force:
            raise BackupError(
                f"backup destination already exists: {dest} "
                "(pass force=True / --force to overwrite)"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".partial")
        if partial.exists():
            partial.unlink()

        skip_paths = {dest.resolve(), partial.resolve()}
        # Never nest default workspace backup archives into a new archive.
        workspace_backup_root = workspace_backups_dir(paths)
        if workspace_backup_root.is_dir():
            try:
                skip_paths.add(workspace_backup_root.resolve())
            except OSError:
                pass

        entries: list[tuple[str, Path]] = []
        includes = {
            "transcripts": True,
            "config": True,
            "durable_data": True,
            "wav_backup": False,
            "recordings": bool(options.include_recordings),
            "outputs": bool(options.include_outputs),
        }

        if paths.transcripts_dir.is_dir():
            entries.extend(
                self._collect_tree(
                    paths.transcripts_dir,
                    prefix="transcripts",
                    skip_paths=skip_paths,
                    skip_rel_prefixes=EXCLUDE_REL_PREFIXES,
                )
            )

        if paths.config_dir.is_dir():
            entries.extend(
                self._collect_tree(
                    paths.config_dir, prefix="config", skip_paths=skip_paths
                )
            )

        for sub in DURABLE_DATA_SUBDIRS:
            root = paths.data_dir / sub
            if root.is_dir():
                entries.extend(
                    self._collect_tree(
                        root, prefix=f"data/{sub}", skip_paths=skip_paths
                    )
                )

        profiles_root = paths.speaker_profiles_dir
        if profiles_root.is_dir():
            entries.extend(
                self._collect_tree(
                    profiles_root,
                    prefix="data/speaker_profiles",
                    skip_paths=skip_paths,
                )
            )

        if paths.wav_backup_dir.is_dir():
            wav_entries = self._collect_tree(
                paths.wav_backup_dir, prefix="wav_backup", skip_paths=skip_paths
            )
            if wav_entries:
                includes["wav_backup"] = True
                entries.extend(wav_entries)

        if options.include_recordings and paths.recordings_dir.is_dir():
            entries.extend(
                self._collect_tree(
                    paths.recordings_dir,
                    prefix="recordings",
                    skip_paths=skip_paths,
                    skip_rel_prefixes=EXCLUDE_REL_PREFIXES,
                )
            )

        if options.include_outputs and paths.outputs_dir.is_dir():
            entries.extend(
                self._collect_tree(
                    paths.outputs_dir, prefix="outputs", skip_paths=skip_paths
                )
            )

        entries.sort(key=lambda item: item[0])
        uncompressed = 0
        for _member, src in entries:
            try:
                uncompressed += src.stat().st_size
            except OSError:
                pass
        _ensure_disk_budget(dest.parent, additional=uncompressed)

        index_lines: list[str] = []
        packed_bytes = 0
        transcript_count = self._count_transcripts(paths.transcripts_dir)
        try:
            with zipfile.ZipFile(
                partial,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True,
            ) as zf:
                for member, src in entries:
                    self._assert_safe_member(member)
                    digest, size = _sha256_file(src)
                    index_lines.append(f"{member}\t{size}\t{digest}")
                    packed_bytes += size
                    zf.write(src, arcname=member)

                manifest = {
                    "format": FORMAT,
                    "schema_version": SCHEMA_VERSION,
                    "created_at": datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "transcriptx_version": __version__,
                    "includes": includes,
                    "counts": {
                        "transcripts": transcript_count,
                        "files": len(entries),
                        "uncompressed_bytes": packed_bytes,
                    },
                    "file_index_sha256": hashlib.sha256(
                        ("\n".join(index_lines) + ("\n" if index_lines else "")).encode(
                            "utf-8"
                        )
                    ).hexdigest(),
                    "roots_note": {
                        "roles": [
                            "transcripts",
                            "config",
                            "data/groups",
                            "data/speaker_profiles",
                            "data/corrections",
                            "data/state",
                            "data/watcher",
                            "wav_backup",
                        ],
                    },
                }
                require_workspace_backup_manifest(manifest)
                zf.writestr(MANIFEST_NAME, strict_json_dumps(manifest, indent=2))
        except BackupError:
            if partial.exists():
                partial.unlink(missing_ok=True)
            raise
        except Exception:
            if partial.exists():
                partial.unlink(missing_ok=True)
            raise

        partial.replace(dest)
        return BackupResult(
            archive_path=dest,
            manifest=manifest,
            file_count=len(entries),
            uncompressed_bytes=packed_bytes,
            transcript_count=transcript_count,
        )

    def verify_backup(self, archive: Path) -> VerifyResult:
        archive = Path(archive)
        messages: list[str] = []
        if not archive.is_file():
            raise BackupError(f"archive not found: {archive}")
        try:
            with zipfile.ZipFile(archive, mode="r") as zf:
                names = zf.namelist()
                if MANIFEST_NAME not in names:
                    raise BackupError(f"missing {MANIFEST_NAME}")
                raw = zf.read(MANIFEST_NAME)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise BackupError(f"manifest is not valid JSON: {exc}") from exc
                manifest = require_workspace_backup_manifest(payload)

                index_lines: list[str] = []
                has_transcripts = False
                has_config = False
                has_durable = False
                for info in zf.infolist():
                    name = info.filename
                    if name.endswith("/"):
                        continue
                    self._assert_safe_member(name)
                    if name == MANIFEST_NAME:
                        continue
                    top = name.split("/", 1)[0]
                    if top not in ROLE_TOP_LEVEL:
                        raise BackupError(f"unexpected top-level member: {name!r}")
                    if name.startswith("transcripts/"):
                        has_transcripts = True
                    if name.startswith("config/"):
                        has_config = True
                    if name.startswith("data/"):
                        has_durable = True
                    digest, size = _sha256_zip_member(zf, info)
                    index_lines.append(f"{name}\t{size}\t{digest}")

                index_lines.sort()
                digest = hashlib.sha256(
                    ("\n".join(index_lines) + ("\n" if index_lines else "")).encode(
                        "utf-8"
                    )
                ).hexdigest()
                expected = manifest.get("file_index_sha256")
                if digest != expected:
                    raise BackupError(
                        "file_index_sha256 mismatch "
                        f"(archive={digest[:12]}… manifest={str(expected)[:12]}…)"
                    )

                includes = manifest.get("includes") or {}
                if includes.get("transcripts") and not has_transcripts:
                    messages.append(
                        "transcripts included but no transcript files packed (empty ok)"
                    )
                if includes.get("config") and not has_config:
                    messages.append(
                        "config included but no config files packed (empty ok)"
                    )
                if includes.get("durable_data") and not has_durable:
                    messages.append(
                        "durable_data included but no data files packed (empty ok)"
                    )

                return VerifyResult(ok=True, manifest=manifest, messages=messages)
        except zipfile.BadZipFile as exc:
            raise BackupError(f"not a valid zip archive: {exc}") from exc

    def restore_backup(
        self,
        paths: PathSettings,
        archive: Path,
        *,
        safety: bool = True,
        dry_run: bool = False,
        safety_options: BackupOptions | None = None,
    ) -> RestoreResult:
        archive = Path(archive)
        verify = self.verify_backup(archive)
        self._refuse_busy(paths)
        self._refuse_archive_under_replace_roots(paths, archive, verify.manifest)

        includes = verify.manifest.get("includes") or {}
        messages = list(verify.messages)
        counts = verify.manifest.get("counts") or {}
        replace_bits = ["transcripts", "config", "durable data"]
        if includes.get("wav_backup"):
            replace_bits.append("wav_backup")
        if includes.get("recordings"):
            replace_bits.append("recordings")
        if includes.get("outputs"):
            replace_bits.append("outputs")
        messages.append("restore will replace: " + ", ".join(replace_bits))
        messages.append(
            f"mapped onto transcripts={paths.transcripts_dir} "
            f"config={paths.config_dir} data={paths.data_dir} "
            f"speaker_profiles={paths.speaker_profiles_dir}"
            + (
                f" recordings={paths.recordings_dir}"
                if includes.get("recordings")
                else ""
            )
            + (f" outputs={paths.outputs_dir}" if includes.get("outputs") else "")
        )
        messages.append(
            "archive counts: "
            f"transcripts={counts.get('transcripts')} files={counts.get('files')} "
            f"uncompressed_bytes={counts.get('uncompressed_bytes')}"
        )

        if dry_run:
            return RestoreResult(
                ok=True,
                safety_archive=None,
                verify=verify,
                integrity=None,
                messages=messages + ["dry_run: no changes written"],
                dry_run=True,
            )

        uncompressed = int(counts.get("uncompressed_bytes") or 0)
        safety_estimate = 0
        if safety:
            safety_estimate = self._estimate_workspace_bytes(paths, BackupOptions())
        _ensure_disk_budget(
            workspace_backups_dir(paths) if safety else paths.data_dir,
            additional=uncompressed + safety_estimate,
        )

        safety_archive: Path | None = None
        if safety:
            safety_dest = default_safety_dest(paths)
            safety_archive = self.create_backup(
                paths,
                safety_dest,
                safety_options or BackupOptions(),
                force=True,
            ).archive_path
            messages.append(f"safety backup written to {safety_archive}")

        try:
            with zipfile.ZipFile(archive, mode="r") as zf:
                members = [
                    info
                    for info in zf.infolist()
                    if not info.filename.endswith("/")
                    and info.filename != MANIFEST_NAME
                ]
                for info in members:
                    self._assert_safe_member(info.filename)

                self._clear_directory_children(paths.transcripts_dir)
                paths.transcripts_dir.mkdir(parents=True, exist_ok=True)
                self._extract_prefix(zf, members, "transcripts/", paths.transcripts_dir)

                self._replace_tree_from_zip(zf, members, "config/", paths.config_dir)

                for sub in DURABLE_DATA_SUBDIRS:
                    prefix = f"data/{sub}/"
                    if any(info.filename.startswith(prefix) for info in members):
                        self._replace_tree_from_zip(
                            zf, members, prefix, paths.data_dir / sub
                        )

                profiles_prefix = "data/speaker_profiles/"
                if any(info.filename.startswith(profiles_prefix) for info in members):
                    self._replace_tree_from_zip(
                        zf, members, profiles_prefix, paths.speaker_profiles_dir
                    )

                if includes.get("wav_backup") or any(
                    info.filename.startswith("wav_backup/") for info in members
                ):
                    self._replace_tree_from_zip(
                        zf, members, "wav_backup/", paths.wav_backup_dir
                    )

                if includes.get("recordings"):
                    self._replace_tree_from_zip(
                        zf, members, "recordings/", paths.recordings_dir
                    )
                if includes.get("outputs"):
                    preserve: set[str] = set()
                    # If outputs somehow nests the workspace backup dir, keep it.
                    try:
                        wb = workspace_backups_dir(paths).resolve()
                        out = paths.outputs_dir.resolve()
                        rel = wb.relative_to(out)
                        preserve.add(rel.parts[0] if rel.parts else "backups")
                    except (ValueError, OSError):
                        pass
                    self._replace_tree_from_zip(
                        zf,
                        members,
                        "outputs/",
                        paths.outputs_dir,
                        preserve_relative=preserve or None,
                    )
        except BackupError:
            raise
        except Exception as exc:
            hint = ""
            if safety_archive is not None:
                hint = f" Safety archive at {safety_archive}."
            raise BackupError(
                f"restore failed after workspace changes began: {exc}.{hint}"
            ) from exc

        cache_dir = paths.data_dir / "cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            messages.append("removed data/cache (rebuildable caches)")

        integrity = self._post_restore_integrity(paths)
        messages.extend(integrity.messages)

        return RestoreResult(
            ok=integrity.ok,
            safety_archive=safety_archive,
            verify=verify,
            integrity=integrity,
            messages=messages,
            dry_run=False,
        )

    def _post_restore_integrity(self, paths: PathSettings) -> IntegritySummary:
        messages: list[str] = []
        profiles = paths.speaker_profiles_dir
        if not profiles.is_dir():
            messages.append("speaker profiles tree absent after restore (ok if unused)")
            return IntegritySummary(ok=True, messages=messages)
        try:
            from transcriptx.core.speaker_profiles.integrity import run_integrity_scan

            report = run_integrity_scan(profiles)
            if report.ok:
                messages.append("speaker profiles integrity ok after restore")
                return IntegritySummary(ok=True, messages=messages)
            messages.append(
                "speaker profiles integrity reported issues after restore "
                f"(ok={report.ok}, corrupt_profiles={len(report.corrupt_profiles)}, "
                f"blocking_operations={len(report.blocking_operations)})"
            )
            return IntegritySummary(ok=False, messages=messages)
        except Exception as exc:  # noqa: BLE001 — surface soft failure
            messages.append(f"speaker profiles integrity scan failed: {exc}")
            return IntegritySummary(ok=False, messages=messages)

    def _refuse_busy(self, paths: PathSettings) -> None:
        # Speaker profiles project lock (sentinel beside speaker_profiles.lock).
        lock_path = paths.speaker_profiles_lock_file
        sentinel = lock_path.with_suffix(".lock.target")
        if sentinel.exists():
            probe = FileLock(sentinel, timeout=0, blocking=False)
            if not probe.acquire():
                raise BackupError(
                    "speaker profiles lock is held; finish profile/voice work first"
                )
            probe.release()

        rename_lock = paths.state_dir / "managed_rename.lock"
        if rename_lock.exists():
            # FileLock appends .lock to the target; use the lock file itself as sentinel.
            probe = FileLock(rename_lock, timeout=0, blocking=False)
            if not probe.acquire():
                raise BackupError(
                    "managed rename lock is held; finish rename/repair work first"
                )
            probe.release()

    def _refuse_archive_under_replace_roots(
        self,
        paths: PathSettings,
        archive: Path,
        manifest: dict[str, Any],
    ) -> None:
        try:
            resolved = archive.resolve()
        except OSError as exc:
            raise BackupError(f"cannot resolve archive path: {archive}: {exc}") from exc

        backups_root = workspace_backups_dir(paths)
        if backups_root.exists() and _is_relative_to(resolved, backups_root):
            return

        includes = manifest.get("includes") or {}
        blocked: list[tuple[str, Path]] = [
            ("transcripts", paths.transcripts_dir),
            ("config", paths.config_dir),
            ("data/groups", paths.data_dir / "groups"),
            ("data/corrections", paths.data_dir / "corrections"),
            ("data/state", paths.state_dir),
            ("data/watcher", paths.data_dir / "watcher"),
            ("data/speaker_profiles", paths.speaker_profiles_dir),
            ("wav_backup", paths.wav_backup_dir),
        ]
        if includes.get("recordings"):
            blocked.append(("recordings", paths.recordings_dir))
        if includes.get("outputs"):
            blocked.append(("outputs", paths.outputs_dir))

        for label, root in blocked:
            if root.exists() and _is_relative_to(resolved, root):
                raise BackupError(
                    f"archive path sits under replace root {label} ({root}); "
                    "move the ZIP outside the workspace trees being replaced "
                    f"({backups_root} is safe)"
                )

    def _estimate_workspace_bytes(
        self,
        paths: PathSettings,
        options: BackupOptions,
    ) -> int:
        total = 0
        skip_paths: set[Path] = set()
        roots: list[tuple[Path, str, frozenset[str] | None]] = [
            (paths.transcripts_dir, "transcripts", EXCLUDE_REL_PREFIXES),
            (paths.config_dir, "config", None),
        ]
        for sub in DURABLE_DATA_SUBDIRS:
            roots.append((paths.data_dir / sub, f"data/{sub}", None))
        roots.append((paths.speaker_profiles_dir, "data/speaker_profiles", None))
        roots.append((paths.wav_backup_dir, "wav_backup", None))
        if options.include_recordings:
            roots.append((paths.recordings_dir, "recordings", EXCLUDE_REL_PREFIXES))
        if options.include_outputs:
            roots.append((paths.outputs_dir, "outputs", None))
        for root, prefix, skip_rel in roots:
            if not root.is_dir():
                continue
            for _member, src in self._collect_tree(
                root,
                prefix=prefix,
                skip_paths=skip_paths,
                skip_rel_prefixes=skip_rel,
            ):
                try:
                    total += src.stat().st_size
                except OSError:
                    continue
        return total

    def _collect_tree(
        self,
        root: Path,
        *,
        prefix: str,
        skip_paths: set[Path],
        skip_rel_prefixes: frozenset[str] | None = None,
    ) -> list[tuple[str, Path]]:
        out: list[tuple[str, Path]] = []
        try:
            root = root.resolve()
        except OSError:
            return out
        skip_resolved: set[Path] = set()
        for sp in skip_paths:
            try:
                skip_resolved.add(sp.resolve())
            except OSError:
                skip_resolved.add(sp)

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            # Skip files under any skipped directory (e.g. workspace backups dir).
            if any(
                _is_relative_to(resolved, sp) for sp in skip_resolved if sp.is_dir()
            ):
                continue
            if resolved in skip_resolved:
                continue
            if path.name.endswith(".partial"):
                continue
            rel = path.relative_to(root).as_posix()
            if skip_rel_prefixes and (
                rel in skip_rel_prefixes
                or any(
                    rel == p.rstrip("/")
                    or rel.startswith(p if p.endswith("/") else p + "/")
                    for p in skip_rel_prefixes
                )
            ):
                continue
            parts = Path(rel).parts
            if any(part in EXCLUDE_DIR_NAMES for part in parts):
                continue
            if path.name.endswith(".lock") or path.suffix == ".lock":
                continue
            if path.name.startswith(".") and path.name.endswith(".lock"):
                continue
            if path.name.endswith(".lock.target"):
                continue
            member = f"{prefix}/{rel}" if prefix else rel
            self._assert_safe_member(member)
            out.append((member, path))
        return out

    @staticmethod
    def _assert_safe_member(name: str) -> None:
        if not name or name.startswith("/") or name.startswith("\\"):
            raise BackupError(f"unsafe zip member path: {name!r}")
        if "\\" in name:
            raise BackupError(f"unsafe zip member path: {name!r}")
        parts = name.split("/")
        if ".." in parts:
            raise BackupError(f"zip-slip member rejected: {name!r}")
        if name != MANIFEST_NAME and parts[0] not in ROLE_TOP_LEVEL:
            raise BackupError(f"unexpected top-level member: {name!r}")

    @staticmethod
    def _count_transcripts(transcripts_root: Path) -> int:
        if not transcripts_root.is_dir():
            return 0
        skip = {"imports", "metadata", "originals", "readable"}
        count = 0
        for path in transcripts_root.rglob("*.json"):
            if not path.is_file():
                continue
            try:
                rel_parts = path.relative_to(transcripts_root).parts
            except ValueError:
                continue
            if rel_parts and rel_parts[0] in skip:
                continue
            count += 1
        return count

    @staticmethod
    def _clear_directory_children(directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for child in directory.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def _replace_tree_from_zip(
        self,
        zf: zipfile.ZipFile,
        members: Iterable[zipfile.ZipInfo],
        prefix: str,
        dest_root: Path,
        *,
        preserve_relative: set[str] | None = None,
    ) -> None:
        preserve_relative = preserve_relative or set()
        preserved: dict[str, Path] = {}
        dest_root.mkdir(parents=True, exist_ok=True)
        if preserve_relative:
            for name in list(preserve_relative):
                src = dest_root / name
                if src.exists():
                    tmp = dest_root / f".preserve-{name}"
                    if tmp.exists():
                        if tmp.is_dir():
                            shutil.rmtree(tmp)
                        else:
                            tmp.unlink()
                    src.rename(tmp)
                    preserved[name] = tmp

        for child in list(dest_root.iterdir()):
            if child.name.startswith(".preserve-"):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        self._extract_prefix(zf, members, prefix, dest_root)

        for name, tmp in preserved.items():
            target = dest_root / name
            if target.exists():
                if tmp.is_dir():
                    shutil.rmtree(tmp)
                else:
                    tmp.unlink()
            else:
                tmp.rename(target)

    @staticmethod
    def _extract_prefix(
        zf: zipfile.ZipFile,
        members: Iterable[zipfile.ZipInfo],
        prefix: str,
        dest_root: Path,
    ) -> None:
        dest_root = dest_root.resolve()
        for info in members:
            name = info.filename
            if not name.startswith(prefix):
                continue
            rel = name[len(prefix) :]
            if not rel:
                continue
            target = (dest_root / rel).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise BackupError(f"zip-slip extract rejected: {name!r}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as dest:
                shutil.copyfileobj(src, dest, length=_HASH_CHUNK)


def get_default_paths() -> PathSettings:
    """Return the process-global PathSettings (env-resolved)."""
    return PATHS
