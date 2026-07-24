"""Keyphrases analysis module — B16 (ranked salience; method-separated)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.keyphrases.analyze import analyze_keyphrases
from transcriptx.core.analysis.keyphrases.contract import (
    CSV_COLUMNS,
    SCHEMA_ID,
    SEMANTICS_VERSION,
    KeyphrasesResult,
)

if TYPE_CHECKING:
    from transcriptx.core.output.output_service import OutputService


class KeyphrasesAnalysis(AnalysisModule):
    """Document/speaker multiword keyphrase ranking (noun_chunks + optional methods)."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "keyphrases"
        self._eligibility_result: Dict[str, Any] | None = None

    def get_dependencies(self) -> List[str]:
        return ["insight_eligibility"]

    def run_from_context(self, context):
        self._eligibility_result = (
            context.get_analysis_result("insight_eligibility") or {}
        )
        try:
            return super().run_from_context(context)
        finally:
            self._eligibility_result = None

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        eligibility = self._eligibility_result or {}
        filtered = (
            eligibility.get("filtered_segments")
            if isinstance(eligibility, dict)
            else None
        )
        if not isinstance(filtered, list):
            filtered = None
        metadata = None
        if segments and isinstance(segments[0], dict):
            metadata = segments[0].get("_transcript_metadata")
            if not isinstance(metadata, dict):
                metadata = None
        if metadata is None and isinstance(eligibility, dict):
            meta = eligibility.get("metadata")
            if isinstance(meta, dict):
                metadata = meta
        result = analyze_keyphrases(
            filtered_segments=filtered,
            metadata=metadata,
        )
        return result.model_dump(mode="json")

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()
        try:
            parsed = KeyphrasesResult.model_validate(results)
            payload = parsed.model_dump(mode="json")
        except Exception:
            payload = dict(results)
            payload.setdefault("schema_id", SCHEMA_ID)
            payload.setdefault("semantics_version", SEMANTICS_VERSION)

        output_service.save_data(payload, "keyphrases", format_type="json")
        csv_path = Path(output_structure.global_data_dir) / (
            f"{base_name}_keyphrases.csv"
        )
        self._write_csv(payload, csv_path)
        output_service.record_file(csv_path, "csv")

        primary = []
        gbm = payload.get("global_by_method") or {}
        nc = gbm.get("noun_chunks") if isinstance(gbm, dict) else None
        if isinstance(nc, dict):
            primary = list(nc.get("phrases") or [])
        speaker_stats: Dict[str, Any] = {}
        sbm = payload.get("speakers_by_method") or {}
        nc_speakers = sbm.get("noun_chunks") if isinstance(sbm, dict) else None
        if isinstance(nc_speakers, dict):
            for speaker, block in nc_speakers.items():
                if isinstance(block, dict):
                    speaker_stats[speaker] = {
                        "phrase_count": len(block.get("phrases") or []),
                        "evaluation_state": block.get("evaluation_state"),
                    }
        output_service.save_summary(
            {
                "phrase_count": len(primary),
                "evaluation_state": payload.get("evaluation_state"),
                "usable": payload.get("usable"),
                "methods_run": payload.get("methods_run") or [],
            },
            speaker_stats,
            analysis_metadata={
                "schema_id": payload.get("schema_id"),
                "semantics_version": payload.get("semantics_version"),
            },
        )

    def _write_csv(self, results: Dict[str, Any], path: Path) -> None:
        rows: list[dict[str, Any]] = []
        gbm = results.get("global_by_method") or {}
        if isinstance(gbm, dict):
            for method, block in sorted(gbm.items()):
                if not isinstance(block, dict):
                    continue
                for phrase in block.get("phrases") or []:
                    if not isinstance(phrase, dict):
                        continue
                    rows.append(
                        {
                            "scope": "global",
                            "speaker": "",
                            "method": method,
                            "rank": phrase.get("rank"),
                            "phrase": phrase.get("phrase"),
                            "canonical_key": phrase.get("canonical_key"),
                            "token_count": phrase.get("token_count"),
                            "raw_score": phrase.get("raw_score"),
                            "score_direction": phrase.get("score_direction"),
                            "rank_weight": phrase.get("rank_weight"),
                            "occurrence_count": phrase.get("occurrence_count"),
                            "segment_support": phrase.get("segment_support"),
                        }
                    )
        sbm = results.get("speakers_by_method") or {}
        if isinstance(sbm, dict):
            for method, by_speaker in sorted(sbm.items()):
                if not isinstance(by_speaker, dict):
                    continue
                for speaker, block in sorted(by_speaker.items()):
                    if not isinstance(block, dict):
                        continue
                    for phrase in block.get("phrases") or []:
                        if not isinstance(phrase, dict):
                            continue
                        rows.append(
                            {
                                "scope": "speaker",
                                "speaker": speaker,
                                "method": method,
                                "rank": phrase.get("rank"),
                                "phrase": phrase.get("phrase"),
                                "canonical_key": phrase.get("canonical_key"),
                                "token_count": phrase.get("token_count"),
                                "raw_score": phrase.get("raw_score"),
                                "score_direction": phrase.get("score_direction"),
                                "rank_weight": phrase.get("rank_weight"),
                                "occurrence_count": phrase.get("occurrence_count"),
                                "segment_support": phrase.get("segment_support"),
                            }
                        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
