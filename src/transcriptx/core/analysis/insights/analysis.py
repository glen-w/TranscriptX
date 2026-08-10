"""Content-first insights module."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.highlights.post_process import stable_quote_id
from transcriptx.core.analysis.phrase_quality import (
    PHRASE_QUALITY_VERSION,
    analyse_phrase,
    resource_fingerprint,
    theme_label_policy,
)
from transcriptx.core.analysis.phrase_quality.analyser import annotations_from_surfaces
from transcriptx.core.analysis.phrase_quality.policies import (
    TIER_ENTITY_PROPN,
    TIER_MULTI_CONTENT_NOUN,
    TIER_STRONG_SINGLE_NOUN,
)
from transcriptx.core.analysis.phrase_quality.scoring import select_diverse_themes
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.nlp_utils import build_tic_mask


def _confidence_band(score: Dict[str, Any]) -> str:
    total = float(score.get("total", 0.0) or 0.0)
    spread = float(score.get("spread", 0.0) or 0.0)
    recurrence = float(score.get("recurrence", 0.0) or 0.0)
    if total >= 0.55 and (spread >= 0.15 or recurrence >= 0.2):
        return "high"
    if total >= 0.35:
        return "medium"
    return "low"


def _topic_label_tokens(topic_modeling: Dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    if not isinstance(topic_modeling, dict):
        return labels

    def _absorb(raw: Any) -> None:
        text = str(raw or "").casefold()
        for tok in text.replace("_", " ").replace("-", " ").split():
            if tok.isalpha() and len(tok) > 2:
                labels.add(tok)

    for key in ("topics", "lda_topics", "topic_labels"):
        blob = topic_modeling.get(key)
        if isinstance(blob, list):
            for row in blob:
                if isinstance(row, dict):
                    _absorb(row.get("label") or row.get("name") or row.get("topic"))
                    words = row.get("words") or row.get("top_words") or []
                    if isinstance(words, list):
                        for w in words[:8]:
                            if isinstance(w, (list, tuple)) and w:
                                _absorb(w[0])
                            else:
                                _absorb(w)
                else:
                    _absorb(row)
        elif isinstance(blob, dict):
            for value in blob.values():
                _absorb(value)
    return labels


def _phrase_topic_overlap(phrase: str, topic_tokens: set[str]) -> bool:
    if not topic_tokens:
        return False
    tokens = {t for t in phrase.casefold().split() if t.isalpha()}
    return bool(tokens & topic_tokens)


def _evidence_quote_ids_for_phrase(
    phrase: str, highlights: Dict[str, Any]
) -> List[str]:
    """Map a theme phrase to highlight quote ids when themes are attached."""
    themes = highlights.get("themes") or []
    if not isinstance(themes, list):
        return []
    needle = phrase.casefold().strip()
    for theme in themes:
        if not isinstance(theme, dict) or theme.get("is_unthemed"):
            continue
        label = str(theme.get("label") or "").casefold().strip()
        if label == needle:
            ids = theme.get("quote_ids") or []
            return [str(q) for q in ids if q][:6]
    # Fallback: emblematic phrase examples → stable ids
    phrases = (
        (highlights.get("sections") or {})
        .get("emblematic_phrases", {})
        .get("phrases", [])
        or []
    )
    tk = str(highlights.get("transcript_key") or "unknown")
    for row in phrases:
        if not isinstance(row, dict):
            continue
        if str(row.get("phrase") or "").casefold().strip() != needle:
            continue
        out: List[str] = []
        for ex in row.get("examples") or []:
            if isinstance(ex, dict) and ex.get("quote"):
                out.append(stable_quote_id(ex, tk))
            if len(out) >= 4:
                break
        return out
    return []


def _enrich_candidate(
    phrase: str,
    score: Dict[str, Any],
    *,
    highlights: Dict[str, Any],
    topic_tokens: set[str],
    topic_boost: float,
    tic_mask: set[str],
) -> Dict[str, Any] | None:
    tokens = [t for t in phrase.split() if t]
    quality = analyse_phrase(annotations_from_surfaces(tokens), tic_mask=tic_mask)
    decision = theme_label_policy(quality)
    if not decision.include:
        return None

    adjusted = dict(score)
    corroborated = _phrase_topic_overlap(phrase, topic_tokens)
    if corroborated and topic_boost > 0:
        adjusted["total"] = float(adjusted.get("total", 0.0) or 0.0) + float(
            topic_boost
        )
        adjusted["topic_boost"] = float(topic_boost)

    return {
        "phrase": phrase,
        "score": adjusted,
        "tokens": tokens,
        "canonical_key": quality.features.canonical_key or phrase.casefold(),
        "head_lemma": quality.features.head_lemma,
        "preference_tier": decision.preference_tier,
        "confidence": _confidence_band(adjusted),
        "evidence_quote_ids": _evidence_quote_ids_for_phrase(phrase, highlights),
        "topic_corroborated": corroborated,
        "score_total": float(adjusted.get("total", 0.0) or 0.0),
    }


def _select_themes(
    eligibility: Dict[str, Any],
    *,
    highlights: Dict[str, Any],
    topic_modeling: Dict[str, Any],
    limit: int,
    min_score: float,
    topic_boost: float,
) -> List[Dict[str, Any]]:
    phrases = eligibility.get("content_phrases") or []
    if not isinstance(phrases, list):
        return []
    score_map = eligibility.get("phrase_scores") or {}
    if not isinstance(score_map, dict):
        score_map = {}
    topic_tokens = _topic_label_tokens(topic_modeling)
    tic_mask = build_tic_mask()

    candidates: List[Dict[str, Any]] = []
    for row in phrases:
        if not isinstance(row, dict):
            continue
        phrase = str(row.get("phrase") or "").strip()
        if not phrase:
            continue
        score = row.get("score")
        if not isinstance(score, dict):
            score = score_map.get(phrase) if isinstance(score_map.get(phrase), dict) else {}
        score = score or {}
        if float(score.get("total", 0.0) or 0.0) < min_score:
            continue
        enriched = _enrich_candidate(
            phrase,
            score,
            highlights=highlights,
            topic_tokens=topic_tokens,
            topic_boost=topic_boost,
            tic_mask=tic_mask,
        )
        if enriched is None:
            continue
        candidates.append(enriched)

    preferred = [
        row
        for row in candidates
        if int(row.get("preference_tier", 99))
        in {TIER_MULTI_CONTENT_NOUN, TIER_ENTITY_PROPN, TIER_STRONG_SINGLE_NOUN}
    ]
    pool = preferred if preferred else candidates
    pool.sort(
        key=lambda row: (
            int(row.get("preference_tier", 99)),
            -float(row.get("score_total", 0.0)),
            str(row.get("phrase") or ""),
        )
    )
    selected = select_diverse_themes(pool, limit=limit)
    return [
        {
            "phrase": row["phrase"],
            "score": row["score"],
            "confidence": row["confidence"],
            "preference_tier": row["preference_tier"],
            "evidence_quote_ids": row.get("evidence_quote_ids") or [],
            "topic_corroborated": bool(row.get("topic_corroborated")),
        }
        for row in selected
    ]


def _select_recurring_ideas(
    eligibility: Dict[str, Any],
    *,
    highlights: Dict[str, Any],
    topic_modeling: Dict[str, Any],
    limit: int,
    min_score: float,
    topic_boost: float,
) -> List[Dict[str, Any]]:
    score_map = eligibility.get("phrase_scores") or {}
    if not isinstance(score_map, dict):
        return []
    topic_tokens = _topic_label_tokens(topic_modeling)
    tic_mask = build_tic_mask()
    candidates: List[Dict[str, Any]] = []
    for phrase, score in score_map.items():
        if not isinstance(score, dict):
            continue
        if float(score.get("recurrence", 0.0) or 0.0) <= 0.0:
            continue
        if float(score.get("total", 0.0) or 0.0) < min_score:
            continue
        text = str(phrase or "").strip()
        if not text:
            continue
        enriched = _enrich_candidate(
            text,
            score,
            highlights=highlights,
            topic_tokens=topic_tokens,
            topic_boost=topic_boost,
            tic_mask=tic_mask,
        )
        if enriched is None:
            continue
        candidates.append(enriched)

    candidates.sort(
        key=lambda row: (
            -float((row.get("score") or {}).get("recurrence", 0.0)),
            -float(row.get("score_total", 0.0)),
            str(row.get("phrase") or ""),
        )
    )
    selected = select_diverse_themes(candidates, limit=limit)
    return [
        {
            "phrase": row["phrase"],
            "score": row["score"],
            "confidence": row["confidence"],
            "preference_tier": row["preference_tier"],
            "evidence_quote_ids": row.get("evidence_quote_ids") or [],
            "topic_corroborated": bool(row.get("topic_corroborated")),
        }
        for row in selected
    ]


def _select_notable_moments(
    highlights: Dict[str, Any], *, limit: int
) -> List[Dict[str, Any]]:
    """Prefer themed cold-open / highlight quotes; fall back to cold_open slice."""
    themes = highlights.get("themes") or []
    tk = str(highlights.get("transcript_key") or "unknown")
    themed_ids: set[str] = set()
    if isinstance(themes, list):
        for theme in themes:
            if not isinstance(theme, dict) or theme.get("is_unthemed"):
                continue
            for qid in theme.get("quote_ids") or []:
                themed_ids.add(str(qid))

    cold_items = list(
        ((highlights.get("sections") or {}).get("cold_open") or {}).get("items") or []
    )
    ranked: List[Dict[str, Any]] = []
    for item in cold_items:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()
        if len(quote) < 24:
            continue
        qid = stable_quote_id(item, tk)
        total = float((item.get("score") or {}).get("total", 0.0) or 0.0)
        ranked.append(
            {
                **item,
                "_qid": qid,
                "_themed": 1 if qid in themed_ids else 0,
                "_total": total,
            }
        )
    ranked.sort(key=lambda row: (-int(row["_themed"]), -float(row["_total"])))
    out: List[Dict[str, Any]] = []
    for row in ranked[:limit]:
        clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
        out.append(clean)
    return out


class InsightsAnalysis(AnalysisModule):
    """Compose key themes and style markers from upstream analysis outputs."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "insights"

    def run_from_context(self, context):
        self._context = context
        try:
            return super().run_from_context(context)
        finally:
            self._context = None

    def analyze(
        self,
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        del segments  # Insights compose from upstream artifacts only.
        context = getattr(self, "_context", None)
        eligibility = (
            context.get_analysis_result("insight_eligibility")
            if context is not None
            else {}
        ) or {}
        highlights = (
            context.get_analysis_result("highlights") if context is not None else {}
        ) or {}
        topic_modeling = (
            context.get_analysis_result("topic_modeling") if context is not None else {}
        ) or {}
        tics = context.get_analysis_result("tics") if context is not None else {}

        cfg = get_config().analysis.insights
        min_score = float(cfg.min_theme_score)
        topic_boost = float(cfg.topic_boost)
        theme_limit = int(cfg.counts.top_themes)
        idea_limit = int(cfg.counts.top_recurring_ideas)
        moment_limit = int(cfg.counts.top_notable_moments)
        min_themes = int(cfg.min_themes_for_signal)

        key_themes = _select_themes(
            eligibility,
            highlights=highlights,
            topic_modeling=topic_modeling,
            limit=theme_limit,
            min_score=min_score,
            topic_boost=topic_boost,
        )
        recurring_ideas = _select_recurring_ideas(
            eligibility,
            highlights=highlights,
            topic_modeling=topic_modeling,
            limit=idea_limit,
            min_score=min_score,
            topic_boost=topic_boost,
        )
        style_markers = {
            "tics": (tics or {}).get("speaker_stats", {}),
            "global_tics": (tics or {}).get("global_stats", {}),
        }
        notable_moments = _select_notable_moments(highlights, limit=moment_limit)

        status = "ok"
        status_reason = None
        if len(key_themes) < min_themes:
            key_themes = []
            status = "insufficient_signal"
            status_reason = "below_min_themes_for_signal"

        return {
            "schema_version": 3,
            "status": status,
            "status_reason": status_reason,
            "phrase_quality_version": PHRASE_QUALITY_VERSION,
            "phrase_quality_resource_fingerprint": resource_fingerprint(),
            "key_themes": key_themes,
            "recurring_ideas": recurring_ideas if status == "ok" else [],
            "style_markers": style_markers,
            "notable_moments": notable_moments,
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_service.save_data(results, "insights", format_type="json")
