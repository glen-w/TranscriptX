"""
Echoes analysis module for TranscriptX.

Detects explicit quotes, lexical echoes, and optional paraphrases.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.models.events import (
    Event,
    generate_event_id,
    sort_events_deterministically,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.similarity_utils import SimilarityCalculator
from transcriptx.io import save_csv, save_json
from transcriptx.core.utils.viz_ids import (
    VIZ_ECHOES_HEATMAP,
    VIZ_ECHOES_TIMELINE,
)
from transcriptx.core.viz.axis_utils import time_axis_display
from transcriptx.core.viz.specs import HeatmapMatrixSpec, LineTimeSeriesSpec

plt = lazy_pyplot()


EXPLICIT_QUOTE_PATTERNS = [
    "as you said",
    "like you said",
    "as you mentioned",
    "you mentioned",
    "to quote",
    "you're saying that",
    "you are saying that",
    "what i'm hearing is",
    "what i am hearing is",
]


class EchoesAnalysis(AnalysisModule):
    """Detect quote/echo/paraphrase links across segments."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "echoes"
        self.config = get_config().analysis.echoes
        self.similarity = SimilarityCalculator()
        self._embedding_model = None

    def _get_embedding_model(self):
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self._embedding_model = None
        return self._embedding_model

    def _token_count(self, text: str) -> int:
        return len([tok for tok in text.lower().split() if tok.strip()])

    def _is_trivial(self, text: str) -> bool:
        cleaned = text.strip().lower()
        if not cleaned:
            return True
        for phrase in getattr(self.config, "exclude_phrases", []):
            if cleaned == phrase.lower():
                return True
        return False

    def _speaker_for_segment(
        self, segment: Dict[str, Any], segments: List[Dict[str, Any]]
    ) -> str:
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        info = extract_speaker_info(segment)
        if info is None:
            return "UNKNOWN"
        return get_speaker_display_name(info.grouping_key, [segment], segments)

    def _collect_candidates(
        self,
        segments: List[Dict[str, Any]],
        current_idx: int,
        lookback_seconds: float,
        max_candidates: int,
    ) -> List[int]:
        current_start = segments[current_idx].get("start", 0.0)
        candidates = []
        for idx in range(current_idx - 1, -1, -1):
            seg = segments[idx]
            seg_start = seg.get("start", 0.0)
            if current_start - seg_start > lookback_seconds:
                break
            candidates.append(idx)
            if len(candidates) >= max_candidates:
                break
        return candidates

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        transcript_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not segments:
            return {"events": [], "stats": {}, "echo_network": []}

        from transcriptx.core.utils.canonicalization import (
            compute_transcript_identity_hash,
        )

        transcript_hash = transcript_hash or compute_transcript_identity_hash(segments)
        lookback_seconds = float(getattr(self.config, "lookback_seconds", 240.0))
        max_candidates = int(getattr(self.config, "max_candidates", 50))
        min_tokens = int(getattr(self.config, "min_tokens", 5))
        lexical_threshold = float(getattr(self.config, "lexical_echo_threshold", 0.6))
        paraphrase_threshold = float(getattr(self.config, "paraphrase_threshold", 0.75))
        explicit_quote_weight = float(
            getattr(self.config, "explicit_quote_weight", 1.0)
        )
        enable_semantic_paraphrase = bool(
            getattr(self.config, "enable_semantic_paraphrase", False)
        )

        events: List[Event] = []
        echo_edges = defaultdict(list)
        counts_by_kind = Counter()
        counts_by_speaker = defaultdict(Counter)

        for idx, seg in enumerate(segments):
            text = (seg.get("text") or "").strip()
            if self._is_trivial(text) or self._token_count(text) < min_tokens:
                continue

            speaker = self._speaker_for_segment(seg, segments)
            candidates = self._collect_candidates(
                segments, idx, lookback_seconds, max_candidates
            )

            # Tier A: explicit quote detection
            lower_text = text.lower()
            explicit_match = next(
                (p for p in EXPLICIT_QUOTE_PATTERNS if p in lower_text), None
            )
            if explicit_match and candidates:
                target_idx = candidates[0]
                target_seg = segments[target_idx]
                target_speaker = self._speaker_for_segment(target_seg, segments)
                if target_speaker != speaker:
                    event = Event(
                        event_id=generate_event_id(
                            transcript_hash,
                            "explicit_quote",
                            target_idx,
                            idx,
                            target_seg.get("start", 0.0),
                            seg.get("end", seg.get("start", 0.0)),
                        ),
                        kind="explicit_quote",
                        time_start=float(seg.get("start", 0.0)),
                        time_end=float(seg.get("end", seg.get("start", 0.0))),
                        speaker=speaker,
                        segment_start_idx=target_idx,
                        segment_end_idx=idx,
                        severity=min(1.0, explicit_quote_weight),
                        score=explicit_quote_weight,
                        evidence=[
                            {
                                "source": "echoes",
                                "feature": "explicit_quote",
                                "value": explicit_match,
                            }
                        ],
                        links=[
                            {"type": "segment", "idx": target_idx},
                            {"type": "segment", "idx": idx},
                        ],
                    )
                    events.append(event)
                    counts_by_kind[event.kind] += 1
                    counts_by_speaker[speaker][event.kind] += 1
                    echo_edges[(target_speaker, speaker)].append(event.score or 1.0)

            # Tier B: lexical echo
            candidate_scores: List[Tuple[int, float, str]] = []
            for cand_idx in candidates:
                cand_seg = segments[cand_idx]
                cand_text = (cand_seg.get("text") or "").strip()
                if (
                    self._is_trivial(cand_text)
                    or self._token_count(cand_text) < min_tokens
                ):
                    continue
                cand_speaker = self._speaker_for_segment(cand_seg, segments)
                if cand_speaker == speaker:
                    continue
                score = self.similarity.calculate_text_similarity(
                    cand_text, text, method="tfidf"
                )
                if score >= lexical_threshold:
                    candidate_scores.append((cand_idx, score, cand_speaker))

            candidate_scores.sort(key=lambda item: (-item[1], abs(idx - item[0])))

            # Deduplicate: keep top K with speaker diversity
            top_k = 3
            used_speakers = set()
            selected = []
            for cand_idx, score, cand_speaker in candidate_scores:
                if cand_speaker in used_speakers:
                    continue
                selected.append((cand_idx, score, cand_speaker))
                used_speakers.add(cand_speaker)
                if len(selected) >= top_k:
                    break
            if len(selected) < top_k:
                for cand in candidate_scores:
                    if cand in selected:
                        continue
                    selected.append(cand)
                    if len(selected) >= top_k:
                        break

            for cand_idx, score, cand_speaker in selected:
                cand_seg = segments[cand_idx]
                event = Event(
                    event_id=generate_event_id(
                        transcript_hash,
                        "echo",
                        cand_idx,
                        idx,
                        cand_seg.get("start", 0.0),
                        seg.get("end", seg.get("start", 0.0)),
                    ),
                    kind="echo",
                    time_start=float(seg.get("start", 0.0)),
                    time_end=float(seg.get("end", seg.get("start", 0.0))),
                    speaker=speaker,
                    segment_start_idx=cand_idx,
                    segment_end_idx=idx,
                    severity=min(1.0, score),
                    score=float(score),
                    evidence=[
                        {
                            "source": "echoes",
                            "feature": "lexical_similarity",
                            "value": float(score),
                        }
                    ],
                    links=[
                        {"type": "segment", "idx": cand_idx},
                        {"type": "segment", "idx": idx},
                    ],
                )
                events.append(event)
                counts_by_kind[event.kind] += 1
                counts_by_speaker[speaker][event.kind] += 1
                echo_edges[(cand_speaker, speaker)].append(event.score or 0.0)

            # Tier C: semantic paraphrase (optional)
            if enable_semantic_paraphrase:
                model = self._get_embedding_model()
                if model:
                    embeddings = model.encode(
                        [text]
                        + [(segments[c].get("text") or "").strip() for c in candidates],
                        show_progress_bar=False,
                    )
                    query_emb = embeddings[0]
                    for cand_idx, cand_emb in zip(
                        candidates, embeddings[1:], strict=False
                    ):
                        cand_seg = segments[cand_idx]
                        cand_text = (cand_seg.get("text") or "").strip()
                        if (
                            self._is_trivial(cand_text)
                            or self._token_count(cand_text) < min_tokens
                        ):
                            continue
                        cand_speaker = self._speaker_for_segment(cand_seg, segments)
                        if cand_speaker == speaker:
                            continue
                        sim = float(
                            np.dot(query_emb, cand_emb)
                            / (
                                np.linalg.norm(query_emb) * np.linalg.norm(cand_emb)
                                + 1e-8
                            )
                        )
                        if sim >= paraphrase_threshold:
                            event = Event(
                                event_id=generate_event_id(
                                    transcript_hash,
                                    "paraphrase",
                                    cand_idx,
                                    idx,
                                    cand_seg.get("start", 0.0),
                                    seg.get("end", seg.get("start", 0.0)),
                                ),
                                kind="paraphrase",
                                time_start=float(seg.get("start", 0.0)),
                                time_end=float(seg.get("end", seg.get("start", 0.0))),
                                speaker=speaker,
                                segment_start_idx=cand_idx,
                                segment_end_idx=idx,
                                severity=min(1.0, sim),
                                score=sim,
                                evidence=[
                                    {
                                        "source": "echoes",
                                        "feature": "semantic_similarity",
                                        "value": sim,
                                    }
                                ],
                                links=[
                                    {"type": "segment", "idx": cand_idx},
                                    {"type": "segment", "idx": idx},
                                ],
                            )
                            events.append(event)
                            counts_by_kind[event.kind] += 1
                            counts_by_speaker[speaker][event.kind] += 1
                            echo_edges[(cand_speaker, speaker)].append(
                                event.score or 0.0
                            )

        # Echo burst detection
        burst_events = self._detect_echo_bursts(events, transcript_hash)
        events.extend(burst_events)
        for event in burst_events:
            counts_by_kind[event.kind] += 1

        echo_network_rows = []
        for (from_speaker, to_speaker), scores in echo_edges.items():
            if not from_speaker or not to_speaker:
                continue
            echo_network_rows.append(
                {
                    "from_speaker": from_speaker,
                    "to_speaker": to_speaker,
                    "count": len(scores),
                    "avg_score": float(np.mean(scores)) if scores else 0.0,
                }
            )

        stats = {
            "total_events": len(events),
            "counts_by_kind": dict(counts_by_kind),
            "counts_by_speaker": {
                speaker: dict(counts) for speaker, counts in counts_by_speaker.items()
            },
        }

        return {"events": events, "stats": stats, "echo_network": echo_network_rows}

    def _detect_echo_bursts(
        self, events: List[Event], transcript_hash: str
    ) -> List[Event]:
        window_seconds = float(getattr(self.config, "echo_burst_window_seconds", 25.0))
        min_events = int(getattr(self.config, "echo_burst_min_events", 3))
        percentile_threshold = float(
            getattr(self.config, "echo_burst_percentile_threshold", 0.95)
        )

        echo_events = [
            e for e in events if e.kind in {"echo", "paraphrase", "explicit_quote"}
        ]
        if not echo_events:
            return []

        echo_events = sort_events_deterministically(echo_events)
        counts = []
        for idx, event in enumerate(echo_events):
            window_end = event.time_start + window_seconds
            count = sum(1 for e in echo_events[idx:] if e.time_start <= window_end)
            counts.append(count)
        count_threshold = max(
            min_events, int(np.percentile(counts, percentile_threshold * 100))
        )

        bursts: List[Event] = []
        idx = 0
        while idx < len(echo_events):
            window_start = echo_events[idx].time_start
            window_end = window_start + window_seconds
            window_events = [e for e in echo_events[idx:] if e.time_start <= window_end]
            if len(window_events) >= count_threshold:
                burst_start = window_events[0].time_start
                burst_end = window_events[-1].time_end
                segment_start = window_events[0].segment_start_idx
                segment_end = window_events[-1].segment_end_idx
                bursts.append(
                    Event(
                        event_id=generate_event_id(
                            transcript_hash,
                            "echo_burst",
                            segment_start,
                            segment_end,
                            burst_start,
                            burst_end,
                        ),
                        kind="echo_burst",
                        time_start=burst_start,
                        time_end=burst_end,
                        speaker=None,
                        segment_start_idx=segment_start,
                        segment_end_idx=segment_end,
                        severity=min(1.0, len(window_events) / max(count_threshold, 1)),
                        score=float(len(window_events)),
                        evidence=[
                            {
                                "source": "echoes",
                                "feature": "echo_burst_count",
                                "value": len(window_events),
                            }
                        ],
                        links=[
                            {"type": "event", "event_id": e.event_id}
                            for e in window_events
                        ],
                    )
                )
                idx += len(window_events)
            else:
                idx += 1

        return bursts

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_complete,
                log_analysis_error,
                log_analysis_start,
            )
            from transcriptx.core.output.output_service import create_output_service

            log_analysis_start(self.module_name, context.transcript_path)
            results = self.analyze(
                context.get_segments(),
                context.get_speaker_map(),
                transcript_hash=context.transcript_key,
            )

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
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "success",
                "results": results,
                "output_directory": str(
                    output_service.get_output_structure().module_dir
                ),
            }
        except Exception as exc:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(exc))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(exc),
                "results": {},
            }

    def save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_structure = output_service.get_output_structure()
        os.makedirs(output_structure.global_data_dir, exist_ok=True)
        os.makedirs(output_structure.global_charts_dir, exist_ok=True)

        events: List[Event] = results.get("events", [])
        stats: Dict[str, Any] = results.get("stats", {})
        echo_network: List[Dict[str, Any]] = results.get("echo_network", [])

        save_events_json(events, output_structure, "echoes.events.json")
        save_json(stats, str(output_structure.global_data_dir / "echoes.stats.json"))

        if echo_network:
            save_csv(
                [
                    [
                        row["from_speaker"],
                        row["to_speaker"],
                        row["count"],
                        row["avg_score"],
                    ]
                    for row in echo_network
                ],
                str(output_structure.global_data_dir / "echo_network.csv"),
                header=["from_speaker", "to_speaker", "count", "avg_score"],
            )

        # Heatmap chart
        speakers = sorted(
            {row["from_speaker"] for row in echo_network}
            | {row["to_speaker"] for row in echo_network}
        )
        if speakers:
            index = {speaker: idx for idx, speaker in enumerate(speakers)}
            matrix = np.zeros((len(speakers), len(speakers)))
            for row in echo_network:
                matrix[index[row["from_speaker"]], index[row["to_speaker"]]] = row[
                    "count"
                ]
            spec = HeatmapMatrixSpec(
                viz_id=VIZ_ECHOES_HEATMAP,
                module=self.module_name,
                name="echo_heatmap",
                scope="global",
                chart_intent="heatmap_matrix",
                title="Echo Network Heatmap",
                x_label="To Speaker",
                y_label="From Speaker",
                z=matrix.tolist(),
                x_labels=speakers,
                y_labels=speakers,
            )
            output_service.save_chart(spec, chart_type="heatmap")

        # Timeline chart
        timeline_events = [
            e for e in events if e.kind in {"echo", "paraphrase", "explicit_quote"}
        ]
        if timeline_events:
            xs = [e.time_start for e in timeline_events]
            x_display, x_label = time_axis_display(xs)
            ys = [e.score or e.severity for e in timeline_events]
            spec = LineTimeSeriesSpec(
                viz_id=VIZ_ECHOES_TIMELINE,
                module=self.module_name,
                name="echo_timeline",
                scope="global",
                chart_intent="line_timeseries",
                title="Echo Timeline",
                x_label=x_label,
                y_label="Score",
                markers=True,
                series=[{"name": "Echo", "x": x_display, "y": ys}],
            )
            output_service.save_chart(spec, chart_type="timeline")

        output_service.save_summary(stats, {}, analysis_metadata={})
