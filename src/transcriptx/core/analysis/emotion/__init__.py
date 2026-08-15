"""
Lexical emotion analysis (NRCLex) — emotion-associated vocabulary, not inferred speaker emotion.

Semantics: emotion_lexical_v2. Does not load HF classifiers or fill context_emotion_*.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.affect.output_helpers import write_enriched_transcript
from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.emotion.lexical_pipeline import (
    NRC_LEXICAL_PIPELINE_V1,
    PLUTCHIK_EIGHT,
    SCHEMA_VERSION,
    SEMANTICS_VERSION,
    VALENCE_KEYS,
    build_lexicon_from_nrclex,
    score_segment_text,
    sum_assignment_maps,
    normalize_profile,
)
from transcriptx.core.analysis.emotion.preflight import run_lexical_preflight
from transcriptx.core.analysis.emotion.projections import (
    apply_lexical_projection,
    clear_lexical_projection,
    project_lexical_segment,
)
from transcriptx.core.analysis.emotion_family.canonical_hash import canonical_json_hash
from transcriptx.core.analysis.emotion_family.fingerprints import (
    build_compatibility_payload,
    build_runtime_metadata,
    compatibility_fingerprint,
    speaker_identity_digest,
    text_source_digest,
    timeline_identity_digest,
)
from transcriptx.core.analysis.emotion_family.cache_validation import (
    validate_lexical_cache_row,
)
from transcriptx.core.analysis.emotion_family.language import (
    LANGUAGE_POLICY_V1,
    is_english,
)
from transcriptx.core.analysis.emotion_family.work_items import (
    build_segment_work_items,
)
from transcriptx.core.analysis.emotion_family.persist import (
    persist_canonical_then_enrich,
)
from transcriptx.core.analysis.emotion_family.run_status import (
    RunStatus,
    derive_run_status_from_rows,
    derive_usable_output,
)
from transcriptx.core.analysis.emotion_family.source_identity import ensure_segment_ids
from transcriptx.core.analysis.emotion_family.split_cache import (
    AggregationCacheStore,
    InferenceCacheStore,
    aggregation_cache_key,
    default_aggregation_cache_root,
    default_inference_cache_root,
    inference_cache_key,
    module_cache_fingerprint,
)
from transcriptx.core.utils.logger import get_logger, log_info, log_warning
from transcriptx.core.utils.viz_ids import (
    VIZ_EMOTION_RADAR_GLOBAL,
    VIZ_EMOTION_RADAR_SPEAKER,
)
from transcriptx.core.viz.specs import BarCategoricalSpec
from transcriptx.utils.text_utils import is_analysis_speaker_label

logger = get_logger()

AGGREGATION_SEMANTICS_V1 = "emotion_aggregation_v1"


class EmotionAnalysis(AnalysisModule):
    """NRC lexical emotion-associated vocabulary analysis."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "emotion"
        self._lexicon: dict[str, list[str]] | None = None
        self._nrclex_cls = None

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        artifact_generation_id = uuid.uuid4().hex
        preflight = run_lexical_preflight()
        if not preflight.ok:
            log_warning("EMOTION", f"Lexical preflight failed: {preflight.details}")
            return self._empty_failed_result(
                segments,
                artifact_generation_id,
                run_status=RunStatus.SKIPPED,
                reason=preflight.reason,
                details=preflight.details or {},
                nrclex_version=preflight.nrclex_version,
            )

        from nrclex import NRCLex

        self._nrclex_cls = NRCLex
        self._lexicon = build_lexicon_from_nrclex(NRCLex)
        if not self._lexicon:
            return self._empty_failed_result(
                segments,
                artifact_generation_id,
                run_status=RunStatus.SKIPPED,
                reason="lexical_preflight_failed",
                details={"error": "empty_lexicon"},
                nrclex_version=preflight.nrclex_version,
            )

        lexicon_digest = canonical_json_hash(
            {k: sorted(v) for k, v in sorted(self._lexicon.items())}
        )
        nrclex_version = preflight.nrclex_version

        try:
            ensure_segment_ids(segments)
        except ValueError as exc:
            return self._empty_failed_result(
                segments,
                artifact_generation_id,
                run_status=RunStatus.FAILED,
                reason="invalid_segment_ids",
                details={"message": str(exc)},
                nrclex_version=nrclex_version,
                lexicon_digest=lexicon_digest,
            )

        try:
            text_digest = text_source_digest(segments)
        except ValueError as exc:
            return self._empty_failed_result(
                segments,
                artifact_generation_id,
                run_status=RunStatus.FAILED,
                reason="invalid_segment_ids",
                details={"message": str(exc)},
                nrclex_version=nrclex_version,
                lexicon_digest=lexicon_digest,
            )

        speaker_digest = speaker_identity_digest(segments)
        timeline_digest = timeline_identity_digest(segments)

        compat_payload = build_compatibility_payload(
            schema_version=SCHEMA_VERSION,
            semantics_version=SEMANTICS_VERSION,
            lexical_pipeline_version=NRC_LEXICAL_PIPELINE_V1,
            language_policy_version=LANGUAGE_POLICY_V1,
            numerical_dtype="n/a",
            lexicon_digest=lexicon_digest,
            nrclex_version=nrclex_version,
            extra={"aggregation_semantics": AGGREGATION_SEMANTICS_V1},
        )
        compat_fp = compatibility_fingerprint(compat_payload)
        runtime_metadata = build_runtime_metadata(
            activation="lexical",
            language_policy_version=LANGUAGE_POLICY_V1,
            lexicon_digest=lexicon_digest,
            nrclex_version=nrclex_version,
        )
        inference_key = inference_cache_key(
            compatibility_fingerprint=compat_fp, text_source_digest=text_digest
        )

        cache_store: InferenceCacheStore | None = None
        try:
            cache_store = InferenceCacheStore(
                default_inference_cache_root(self.module_name)
            )
        except Exception as exc:
            log_warning("EMOTION", f"inference cache unavailable: {exc}")

        cached_rows: dict[str, dict[str, Any]] | None = None
        inference_cache_hit = False
        inference_generation_id = artifact_generation_id
        needed_sids = [
            str(seg.get("id") or seg.get("segment_id"))
            for seg in segments
            if (seg.get("text") or "").strip()
        ]
        if cache_store is not None:
            cached = cache_store.load(inference_key)
            if cached:
                rows = cached.get("rows_by_segment") or {}
                if needed_sids and all(
                    sid in rows and validate_lexical_cache_row(rows[sid])
                    for sid in needed_sids
                ):
                    cached_rows = rows
                    inference_cache_hit = True
                    cached_inference_id = str(
                        cached.get("inference_generation_id") or ""
                    ).strip()
                    if cached_inference_id:
                        inference_generation_id = cached_inference_id

        from transcriptx.core.utils.config import get_config

        lex_cfg = getattr(get_config().analysis, "emotion", None)
        raw_no_hit = getattr(lex_cfg, "no_hit_rate_warn", None)
        no_hit_warn = 0.8 if raw_no_hit is None else float(raw_no_hit)
        raw_low_cov = getattr(lex_cfg, "low_coverage_threshold", None)
        low_cov_th = 0.05 if raw_low_cov is None else float(raw_low_cov)
        aggregation_settings = {
            "no_hit_rate_warn": no_hit_warn,
            "low_coverage_threshold": low_cov_th,
        }

        agg_key = aggregation_cache_key(
            inference_generation_id=inference_generation_id,
            speaker_identity_digest=speaker_digest,
            timeline_identity_digest=timeline_digest,
            aggregation_semantics_version=AGGREGATION_SEMANTICS_V1,
            aggregation_settings=aggregation_settings,
        )

        # Work items only after cache lookup (preserve call-order / failure timing).
        work, assumed_en_warnings = build_segment_work_items(segments)

        canonical_rows: list[dict[str, Any]] = []
        pending_projections: list[tuple[dict[str, Any], dict[str, Any]]] = []
        speaker_assignments: dict[str, list[dict[str, int]]] = defaultdict(list)
        speaker_valence: dict[str, list[dict[str, int]]] = defaultdict(list)
        segments_scored = 0
        segments_skipped = 0
        segments_empty = 0
        scored_for_cache: dict[str, dict[str, Any]] = {}

        for item in work:
            seg = item.seg
            speaker = item.speaker
            sid = item.sid
            lang = item.lang
            lang_res = item.lang_res

            if not is_english(lang):
                segments_skipped += 1
                row = {
                    "segment_id": sid,
                    "speaker": speaker,
                    "evaluation_state": "skipped",
                    "skip_reason": "unsupported_language",
                    "language": lang,
                    "language_resolution": lang_res,
                    "scored_text_hash": item.text_hash,
                    "coverage": 0.0,
                    "tokens_considered": 0,
                    "matched_occurrences": 0,
                    "assignment_counts": {k: 0 for k in PLUTCHIK_EIGHT},
                    "valence_assignment_counts": {k: 0 for k in VALENCE_KEYS},
                    "emotion_scores": {k: 0.0 for k in PLUTCHIK_EIGHT},
                    "valence_scores": {k: 0.0 for k in VALENCE_KEYS},
                    "contributing": [],
                }
                canonical_rows.append(row)
                proj = project_lexical_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                pending_projections.append((seg, proj))
                continue

            reused = (
                cached_rows.get(sid)
                if inference_cache_hit and cached_rows is not None
                else None
            )
            if reused is not None:
                result_state = reused.get("evaluation_state") or "scored"
                coverage = float(reused.get("coverage") or 0.0)
                tokens_considered = int(reused.get("tokens_considered") or 0)
                matched_occurrences = int(reused.get("matched_occurrences") or 0)
                assignment_counts = dict(
                    reused.get("assignment_counts") or {k: 0 for k in PLUTCHIK_EIGHT}
                )
                valence_assignment_counts = dict(
                    reused.get("valence_assignment_counts")
                    or {k: 0 for k in VALENCE_KEYS}
                )
                emotion_scores = dict(
                    reused.get("emotion_scores") or {k: 0.0 for k in PLUTCHIK_EIGHT}
                )
                valence_scores = dict(
                    reused.get("valence_scores") or {k: 0.0 for k in VALENCE_KEYS}
                )
                contributing = list(reused.get("contributing") or [])
            else:
                # Score original segment text (not work.text) — locked policy.
                result = score_segment_text(
                    seg.get("text") or "",
                    self._lexicon,
                    language_resolution=lang_res,
                )
                result_state = result.evaluation_state
                coverage = result.coverage
                tokens_considered = result.tokens_considered
                matched_occurrences = result.matched_occurrences
                assignment_counts = result.assignment_counts
                valence_assignment_counts = result.valence_assignment_counts
                emotion_scores = result.emotion_scores
                valence_scores = result.valence_scores
                contributing = result.contributing

            if result_state == "empty":
                segments_empty += 1
            elif result_state == "scored":
                segments_scored += 1

            text_hash = item.text_hash
            row = {
                "segment_id": sid,
                "speaker": speaker,
                "evaluation_state": result_state,
                "language": lang,
                "language_resolution": lang_res,
                "scored_text_hash": text_hash,
                "coverage": coverage,
                "tokens_considered": tokens_considered,
                "matched_occurrences": matched_occurrences,
                "assignment_counts": assignment_counts,
                "valence_assignment_counts": valence_assignment_counts,
                "emotion_scores": emotion_scores,
                "valence_scores": valence_scores,
                "contributing": contributing,
            }
            canonical_rows.append(row)
            # Inference cache stores speaker-free score rows only.
            scored_for_cache[sid] = {
                "evaluation_state": result_state,
                "scored_text_hash": text_hash,
                "coverage": coverage,
                "tokens_considered": tokens_considered,
                "matched_occurrences": matched_occurrences,
                "assignment_counts": assignment_counts,
                "valence_assignment_counts": valence_assignment_counts,
                "emotion_scores": emotion_scores,
                "valence_scores": valence_scores,
                "contributing": contributing,
            }

            # Enriched lightweight projection (no full vectors required beyond nrc_emotion)
            proj = project_lexical_segment(
                row,
                artifact_generation_id=artifact_generation_id,
                schema_version=SCHEMA_VERSION,
            )
            pending_projections.append((seg, proj))

            if is_analysis_speaker_label(speaker) and result_state == "scored":
                speaker_assignments[speaker].append(assignment_counts)
                speaker_valence[speaker].append(valence_assignment_counts)

        if cache_store is not None and not inference_cache_hit and scored_for_cache:
            try:
                cache_store.store(
                    inference_key,
                    inference_generation_id=inference_generation_id,
                    rows_by_segment=scored_for_cache,
                )
            except Exception as exc:
                log_warning("EMOTION", f"inference cache write failed: {exc}")

        speaker_stats: dict[str, Any] = {}
        speaker_coverage_acc: dict[str, list[float]] = defaultdict(list)
        speaker_tokens: dict[str, int] = defaultdict(int)
        speaker_matches: dict[str, int] = defaultdict(int)
        speaker_zero_hit: dict[str, int] = defaultdict(int)
        speaker_scored_n: dict[str, int] = defaultdict(int)

        for speaker, maps in speaker_assignments.items():
            summed = sum_assignment_maps(maps, PLUTCHIK_EIGHT)
            vsummed = sum_assignment_maps(speaker_valence[speaker], VALENCE_KEYS)
            speaker_stats[speaker] = {
                "assignment_counts": summed,
                "emotion_scores": normalize_profile(summed, PLUTCHIK_EIGHT),
                "valence_assignment_counts": vsummed,
                "valence_scores": normalize_profile(vsummed, VALENCE_KEYS),
                **normalize_profile(summed, PLUTCHIK_EIGHT),
            }

        for r in canonical_rows:
            if r["evaluation_state"] != "scored":
                continue
            sp = r.get("speaker") or ""
            if not is_analysis_speaker_label(sp):
                continue
            speaker_scored_n[sp] += 1
            speaker_tokens[sp] += int(r.get("tokens_considered") or 0)
            speaker_matches[sp] += int(r.get("matched_occurrences") or 0)
            speaker_coverage_acc[sp].append(float(r.get("coverage") or 0.0))
            if int(r.get("matched_occurrences") or 0) == 0:
                speaker_zero_hit[sp] += 1

        for sp, st in speaker_stats.items():
            n = max(speaker_scored_n.get(sp, 0), 1)
            covs = speaker_coverage_acc.get(sp) or []
            st["tokens_considered"] = speaker_tokens.get(sp, 0)
            st["matched_occurrences"] = speaker_matches.get(sp, 0)
            st["mean_coverage"] = sum(covs) / len(covs) if covs else 0.0
            st["zero_hit_segments"] = speaker_zero_hit.get(sp, 0)
            st["no_hit_rate"] = speaker_zero_hit.get(sp, 0) / n

        global_assignments = sum_assignment_maps(
            [
                r["assignment_counts"]
                for r in canonical_rows
                if r["evaluation_state"] == "scored"
            ],
            PLUTCHIK_EIGHT,
        )
        global_valence = sum_assignment_maps(
            [
                r["valence_assignment_counts"]
                for r in canonical_rows
                if r["evaluation_state"] == "scored"
            ],
            VALENCE_KEYS,
        )
        scored_rows = [r for r in canonical_rows if r["evaluation_state"] == "scored"]
        zero_hit = sum(
            1 for r in scored_rows if int(r.get("matched_occurrences") or 0) == 0
        )
        total_tokens = sum(int(r.get("tokens_considered") or 0) for r in scored_rows)
        total_matches = sum(int(r.get("matched_occurrences") or 0) for r in scored_rows)
        mean_coverage = (
            sum(float(r.get("coverage") or 0.0) for r in scored_rows) / len(scored_rows)
            if scored_rows
            else 0.0
        )
        global_stats = {
            "assignment_counts": global_assignments,
            "emotion_scores": normalize_profile(global_assignments, PLUTCHIK_EIGHT),
            "valence_assignment_counts": global_valence,
            "valence_scores": normalize_profile(global_valence, VALENCE_KEYS),
            "tokens_considered": total_tokens,
            "matched_occurrences": total_matches,
            "mean_coverage": mean_coverage,
            "zero_hit_segments": zero_hit,
            "no_hit_rate": zero_hit / max(len(scored_rows), 1),
            **normalize_profile(global_assignments, PLUTCHIK_EIGHT),
        }

        run_status, segments_scored, segments_failed = derive_run_status_from_rows(
            canonical_rows
        )
        # Preserve empty/skip counts already tracked; override scored from rows
        usable = derive_usable_output(
            run_status=run_status, segments_scored=segments_scored
        )
        warnings = []
        if assumed_en_warnings:
            warnings.append(
                f"{assumed_en_warnings} segment(s) assumed English (missing language metadata)"
            )
        no_hit = zero_hit
        if segments_scored and no_hit / max(segments_scored, 1) > no_hit_warn:
            warnings.append(
                "low_lexical_coverage: high no-hit rate among scored segments"
            )
        if segments_scored and mean_coverage < low_cov_th:
            warnings.append(
                f"low_lexical_coverage: mean coverage {mean_coverage:.3f} "
                f"below threshold {low_cov_th}"
            )

        aggregation_cache_hit = False
        try:
            agg_store = AggregationCacheStore(
                default_aggregation_cache_root(self.module_name)
            )
            cached_agg = agg_store.load(agg_key)
            if cached_agg and isinstance(cached_agg.get("aggregates"), dict):
                aggregates = cached_agg["aggregates"]
                speaker_stats = aggregates.get("speaker_stats") or speaker_stats
                global_stats = aggregates.get("global_stats") or global_stats
                aggregation_cache_hit = True
            else:
                agg_store.store(
                    agg_key,
                    inference_generation_id=inference_generation_id,
                    aggregates={
                        "speaker_stats": speaker_stats,
                        "global_stats": global_stats,
                    },
                )
        except Exception as exc:
            log_warning("EMOTION", f"aggregation cache unavailable: {exc}")

        log_info(
            "EMOTION",
            f"lexical v2 complete: scored={segments_scored} skipped={segments_skipped} "
            f"empty={segments_empty} failed={segments_failed} usable={usable} "
            f"cache_hit={inference_cache_hit}",
        )

        # Projections stay pending until canonical persist succeeds (_save_results).
        result = {
            "schema_version": SCHEMA_VERSION,
            "semantics_version": SEMANTICS_VERSION,
            "module_id": self.module_name,
            "run_status": run_status.value,
            "usable_output": usable,
            "segments_scored": segments_scored,
            "segments_failed": segments_failed,
            "segments_skipped": segments_skipped,
            "segments_empty": segments_empty,
            "artifact_generation_id": artifact_generation_id,
            "inference_generation_id": inference_generation_id,
            "ordered_segment_ids": [
                str(s.get("id") or s.get("segment_id")) for s in segments
            ],
            "compatibility_fingerprint": compat_fp,
            "text_source_digest": text_digest,
            "speaker_identity_digest": speaker_digest,
            "timeline_identity_digest": timeline_digest,
            "inference_cache_key": inference_key,
            "aggregation_cache_key": agg_key,
            "cache_fingerprint": module_cache_fingerprint(
                inference_key=inference_key, aggregation_key=agg_key
            ),
            "inference_cache_hit": inference_cache_hit,
            "aggregation_cache_hit": aggregation_cache_hit,
            "aggregation_semantics_version": AGGREGATION_SEMANTICS_V1,
            "_canonical_rows": canonical_rows,
            "_pending_projections": pending_projections,
            "segments_with_emotion": segments,
            "nrc_scores": {
                sp: st.get("emotion_scores", st) for sp, st in speaker_stats.items()
            },
            "speaker_stats": speaker_stats,
            "global_stats": global_stats,
            "all_scores": global_stats.get("emotion_scores", global_stats),
            "emotions": global_stats.get("emotion_scores", global_stats),
            "combined_rows": [
                {"speaker": sp, **st.get("emotion_scores", {})}
                for sp, st in speaker_stats.items()
            ],
            "warnings": warnings,
            "ui_copy": (
                "Emotion-associated vocabulary (NRC lexicon), "
                "not a definitive inference of speaker emotion."
            ),
            "method": "nrc_lexical",
            "release_channel": "stable",
            "lexicon_digest": lexicon_digest,
            "nrclex_version": nrclex_version,
            "runtime_metadata": runtime_metadata,
            "projection_fields": [
                "segment_id",
                "evaluation_state",
                "nrc_emotion",
                "nrc_emotion_coverage",
                "emotion_scored_text_hash",
                "canonical_ref",
            ],
            "sample_projection": {
                "segment_id": None,
                "evaluation_state": None,
                "nrc_emotion": {},
                "nrc_emotion_coverage": 0.0,
                "emotion_scored_text_hash": "",
                "canonical_ref": {},
            },
            "contextual_all": {},
            "contextual_examples": {},
        }
        if pending_projections:
            sample = pending_projections[0][1]
            result["sample_projection"] = {
                field: sample.get(field)
                for field in result["projection_fields"]
                if field in sample or field == "evaluation_state"
            }
            if "evaluation_state" in sample:
                result["sample_projection"]["evaluation_state"] = sample.get(
                    "evaluation_state"
                )
        result["segments"] = segments
        return result

    def _empty_failed_result(
        self,
        segments: List[Dict[str, Any]],
        generation_id: str,
        *,
        run_status: RunStatus,
        reason: str,
        details: dict[str, Any],
        nrclex_version: str | None = None,
        lexicon_digest: str | None = None,
    ) -> Dict[str, Any]:
        for seg in segments:
            clear_lexical_projection(seg)
        return {
            "schema_version": SCHEMA_VERSION,
            "semantics_version": SEMANTICS_VERSION,
            "module_id": self.module_name,
            "run_status": run_status.value,
            "usable_output": False,
            "segments_scored": 0,
            "segments_skipped": 0,
            "segments_empty": 0,
            "segments_failed": 0,
            "artifact_generation_id": generation_id,
            "inference_generation_id": generation_id,
            "ordered_segment_ids": [],
            "preflight_reason": reason,
            "preflight_details": details,
            "segments_with_emotion": segments,
            "nrc_scores": {},
            "speaker_stats": {},
            "global_stats": {},
            "all_scores": {},
            "emotions": {},
            "combined_rows": [],
            "_canonical_rows": [],
            "_pending_projections": [],
            "lexicon_digest": lexicon_digest,
            "nrclex_version": nrclex_version,
            "runtime_metadata": build_runtime_metadata(
                activation="lexical",
                language_policy_version=LANGUAGE_POLICY_V1,
                lexicon_digest=lexicon_digest,
                nrclex_version=nrclex_version,
            ),
            "projection_fields": [
                "segment_id",
                "evaluation_state",
                "nrc_emotion",
                "nrc_emotion_coverage",
                "emotion_scored_text_hash",
                "canonical_ref",
            ],
            "contextual_all": {},
            "contextual_examples": {},
            "warnings": [reason],
            "ui_copy": (
                "Emotion-associated vocabulary (NRC lexicon), "
                "not a definitive inference of speaker emotion."
            ),
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        def write_enriched():
            segments = results["segments_with_emotion"]
            pending = results.pop("_pending_projections", None)
            if pending:
                for seg, proj in pending:
                    apply_lexical_projection(seg, proj)
            write_enriched_transcript(output_service, segments, "emotion")

        def after_enrich():
            output_service.save_data(
                {
                    "schema_version": results.get("schema_version"),
                    "semantics_version": results.get("semantics_version"),
                    "module_id": results.get("module_id"),
                    "run_status": results.get("run_status"),
                    "usable_output": results.get("usable_output"),
                    "segments_scored": results.get("segments_scored"),
                    "compatibility_fingerprint": results.get(
                        "compatibility_fingerprint"
                    ),
                    "artifact_generation_id": results.get("artifact_generation_id"),
                    "inference_generation_id": results.get("inference_generation_id"),
                    "warnings": results.get("warnings"),
                    "ui_copy": results.get("ui_copy"),
                },
                "lexical_emotion_canonical",
                format_type="json",
            )

            nrc_scores = results.get("nrc_scores") or {}
            combined_rows = results.get("combined_rows") or []
            output_service.save_data(
                nrc_scores, "nrc_emotion_scores", format_type="json"
            )
            output_service.save_data(
                combined_rows, "nrc_emotion_scores", format_type="csv"
            )

            # Absolute count bars (assignment counts) preferred over relative-only radar
            global_counts = (results.get("global_stats") or {}).get(
                "assignment_counts"
            ) or {}
            if global_counts:
                spec = BarCategoricalSpec(
                    viz_id=VIZ_EMOTION_RADAR_GLOBAL,
                    module=self.module_name,
                    name="emotion_assignment_counts",
                    scope="global",
                    chart_intent="bar_categorical",
                    title="Emotion-associated vocabulary counts (all speakers)",
                    x_label="Category",
                    y_label="Assignment count",
                    categories=list(PLUTCHIK_EIGHT),
                    values=[float(global_counts.get(k, 0)) for k in PLUTCHIK_EIGHT],
                )
                output_service.save_chart(spec, chart_type="bar")

            for speaker, scores in nrc_scores.items():
                speaker_safe = speaker.replace(" ", "_")
                output_service.save_data(
                    scores,
                    f"{speaker_safe}_nrc_emotion",
                    format_type="json",
                    subdirectory="speakers",
                    speaker=speaker,
                )
                st = (results.get("speaker_stats") or {}).get(speaker) or {}
                counts = st.get("assignment_counts") or {}
                if counts:
                    spec = BarCategoricalSpec(
                        viz_id=VIZ_EMOTION_RADAR_SPEAKER,
                        module=self.module_name,
                        name="emotion_assignment_counts",
                        scope="speaker",
                        speaker=speaker,
                        chart_intent="bar_categorical",
                        title=f"Emotion-associated vocabulary counts: {speaker}",
                        x_label="Category",
                        y_label="Assignment count",
                        categories=list(PLUTCHIK_EIGHT),
                        values=[float(counts.get(k, 0)) for k in PLUTCHIK_EIGHT],
                    )
                    output_service.save_chart(spec, chart_type="bar")

            output_service.save_summary(
                results.get("global_stats") or {},
                results.get("speaker_stats") or {},
                analysis_metadata={
                    "schema_version": results.get("schema_version"),
                    "semantics_version": results.get("semantics_version"),
                    "run_status": results.get("run_status"),
                    "usable_output": results.get("usable_output"),
                    "ui_copy": results.get("ui_copy"),
                },
            )

        persist_canonical_then_enrich(
            results=results,
            output_service=output_service,
            module_id=self.module_name,
            log_prefix="EMOTION",
            write_enriched=write_enriched,
            after_enrich=after_enrich,
            clear_owned_fields=clear_lexical_projection,
        )


def compute_nrc_emotions(text: str) -> dict:
    """Standalone helper: Plutchik eight-category shares for text."""
    pre = run_lexical_preflight()
    if not pre.ok:
        return {}
    from nrclex import NRCLex

    lexicon = build_lexicon_from_nrclex(NRCLex)
    result = score_segment_text(text or "", lexicon)
    return dict(result.emotion_scores)
