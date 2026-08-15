"""Contextual emotion module — broad softmax classifier (experimental until Phase 5)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.affect.output_helpers import write_enriched_transcript
from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.contextual_emotion.projections import (
    apply_contextual_projection,
    project_contextual_segment,
)
from transcriptx.core.analysis.emotion_family.cache_validation import (
    validate_classifier_cache_row,
)
from transcriptx.core.analysis.emotion_family.classifier_inference import (
    resolve_classifier_scores,
)
from transcriptx.core.analysis.emotion_family.fingerprints import (
    build_aggregation_settings,
    build_compatibility_payload,
    build_runtime_metadata,
    compatibility_fingerprint,
    library_versions,
    speaker_identity_digest,
    text_source_digest,
    timeline_identity_digest,
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
from transcriptx.core.analysis.hf_text_classification import (
    LONG_TEXT_POLICY_V2,
    load_classifier,
    score_texts,
)
from transcriptx.core.analysis.hf_text_classification.profiles import (
    CONTEXTUAL_HARTMANN_V1,
    THRESHOLD_PROFILE_PROVISIONAL_V0,
    get_builtin_profile,
)
from transcriptx.core.utils.logger import get_logger, log_info, log_warning
from transcriptx.utils.text_utils import is_analysis_speaker_label

logger = get_logger()

SCHEMA_VERSION = "transcriptx.contextual_emotion_result.v1"
SEMANTICS_VERSION = "contextual_emotion_v1"
AGGREGATION_SEMANTICS_V1 = "contextual_emotion_aggregation_v1"
PROVISIONAL_CONFIDENCE_THRESHOLD = 0.45

CONTEXTUAL_PROJECTION_FIELDS = (
    "segment_id",
    "evaluation_state",
    "analytical_outcome",
    "contextual_emotion_label",
    "contextual_emotion_confidence",
    "truncated",
    "canonical_ref",
)

_RESULT_SAVE_KEYS = (
    "schema_version",
    "semantics_version",
    "module_id",
    "run_status",
    "usable_output",
    "segments_scored",
    "segments_failed",
    "compatibility_fingerprint",
    "artifact_generation_id",
    "inference_generation_id",
    "primary_rates",
    "label_counts",
    "release_channel",
    "warnings",
    "profile_id",
    "threshold_profile_version",
    "confidence_threshold",
    "projection_fields",
    "runtime_metadata",
    "enriched_projection_status",
)


class ContextualEmotionAnalysis(AnalysisModule):
    """Segment-level contextual emotion (softmax). Experimental channel."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "contextual_emotion"
        from transcriptx.core.utils.config import get_config

        cfg = get_config().analysis
        nested = getattr(cfg, "contextual_emotion", None)

        raw_profile = getattr(nested, "profile_id", None)
        if raw_profile is None:
            raw_profile = getattr(cfg, "contextual_emotion_profile_id", None)
        profile_id = (
            CONTEXTUAL_HARTMANN_V1.profile_id
            if raw_profile is None
            else str(raw_profile)
        )
        self.profile = get_builtin_profile(profile_id)

        raw = getattr(nested, "confidence_threshold", None)
        if raw is None:
            raw = getattr(cfg, "contextual_emotion_confidence_threshold", None)
        self.confidence_threshold = (
            PROVISIONAL_CONFIDENCE_THRESHOLD if raw is None else float(raw)
        )

        raw_batch = getattr(nested, "batch_size", None)
        if raw_batch is None:
            raw_batch = getattr(cfg, "contextual_emotion_batch_size", None)
        self.batch_size = 8 if raw_batch is None else int(raw_batch)

    def _inference_cache(self) -> InferenceCacheStore | None:
        try:
            return InferenceCacheStore(default_inference_cache_root(self.module_name))
        except Exception as exc:
            log_warning("CONTEXTUAL_EMOTION", f"inference cache unavailable: {exc}")
            return None

    def _aggregation_cache(self) -> AggregationCacheStore | None:
        try:
            return AggregationCacheStore(
                default_aggregation_cache_root(self.module_name)
            )
        except Exception as exc:
            log_warning("CONTEXTUAL_EMOTION", f"aggregation cache unavailable: {exc}")
            return None

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        artifact_generation_id = uuid.uuid4().hex
        try:
            ensure_segment_ids(segments)
        except ValueError as exc:
            return self._failed(
                segments,
                artifact_generation_id,
                RunStatus.FAILED,
                reason="invalid_segment_ids",
                details={"message": str(exc)},
            )

        try:
            loaded = load_classifier(self.profile)
        except Exception as exc:
            log_warning("CONTEXTUAL_EMOTION", f"preflight failed: {exc}")
            return self._failed(
                segments,
                artifact_generation_id,
                RunStatus.SKIPPED,
                reason="preflight_failed",
                details={"message": str(exc)},
            )

        try:
            text_digest = text_source_digest(segments)
        except ValueError as exc:
            return self._failed(
                segments,
                artifact_generation_id,
                RunStatus.FAILED,
                reason="invalid_segment_ids",
                details={"message": str(exc)},
            )

        work, assumed_en_warnings = build_segment_work_items(segments)

        label_map_hash = loaded.resolved_label_map_hash
        effective_max = loaded.effective_max_length
        libs = library_versions()
        aggregation_settings = build_aggregation_settings(
            threshold_profile_version=self.profile.threshold_profile_version,
            effective_threshold=self.confidence_threshold,
            aggregation_semantics=AGGREGATION_SEMANTICS_V1,
        )
        compat = build_compatibility_payload(
            schema_version=SCHEMA_VERSION,
            semantics_version=SEMANTICS_VERSION,
            profile_id=self.profile.profile_id,
            model_id=self.profile.model_id,
            tokenizer_id=self.profile.tokenizer_id,
            model_revision=self.profile.model_revision,
            tokenizer_revision=self.profile.tokenizer_revision,
            label_map_hash=label_map_hash,
            activation="softmax",
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
            activation="softmax",
            label_map_hash=label_map_hash,
            model_id=self.profile.model_id,
            tokenizer_id=self.profile.tokenizer_id,
            model_revision=self.profile.model_revision,
            tokenizer_revision=self.profile.tokenizer_revision,
            device_class=loaded.device_class,
            numerical_dtype="float32",
            language_policy_version=LANGUAGE_POLICY_V1,
            long_text_policy_version=LONG_TEXT_POLICY_V2,
            effective_max_length=effective_max,
            effective_threshold=self.confidence_threshold,
            threshold_profile_version=self.profile.threshold_profile_version,
            batch_size=self.batch_size,
        )
        inference_key = inference_cache_key(
            compatibility_fingerprint=compat_fp, text_source_digest=text_digest
        )

        cache_store = self._inference_cache()
        inference_result = resolve_classifier_scores(
            loaded=loaded,
            expected_labels=self.profile.labels,
            activation="softmax",
            batch_size=self.batch_size,
            effective_max_length=effective_max,
            inference_key=inference_key,
            artifact_generation_id=artifact_generation_id,
            cache_store=cache_store,
            log_prefix="CONTEXTUAL_EMOTION",
            work_items=work,
            score_texts_fn=score_texts,
        )
        if inference_result.kind == "failure":
            if inference_result.reason == "inference_failed":
                log_warning(
                    "CONTEXTUAL_EMOTION",
                    f"inference failed: {inference_result.details.get('message')}",
                )
            return self._failed(
                segments,
                artifact_generation_id,
                RunStatus.FAILED,
                reason=inference_result.reason,
                details=dict(inference_result.details),
            )
        scored_by_sid = inference_result.scored_by_sid
        inference_cache_hit = inference_result.inference_cache_hit
        inference_generation_id = inference_result.inference_generation_id

        label_counts: dict[str, int] = defaultdict(int)
        outcome_counts: dict[str, int] = defaultdict(int)
        segments_skipped = 0
        segments_empty = 0
        canonical_rows: list[dict[str, Any]] = []
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
            seg = item.seg
            if not is_english(item.lang):
                segments_skipped += 1
                row = self._skip_row(
                    item.sid,
                    item.speaker,
                    item.lang,
                    item.lang_res,
                    "unsupported_language",
                    text_hash=item.text_hash,
                )
                canonical_rows.append(row)
                proj = project_contextual_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                pending_projections.append((seg, proj))
                continue
            if not item.text:
                segments_empty += 1
                row = self._skip_row(
                    item.sid,
                    item.speaker,
                    item.lang,
                    item.lang_res,
                    "empty",
                    text_hash=item.text_hash,
                )
                canonical_rows.append(row)
                proj = project_contextual_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                pending_projections.append((seg, proj))
                continue

            sr = scored_by_sid.get(item.sid) if scored_by_sid else None
            if sr is None or not validate_classifier_cache_row(
                sr,
                expected_labels=self.profile.labels,
                activation="softmax",
            ):
                row = {
                    "segment_id": item.sid,
                    "speaker": item.speaker,
                    "evaluation_state": "failed",
                    "analytical_outcome": None,
                    "scores": {},
                    "truncated": False,
                    "fail_reason": "invalid_or_missing_scores",
                    "scored_text_hash": item.text_hash,
                }
                canonical_rows.append(row)
                proj = project_contextual_segment(
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
            omitted_token_count_lower_bound = int(
                sr.get(
                    "omitted_token_count_lower_bound",
                    sr.get("omitted_token_count"),
                )
                or 0
            )

            top_label = max(scores, key=scores.get)
            top_score = scores[top_label]
            if top_score < self.confidence_threshold:
                outcome = AnalyticalOutcome.ABSTAINED.value
                selected = None
            elif top_label == "neutral":
                outcome = AnalyticalOutcome.NEUTRAL.value
                selected = "neutral"
            else:
                outcome = AnalyticalOutcome.LABELED.value
                selected = top_label

            if selected:
                label_counts[selected] += 1
            outcome_counts[outcome] += 1
            confidences.append(top_score)

            row = {
                "segment_id": item.sid,
                "speaker": item.speaker,
                "evaluation_state": "scored",
                "analytical_outcome": outcome,
                "contextual_emotion_label": selected,
                "contextual_emotion_confidence": top_score,
                "scores": scores,
                "truncated": truncated,
                "omitted_token_count_lower_bound": omitted_token_count_lower_bound,
                "language_resolution": item.lang_res,
                "scored_text_hash": item.text_hash,
            }
            canonical_rows.append(row)

            proj = project_contextual_segment(
                row,
                artifact_generation_id=artifact_generation_id,
                schema_version=SCHEMA_VERSION,
            )
            pending_projections.append((seg, proj))

            if is_analysis_speaker_label(item.speaker):
                if selected:
                    speaker_label_counts[item.speaker][selected] += 1
                speaker_outcome_counts[item.speaker][outcome] += 1

            timeline.append(
                {
                    "segment_id": item.sid,
                    "speaker": item.speaker,
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "label": selected,
                    "confidence": top_score,
                    "analytical_outcome": outcome,
                }
            )
            if selected and len(examples[selected]) < 3:
                examples[selected].append(
                    {
                        "segment_id": item.sid,
                        "speaker": item.speaker,
                        "text": (item.text or "")[:160],
                        "confidence": top_score,
                    }
                )

        run_status, segments_scored, segments_failed = derive_run_status_from_rows(
            canonical_rows
        )
        usable = derive_usable_output(
            run_status=run_status, segments_scored=segments_scored
        )

        speaker_digest = speaker_identity_digest(segments)
        timeline_digest = timeline_identity_digest(segments)
        agg_key = aggregation_cache_key(
            inference_generation_id=inference_generation_id,
            speaker_identity_digest=speaker_digest,
            timeline_identity_digest=timeline_digest,
            aggregation_semantics_version=SEMANTICS_VERSION,
            aggregation_settings=aggregation_settings,
        )

        denom = max(segments_scored, 1)
        primary_rates = {
            "neutral_rate": (
                outcome_counts.get("neutral", 0) / denom if segments_scored else 0.0
            ),
            "abstained_rate": (
                outcome_counts.get("abstained", 0) / denom if segments_scored else 0.0
            ),
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
        all_speakers = set(speaker_outcome_counts) | set(speaker_label_counts)
        speaker_stats: dict[str, Any] = {}
        for sp in all_speakers:
            outcomes = dict(speaker_outcome_counts.get(sp) or {})
            labels = dict(speaker_label_counts.get(sp) or {})
            scored_n = sum(outcomes.values())
            speaker_stats[sp] = {
                "label_counts": labels,
                "outcome_counts": outcomes,
                "segments_scored": scored_n,
                "rates": {
                    k: (v / scored_n if scored_n else 0.0) for k, v in outcomes.items()
                },
            }
        global_stats = {
            "label_counts": dict(label_counts),
            **primary_rates,
            "confidence_summary": confidence_summary,
        }

        agg_store = self._aggregation_cache()
        aggregation_cache_hit = False
        if agg_store is not None:
            cached_agg = agg_store.load(agg_key)
            if cached_agg and isinstance(cached_agg.get("aggregates"), dict):
                aggregates = cached_agg["aggregates"]
                speaker_stats = aggregates.get("speaker_stats") or speaker_stats
                global_stats = aggregates.get("global_stats") or global_stats
                timeline = aggregates.get("timeline") or timeline
                examples = aggregates.get("representative_examples") or examples
                primary_rates = aggregates.get("primary_rates") or primary_rates
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
                            "label_counts": dict(label_counts),
                        },
                    )
                except Exception as exc:
                    log_warning(
                        "CONTEXTUAL_EMOTION",
                        f"aggregation cache write failed: {exc}",
                    )

        log_info(
            "CONTEXTUAL_EMOTION",
            f"scored={segments_scored} failed={segments_failed} "
            f"usable={usable} channel={self.profile.release_channel}",
        )

        warnings: list[str] = []
        if self.profile.threshold_profile_version == THRESHOLD_PROFILE_PROVISIONAL_V0:
            warnings.append("experimental: provisional threshold profile")
        if assumed_en_warnings:
            warnings.append(
                f"{assumed_en_warnings} segment(s) assumed English "
                f"(missing language metadata)"
            )

        sample_projection = None
        for row in canonical_rows:
            if row.get("evaluation_state") == "scored":
                proj = project_contextual_segment(
                    row,
                    artifact_generation_id=artifact_generation_id,
                    schema_version=SCHEMA_VERSION,
                )
                sample_projection = {
                    field: proj.get(field) for field in CONTEXTUAL_PROJECTION_FIELDS
                }
                break

        ordered_segment_ids = [
            str(s.get("id") or s.get("segment_id")) for s in segments
        ]

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
            "ordered_segment_ids": ordered_segment_ids,
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
            "_canonical_rows": canonical_rows,
            "_pending_projections": pending_projections,
            "segments_with_contextual_emotion": segments,
            "label_counts": dict(label_counts),
            "outcome_counts": dict(outcome_counts),
            "primary_rates": primary_rates,
            "global_stats": global_stats,
            "speaker_stats": speaker_stats,
            "timeline": timeline,
            "representative_examples": dict(examples),
            "confidence_summary": confidence_summary,
            "release_channel": self.profile.release_channel,
            "threshold_profile_version": self.profile.threshold_profile_version,
            "confidence_threshold": self.confidence_threshold,
            "effective_max_length": effective_max,
            "profile_id": self.profile.profile_id,
            "runtime_metadata": runtime_metadata,
            "warnings": warnings,
            "projection_fields": list(CONTEXTUAL_PROJECTION_FIELDS),
            "sample_projection": sample_projection,
        }

    def _skip_row(self, sid, speaker, lang, lang_res, reason, *, text_hash: str):
        state = "empty" if reason == "empty" else "skipped"
        return {
            "segment_id": sid,
            "speaker": speaker,
            "evaluation_state": state,
            "skip_reason": reason,
            "language": lang,
            "language_resolution": lang_res,
            "scored_text_hash": text_hash,
            "analytical_outcome": None,
            "contextual_emotion_label": None,
            "contextual_emotion_confidence": 0.0,
            "scores": {},
            "truncated": False,
        }

    def _failed(self, segments, generation_id, status, reason, details):
        from transcriptx.core.analysis.contextual_emotion.projections import (
            clear_contextual_projection,
        )

        for seg in segments:
            clear_contextual_projection(seg)
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
            "preflight_reason": reason,
            "preflight_details": details,
            "_canonical_rows": [],
            "_pending_projections": [],
            "segments_with_contextual_emotion": segments,
            "global_stats": {},
            "speaker_stats": {},
            "release_channel": self.profile.release_channel,
            "warnings": [reason],
            "projection_fields": list(CONTEXTUAL_PROJECTION_FIELDS),
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        from transcriptx.core.analysis.contextual_emotion.projections import (
            clear_contextual_projection,
        )

        def write_enriched():
            segments = results.get("segments_with_contextual_emotion") or []
            pending = results.pop("_pending_projections", None)
            if pending:
                for seg, proj in pending:
                    apply_contextual_projection(seg, proj)
            write_enriched_transcript(output_service, segments, "contextual_emotion")

        def after_enrich():
            output_service.save_data(
                {k: results.get(k) for k in _RESULT_SAVE_KEYS},
                "contextual_emotion_results",
                format_type="json",
            )
            label_counts = results.get("label_counts") or {}
            if label_counts:
                from transcriptx.core.analysis.emotion_family.non_neutral_charts import (
                    emit_non_neutral_bar_charts,
                    iter_named_speaker_label_counts,
                    save_chart_isolated,
                )
                from transcriptx.core.utils.viz_ids import (
                    VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL,
                    VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER,
                    VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL,
                    VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER,
                    VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL,
                    VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER,
                )
                from transcriptx.core.viz.specs import BarCategoricalSpec

                def _save(spec: BarCategoricalSpec) -> None:
                    output_service.save_chart(spec, chart_type="bar")

                cats = sorted(label_counts.keys())
                save_chart_isolated(
                    _save,
                    BarCategoricalSpec(
                        viz_id=VIZ_CONTEXTUAL_EMOTION_LABELS_GLOBAL,
                        module=self.module_name,
                        name="contextual_emotion_label_counts",
                        scope="global",
                        chart_intent="bar_categorical",
                        title="Contextual emotion label counts",
                        x_label="Label",
                        y_label="Count",
                        categories=cats,
                        values=[float(label_counts[c]) for c in cats],
                    ),
                    log_prefix="CONTEXTUAL_EMOTION",
                )
                emit_non_neutral_bar_charts(
                    counts=label_counts,
                    order="alpha",
                    module=self.module_name,
                    log_prefix="CONTEXTUAL_EMOTION",
                    save_chart=_save,
                    count_viz_id=VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_GLOBAL,
                    share_viz_id=VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_GLOBAL,
                    count_name="contextual_emotion_label_counts_excluding_neutral",
                    share_name="contextual_emotion_label_share_non_neutral",
                    count_title="Contextual emotion label counts (excluding neutral)",
                    share_title="Contextual emotion share of non-neutral",
                    scope="global",
                )
                for speaker, sp_counts in iter_named_speaker_label_counts(
                    results.get("speaker_stats") or {}
                ):
                    sp_cats = sorted(sp_counts.keys())
                    save_chart_isolated(
                        _save,
                        BarCategoricalSpec(
                            viz_id=VIZ_CONTEXTUAL_EMOTION_LABELS_SPEAKER,
                            module=self.module_name,
                            name="contextual_emotion_label_counts",
                            scope="speaker",
                            speaker=speaker,
                            chart_intent="bar_categorical",
                            title=f"Contextual emotion label counts: {speaker}",
                            x_label="Label",
                            y_label="Count",
                            categories=sp_cats,
                            values=[float(sp_counts[c]) for c in sp_cats],
                        ),
                        log_prefix="CONTEXTUAL_EMOTION",
                    )
                    emit_non_neutral_bar_charts(
                        counts=sp_counts,
                        order="alpha",
                        module=self.module_name,
                        log_prefix="CONTEXTUAL_EMOTION",
                        save_chart=_save,
                        count_viz_id=(
                            VIZ_CONTEXTUAL_EMOTION_LABELS_EXCLUDING_NEUTRAL_SPEAKER
                        ),
                        share_viz_id=(
                            VIZ_CONTEXTUAL_EMOTION_LABEL_SHARE_NON_NEUTRAL_SPEAKER
                        ),
                        count_name=(
                            "contextual_emotion_label_counts_excluding_neutral"
                        ),
                        share_name="contextual_emotion_label_share_non_neutral",
                        count_title=(
                            f"Contextual emotion label counts "
                            f"(excluding neutral): {speaker}"
                        ),
                        share_title=(
                            f"Contextual emotion share of non-neutral: {speaker}"
                        ),
                        scope="speaker",
                        speaker=speaker,
                    )
            if results.get("timeline"):
                output_service.save_data(
                    results["timeline"],
                    "contextual_emotion_timeline",
                    format_type="json",
                )
            if results.get("representative_examples"):
                output_service.save_data(
                    results["representative_examples"],
                    "contextual_emotion_examples",
                    format_type="json",
                )
            output_service.save_summary(
                results.get("global_stats") or {},
                results.get("speaker_stats") or {},
                analysis_metadata={
                    "release_channel": results.get("release_channel"),
                    "usable_output": results.get("usable_output"),
                    "artifact_generation_id": results.get("artifact_generation_id"),
                    "inference_generation_id": results.get("inference_generation_id"),
                },
            )

        persist_canonical_then_enrich(
            results=results,
            output_service=output_service,
            module_id=self.module_name,
            log_prefix="CONTEXTUAL_EMOTION",
            write_enriched=write_enriched,
            after_enrich=after_enrich,
            clear_owned_fields=clear_contextual_projection,
        )
