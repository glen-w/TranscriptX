"""
ConvoKit analysis module for TranscriptX.

This module converts diarized transcript segments into a ConvoKit Corpus and
computes coordination/accommodation metrics between speakers. It complements
existing interaction and temporal analyses by providing ConvoKit-native metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)
from transcriptx.core.utils.lazy_imports import get_convokit, optional_import
from transcriptx.core.utils.module_result import now_iso
from transcriptx.utils.text_utils import is_named_speaker

logger = get_logger()


@dataclass
class ReplyLinkingStats:
    total_utterances: int
    reply_links: int
    strategy: str
    response_threshold: Optional[float] = None


class ConvoKitAnalysis(AnalysisModule):
    """
    ConvoKit coordination analysis module.

    This module builds a ConvoKit Corpus from diarized transcript segments,
    constructs reply links, and computes linguistic coordination between speakers.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "convokit"

        from transcriptx.core.utils.config import get_config

        profile_config = get_config().analysis.convokit

        self.exclude_unidentified = self.config.get(
            "exclude_unidentified", profile_config.exclude_unidentified
        )
        self.min_tokens_per_utterance = self.config.get(
            "min_tokens_per_utterance", profile_config.min_tokens_per_utterance
        )
        self.max_utterances = self.config.get(
            "max_utterances", profile_config.max_utterances
        )
        self.reply_linking_strategy = self.config.get(
            "reply_linking_strategy", profile_config.reply_linking_strategy
        )
        self.response_threshold = self.config.get(
            "response_threshold", profile_config.response_threshold
        )
        self.enable_politeness = self.config.get(
            "enable_politeness", profile_config.enable_politeness
        )

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform ConvoKit coordination analysis on transcript segments (pure logic, no I/O).
        """
        try:
            convokit = get_convokit()
            pandas = optional_import("pandas", "ConvoKit analysis", "convokit")
        except ImportError as exc:
            logger.warning(str(exc))
            return {
                "skipped": True,
                "skipped_reason": "convokit_not_installed",
                "error": str(exc),
            }

        if not segments:
            return {
                "skipped": True,
                "skipped_reason": "no_segments",
            }

        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )

        transcript_key = compute_transcript_identity_hash(segments)

        utterance_records, conversion_stats = self._build_utterance_records(
            segments, transcript_key
        )

        if len(conversion_stats["named_speakers"]) < 2:
            return {
                "skipped": True,
                "skipped_reason": "insufficient_named_speakers",
                "conversion_stats": conversion_stats,
            }

        reply_stats = self._build_reply_to_links(
            utterance_records,
            strategy=self.reply_linking_strategy,
            response_threshold=self.response_threshold,
        )

        if reply_stats.reply_links == 0:
            logger.warning(
                "ConvoKit reply graph has no links; coordination may be empty."
            )

        utterances_df = pandas.DataFrame(utterance_records)
        try:
            corpus = convokit.Corpus.from_pandas(utterances_df)
        except Exception:
            # Fallback: try Corpus constructor with utterance objects
            utterances = []
            speakers = {}
            for record in utterance_records:
                speaker_id = record.get("speaker")
                if speaker_id not in speakers:
                    speakers[speaker_id] = convokit.Speaker(id=speaker_id)
                utterances.append(
                    convokit.Utterance(
                        id=record["id"],
                        speaker=speakers[speaker_id],
                        conversation_id=record["conversation_id"],
                        reply_to=record.get("reply_to"),
                        timestamp=record.get("timestamp"),
                        text=record.get("text"),
                        meta={
                            "start": record.get("meta.start"),
                            "end": record.get("meta.end"),
                            "duration": record.get("meta.duration"),
                            "segment_index": record.get("meta.segment_index"),
                            "speaker_id": record.get("meta.speaker_id"),
                            "speaker_db_id": record.get("meta.speaker_db_id"),
                        },
                    )
                )
            corpus = convokit.Corpus(
                utterances=utterances, speakers=list(speakers.values())
            )

        coordination_edges, coordination_matrix, coordination_summary = (
            self._compute_coordination(convokit, corpus)
        )

        run_timestamp = now_iso()
        coordination_summary = {
            **coordination_summary,
            "metadata": {
                "transcript_key": transcript_key,
                "run_timestamp": run_timestamp,
                "module_version": "1.0.0",
                "reply_linking_strategy": reply_stats.strategy,
                "response_threshold": reply_stats.response_threshold,
                "exclude_unidentified": self.exclude_unidentified,
                "min_tokens_per_utterance": self.min_tokens_per_utterance,
                "max_utterances": self.max_utterances,
                "schema_version": "1.0.0",
            },
        }

        politeness_results = None
        if self.enable_politeness:
            politeness_results = self._compute_politeness(convokit, corpus)

        return {
            "skipped": False,
            "conversion_stats": conversion_stats,
            "reply_linking": {
                "strategy": reply_stats.strategy,
                "reply_links": reply_stats.reply_links,
                "total_utterances": reply_stats.total_utterances,
                "response_threshold": reply_stats.response_threshold,
            },
            "coordination_edges": coordination_edges,
            "coordination_matrix": coordination_matrix,
            "coordination_summary": coordination_summary,
            "corpus_manifest": {
                "transcript_key": transcript_key,
                "conversation_id": transcript_key,
                "utterances": len(utterance_records),
                "speakers": len(conversion_stats["named_speakers"]),
                "exclude_unidentified": self.exclude_unidentified,
                "min_tokens_per_utterance": self.min_tokens_per_utterance,
                "max_utterances": self.max_utterances,
                "reply_linking_strategy": reply_stats.strategy,
                "response_threshold": reply_stats.response_threshold,
                "excluded_speakers": conversion_stats["excluded_speakers"],
                "run_timestamp": run_timestamp,
                "schema_version": "1.0.0",
            },
            "politeness": politeness_results,
        }

    def _build_utterance_records(
        self, segments: List[Dict[str, Any]], transcript_key: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        utterance_records: List[Dict[str, Any]] = []
        excluded_speakers: List[str] = []
        named_speakers: set[str] = set()
        skipped_empty = 0
        skipped_short = 0

        for idx, segment in enumerate(segments):
            text = (segment.get("text") or "").strip()
            if not text:
                skipped_empty += 1
                continue

            token_count = len(text.split())
            if token_count < self.min_tokens_per_utterance:
                skipped_short += 1
                continue

            info = extract_speaker_info(segment)
            display_name = None
            if info is not None:
                display_name = get_speaker_display_name(
                    info.grouping_key, [segment], segments
                )
            if not display_name:
                display_name = segment.get("speaker")

            raw_label = segment.get("speaker")
            is_placeholder = (
                raw_label
                and not is_named_speaker(raw_label)
                and display_name
                and display_name.startswith("Speaker ")
                and segment.get("speaker_db_id") is not None
            )

            if self.exclude_unidentified and (
                not display_name or not is_named_speaker(display_name) or is_placeholder
            ):
                excluded_speakers.append(display_name or "UNKNOWN")
                continue

            named_speakers.add(display_name)

            start = segment.get("start", 0.0)
            end = segment.get("end", start)
            duration = max(0.0, end - start)
            speaker_id = segment.get("speaker")
            speaker_db_id = segment.get("speaker_db_id")

            utterance_records.append(
                {
                    "id": f"{transcript_key}:{idx}",
                    "speaker": display_name,
                    "conversation_id": transcript_key,
                    "timestamp": start,
                    "text": text,
                    "reply_to": None,
                    "meta.start": start,
                    "meta.end": end,
                    "meta.duration": duration,
                    "meta.segment_index": idx,
                    "meta.speaker_id": speaker_id,
                    "meta.speaker_db_id": speaker_db_id,
                }
            )

            if self.max_utterances and len(utterance_records) >= self.max_utterances:
                break

        conversion_stats = {
            "utterances": len(utterance_records),
            "named_speakers": sorted(named_speakers),
            "excluded_speakers": sorted(set(excluded_speakers)),
            "skipped_empty": skipped_empty,
            "skipped_short": skipped_short,
        }

        return utterance_records, conversion_stats

    def _build_reply_to_links(
        self,
        utterance_records: List[Dict[str, Any]],
        strategy: str,
        response_threshold: float,
    ) -> ReplyLinkingStats:
        sorted_utts = sorted(
            utterance_records,
            key=lambda u: (u.get("timestamp", 0.0), u.get("meta.segment_index", 0)),
        )
        reply_links = 0

        for i, current in enumerate(sorted_utts):
            current_speaker = current.get("speaker")
            current_start = current.get("meta.start", current.get("timestamp", 0.0))

            reply_to = None

            if strategy == "prev_diff_speaker":
                for j in range(i - 1, -1, -1):
                    prev = sorted_utts[j]
                    if prev.get("speaker") != current_speaker:
                        reply_to = prev.get("id")
                        break
            elif strategy == "threshold_gap":
                for j in range(i - 1, -1, -1):
                    prev = sorted_utts[j]
                    if prev.get("speaker") == current_speaker:
                        continue
                    prev_end = prev.get("meta.end", prev.get("timestamp", 0.0))
                    gap = current_start - prev_end
                    if gap <= 0:
                        continue
                    if gap <= response_threshold:
                        reply_to = prev.get("id")
                        break
                    # Earlier utterances will have even larger gaps
                    break
            else:
                raise ValueError(f"Unknown reply linking strategy: {strategy}")

            current["reply_to"] = reply_to
            if reply_to:
                reply_links += 1

        return ReplyLinkingStats(
            total_utterances=len(sorted_utts),
            reply_links=reply_links,
            strategy=strategy,
            response_threshold=response_threshold if strategy == "threshold_gap" else None,
        )

    def _compute_coordination(self, convokit, corpus):
        coord = convokit.Coordination()
        coord.fit(corpus)
        corpus = coord.transform(corpus)
        summary = None
        try:
            summary = coord.summarize(corpus)
        except Exception as exc:
            logger.warning(f"Failed to summarize coordination: {exc}")

        edges = self._normalize_coordination_edges(summary)
        matrix = self._build_coordination_matrix(edges)
        summary_stats = self._build_coordination_summary(edges)

        return edges, matrix, summary_stats

    def _normalize_coordination_edges(self, summary: Any) -> List[Dict[str, Any]]:
        if summary is None:
            return []

        records: List[Dict[str, Any]] = []
        if hasattr(summary, "to_dict"):
            try:
                records = summary.to_dict(orient="records")
            except Exception:
                pass
        elif isinstance(summary, list):
            records = summary
        elif isinstance(summary, dict):
            if isinstance(summary.get("coordination"), list):
                records = summary["coordination"]
            else:
                records = [summary]

        edges: List[Dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue

            source = record.get("speaker") or record.get("source") or record.get("from")
            target = record.get("target") or record.get("to") or record.get(
                "target_speaker"
            )
            score = (
                record.get("coordination")
                or record.get("coord")
                or record.get("score")
                or record.get("value")
            )
            n_utts = (
                record.get("n_utts")
                or record.get("num_utts")
                or record.get("count")
                or record.get("n")
                or record.get("num_utterances")
            )

            if source is None or target is None:
                continue

            edges.append(
                {
                    "from": source,
                    "to": target,
                    "score": score,
                    "n_utts": n_utts,
                }
            )

        return edges

    def _build_coordination_matrix(
        self, edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        speakers = sorted(
            {edge["from"] for edge in edges} | {edge["to"] for edge in edges}
        )
        if not speakers:
            return []

        matrix_rows: List[Dict[str, Any]] = []
        edge_map = {(edge["from"], edge["to"]): edge.get("score") for edge in edges}

        for speaker in speakers:
            row = {"speaker": speaker}
            for target in speakers:
                row[target] = edge_map.get((speaker, target))
            matrix_rows.append(row)

        return matrix_rows

    def _build_coordination_summary(
        self, edges: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not edges:
            return {
                "summary": {},
                "per_speaker": {},
                "top_dyads": [],
            }

        scores = [edge.get("score") for edge in edges if edge.get("score") is not None]
        if not scores:
            return {
                "summary": {},
                "per_speaker": {},
                "top_dyads": [],
            }

        outgoing: Dict[str, List[float]] = {}
        incoming: Dict[str, List[float]] = {}
        for edge in edges:
            score = edge.get("score")
            if score is None:
                continue
            outgoing.setdefault(edge["from"], []).append(score)
            incoming.setdefault(edge["to"], []).append(score)

        per_speaker = {}
        for speaker in set(outgoing.keys()) | set(incoming.keys()):
            per_speaker[speaker] = {
                "coordination_to_others": (
                    sum(outgoing.get(speaker, [])) / len(outgoing.get(speaker, []) or [1])
                ),
                "others_coordinate_to_them": (
                    sum(incoming.get(speaker, [])) / len(incoming.get(speaker, []) or [1])
                ),
            }

        top_dyads = sorted(
            [edge for edge in edges if edge.get("score") is not None],
            key=lambda e: e["score"],
            reverse=True,
        )[:10]

        return {
            "summary": {
                "mean_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "edge_count": len(edges),
                "speaker_count": len(per_speaker),
            },
            "per_speaker": per_speaker,
            "top_dyads": top_dyads,
        }

    def _compute_politeness(self, convokit, corpus) -> Optional[Dict[str, Any]]:
        try:
            politeness = convokit.PolitenessStrategies()
            corpus = politeness.transform(corpus)
            summary = politeness.summarize(corpus)
        except Exception as exc:
            logger.warning(f"Politeness analysis failed: {exc}")
            return {"error": str(exc)}

        if hasattr(summary, "to_dict"):
            try:
                summary = summary.to_dict(orient="records")
            except Exception:
                pass

        return {"summary": summary}

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        skipped = results.get("skipped", False)
        if skipped:
            output_service.save_data(
                results, "convokit_summary", format_type="json"
            )
            return

        output_service.save_data(
            results.get("coordination_edges", []),
            "convokit_coordination_edges",
            format_type="csv",
        )
        output_service.save_data(
            results.get("coordination_matrix", []),
            "convokit_coordination_matrix",
            format_type="csv",
        )
        output_service.save_data(
            results.get("coordination_summary", {}),
            "convokit_coordination_summary",
            format_type="json",
        )
        output_service.save_data(
            results.get("corpus_manifest", {}),
            "convokit_corpus_manifest",
            format_type="json",
        )

        politeness = results.get("politeness")
        if politeness:
            output_service.save_data(
                politeness,
                "convokit_politeness_summary",
                format_type="json",
            )

