"""Load and validate the bundled demo pack via importlib.resources."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from transcriptx.core.utils.schema_epoch import CURRENT_SCHEMA_EPOCH

PACK_PACKAGE = "transcriptx.demo.pack"
MANIFEST_NAME = "manifest.json"
PROVENANCE_NAME = "PROVENANCE.md"


@dataclass(frozen=True)
class PackTranscript:
    basename: str
    slug: str
    content_sha256: str
    title: str
    provenance_label: str
    bytes: bytes


@dataclass(frozen=True)
class DemoPack:
    pack_id: str
    pack_version: str
    required_schema_epoch: int
    base_install_modules: tuple[str, ...]
    deterministic_run_id: str
    group_name: str
    group_description: str
    member_slugs: tuple[str, ...]
    transcripts: tuple[PackTranscript, ...]
    provenance_text: str
    pack_hash: str


class PackValidationError(ValueError):
    pass


def _pack_root():
    return resources.files(PACK_PACKAGE)


def load_and_validate_pack() -> DemoPack:
    root = _pack_root()
    try:
        manifest_raw = root.joinpath(MANIFEST_NAME).read_bytes()
        provenance = root.joinpath(PROVENANCE_NAME).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, AttributeError) as exc:
        raise PackValidationError(f"Demo pack resources missing: {exc}") from exc

    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackValidationError(f"Invalid demo pack manifest JSON: {exc}") from exc

    if not isinstance(manifest, dict):
        raise PackValidationError("Demo pack manifest must be an object")
    if manifest.get("schema_version") != 1:
        raise PackValidationError(
            f"Unsupported demo pack manifest schema_version={manifest.get('schema_version')!r}"
        )

    pack_id = manifest.get("pack_id")
    pack_version = manifest.get("pack_version")
    epoch = manifest.get("required_schema_epoch")
    if not isinstance(pack_id, str) or not pack_id:
        raise PackValidationError("pack_id required")
    if not isinstance(pack_version, str) or not pack_version:
        raise PackValidationError("pack_version required")
    if epoch != CURRENT_SCHEMA_EPOCH:
        raise PackValidationError(
            f"Pack requires schema epoch {epoch!r}; runtime epoch is {CURRENT_SCHEMA_EPOCH}"
        )
    if not provenance.strip():
        raise PackValidationError("PROVENANCE.md is empty")

    group = manifest.get("group")
    if not isinstance(group, dict):
        raise PackValidationError("group definition required")
    member_slugs = group.get("member_slugs")
    if not isinstance(member_slugs, list) or not member_slugs:
        raise PackValidationError("group.member_slugs required")

    raw_txs = manifest.get("transcripts")
    if not isinstance(raw_txs, list) or not raw_txs:
        raise PackValidationError("transcripts list required")

    seen_basenames: set[str] = set()
    seen_slugs: set[str] = set()
    loaded: list[PackTranscript] = []
    for item in raw_txs:
        if not isinstance(item, dict):
            raise PackValidationError("transcript entry must be an object")
        basename = item.get("basename")
        slug = item.get("slug")
        expected_hash = item.get("content_sha256")
        title = item.get("title") or slug
        label = item.get("provenance_label") or "synthetic/authored"
        if not isinstance(basename, str) or not basename.endswith(".json"):
            raise PackValidationError(f"Invalid basename: {basename!r}")
        if not isinstance(slug, str) or not slug.startswith("demo__"):
            raise PackValidationError(f"Demo slug must use demo__ prefix: {slug!r}")
        if basename in seen_basenames or slug in seen_slugs:
            raise PackValidationError(f"Duplicate basename/slug: {basename}/{slug}")
        seen_basenames.add(basename)
        seen_slugs.add(slug)
        try:
            data = root.joinpath("transcripts", basename).read_bytes()
        except (FileNotFoundError, OSError) as exc:
            raise PackValidationError(f"Missing transcript {basename}: {exc}") from exc
        digest = hashlib.sha256(data).hexdigest()
        if expected_hash and digest != expected_hash:
            raise PackValidationError(
                f"Hash mismatch for {basename}: expected {expected_hash}, got {digest}"
            )
        loaded.append(
            PackTranscript(
                basename=basename,
                slug=slug,
                content_sha256=digest,
                title=str(title),
                provenance_label=str(label),
                bytes=data,
            )
        )

    for slug in member_slugs:
        if slug not in seen_slugs:
            raise PackValidationError(f"Group references unknown slug {slug!r}")

    modules = manifest.get("base_install_modules") or []
    if not isinstance(modules, list):
        raise PackValidationError("base_install_modules must be a list")
    run_id = manifest.get("deterministic_run_id") or "demo_base_install_v1"
    pack_hash = hashlib.sha256(
        manifest_raw + provenance.encode("utf-8") + b"".join(t.bytes for t in loaded)
    ).hexdigest()

    return DemoPack(
        pack_id=pack_id,
        pack_version=pack_version,
        required_schema_epoch=int(epoch),
        base_install_modules=tuple(str(m) for m in modules),
        deterministic_run_id=str(run_id),
        group_name=str(group.get("name") or "Demo examples"),
        group_description=str(group.get("description") or ""),
        member_slugs=tuple(str(s) for s in member_slugs),
        transcripts=tuple(loaded),
        provenance_text=provenance,
        pack_hash=pack_hash,
    )


def extract_transcript_to_temp(tx: PackTranscript, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / tx.basename
    path.write_bytes(tx.bytes)
    return path
