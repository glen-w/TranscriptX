"""SpeakerMatchService — snapshot under lock, compute outside, revalidate, cache."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.layout import speaker_profiles_project_lock
from transcriptx.core.speaker_profiles.store_io import (
    read_live_link,
    read_profile,
    utc_now_iso,
)
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.audio_resolve import (
    resolve_managed_transcript_audio,
    verify_audio_unchanged,
)
from transcriptx.core.speaker_profiles.voice.caches import (
    VoiceQueryCache,
    VoiceSuggestionCache,
    query_cache_key,
    suggestion_cache_key,
)
from transcriptx.core.speaker_profiles.voice.decisions import (
    decision_suppresses_suggestion,
)
from transcriptx.core.speaker_profiles.voice.excerpt_cache import VoiceExcerptStore
from transcriptx.core.speaker_profiles.voice.excerpts import (
    select_excerpts_v1,
)
from transcriptx.core.speaker_profiles.voice.generations import VoiceGenerationRegistry
from transcriptx.core.speaker_profiles.voice.matching import (
    MatchOutcome,
    rank_open_set,
    reference_corpus_digest,
    suggestion_digest,
)
from transcriptx.core.speaker_profiles.voice.models import VoiceMatchDecisionV1
from transcriptx.core.speaker_profiles.voice.ref_index import (
    VoiceRefIndexStore,
    list_eligible_embedding_ids,
    load_or_rebuild_refs,
)
from transcriptx.core.speaker_profiles.voice.runtime import (
    MODEL_ID,
    MODEL_REVISION_PIN,
    ModelUnavailable,
    SpeakerEmbeddingRuntime,
)
from transcriptx.core.speaker_profiles.voice.thresholds import PROVISIONAL_THRESHOLDS
from transcriptx.core.speaker_profiles.voice.versioning import (
    PREPROCESSING_POLICY_ID,
    QUALITY_POLICY_ID,
    VOICE_SUGGESTION_SCHEMA_ID,
)
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


@dataclass(frozen=True)
class MatchSnapshot:
    managed_transcript_id: str
    local_speaker_key: str
    occurrence_fingerprint: str
    link_id: str | None
    profile_id: str | None
    link_fingerprint: str | None
    model_generation_id: str
    reference_corpus_digest: str
    privacy_enabled: bool
    active_decisions: tuple[VoiceMatchDecisionV1, ...]
    transcript_path: str
    segments: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class AnalyseResult:
    outcome: str
    match: MatchOutcome | None
    suggestion_id: str | None
    suggestion_digest: str | None
    detail: str | None = None
    one_excerpt_fallback: bool = False
    candidates_ui: tuple[dict[str, Any], ...] = ()
    model_generation_id: str | None = None
    occurrence_fingerprint: str | None = None
    reference_corpus_digest: str | None = None
    audio_stat_fingerprint: str | None = None
    audio_content_sha256: str | None = None
    expected_link_id: str | None = None
    expected_owner_profile_id: str | None = None
    expected_fingerprint: str | None = None
    query_cache_key: str | None = None


class SpeakerMatchService:
    def __init__(
        self,
        *,
        root: Path | None = None,
        state_dir: Path | None = None,
        runtime: SpeakerEmbeddingRuntime | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.barrier = ActivationBarrier(self.root)
        self.generations = VoiceGenerationRegistry(self.root)
        self.query_cache = VoiceQueryCache(self.root)
        self.suggestion_cache = VoiceSuggestionCache(self.root)
        self.excerpts = VoiceExcerptStore(self.root)
        self.runtime = runtime or SpeakerEmbeddingRuntime()
        self.ref_index = VoiceRefIndexStore(self.root)

    def _lock(self) -> FileLock:
        return speaker_profiles_project_lock(self.state_dir)

    def _load_eligible_refs(
        self, model_generation_id: str
    ) -> tuple[dict[str, list[np.ndarray]], list[str]]:
        """Load eligible refs via Stage 9 file index when digest-fresh, else scan."""
        emb_ids_meta = list_eligible_embedding_ids(
            self.root, model_generation_id=model_generation_id
        )
        corpus = reference_corpus_digest(emb_ids_meta)
        refs, emb_ids, _source = load_or_rebuild_refs(
            self.root,
            model_generation_id=model_generation_id,
            corpus_digest=corpus,
            store=self.ref_index,
        )
        return refs, emb_ids

    def _load_decisions_for_occurrence(
        self, *, managed_transcript_id: str, local_speaker_key: str
    ) -> tuple[VoiceMatchDecisionV1, ...]:
        ddir = self.root / "voice" / "decisions"
        out: list[VoiceMatchDecisionV1] = []
        if not ddir.is_dir():
            return ()
        for path in ddir.glob("*.voice_decision.json"):
            try:
                d = VoiceMatchDecisionV1.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except Exception:
                continue
            if (
                d.managed_transcript_id == managed_transcript_id
                and d.local_speaker_key == local_speaker_key
            ):
                out.append(d)
        return tuple(out)

    def snapshot(
        self,
        *,
        managed_transcript_id: str,
        local_speaker_key: str,
        transcript_path: Path,
        segments: list[dict[str, Any]],
        occurrence_fingerprint: str,
    ) -> MatchSnapshot:
        with self._lock():
            self.barrier.assert_processing_allowed()
            active = self.generations.read_active()
            if active is None:
                pin = self.generations.ensure_default_generation_and_activate(
                    operation_idempotency_key=f"voice-gen-activate:{managed_transcript_id}"
                )
                model_generation_id = pin.model_generation_id
            else:
                model_generation_id = active.model_generation_id
            emb_ids = list_eligible_embedding_ids(
                self.root, model_generation_id=model_generation_id
            )
            corpus = reference_corpus_digest(emb_ids)
            key = link_file_key(managed_transcript_id, local_speaker_key)
            link = read_live_link(key, root=self.root)
            decisions = self._load_decisions_for_occurrence(
                managed_transcript_id=managed_transcript_id,
                local_speaker_key=local_speaker_key,
            )
            return MatchSnapshot(
                managed_transcript_id=managed_transcript_id,
                local_speaker_key=local_speaker_key,
                occurrence_fingerprint=occurrence_fingerprint,
                link_id=link.link_id if link else None,
                profile_id=link.profile_id if link else None,
                link_fingerprint=link.occurrence_fingerprint if link else None,
                model_generation_id=model_generation_id,
                reference_corpus_digest=corpus,
                privacy_enabled=True,
                active_decisions=decisions,
                transcript_path=str(transcript_path),
                segments=tuple(dict(s) for s in segments),
            )

    def analyse_occurrence(
        self,
        *,
        managed_transcript_id: str,
        local_speaker_key: str,
        transcript_path: Path,
        segments: list[dict[str, Any]],
        occurrence_fingerprint: str,
        require_activation: bool = True,
    ) -> AnalyseResult:
        if require_activation:
            self.barrier.assert_processing_allowed()

        snap = self.snapshot(
            managed_transcript_id=managed_transcript_id,
            local_speaker_key=local_speaker_key,
            transcript_path=transcript_path,
            segments=segments,
            occurrence_fingerprint=occurrence_fingerprint,
        )

        # Compute outside lock
        selection = select_excerpts_v1(
            list(snap.segments),
            local_speaker_key=local_speaker_key,
            normalize_speaker=normalize_diarized_id,
        )
        if selection.outcome != "ok":
            return AnalyseResult(
                outcome=selection.outcome,
                match=None,
                suggestion_id=None,
                suggestion_digest=None,
                detail=selection.outcome,
            )

        try:
            audio = resolve_managed_transcript_audio(Path(snap.transcript_path))
        except Exception as exc:
            return AnalyseResult(
                outcome="SourceAudioMissing",
                match=None,
                suggestion_id=None,
                suggestion_digest=None,
                detail=str(exc),
            )

        ranges = [(ex.start_us, ex.end_us) for ex in selection.excerpts]
        qkey = query_cache_key(
            occurrence_fingerprint=snap.occurrence_fingerprint,
            audio_content_sha256=audio.audio_content_sha256,
            model_generation_id=snap.model_generation_id,
            preprocessing_policy_id=PREPROCESSING_POLICY_ID,
            quality_policy_id=QUALITY_POLICY_ID,
            ranges_us=ranges,
        )
        cached = self.query_cache.read(qkey)
        if cached is not None:
            _, query_vectors = cached
        else:
            try:
                wav_paths = []
                for plan in selection.excerpts:
                    wav_paths.append(
                        self.excerpts.get_or_extract(
                            audio_path=audio.audio_path,
                            audio_content_sha256=audio.audio_content_sha256,
                            plan=plan,
                            model_generation_id=snap.model_generation_id,
                        )
                    )
                verify_audio_unchanged(audio)
                batch = self.runtime.embed_wav_paths(wav_paths)
                query_vectors = list(batch.vectors)
            except ModelUnavailable as exc:
                return AnalyseResult(
                    outcome="ModelUnavailable",
                    match=None,
                    suggestion_id=None,
                    suggestion_digest=None,
                    detail=str(exc),
                )
            except Exception as exc:
                return AnalyseResult(
                    outcome="EmbeddingFailed",
                    match=None,
                    suggestion_id=None,
                    suggestion_digest=None,
                    detail=str(exc),
                )

        # Revalidate under lock before ranking/cache write
        with self._lock():
            self.barrier.assert_processing_allowed()
            active = self.generations.read_active()
            if active is None or active.model_generation_id != snap.model_generation_id:
                return AnalyseResult(
                    outcome="IncompatibleEmbeddingGeneration",
                    match=None,
                    suggestion_id=None,
                    suggestion_digest=None,
                    detail="active generation changed during analyse",
                )
            key = link_file_key(managed_transcript_id, local_speaker_key)
            live = read_live_link(key, root=self.root)
            live_link_id = live.link_id if live else None
            live_profile_id = live.profile_id if live else None
            live_fp = live.occurrence_fingerprint if live else None
            if live_link_id != snap.link_id or live_profile_id != snap.profile_id:
                return AnalyseResult(
                    outcome="StaleLinkState",
                    match=None,
                    suggestion_id=None,
                    suggestion_digest=None,
                    detail="link owner changed during analyse",
                )
            if (
                snap.occurrence_fingerprint
                and live_fp is not None
                and live_fp != snap.occurrence_fingerprint
                and snap.link_fingerprint is not None
                and live_fp != snap.link_fingerprint
            ):
                return AnalyseResult(
                    outcome="StaleFingerprint",
                    match=None,
                    suggestion_id=None,
                    suggestion_digest=None,
                    detail="occurrence fingerprint drifted during analyse",
                )
            try:
                verify_audio_unchanged(audio)
            except Exception as exc:
                return AnalyseResult(
                    outcome="SourceAudioReplaced",
                    match=None,
                    suggestion_id=None,
                    suggestion_digest=None,
                    detail=str(exc),
                )

            refs, emb_ids = self._load_eligible_refs(snap.model_generation_id)
            corpus = reference_corpus_digest(emb_ids)
            if corpus != snap.reference_corpus_digest:
                # Still proceed with fresh corpus; invalidate suggestion cache key
                pass

            skey = suggestion_cache_key(
                occurrence_fingerprint=snap.occurrence_fingerprint,
                model_generation_id=snap.model_generation_id,
                threshold_policy_id=PROVISIONAL_THRESHOLDS.policy_id,
                reference_corpus_digest=corpus,
            )
            cached_sug = self.suggestion_cache.read(skey)
            if cached_sug and cached_sug.get("reference_corpus_digest") == corpus:
                return AnalyseResult(
                    outcome=cached_sug.get("outcome", "SuggestionAvailable"),
                    match=None,
                    suggestion_id=cached_sug.get("suggestion_id"),
                    suggestion_digest=cached_sug.get("suggestion_digest"),
                    candidates_ui=tuple(cached_sug.get("candidates_ui") or ()),
                    one_excerpt_fallback=bool(cached_sug.get("one_excerpt_fallback")),
                    model_generation_id=snap.model_generation_id,
                    occurrence_fingerprint=snap.occurrence_fingerprint,
                    reference_corpus_digest=corpus,
                    audio_stat_fingerprint=audio.audio_stat_fingerprint,
                    audio_content_sha256=audio.audio_content_sha256,
                    expected_link_id=live_link_id,
                    expected_owner_profile_id=live_profile_id,
                    expected_fingerprint=live_fp,
                    query_cache_key=cached_sug.get("query_cache_key") or qkey,
                )

            self.query_cache.write(
                qkey,
                meta={
                    "occurrence_fingerprint": snap.occurrence_fingerprint,
                    "model_generation_id": snap.model_generation_id,
                    "model_id": MODEL_ID,
                    "model_revision": MODEL_REVISION_PIN,
                    "created_at": utc_now_iso(),
                    "ranges_us": ranges,
                    "audio_stat_fingerprint": audio.audio_stat_fingerprint,
                    "audio_content_sha256": audio.audio_content_sha256,
                },
                vectors=query_vectors,
            )

            match = rank_open_set(
                query_vectors=query_vectors,
                profile_refs=refs,
                one_excerpt_fallback=selection.one_excerpt_fallback,
            )
            decisions = self._load_decisions_for_occurrence(
                managed_transcript_id=managed_transcript_id,
                local_speaker_key=local_speaker_key,
            )
            kept = []
            for cand in match.candidates:
                if decision_suppresses_suggestion(
                    list(decisions),
                    candidate_profile_id=cand.profile_id,
                    model_generation_id=snap.model_generation_id,
                    reference_corpus_digest=corpus,
                ):
                    continue
                profile = read_profile(cand.profile_id, root=self.root)
                kept.append(
                    {
                        "profile_id": cand.profile_id,
                        "display_name": (
                            profile.display_name if profile else cand.profile_id
                        ),
                        "confidence": cand.confidence,
                        "reference_count": cand.reference_count,
                        # raw score only for diagnostics payload in cache, not main UI
                        "score_diagnostic": cand.score,
                    }
                )
            if not kept:
                outcome = "NoReliableMatch"
                suggestion_id = None
                digest = None
            else:
                outcome = "SuggestionAvailable"
                suggestion_id = str(uuid4())
                digest = suggestion_digest(
                    occurrence_fingerprint=snap.occurrence_fingerprint,
                    model_generation_id=snap.model_generation_id,
                    threshold_policy_id=PROVISIONAL_THRESHOLDS.policy_id,
                    corpus_digest=corpus,
                    candidate_profile_ids=[c["profile_id"] for c in kept],
                )
            payload = {
                "schema_id": VOICE_SUGGESTION_SCHEMA_ID,
                "suggestion_id": suggestion_id,
                "suggestion_digest": digest,
                "outcome": outcome,
                "reference_corpus_digest": corpus,
                "model_generation_id": snap.model_generation_id,
                "threshold_policy_id": PROVISIONAL_THRESHOLDS.policy_id,
                "candidates_ui": kept,
                "one_excerpt_fallback": selection.one_excerpt_fallback,
                "query_cache_key": qkey,
                "created_at": utc_now_iso(),
            }
            self.suggestion_cache.write(skey, payload)
            return AnalyseResult(
                outcome=outcome,
                match=match,
                suggestion_id=suggestion_id,
                suggestion_digest=digest,
                candidates_ui=tuple(kept),
                one_excerpt_fallback=selection.one_excerpt_fallback,
                model_generation_id=snap.model_generation_id,
                occurrence_fingerprint=snap.occurrence_fingerprint,
                reference_corpus_digest=corpus,
                audio_stat_fingerprint=audio.audio_stat_fingerprint,
                audio_content_sha256=audio.audio_content_sha256,
                expected_link_id=live_link_id,
                expected_owner_profile_id=live_profile_id,
                expected_fingerprint=live_fp,
                query_cache_key=qkey,
            )
