"""Fine-grained multi-label emotion (GoEmotions-style, experimental until Phase 5)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.affect.output_helpers import write_enriched_transcript
from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.emotion_family.cache_validation import (
    validate_classifier_cache_row,
)
from transcriptx.core.analysis.emotion_family.fingerprints import (
    build_aggregation_settings,
    build_compatibility_payload,
    build_display_fingerprint,
    build_runtime_metadata,
    compatibility_fingerprint,
    library_versions,
    segment_text_hash,
    speaker_identity_digest,
    text_source_digest,
    timeline_identity_digest,
)
from transcriptx.core.analysis.emotion_family.language import (
    LANGUAGE_POLICY_V1,
    extract_transcript_metadata,
    is_english,
    resolve_segment_language,
)
from transcriptx.core.analysis.emotion_family.persist import (
    persist_canonical_then_enrich,
)
from transcriptx.core.analysis.emotion_family.run_status import (
    AnalyticalOutcome,
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
from transcriptx.core.analysis.fine_grained_emotion.projections import (
    FAMILY_ONTOLOGY_V1,
    apply_fine_grained_projection,
    project_fine_grained_segment,
)
from transcriptx.core.analysis.hf_text_classification import (
    LONG_TEXT_POLICY_V2,
    load_classifier,
    score_texts,
)
from transcriptx.core.analysis.hf_text_classification.profiles import (
    FINE_GRAINED_GOEMOTIONS_V1,
    THRESHOLD_PROFILE_PROVISIONAL_V0,
    get_builtin_profile,
)
from transcriptx.core.utils.logger import get_logger, log_info, log_warning
from transcriptx.utils.text_utils import is_named_speaker

logger = get_logger()

SCHEMA_VERSION = "fine_grained_emotion_result_schema_v2"
SEMANTICS_VERSION = "fine_grained_emotion_v1"
PROVISIONAL_LABEL_THRESHOLD = 0.28
DEFAULT_MAX_LABELS = 3

_RESULT_SAVE_KEYS = (
    "schema_version",
    "semantics_version",
    "module_id",
    "run_status",
    "usable_output",
    "segments_scored",
    "segments_failed",
    "compatibility_fingerprint",
    "display_fingerprint",
    "artifact_generation_id",
    "inference_generation_id",
    "runtime_metadata",
    "enriched_projection_status",
    "primary_rates",
    "native_label_prevalence",
    "release_channel",
    "warnings",
    "family_ontology_version",
    "profile_id",
    "label_threshold",
)


def order_display_labels(
    qualifying: list[str],
    scores: dict[str, float],
    canonical_labels: tuple[str, ...],
    max_labels: int,
) -> list[str]:
    """Emotion by score desc, tie by canonical index; neutral last; then cap."""
    index = {lab: i for i, lab in enumerate(canonical_labels)}
    emotions = [lab for lab in qualifying if lab != "neutral"]
    emotions.sort(key=lambda lab: (-scores.get(lab, 0.0), index.get(lab, 10_000)))
    ordered = list(emotions)
    if "neutral" in qualifying:
        ordered.append("neutral")
    return ordered[: max(0, int(max_labels))]


class FineGrainedEmotionAnalysis(AnalysisModule):
    """Multi-label sigmoid emotion. Experimental; domain-dependent."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "fine_grained_emotion"
        from transcriptx.core.utils.config import get_config

        cfg = get_config().analysis
        nested = getattr(cfg, "fine_grained_emotion", None)

        profile_id = getattr(nested, "profile_id", None)
        if profile_id is None:
            profile_id = getattr(cfg, "fine_grained_emotion_profile_id", None)
        if profile_id is None:
            profile_id = FINE_GRAINED_GOEMOTIONS_V1.profile_id
        self.profile = get_builtin_profile(profile_id)

        label_threshold = getattr(nested, "label_threshold", None)
        if label_threshold is None:
            label_threshold = getattr(cfg, "fine_grained_emotion_label_threshold", None)
        if label_threshold is None:
            label_threshold = PROVISIONAL_LABEL_THRESHOLD
        self.label_threshold = float(label_threshold)

        max_labels = getattr(nested, "max_labels_per_segment", None)
        if max_labels is None:
            max_labels = getattr(
                cfg, "fine_grained_emotion_max_labels_per_segment", None
            )
        if max_labels is None:
            max_labels = DEFAULT_MAX_LABELS
        self.max_labels = int(max_labels)

        batch_size = getattr(nested, "batch_size", None)
        if batch_size is None:
            batch_size = getattr(cfg, "fine_grained_emotion_batch_size", None)
        if batch_size is None:
            batch_size = 8
        self.batch_size = int(batch_size)

    def _inference_cache(self) -> InferenceCacheStore | None:
        try:
            return InferenceCacheStore(default_inference_cache_root(self.module_name))
        except Exception as exc:
            log_warning("FINE_GRAINED_EMOTION", f"inference cache unavailable: {exc}")
            return None

    def _aggregation_cache(self) -> AggregationCacheStore | None:
        try:
            return AggregationCacheStore(
                default_aggregation_cache_root(self.module_name)
            )
        except Exception as exc:
            log_warning("FINE_GRAINED_EMOTION", f"aggregation cache unavailable: {exc}")
            return None

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        artifact_generation_id = uuid.uuid4().hex
        inference_generation_id = artifact_generation_id
        try:
            ensure_segment_ids(segments)
        except ValueError as exc:
            return self._failed(
                segments, artifact_generation_id, RunStatus.FAILED, str(exc)
            )

        try:
            loaded = load_classifier(self.profile)
        except Exception as exc:
            log_warning("FINE_GRAINED_EMOTION", f"preflight failed: {exc}")
            return self._failed(
                segments,
                artifact_generation_id,
                RunStatus.SKIPPED,
                f"preflight_failed: {exc}",
            )

        try:
            text_digest = text_source_digest(segments)
        except ValueError as exc:
            return self._failed(
                segments, artifact_generation_id, RunStatus.FAILED, str(exc)
            )

        meta = extract_transcript_metadata(segments)
        work: list[dict[str, Any]] = []
        assumed_en_warnings = 0
        for seg in segments:
            speaker_info = extract_speaker_info(seg)
            speaker = ""
            if speaker_info is not None:
                speaker = get_speaker_display_name(
                    speaker_info.grouping_key, [seg], segments
                )
            sid = str(seg.get("id") or seg.get("segment_id"))
            lang, lang_res = resolve_segment_language(seg, meta)
            if lang_res == "assumed_en_missing_metadata":
                assumed_en_warnings += 1
            text = (seg.get("text") or "").strip()
            work.append(
                {
                    "seg": seg,
                    "sid": sid,
                    "speaker": speaker,
                    "lang": lang,
                    "lang_res": lang_res,
                    "text": text,
                    "text_hash": segment_text_hash(seg.get("text")),
                }
            )

        effective_max = loaded.effective_max_length
        libs = library_versions()
        display_fp = build_display_fingerprint(
            family_ontology_version=FAMILY_ONTOLOGY_V1,
            display_cap=self.max_labels,
        )
        aggregation_settings = build_aggregation_settings(
            threshold_profile_version=self.profile.threshold_profile_version,
            effective_threshold=self.label_threshold,
            max_labels=self.max_labels,
            aggregation_semantics=SEMANTICS_VERSION,
        )
        compat = build_compatibility_payload(
            schema_version=SCHEMA_VERSION,
            semantics_version=SEMANTICS_VERSION,
            profile_id=self.profile.profile_id,
            model_id=self.profile.model_id,
            tokenizer_id=self.profile.tokenizer_id,
            model_revision=self.profile.model_revision,
            tokenizer_revision=self.profile.tokenizer_revision,
            label_map_hash=loaded.resolved_label_map_hash,
            activation="sigmoid",
            effective_max_length=effective_max,
            long_text_policy_version=LONG_TEXT_POLICY_V2,
            language_policy_version=LANGUAGE_POLICY_V1,
            numerical_dtype="float32",
            device_class=loaded.device_class,
            transformers_version=libs.get("transformers_version"),
            torch_version=libs.get("torch_version"),
        )
        compat_fp = compatibility_fingerprint(compat)
        runtime_metadata = build_runtime_metadata(
            activation="sigmoid",
            label_map_hash=loaded.resolved_label_map_hash,
            model_id=self.profile.model_id,
            tokenizer_id=self.profile.tokenizer_id,
            model_revision=self.profile.model_revision,
            tokenizer_revision=self.profile.tokenizer_revision,
            device_class=loaded.device_class,
            numerical_dtype="float32",
            language_policy_version=LANGUAGE_POLICY_V1,
            long_text_policy_version=LONG_TEXT_POLICY_V2,
            effective_max_length=effective_max,
            effective_threshold=self.label_threshold,
            threshold_profile_version=self.profile.threshold_profile_version,
            batch_size=self.batch_size,
        )
        inference_key = inference_cache_key(
            compatibility_fingerprint=compat_fp, text_source_digest=text_digest
        )

        to_score = [item for item in work if is_english(item["lang"]) and item["text"]]
        needed_sids = [item["sid"] for item in to_score]

        cache_store = self._inference_cache()
        scored_by_sid: dict[str, dict[str, Any]] | None = None
        inference_cache_hit = False
        if cache_store is not None:
            cached = cache_store.load(inference_key)
            if cached:
                rows = cached.get("rows_by_segment") or {}
                if needed_sids and all(
                    sid in rows
                    and validate_classifier_cache_row(
                        rows[sid],
                        expected_labels=self.profile.labels,
                        activation="sigmoid",
                    )
                    for sid in needed_sids
                ):
                    scored_by_sid = {sid: dict(rows[sid]) for sid in needed_sids}
                    inference_cache_hit = True
                    cached_inference_id = str(
                        cached.get("inference_generation_id") or ""
                    ).strip()
                    if cached_inference_id:
                        inference_generation_id = cached_inference_id

        if scored_by_sid is None:
            texts_to_score = [item["text"] for item in to_score]
            try:
                scored = []
                bs = max(1, self.batch_size)
                for start in range(0, len(texts_to_score), bs):
                    scored.extend(
                        score_texts(
                            loaded,
                            texts_to_score[start : start + bs],
                            max_length=effective_max,
                        )
                    )
            except Exception as exc:
                return self._failed(
                    segments,
                    artifact_generation_id,
                    RunStatus.FAILED,
                    f"inference_failed: {exc}",
                )
            if len(scored) != len(to_score):
                return self._failed(
                    segments,
                    artifact_generation_id,
                    RunStatus.FAILED,
                    f"scorer_cardinality_mismatch: expected {len(to_score)} got {len(scored)}",
                )
            scored_by_sid = {}
            for item, sr in zip(to_score, scored, strict=True):
                scored_by_sid[item["sid"]] = {
                    "scores": {k: float(v) for k, v in sr.scores.items()},
                    "truncated": bool(sr.truncated),
                    "omitted_token_count_lower_bound": int(
                        sr.omitted_token_count_lower_bound
                    ),
                    "scored_text_hash": item["text_hash"],
                }
            if cache_store is not None:
                try:
                    cache_store.store(
                        inference_key,
                        inference_generation_id=inference_generation_id,
                        rows_by_segment=scored_by_sid,
                    )
                except Exception as exc:
                    log_warning(
                        "FINE_GRAINED_EMOTION",
                        f"inference cache write failed: {exc}",
                    )

        canonical_rows: list[dict[str, Any]] = []
        segments_skipped = 0
        segments_empty = 0
        outcome_counts: dict[str, int] = defaultdict(int)
        mixed_count = 0
        native_prevalence: dict[str, int] = defaultdict(int)
        speaker_label_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        speaker_outcome_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        confidences: list[float] = []
        examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
        timeline: list[dict[str, Any]] = []
        pending_projections: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for item in work:
            seg = item["seg"]
            if not is_english(item["lang"]):
                segments_skipped += 1
                row = {
                    "segment_id": item["sid"],
                    "speaker": item["speaker"],
                    "evaluation_state": "skipped",
                    "skip_reason": "unsupported_language",
                    "scores": {},
                    "scored_text_hash": item["text_hash"],
                    "display_labels": [],
                    "qualifying_emotion_count": 0,
                    "truncated": False,
                }
                canonical_rows.append(row)
                proj = project_fine_grained_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                pending_projections.append((seg, proj))
                continue
            if not item["text"]:
                segments_empty += 1
                row = {
                    "segment_id": item["sid"],
                    "speaker": item["speaker"],
                    "evaluation_state": "empty",
                    "scores": {},
                    "scored_text_hash": item["text_hash"],
                    "display_labels": [],
                    "qualifying_emotion_count": 0,
                    "truncated": False,
                }
                canonical_rows.append(row)
                proj = project_fine_grained_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                pending_projections.append((seg, proj))
                continue

            sr = scored_by_sid.get(item["sid"]) if scored_by_sid else None
            if sr is None or not validate_classifier_cache_row(
                sr,
                expected_labels=self.profile.labels,
                activation="sigmoid",
            ):
                row = {
                    "segment_id": item["sid"],
                    "speaker": item["speaker"],
                    "evaluation_state": "failed",
                    "analytical_outcome": None,
                    "scores": {},
                    "fail_reason": "invalid_or_missing_scores",
                    "scored_text_hash": item["text_hash"],
                    "display_labels": [],
                    "qualifying_emotion_count": 0,
                    "truncated": False,
                }
                canonical_rows.append(row)
                proj = project_fine_grained_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                pending_projections.append((seg, proj))
                continue

            scores = {
                k.casefold(): float(v) for k, v in (sr.get("scores") or {}).items()
            }
            truncated = bool(sr.get("truncated"))
            omitted_token_count = int(
                sr.get("omitted_token_count_lower_bound")
                if sr.get("omitted_token_count_lower_bound") is not None
                else (sr.get("omitted_token_count") or 0)
            )
            qualifying = [lab for lab, p in scores.items() if p >= self.label_threshold]
            emotion_qual = [lab for lab in qualifying if lab != "neutral"]
            if not qualifying:
                outcome = AnalyticalOutcome.NO_LABEL.value
            elif not emotion_qual and "neutral" in qualifying:
                outcome = AnalyticalOutcome.NEUTRAL.value
            elif len(emotion_qual) >= 2:
                outcome = AnalyticalOutcome.MIXED.value
                mixed_count += 1
            else:
                outcome = AnalyticalOutcome.LABELED.value

            display = order_display_labels(
                qualifying, scores, self.profile.labels, self.max_labels
            )
            top_conf = max((scores.get(lab, 0.0) for lab in qualifying), default=0.0)
            confidences.append(top_conf)
            outcome_counts[outcome] += 1
            for lab in qualifying:
                native_prevalence[lab] += 1
            if is_named_speaker(item["speaker"]):
                speaker_outcome_counts[item["speaker"]][outcome] += 1
                for lab in qualifying:
                    speaker_label_counts[item["speaker"]][lab] += 1

            row = {
                "segment_id": item["sid"],
                "speaker": item["speaker"],
                "evaluation_state": "scored",
                "analytical_outcome": outcome,
                "scores": scores,
                "qualifying_labels": qualifying,
                "qualifying_emotion_labels": emotion_qual,
                "qualifying_emotion_count": len(emotion_qual),
                "mixed": len(emotion_qual) >= 2,
                "display_labels": display,
                "truncated": truncated,
                "omitted_token_count_lower_bound": omitted_token_count,
                "language_resolution": item["lang_res"],
                "scored_text_hash": item["text_hash"],
            }
            canonical_rows.append(row)
            proj = project_fine_grained_segment(
                row,
                artifact_generation_id=artifact_generation_id,
                schema_version=SCHEMA_VERSION,
            )
            pending_projections.append((seg, proj))

            timeline.append(
                {
                    "segment_id": item["sid"],
                    "speaker": item["speaker"],
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "labels": display,
                    "analytical_outcome": outcome,
                    "confidence": top_conf,
                }
            )
            for lab in display[:1]:
                if len(examples[lab]) < 3:
                    examples[lab].append(
                        {
                            "segment_id": item["sid"],
                            "speaker": item["speaker"],
                            "text": (item["text"] or "")[:160],
                            "confidence": scores.get(lab, 0.0),
                        }
                    )

        run_status, segments_scored, segments_failed = derive_run_status_from_rows(
            canonical_rows
        )
        usable = derive_usable_output(
            run_status=run_status, segments_scored=segments_scored
        )
        denom = max(segments_scored, 1)
        primary_rates = {
            "no_label_rate": (
                outcome_counts.get("no_label", 0) / denom if segments_scored else 0.0
            ),
            "neutral_rate": (
                outcome_counts.get("neutral", 0) / denom if segments_scored else 0.0
            ),
            "mixed_rate": mixed_count / denom if segments_scored else 0.0,
            "labeled_rate": (
                outcome_counts.get("labeled", 0) / denom if segments_scored else 0.0
            ),
        }
        confidence_summary = {
            "mean": sum(confidences) / len(confidences) if confidences else 0.0,
            "min": min(confidences) if confidences else 0.0,
            "max": max(confidences) if confidences else 0.0,
            "n": len(confidences),
        }
        speaker_stats: dict[str, Any] = {}
        for sp, outcomes in speaker_outcome_counts.items():
            n = sum(int(v) for v in outcomes.values())
            sp_denom = max(n, 1)
            speaker_stats[sp] = {
                "label_counts": dict(speaker_label_counts.get(sp) or {}),
                "outcome_counts": dict(outcomes),
                "segments_scored": n,
                "no_label_rate": outcomes.get("no_label", 0) / sp_denom,
                "neutral_rate": outcomes.get("neutral", 0) / sp_denom,
                "mixed_rate": outcomes.get("mixed", 0) / sp_denom,
                "labeled_rate": outcomes.get("labeled", 0) / sp_denom,
            }
        global_stats = {
            **primary_rates,
            "native_label_prevalence": dict(native_prevalence),
            "confidence_summary": confidence_summary,
        }

        speaker_digest = speaker_identity_digest(segments)
        timeline_digest = timeline_identity_digest(segments)
        agg_key = aggregation_cache_key(
            inference_generation_id=inference_generation_id,
            speaker_identity_digest=speaker_digest,
            timeline_identity_digest=timeline_digest,
            aggregation_semantics_version=SEMANTICS_VERSION,
            aggregation_settings=aggregation_settings,
        )
        aggregation_cache_hit = False
        agg_store = self._aggregation_cache()
        if agg_store is not None:
            cached_agg = agg_store.load(agg_key)
            if cached_agg and isinstance(cached_agg.get("aggregates"), dict):
                aggregates = cached_agg["aggregates"]
                speaker_stats = aggregates.get("speaker_stats") or speaker_stats
                global_stats = aggregates.get("global_stats") or global_stats
                timeline = aggregates.get("timeline") or timeline
                examples = aggregates.get("representative_examples") or examples
                primary_rates = aggregates.get("primary_rates") or primary_rates
                native_prevalence = defaultdict(
                    int, aggregates.get("native_label_prevalence") or native_prevalence
                )
                aggregation_cache_hit = True
            else:
                try:
                    agg_store.store(
                        agg_key,
                        inference_generation_id=inference_generation_id,
                        aggregates={
                            "speaker_stats": speaker_stats,
                            "global_stats": global_stats,
                            "timeline": timeline,
                            "representative_examples": dict(examples),
                            "primary_rates": primary_rates,
                            "native_label_prevalence": dict(native_prevalence),
                        },
                    )
                except Exception as exc:
                    log_warning(
                        "FINE_GRAINED_EMOTION",
                        f"aggregation cache write failed: {exc}",
                    )

        warnings: list[str] = []
        if assumed_en_warnings:
            warnings.append(
                f"{assumed_en_warnings} segment(s) assumed English (missing language metadata)"
            )
        if self.profile.threshold_profile_version == THRESHOLD_PROFILE_PROVISIONAL_V0:
            warnings.extend(
                [
                    "experimental: GoEmotions-domain model; not definitive transcript emotion",
                    "provisional threshold profile — not stable until Phase 5",
                ]
            )
        else:
            warnings.append(
                "experimental: GoEmotions-domain model; not definitive transcript emotion"
            )

        log_info(
            "FINE_GRAINED_EMOTION",
            f"scored={segments_scored} failed={segments_failed} mixed={mixed_count}",
        )

        # Projections stay pending until canonical persist succeeds (_save_results).
        return {
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
            "compatibility_fingerprint": compat_fp,
            "display_fingerprint": display_fp,
            "runtime_metadata": runtime_metadata,
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
            "_canonical_rows": canonical_rows,
            "_pending_projections": pending_projections,
            "segments_with_fine_grained_emotion": segments,
            "primary_rates": primary_rates,
            "outcome_counts": dict(outcome_counts),
            "native_label_prevalence": dict(native_prevalence),
            "global_stats": global_stats,
            "speaker_stats": speaker_stats,
            "timeline": timeline,
            "representative_examples": dict(examples),
            "confidence_summary": confidence_summary,
            "release_channel": self.profile.release_channel,
            "threshold_profile_version": self.profile.threshold_profile_version,
            "family_ontology_version": FAMILY_ONTOLOGY_V1,
            "label_threshold": self.label_threshold,
            "effective_max_length": effective_max,
            "max_labels_per_segment": self.max_labels,
            "profile_id": self.profile.profile_id,
            "warnings": warnings,
        }

    def _failed(self, segments, generation_id, status, warning):
        from transcriptx.core.analysis.fine_grained_emotion.projections import (
            clear_fine_grained_projection,
        )

        for seg in segments:
            clear_fine_grained_projection(seg)
        return {
            "schema_version": SCHEMA_VERSION,
            "semantics_version": SEMANTICS_VERSION,
            "module_id": self.module_name,
            "run_status": status.value,
            "usable_output": False,
            "segments_scored": 0,
            "segments_skipped": 0,
            "segments_empty": 0,
            "segments_failed": 0,
            "artifact_generation_id": generation_id,
            "inference_generation_id": generation_id,
            "ordered_segment_ids": [],
            "warnings": [warning],
            "_canonical_rows": [],
            "_pending_projections": [],
            "segments_with_fine_grained_emotion": segments,
            "global_stats": {},
            "speaker_stats": {},
            "release_channel": self.profile.release_channel,
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        from transcriptx.core.analysis.fine_grained_emotion.projections import (
            clear_fine_grained_projection,
        )

        def write_enriched():
            segments = results.get("segments_with_fine_grained_emotion") or []
            pending = results.pop("_pending_projections", None)
            if pending:
                for seg, proj in pending:
                    apply_fine_grained_projection(seg, proj)
            write_enriched_transcript(output_service, segments, "fine_grained_emotion")

        def after_enrich():
            output_service.save_data(
                {k: results.get(k) for k in _RESULT_SAVE_KEYS},
                "fine_grained_emotion_results",
                format_type="json",
            )
            prevalence = results.get("native_label_prevalence") or {}
            if prevalence:
                try:
                    from transcriptx.core.utils.viz_ids import (
                        VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL,
                        VIZ_FINE_GRAINED_EMOTION_LABELS_SPEAKER,
                    )
                    from transcriptx.core.viz.specs import BarCategoricalSpec

                    top = sorted(prevalence.items(), key=lambda kv: (-kv[1], kv[0]))[
                        :15
                    ]
                    cats = [k for k, _ in top]
                    spec = BarCategoricalSpec(
                        viz_id=VIZ_FINE_GRAINED_EMOTION_LABELS_GLOBAL,
                        module=self.module_name,
                        name="fine_grained_native_label_prevalence",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="Fine-grained native label prevalence",
                        x_label="Label",
                        y_label="Count",
                        categories=cats,
                        values=[float(v) for _, v in top],
                    )
                    output_service.save_chart(spec, chart_type="bar")
                    for speaker, st in (results.get("speaker_stats") or {}).items():
                        sp_counts = (st or {}).get("label_counts") or {}
                        if not sp_counts:
                            continue
                        sp_top = sorted(
                            sp_counts.items(), key=lambda kv: (-kv[1], kv[0])
                        )[:15]
                        sp_cats = [k for k, _ in sp_top]
                        sp_spec = BarCategoricalSpec(
                            viz_id=VIZ_FINE_GRAINED_EMOTION_LABELS_SPEAKER,
                            module=self.module_name,
                            name="fine_grained_native_label_prevalence",
                            scope="speaker",
                            speaker=speaker,
                            chart_intent="bar_categorical",
                            title=f"Fine-grained native label prevalence: {speaker}",
                            x_label="Label",
                            y_label="Count",
                            categories=sp_cats,
                            values=[float(v) for _, v in sp_top],
                        )
                        output_service.save_chart(sp_spec, chart_type="bar")
                except Exception as exc:
                    log_warning("FINE_GRAINED_EMOTION", f"chart save failed: {exc}")
            if results.get("timeline"):
                output_service.save_data(
                    results["timeline"],
                    "fine_grained_emotion_timeline",
                    format_type="json",
                )
            if results.get("representative_examples"):
                output_service.save_data(
                    results["representative_examples"],
                    "fine_grained_emotion_examples",
                    format_type="json",
                )
            output_service.save_summary(
                results.get("global_stats") or {},
                results.get("speaker_stats") or {},
                analysis_metadata={
                    "release_channel": results.get("release_channel"),
                    "warnings": results.get("warnings"),
                    "artifact_generation_id": results.get("artifact_generation_id"),
                    "inference_generation_id": results.get("inference_generation_id"),
                },
            )

        persist_canonical_then_enrich(
            results=results,
            output_service=output_service,
            module_id=self.module_name,
            log_prefix="FINE_GRAINED_EMOTION",
            write_enriched=write_enriched,
            after_enrich=after_enrich,
            clear_owned_fields=clear_fine_grained_projection,
        )
