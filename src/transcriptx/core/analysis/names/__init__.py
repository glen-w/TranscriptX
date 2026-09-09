"""People-mentioned analysis module (spaCy PERSON catalog via upstream NER)."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.names.catalog import build_names_catalog
from transcriptx.core.analysis.names.schema import SCHEMA_ID, SEMANTICS_VERSION
from transcriptx.core.analysis.common import (
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.module_result import build_module_result, now_iso

if TYPE_CHECKING:
    from transcriptx.core.output.output_service import OutputService
    from transcriptx.core.pipeline.pipeline_context import PipelineContext


class NamesAnalysis(AnalysisModule):
    """Catalog people mentioned in transcript text from upstream NER PERSON entities."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "names"

    def _settings(self) -> tuple[int, bool, int]:
        try:
            from transcriptx.core.utils.config import get_config

            cfg = get_config().analysis.names
            return (
                int(cfg.min_mentions),
                bool(cfg.exclude_known_speakers),
                int(cfg.max_mentions_per_person),
            )
        except Exception:
            return 1, False, 50

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        ner_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        min_mentions, exclude_known_speakers, max_mentions_per_person = self._settings()
        metadata = {
            "schema_id": SCHEMA_ID,
            "semantics_version": SEMANTICS_VERSION,
            "min_mentions": min_mentions,
            "exclude_known_speakers": exclude_known_speakers,
            "max_mentions_per_person": max_mentions_per_person,
        }

        if not ner_data or not isinstance(ner_data, dict):
            return {
                "usable": False,
                "metadata": metadata,
                "people": [],
                "global_stats": {"unique_people": 0, "total_mentions": 0},
                "exclusions": {"reason": "missing_ner_result"},
            }

        person_mentions = ner_data.get("person_mentions")
        if not isinstance(person_mentions, list):
            return {
                "usable": False,
                "metadata": metadata,
                "people": [],
                "global_stats": {"unique_people": 0, "total_mentions": 0},
                "exclusions": {"reason": "missing_person_mentions"},
            }

        catalog = build_names_catalog(
            person_mentions,
            segments=segments,
            min_mentions=min_mentions,
            exclude_known_speakers=exclude_known_speakers,
            max_mentions_per_person=max_mentions_per_person,
        )
        return {
            "usable": True,
            "metadata": metadata,
            "people": catalog["people"],
            "global_stats": catalog["global_stats"],
            "exclusions": {},
        }

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        started_at = now_iso()
        start_time = time.time()
        try:
            log_analysis_start(self.module_name, context.transcript_path)
            segments = context.get_segments()
            ner_result = context.get_analysis_result("ner")
            results = self.analyze(segments, ner_data=ner_result)

            from transcriptx.core.output.output_service import create_output_service

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)
            context.store_analysis_result(self.module_name, results)
            log_analysis_complete(self.module_name, context.transcript_path)

            finished_at = now_iso()
            duration_seconds = time.time() - start_time
            output_structure = output_service.get_output_structure()
            output_directory = str(getattr(output_structure, "module_dir", ""))

            module_result = build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                artifacts=output_service.get_artifacts(),
                metrics={
                    "duration_seconds": duration_seconds,
                    "output_directory": output_directory,
                },
                payload_type="analysis_results",
                payload=results,
            )
            module_result["output_directory"] = output_directory
            return module_result
        except Exception as e:
            log_analysis_error(self.module_name, context.transcript_path, str(e))
            if isinstance(e, ValueError):
                raise
            return build_module_result(
                module_name=self.module_name,
                status="error",
                started_at=started_at,
                finished_at=now_iso(),
                artifacts=[],
                metrics={"duration_seconds": time.time() - start_time},
                payload_type="analysis_results",
                payload={},
                error={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_service.save_data(results, "names", format_type="json")

        mention_rows: list[dict[str, Any]] = []
        summary_rows: list[dict[str, Any]] = []
        for person in results.get("people") or []:
            if not isinstance(person, dict):
                continue
            summary_rows.append(
                {
                    "display_name": person.get("display_name"),
                    "normalized_key": person.get("normalized_key"),
                    "mention_count": person.get("mention_count"),
                    "mentioned_by_speakers": ", ".join(
                        person.get("mentioned_by_speakers") or []
                    ),
                }
            )
            for mention in person.get("mentions") or []:
                if not isinstance(mention, dict):
                    continue
                mention_rows.append(
                    {
                        "display_name": person.get("display_name"),
                        "normalized_key": person.get("normalized_key"),
                        "segment_index": mention.get("segment_index"),
                        "start": mention.get("start"),
                        "speaker": mention.get("speaker"),
                        "surface": mention.get("surface"),
                        "text": mention.get("text"),
                    }
                )

        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()
        summary_path = Path(output_structure.global_data_dir) / (
            f"{base_name}_names_summary.csv"
        )
        self._write_csv(summary_rows, summary_path)
        output_service.record_file(summary_path, "csv")

        if mention_rows:
            mentions_path = Path(output_structure.global_data_dir) / (
                f"{base_name}_names.csv"
            )
            self._write_csv(mention_rows, mentions_path)
            output_service.record_file(mentions_path, "csv")

        output_service.save_summary(
            results.get("global_stats") or {},
            {},
            analysis_metadata=results.get("metadata") or {},
        )

    def _write_csv(self, rows: list[dict[str, Any]], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0].keys()) if rows else ["display_name"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
