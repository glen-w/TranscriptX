"""View-model helpers for charts page orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from transcriptx.core.utils.chart_registry import (
    ChartDefinition,
    find_chart_definition_for_artifact,
    get_chart_definition,
    get_chart_registry,
    get_default_group_overview_charts,
    get_default_overview_charts,
    select_preferred_artifacts,
)
from transcriptx.web.module_ui_groups import order_module_ids
from transcriptx.web.models.artifact import Artifact, ArtifactFilters

_UNREGISTERED_RANK = 9999


@dataclass
class ChartGallerySlice:
    key: str
    label: str
    artifacts: list[Artifact]


@dataclass
class ChartGalleryFamily:
    key: str
    label: str
    description: str | None
    cardinality: str
    rank: int
    slices: list[ChartGallerySlice]

    @property
    def artifact_count(self) -> int:
        return sum(len(s.artifacts) for s in self.slices)


def resolve_chart_description(artifact: Artifact) -> str | None:
    """Return the registry description for a chart artifact, if any."""
    cd = find_chart_definition_for_artifact(artifact)
    if cd and cd.description:
        return cd.description.strip() or None
    return None


def compute_chart_badges(all_charts: List[Artifact]) -> List[str]:
    st_c = sum(1 for a in all_charts if a.kind == "chart_static")
    dyn_c = sum(1 for a in all_charts if a.kind == "chart_dynamic")
    badge_bits: List[str] = []
    if all_charts:
        badge_bits.append(f"{len(all_charts)} charts")
        if st_c:
            badge_bits.append(f"Static {st_c}")
        if dyn_c:
            badge_bits.append(f"Dynamic {dyn_c}")
    return badge_bits


def build_filter_options(
    all_charts: List[Artifact],
) -> Tuple[List[str], List[str], List[str], List[str]]:
    modules = order_module_ids({a.module for a in all_charts if a.module})
    scopes = sorted({a.scope for a in all_charts if a.scope})
    tags = sorted({tag for a in all_charts for tag in a.tags})
    subviews = sorted({a.subview for a in all_charts if a.subview})
    return modules, scopes, tags, subviews


def apply_chart_filters(
    all_charts: List[Artifact],
    *,
    module: str | None,
    scope: str | None,
    kind: str | None,
    tags: List[str] | None,
    subview: str | None,
    slice_id: str | None,
) -> List[Artifact]:
    if kind == "__none__":
        return []
    flt = ArtifactFilters(
        module=module,
        scope=scope,
        kind=kind,
        tags=tags or None,
        subview=subview,
        slice_id=slice_id,
    )
    return [a for a in all_charts if flt.matches(a)]


def _meta_str(artifact: Artifact, key: str) -> str | None:
    meta = artifact.meta
    if not isinstance(meta, dict):
        return None
    value = meta.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cleaned_filename_stem(artifact: Artifact) -> str:
    stem = Path(artifact.rel_path).stem
    if not stem:
        return ""
    return stem.replace("_", " ").replace("-", " ").strip()


def infer_session_slice_from_title(title: str | None) -> str | None:
    """Last-resort session/member slice key from a title prefix like ``session_a: ...``."""
    if not title or ":" not in title:
        return None
    prefix = title.split(":", 1)[0].strip()
    return prefix or None


def _get_gallery_family_key(
    artifact: Artifact, chart_def: ChartDefinition | None
) -> str:
    if chart_def is not None:
        return chart_def.viz_id
    rel = Path(artifact.rel_path)
    return (
        f"unregistered:{artifact.module or 'unknown'}:"
        f"{artifact.kind}:{rel.parent.as_posix()}:{rel.stem}"
    )


def _get_gallery_family_label(
    artifact: Artifact, chart_def: ChartDefinition | None
) -> str:
    if chart_def is not None:
        return chart_def.label
    if artifact.title:
        return artifact.title
    stem_label = _cleaned_filename_stem(artifact)
    if stem_label:
        return stem_label
    return "Unregistered chart"


def _get_gallery_family_description(
    chart_def: ChartDefinition | None,
) -> str | None:
    if chart_def is None or not chart_def.description:
        return None
    return chart_def.description.strip() or None


def _get_gallery_family_rank(chart_def: ChartDefinition | None) -> int:
    if chart_def is None:
        return _UNREGISTERED_RANK
    return chart_def.rank_default


def _get_gallery_family_cardinality(chart_def: ChartDefinition | None) -> str:
    if chart_def is None:
        return "unknown"
    return chart_def.cardinality


def _get_gallery_slice_key(
    artifact: Artifact, chart_def: ChartDefinition | None
) -> str:
    if chart_def is None:
        if artifact.subview in {"by_speaker", "by_session"} and artifact.slice_id:
            return artifact.slice_id
        if artifact.has_tag("member_session") and artifact.slice_id:
            return artifact.slice_id
        for key in ("slice_id", "session_id"):
            value = _meta_str(artifact, key)
            if value:
                return value
        return "all"

    if artifact.has_tag("member_session"):
        return (
            artifact.slice_id
            or _meta_str(artifact, "slice_id")
            or _meta_str(artifact, "session_id")
            or _meta_str(artifact, "session")
            or infer_session_slice_from_title(artifact.title)
            or "all"
        )

    cardinality = chart_def.cardinality
    if cardinality in {"single", "paired_static_dynamic"}:
        return "all"

    if artifact.subview == "by_session":
        return (
            artifact.slice_id
            or _meta_str(artifact, "session_id")
            or _meta_str(artifact, "session")
            or "unknown-session"
        )

    if artifact.subview == "by_speaker":
        return (
            artifact.slice_id
            or _meta_str(artifact, "speaker_id")
            or artifact.speaker
            or "unknown-speaker"
        )

    if cardinality == "speaker_set" or artifact.scope == "speaker":
        return (
            artifact.speaker
            or _meta_str(artifact, "speaker_id")
            or _meta_str(artifact, "speaker_display")
            or "unknown-speaker"
        )

    return "all"


def _get_gallery_slice_label(artifact: Artifact, slice_key: str) -> str:
    if slice_key == "all":
        return ""

    if artifact.subview == "by_session" or slice_key == "unknown-session":
        return (
            _meta_str(artifact, "session_label")
            or artifact.slice_id
            or _meta_str(artifact, "session_id")
            or _meta_str(artifact, "session")
            or (
                slice_key
                if slice_key not in {"unknown-session", "unknown-speaker"}
                else "Unknown session"
            )
        )

    return (
        _meta_str(artifact, "speaker_display")
        or artifact.speaker
        or _meta_str(artifact, "speaker_name")
        or (
            slice_key
            if slice_key not in {"unknown-speaker", "unknown-session"}
            else "Unknown speaker"
        )
    )


def _sort_artifacts(artifacts: list[Artifact]) -> list[Artifact]:
    return sorted(
        artifacts,
        key=lambda a: (a.title or "", a.rel_path or "", a.id or ""),
    )


def _sort_slices(slices: list[ChartGallerySlice]) -> list[ChartGallerySlice]:
    def sort_key(sl: ChartGallerySlice) -> tuple:
        if sl.key == "all":
            return (0, "", "")
        return (1, sl.label.lower(), sl.key)

    return sorted(slices, key=sort_key)


def _build_slices_from_artifacts(
    artifacts: list[Artifact],
    chart_def: ChartDefinition | None,
) -> list[ChartGallerySlice]:
    by_slice: dict[str, list[Artifact]] = {}
    slice_labels: dict[str, str] = {}
    for artifact in artifacts:
        slice_key = _get_gallery_slice_key(artifact, chart_def)
        by_slice.setdefault(slice_key, []).append(artifact)
        if slice_key not in slice_labels:
            slice_labels[slice_key] = _get_gallery_slice_label(artifact, slice_key)

    slices = [
        ChartGallerySlice(
            key=slice_key,
            label=slice_labels[slice_key],
            artifacts=_sort_artifacts(slice_artifacts),
        )
        for slice_key, slice_artifacts in by_slice.items()
    ]
    return _sort_slices(slices)


def group_charts_into_families(charts: list[Artifact]) -> list[ChartGalleryFamily]:
    """Group chart artifacts into registry families with speaker/session slices."""
    if not charts:
        return []

    family_buckets: dict[str, dict[str, Any]] = {}

    for artifact in charts:
        chart_def = find_chart_definition_for_artifact(artifact)
        family_key = _get_gallery_family_key(artifact, chart_def)
        slice_key = _get_gallery_slice_key(artifact, chart_def)

        bucket = family_buckets.setdefault(
            family_key,
            {
                "chart_def": chart_def,
                "label": _get_gallery_family_label(artifact, chart_def),
                "description": _get_gallery_family_description(chart_def),
                "cardinality": _get_gallery_family_cardinality(chart_def),
                "rank": _get_gallery_family_rank(chart_def),
                "slices": {},
                "slice_labels": {},
            },
        )
        if chart_def is not None:
            bucket["label"] = chart_def.label
            bucket["description"] = _get_gallery_family_description(chart_def)
            bucket["cardinality"] = chart_def.cardinality
            bucket["rank"] = chart_def.rank_default

        slice_bucket: dict[str, list[Artifact]] = bucket["slices"]
        slice_bucket.setdefault(slice_key, []).append(artifact)
        if slice_key not in bucket["slice_labels"]:
            bucket["slice_labels"][slice_key] = _get_gallery_slice_label(
                artifact, slice_key
            )

    families: list[ChartGalleryFamily] = []
    for family_key, bucket in family_buckets.items():
        slices = [
            ChartGallerySlice(
                key=slice_key,
                label=bucket["slice_labels"][slice_key],
                artifacts=_sort_artifacts(slice_artifacts),
            )
            for slice_key, slice_artifacts in bucket["slices"].items()
        ]
        families.append(
            ChartGalleryFamily(
                key=family_key,
                label=bucket["label"],
                description=bucket["description"],
                cardinality=bucket["cardinality"],
                rank=bucket["rank"],
                slices=_sort_slices(slices),
            )
        )

    return sorted(
        families,
        key=lambda f: (f.rank, f.label.lower(), f.key),
    )


def family_from_overview_slot(slot: dict[str, Any]) -> ChartGalleryFamily | None:
    """Build a gallery family from an overview slot, preserving slot-level label."""
    artifacts = list(slot.get("artifacts") or [])
    if not artifacts:
        return None
    viz_id = str(slot["viz_id"])
    chart_def = get_chart_definition(viz_id)
    return ChartGalleryFamily(
        key=viz_id,
        label=str(slot.get("label") or (chart_def.label if chart_def else viz_id)),
        description=slot.get("description"),
        cardinality=str(
            slot.get("cardinality")
            or (chart_def.cardinality if chart_def else "unknown")
        ),
        rank=chart_def.rank_default if chart_def else _UNREGISTERED_RANK,
        slices=_build_slices_from_artifacts(artifacts, chart_def),
    )


def build_overview_slots(
    overview_candidates: List[Artifact],
    user_overview: List[str],
    missing_behavior: str,
    max_items: int | None,
) -> List[Dict[str, Any]]:
    registry = get_chart_registry()
    if user_overview:
        enabled_viz_ids = user_overview
    elif any("group_aggregate" in a.tags for a in overview_candidates):
        enabled_viz_ids = get_default_group_overview_charts()
    else:
        enabled_viz_ids = get_default_overview_charts()
    if isinstance(max_items, int) and max_items > 0:
        enabled_viz_ids = enabled_viz_ids[:max_items]

    slots: List[Dict[str, Any]] = []
    for viz_id in enabled_viz_ids:
        chart_def = registry.get(viz_id)
        if not chart_def:
            if missing_behavior == "show_placeholder":
                slots.append(
                    {
                        "label": f"{viz_id} (not available)",
                        "viz_id": viz_id,
                        "artifacts": [],
                        "description": None,
                        "missing": True,
                    }
                )
            continue
        cd = get_chart_definition(viz_id)
        matching = (
            select_preferred_artifacts(
                [a for a in overview_candidates if cd and cd.match.matches(a, cd)],
                cd,
            )
            if cd
            else []
        )
        if matching or missing_behavior == "show_placeholder":
            if chart_def.cardinality == "single" and matching and matching[0].title:
                display_title = matching[0].title
            else:
                display_title = chart_def.label
            description = (
                chart_def.description.strip()
                if chart_def.description and chart_def.description.strip()
                else None
            )
            slots.append(
                {
                    "label": display_title,
                    "viz_id": viz_id,
                    "artifacts": matching,
                    "cardinality": chart_def.cardinality,
                    "description": description,
                    "missing": not matching,
                }
            )
    return slots
