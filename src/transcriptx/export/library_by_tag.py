"""Resolve Library multi-transcript export items by artifact kind.

Packages selectable kinds from each matching row's latest analysis run into a
flat ZIP layout ``{slug_or_stem}/{filename}``. No HTML/EPUB index for this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from transcriptx.app.corpus_inventory.models import InventoryRow

LIBRARY_EXPORT_KIND_IDS: tuple[str, ...] = (
    "readable_txt",
    "readable_csv",
    "readable_srt",
    "readable_vtt",
    "transcript_json",
    "summaries",
    "charts_static",
    "data",
)

_READABLE_SUFFIX: dict[str, str] = {
    "readable_txt": ".txt",
    "readable_csv": ".csv",
    "readable_srt": ".srt",
    "readable_vtt": ".vtt",
}

_SUMMARY_MODULES = frozenset(
    {
        "summary",
        "llm_summary",
        "narrative_summary",
        "llm_action_items",
        "llm_speaker_summary",
    }
)

_SUMMARY_NAME_MARKERS = (
    "_llm_summary.",
    "_narrative_summary.",
    "_llm_speaker_summary.",
    "_llm_action_items.",
    "_summary.",
)


@dataclass(frozen=True)
class LibraryExportItem:
    """One file to copy into a library-by-tag ZIP."""

    src: Path
    dest_rel: Path
    kind: str
    transcript_slug: str


@dataclass(frozen=True)
class ResolveResult:
    """Resolved copy list plus skip/include counters for the Library UI preview."""

    items: tuple[LibraryExportItem, ...]
    matching_rows: int
    included_rows: int
    skipped_rows: int
    estimated_bytes: int


def _row_slug(row: InventoryRow) -> str:
    return row.slug or row.transcript_path.stem


def _is_summary_artifact(artifact: object) -> bool:
    module = (getattr(artifact, "module", None) or "").strip()
    if module in _SUMMARY_MODULES:
        return True
    rel_path = str(getattr(artifact, "rel_path", "") or "")
    name = Path(rel_path).name.lower()
    rel = rel_path.replace("\\", "/").lower()
    if any(marker in name for marker in _SUMMARY_NAME_MARKERS):
        return True
    return "/summary" in rel or rel.startswith("summary/")


def _artifact_matches_kind(artifact: object, kind: str) -> bool:
    art_kind = str(getattr(artifact, "kind", "") or "")
    rel_path = str(getattr(artifact, "rel_path", "") or "")
    if kind in _READABLE_SUFFIX:
        if art_kind != "transcript":
            return False
        return Path(rel_path).suffix.lower() == _READABLE_SUFFIX[kind]
    if kind == "summaries":
        return _is_summary_artifact(artifact)
    if kind == "charts_static":
        return art_kind == "chart_static"
    if kind == "data":
        return art_kind.startswith("data")
    return False


def _disambiguate_dest(
    slug: str,
    filename: str,
    used: set[str],
    *,
    short_id: str | None = None,
) -> Path:
    base = f"{slug}/{filename}"
    if base not in used:
        used.add(base)
        return Path(slug) / filename
    prefix = (short_id or "x")[:8]
    candidate = f"{slug}/{prefix}_{filename}"
    n = 1
    while candidate in used:
        n += 1
        candidate = f"{slug}/{prefix}_{n}_{filename}"
    used.add(candidate)
    return Path(candidate)


def resolve_library_export_items(
    rows: Sequence[InventoryRow],
    kinds: Sequence[str],
    *,
    outputs_dir: Path | None = None,
) -> ResolveResult:
    """Collect export files for ``kinds`` from each row's latest run."""
    selected_kinds = [k for k in kinds if k in LIBRARY_EXPORT_KIND_IDS]
    if not selected_kinds:
        return ResolveResult(
            items=(),
            matching_rows=len(rows),
            included_rows=0,
            skipped_rows=len(rows),
            estimated_bytes=0,
        )

    if outputs_dir is None:
        from transcriptx.core.utils.paths import OUTPUTS_DIR

        outputs_dir = Path(OUTPUTS_DIR)

    from transcriptx.web.services.artifact_service import ArtifactService

    items: list[LibraryExportItem] = []
    used_dests: set[str] = set()
    included = 0
    skipped = 0

    for row in rows:
        slug = _row_slug(row)
        row_items: list[LibraryExportItem] = []
        run_id = row.analysis.latest_run_id
        artifacts: list = []
        run_dir: Path | None = None
        if run_id:
            run_dir = outputs_dir / slug / run_id
            if run_dir.is_dir():
                try:
                    artifacts = ArtifactService.list_artifacts(run_dir)
                except Exception:
                    artifacts = []

        for kind in selected_kinds:
            if kind == "transcript_json":
                src = Path(row.transcript_path)
                if not src.is_file():
                    continue
                dest = _disambiguate_dest(
                    slug, src.name, used_dests, short_id=row.transcript_key
                )
                row_items.append(
                    LibraryExportItem(
                        src=src,
                        dest_rel=dest,
                        kind=kind,
                        transcript_slug=slug,
                    )
                )
                continue

            if run_dir is None:
                continue
            for artifact in artifacts:
                if not _artifact_matches_kind(artifact, kind):
                    continue
                path = ArtifactService.resolve_artifact_source_path(run_dir, artifact)
                if path is None or not path.is_file():
                    continue
                dest = _disambiguate_dest(
                    slug,
                    path.name,
                    used_dests,
                    short_id=artifact.id,
                )
                row_items.append(
                    LibraryExportItem(
                        src=path,
                        dest_rel=dest,
                        kind=kind,
                        transcript_slug=slug,
                    )
                )

        if row_items:
            included += 1
            items.extend(row_items)
        else:
            skipped += 1

    estimated = 0
    for item in items:
        try:
            estimated += item.src.stat().st_size
        except OSError:
            continue

    return ResolveResult(
        items=tuple(items),
        matching_rows=len(rows),
        included_rows=included,
        skipped_rows=skipped,
        estimated_bytes=estimated,
    )


def build_library_export_manifest(
    *,
    tags: Sequence[str],
    kinds: Sequence[str],
    items: Iterable[LibraryExportItem],
    matching_rows: int,
    included_rows: int,
    skipped_rows: int,
) -> dict:
    """Build a JSON-serializable manifest for the library-by-tag ZIP."""
    item_list = list(items)
    return {
        "manifest_type": "library_tag_export",
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tags": list(tags),
        "kinds": list(kinds),
        "matching_rows": matching_rows,
        "included_rows": included_rows,
        "skipped_rows": skipped_rows,
        "item_count": len(item_list),
        "items": [
            {
                "src": str(item.src),
                "dest": item.dest_rel.as_posix(),
                "kind": item.kind,
                "transcript_slug": item.transcript_slug,
            }
            for item in item_list
        ],
    }
