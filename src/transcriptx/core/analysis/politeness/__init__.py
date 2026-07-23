"""Politeness / formality / directiveness analysis module — B7."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.lexicon_markers import derive_soft_request_ratio
from transcriptx.core.analysis.lexicon_markers.pipeline import run_marker_analysis
from transcriptx.core.utils.viz_ids import VIZ_POLITENESS_CATEGORY_SPEAKER
from transcriptx.core.viz.specs import BarCategoricalSpec

if TYPE_CHECKING:
    from transcriptx.core.output.output_service import OutputService

SCHEMA_ID = "transcriptx.politeness.v1"
SEMANTICS_VERSION = "politeness_v1"
CATEGORIES = (
    "gratitude",
    "apology",
    "request_softener",
    "polite_disagreement",
    "bare_directive",
    "formal_marker",
)
LEXICON_FILENAME = "politeness_en.json"


def _derive_politeness(stats: Dict[str, Any]) -> Dict[str, Any]:
    return {"soft_request_ratio": derive_soft_request_ratio(stats)}


class PolitenessAnalysis(AnalysisModule):
    """Lexicon-first politeness / lexical formality / directiveness markers."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "politeness"

    def _settings(self) -> tuple[list[str] | None, int]:
        try:
            from transcriptx.core.utils.config import get_config

            cfg = get_config().analysis.politeness
            enabled = list(cfg.enabled_categories) if cfg.enabled_categories else None
            min_tokens = int(cfg.min_tokens_for_rates)
            return enabled, min_tokens
        except Exception:
            return None, 20

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        enabled, min_tokens = self._settings()
        metadata = None
        if segments and isinstance(segments[0], dict):
            metadata = segments[0].get("_transcript_metadata")
            if not isinstance(metadata, dict):
                metadata = None
        return run_marker_analysis(
            segments,
            module=self.module_name,
            lexicon_filename=LEXICON_FILENAME,
            categories=CATEGORIES,
            schema_id=SCHEMA_ID,
            semantics_version=SEMANTICS_VERSION,
            enabled_categories=enabled,
            min_tokens_for_rates=min_tokens,
            derive_fn=_derive_politeness,
            metadata=metadata,
        )

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()
        payload = {
            "schema_id": results["metadata"]["schema_id"],
            "usable": results.get("usable", True),
            "metadata": results["metadata"],
            "speaker_stats": results["speaker_stats"],
            "global_stats": results["global_stats"],
            "hits": results.get("hits") or [],
            "exclusions": results.get("exclusions") or {},
        }
        output_service.save_data(payload, "politeness", format_type="json")
        csv_path = Path(output_structure.global_data_dir) / (
            f"{base_name}_politeness.csv"
        )
        self._write_csv(results, csv_path)
        output_service.record_file(csv_path, "csv")
        self._save_charts(results, output_service)
        output_service.save_summary(
            results["global_stats"],
            results["speaker_stats"],
            analysis_metadata=results.get("metadata") or {},
        )

    def _write_csv(self, results: Dict[str, Any], path: Path) -> None:
        rows: list[dict[str, Any]] = []
        global_stats = results.get("global_stats") or {}
        rows.append(
            {
                "scope": "global",
                "speaker": "",
                "token_count": global_stats.get("token_count"),
                "total_marker_hits": global_stats.get("total_marker_hits"),
                "hits_per_100_tokens": global_stats.get("hits_per_100_tokens"),
                "soft_request_ratio": global_stats.get("soft_request_ratio"),
                **{
                    f"count_{c}": (global_stats.get("category_counts") or {}).get(c)
                    for c in CATEGORIES
                },
            }
        )
        for speaker, stats in sorted((results.get("speaker_stats") or {}).items()):
            if not isinstance(stats, dict):
                continue
            rows.append(
                {
                    "scope": "speaker",
                    "speaker": speaker,
                    "token_count": stats.get("token_count"),
                    "total_marker_hits": stats.get("total_marker_hits"),
                    "hits_per_100_tokens": stats.get("hits_per_100_tokens"),
                    "soft_request_ratio": stats.get("soft_request_ratio"),
                    **{
                        f"count_{c}": (stats.get("category_counts") or {}).get(c)
                        for c in CATEGORIES
                    },
                }
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0].keys()) if rows else ["scope"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _save_charts(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        for speaker, stats in (results.get("speaker_stats") or {}).items():
            if not isinstance(stats, dict):
                continue
            rates = stats.get("category_rates_per_100_tokens") or {}
            labels: list[str] = []
            values: list[float] = []
            for category in CATEGORIES:
                rate = rates.get(category)
                if rate is None:
                    continue
                labels.append(category)
                values.append(float(rate))
            if not labels:
                counts = stats.get("category_counts") or {}
                for category in CATEGORIES:
                    count = int(counts.get(category, 0) or 0)
                    if count <= 0:
                        continue
                    labels.append(category)
                    values.append(float(count))
            if not labels:
                continue
            spec = BarCategoricalSpec(
                viz_id=VIZ_POLITENESS_CATEGORY_SPEAKER,
                module=self.module_name,
                name="category_rates",
                scope="speaker",
                speaker=speaker,
                chart_intent="bar_categorical",
                title=f"Politeness markers: {speaker}",
                x_label="Category",
                y_label="Rate per 100 tokens (or count)",
                categories=labels,
                values=values,
            )
            output_service.save_chart(spec, chart_type="politeness")
