"""Chart registry for TranscriptX overview selection and matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Literal

import fnmatch
import re

Cardinality = Literal["single", "multi", "speaker_set", "paired_static_dynamic"]


@dataclass(frozen=True)
class ChartDefinition:
    viz_id: str
    label: str
    rank_default: int
    kind: str
    module: str
    scope: Literal["global", "speaker"]
    cardinality: Cardinality
    prefer_formats: List[str] = field(default_factory=lambda: ["html", "png"])
    match: "ChartMatcher" = field(default_factory=lambda: ChartMatcher())
    description: Optional[str] = None
    family_id: Optional[str] = None
    variant: Optional[str] = None


@dataclass(frozen=True)
class ChartMatcher:
    by_viz_id: Optional[str] = None
    by_artifact_key_prefix: Optional[str] = None
    by_chart_slug_regex: Optional[str] = None
    by_filename_glob: Optional[List[str]] = None

    def matches(self, artifact, chart_def: ChartDefinition) -> bool:
        artifact_kind = getattr(artifact, "kind", None)
        if artifact_kind and chart_def.kind:
            if not _kind_matches(artifact_kind, chart_def.kind):
                return False

        artifact_viz_id = _artifact_meta_value(artifact, "viz_id")
        if artifact_viz_id and self.by_viz_id:
            return artifact_viz_id == self.by_viz_id

        artifact_module = getattr(artifact, "module", None)
        artifact_scope = getattr(artifact, "scope", None)
        if artifact_module == chart_def.module and artifact_scope == chart_def.scope:
            if self.by_chart_slug_regex:
                if re.search(
                    self.by_chart_slug_regex, artifact.rel_path, re.IGNORECASE
                ):
                    return True

        if self.by_artifact_key_prefix:
            if artifact.rel_path.startswith(self.by_artifact_key_prefix):
                return True

        if self.by_filename_glob:
            for pattern in self.by_filename_glob:
                if fnmatch.fnmatch(artifact.rel_path, pattern):
                    return True

        return False


def _kind_matches(artifact_kind: str, chart_kind: str) -> bool:
    if chart_kind in {"chart", "map", "wordcloud"}:
        return artifact_kind.startswith("chart")
    return artifact_kind.startswith(chart_kind)


def _artifact_meta_value(artifact, key: str) -> Optional[str]:
    meta = getattr(artifact, "meta", None)
    if isinstance(meta, dict):
        return meta.get(key)
    return None


def get_artifact_format(artifact) -> Optional[str]:
    meta_format = _artifact_meta_value(artifact, "format")
    if meta_format:
        return str(meta_format).lower()
    suffix = Path(artifact.rel_path).suffix.lower().lstrip(".")
    return suffix or None


def select_preferred_artifacts(artifacts: List, chart_def: ChartDefinition) -> List:
    if not artifacts:
        return []

    def _pick_best(candidates: List) -> Optional[object]:
        if not candidates:
            return None
        for preferred in chart_def.prefer_formats:
            for candidate in candidates:
                if get_artifact_format(candidate) == preferred:
                    return candidate
        return candidates[0]

    if chart_def.cardinality == "single":
        best = _pick_best(artifacts)
        return [best] if best else []

    if chart_def.cardinality == "paired_static_dynamic":
        selected: List = []
        for preferred in chart_def.prefer_formats:
            match = next(
                (a for a in artifacts if get_artifact_format(a) == preferred), None
            )
            if match:
                selected.append(match)
        return selected or artifacts[:1]

    if chart_def.cardinality == "speaker_set":
        by_speaker: Dict[str, List] = {}
        for artifact in artifacts:
            speaker = getattr(artifact, "speaker", None) or "unknown"
            by_speaker.setdefault(speaker, []).append(artifact)
        selected = []
        for speaker_key in sorted(by_speaker.keys()):
            best = _pick_best(by_speaker[speaker_key])
            if best:
                selected.append(best)
        return selected

    return artifacts


def _load_chart_definitions() -> List[ChartDefinition]:
    """Build chart definitions from packaged chart_definitions.json."""
    import importlib.resources
    import json

    resource = importlib.resources.files("transcriptx.core.utils").joinpath(
        "chart_definitions.json"
    )
    raw_list = json.loads(resource.read_text(encoding="utf-8"))
    definitions: List[ChartDefinition] = []
    for item in raw_list:
        m = item["match"]
        matcher = ChartMatcher(
            by_viz_id=m.get("by_viz_id"),
            by_artifact_key_prefix=m.get("by_artifact_key_prefix"),
            by_chart_slug_regex=m.get("by_chart_slug_regex"),
            by_filename_glob=m.get("by_filename_glob"),
        )
        definitions.append(
            ChartDefinition(
                viz_id=item["viz_id"],
                label=item["label"],
                rank_default=item["rank_default"],
                kind=item["kind"],
                module=item["module"],
                scope=item["scope"],
                cardinality=item["cardinality"],
                prefer_formats=item.get("prefer_formats") or ["html", "png"],
                match=matcher,
                description=item.get("description"),
                family_id=item.get("family_id"),
                variant=item.get("variant"),
            )
        )
    return definitions


DEFAULT_OVERVIEW_VIZ_IDS: List[str] = [
    "sentiment.multi_speaker_sentiment.global",
    "emotion.radar.global",
    "interactions.network.global",
    "interactions.dominance.global",
    "interactions.heatmap.global",
    "momentum.momentum.global",
    "interactions.timeline.global",
    "acts.acts_temporal_all.global",
    "acts.acts_temporal.speaker",
    "conversation_loops.loop_timeline.global",
    "temporal_dynamics.temporal_dashboard.global",
    "temporal_dynamics.temporal_dashboard_speaking_rate.global",
    "understandability.readability_indices.global",
    "wordcloud.wordcloud.global.basic",
]

# Opt a cross-session speaker chart into the default group overview strip by adding
# its concrete viz_id here (see ``docs/groups/group_charts_default_overview.md``).
CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST: frozenset[str] = frozenset()

# Pooled ``pooled_single_view`` charts are gallery-only unless explicitly listed here.
# The acts global pie is both the default strip anchor and the audited pooled act mix.
POOLED_GROUP_OVERVIEW_ALLOWLIST: frozenset[str] = frozenset(
    {"group.acts.global_acts_pie.global"}
)

DEFAULT_GROUP_OVERVIEW_VIZ_IDS: List[str] = [
    "group.acts.global_acts_pie.global",
    "group.sentiment.session.compound_mean",
    "group.stats.session.total_words",
    "group.acts.temporal_overlay.global",
    "group.sentiment.temporal_overlay.global",
    "group.pauses.temporal_overlay.global",
    "group.emotion.temporal_overlay.global",
]


CHART_DEFINITIONS: List[ChartDefinition] = _load_chart_definitions()


_REGISTRY_BY_ID: Dict[str, ChartDefinition] = {c.viz_id: c for c in CHART_DEFINITIONS}


def get_chart_registry() -> Dict[str, ChartDefinition]:
    return dict(_REGISTRY_BY_ID)


def get_chart_definition(viz_id: str) -> Optional[ChartDefinition]:
    return _REGISTRY_BY_ID.get(viz_id)


def iter_chart_definitions() -> Iterable[ChartDefinition]:
    return CHART_DEFINITIONS


def get_default_overview_charts() -> List[str]:
    return list(DEFAULT_OVERVIEW_VIZ_IDS)


def get_default_group_overview_charts() -> List[str]:
    return list(DEFAULT_GROUP_OVERVIEW_VIZ_IDS)
