"""Post-process highlights: assign quotes to themes derived from emblematic phrases."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from transcriptx.core.analysis.exemplars import _normalize_text, _tokenize
from transcriptx.core.utils.nlp_runtime import get_nlp_model
from transcriptx.core.utils.nlp_utils import (
    DISCOURSE_HEDGE_TERMS,
    build_tic_mask,
    get_all_stopwords,
)

LOW_INFORMATION_LABELS = {
    "a lot",
    "lot of",
    "lots of",
    "kind of",
    "sort of",
    "i mean",
    "you know",
    "things like that",
    "stuff like this",
}


@dataclass
class ThemeGroup:
    """One theme bucket (emblematic phrase or synthetic Unthemed)."""

    label: str
    phrase_score: float
    phrase_index: int
    is_unthemed: bool
    quote_ids: List[str]
    conflict_event_ids: List[str]
    representative_quote_id: Optional[str]


def _anchor_key_from_refs(
    refs: Dict[str, Any], *, transcript_key: str = "unknown"
) -> str:
    db_ids = refs.get("segment_db_ids") or []
    uuids = refs.get("segment_uuids") or []
    indexes = refs.get("segment_indexes") or []
    if db_ids:
        return f"db:{int(db_ids[0])}"
    if uuids:
        return f"uuid:{uuids[0]}"
    if indexes:
        return f"idx:{transcript_key}:{int(indexes[0])}"
    return "unknown"


def stable_quote_id(quote: Dict[str, Any], transcript_key: str = "unknown") -> str:
    """Match highlights/core._assign_quote_ids when id is missing (e.g. conflict anchors)."""
    qid = quote.get("id")
    if qid is not None and str(qid).strip():
        return str(qid)
    refs = quote.get("segment_refs") or {}
    anchor_key = _anchor_key_from_refs(refs, transcript_key=transcript_key)
    normalized = _normalize_text(quote.get("quote") or "")
    return f"{anchor_key}|{normalized}"


def _tokenize_normalized(text: str) -> List[str]:
    return _tokenize(_normalize_text(text))


def _is_subsequence(small: List[str], large: List[str]) -> bool:
    """True if all tokens in small appear in order in large (not necessarily adjacent)."""
    if not small:
        return True
    it = iter(large)
    for tok in small:
        found = False
        for t in it:
            if t == tok:
                found = True
                break
        if not found:
            return False
    return True


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def _label_is_low_information(label: str) -> bool:
    normalized = _normalize_text(label or "")
    tokens = _tokenize(normalized)
    if not tokens:
        return True

    stopwords = get_all_stopwords()
    tic_mask = build_tic_mask()
    stopword_ratio = float(sum(1 for t in tokens if t in stopwords)) / float(
        len(tokens)
    )
    meaningful_tokens = [
        t for t in tokens if len(t) > 1 and t not in stopwords and t not in tic_mask
    ]

    nlp = get_nlp_model()
    doc = nlp(normalized)
    content_pos = {"NOUN", "PROPN", "VERB"}
    content_tokens = [
        tok
        for tok in doc
        if tok.is_alpha
        and tok.pos_ in content_pos
        and tok.text.lower() not in stopwords
    ]
    has_content_pos = bool(content_tokens)
    strong_content_head = bool(content_tokens) and content_tokens[0].pos_ in {
        "NOUN",
        "PROPN",
        "VERB",
    }

    known_filler = normalized in tic_mask or normalized in DISCOURSE_HEDGE_TERMS
    if normalized in LOW_INFORMATION_LABELS:
        return True
    low_information_structure = (
        any(t in DISCOURSE_HEDGE_TERMS for t in tokens)
        or all(t in stopwords or t in tic_mask for t in tokens)
        or not has_content_pos
    )

    if known_filler:
        return True
    if stopword_ratio > 0.7 and low_information_structure:
        return True
    if (len(meaningful_tokens) < 2) and (
        not strong_content_head or low_information_structure
    ):
        return True
    return False


def collect_highlight_quotes(highlights: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Union of cold_open items and conflict anchor quotes (deduped by stable id)."""
    sections = highlights.get("sections") or {}
    tk = str(highlights.get("transcript_key") or "unknown")
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []

    for item in sections.get("cold_open", {}).get("items", []) or []:
        qid = stable_quote_id(item, tk)
        if qid not in seen:
            seen.add(qid)
            out.append(item)

    for event in sections.get("conflict_points", {}).get("events", []) or []:
        anchor = event.get("anchor_quote") or {}
        if not anchor.get("quote"):
            continue
        qid = stable_quote_id(anchor, tk)
        if qid not in seen:
            seen.add(qid)
            out.append(anchor)

    return out


def _best_phrase_for_quote(
    quote_text: str,
    phrases: List[Dict[str, Any]],
) -> Optional[int]:
    """Return index of best-matching emblematic phrase, or None."""
    q_tokens = _tokenize_normalized(quote_text)
    q_set = set(q_tokens)
    if not phrases:
        return None

    best_idx: Optional[int] = None
    best_key: Tuple[int, float, float] = (-1, -1.0, -1.0)

    for idx, phrase in enumerate(phrases):
        phrase_text = phrase.get("phrase") or ""
        p_tokens = _tokenize_normalized(phrase_text)
        if not p_tokens:
            continue
        p_set = set(p_tokens)

        if _is_subsequence(p_tokens, q_tokens):
            tier = 2
        else:
            overlap = len(p_set & q_set) / len(p_set)
            if overlap >= 0.5:
                tier = 1
            else:
                continue

        phrase_score = float((phrase.get("score") or {}).get("total") or 0.0)
        jac = _jaccard(p_set, q_set)
        key = (tier, phrase_score, jac)
        if key > best_key:
            best_key = key
            best_idx = idx

    return best_idx


def assign_themes(highlights: Dict[str, Any]) -> List[ThemeGroup]:
    """
    Build theme groups from emblematic phrases + highlight quotes.
    Always appends a synthetic Unthemed group as the last element.
    """
    sections = highlights.get("sections") or {}
    tk = str(highlights.get("transcript_key") or "unknown")
    phrases = list(sections.get("emblematic_phrases", {}).get("phrases", []) or [])
    quotes = collect_highlight_quotes(highlights)
    events = list(sections.get("conflict_points", {}).get("events", []) or [])

    phrase_to_quotes: Dict[int, List[str]] = {i: [] for i in range(len(phrases))}
    unthemed_ids: List[str] = []

    quote_by_id: Dict[str, Dict[str, Any]] = {}
    for q in quotes:
        qid = stable_quote_id(q, tk)
        quote_by_id[qid] = q

    for q in quotes:
        qid = stable_quote_id(q, tk)
        text = q.get("quote") or ""
        pidx = _best_phrase_for_quote(text, phrases)
        if pidx is None:
            unthemed_ids.append(qid)
        else:
            phrase_to_quotes[pidx].append(qid)

    def _rep_quote_id(quote_ids: List[str]) -> Optional[str]:
        if not quote_ids:
            return None
        best: Optional[str] = None
        best_score = -1.0
        for qid in quote_ids:
            item = quote_by_id.get(qid) or {}
            total = (item.get("score") or {}).get("total")
            if total is None:
                sc = 0.0
            else:
                sc = float(total)
            if sc > best_score:
                best_score = sc
                best = qid
        return best

    groups: List[ThemeGroup] = []
    indexed_phrases = list(enumerate(phrases))
    indexed_phrases.sort(
        key=lambda it: -float((it[1].get("score") or {}).get("total") or 0.0)
    )

    for pidx, phrase in indexed_phrases:
        qids = phrase_to_quotes.get(pidx, [])
        if not qids:
            continue
        label = str(phrase.get("phrase") or "").strip() or f"theme-{pidx}"
        if _label_is_low_information(label):
            unthemed_ids.extend(qids)
            continue
        phrase_score = float((phrase.get("score") or {}).get("total") or 0.0)
        groups.append(
            ThemeGroup(
                label=label,
                phrase_score=phrase_score,
                phrase_index=pidx,
                is_unthemed=False,
                quote_ids=list(qids),
                conflict_event_ids=[],
                representative_quote_id=_rep_quote_id(qids),
            )
        )

    # Deterministic order: by phrase score desc (already), then phrase_index
    groups.sort(key=lambda g: (-g.phrase_score, g.phrase_index))

    quote_id_to_group_index: Dict[str, int] = {}
    for gi, g in enumerate(groups):
        for qid in g.quote_ids:
            quote_id_to_group_index[qid] = gi

    unthemed_group_index = len(groups)
    for qid in unthemed_ids:
        quote_id_to_group_index[qid] = unthemed_group_index

    def _assign_event_to_group(event: Dict[str, Any]) -> int:
        anchor = event.get("anchor_quote") or {}
        anchor_id = stable_quote_id(anchor, tk) if anchor.get("quote") else ""
        if anchor_id and anchor_id in quote_id_to_group_index:
            gi_anchor = quote_id_to_group_index[anchor_id]
            if gi_anchor != unthemed_group_index:
                return gi_anchor

        ev_start = float(event.get("start") or 0.0)
        ev_end = float(event.get("end") or 0.0)
        candidates_overlap: List[Tuple[float, str]] = []
        for q in quotes:
            qid = stable_quote_id(q, tk)
            if qid == anchor_id:
                continue
            qs = float(q.get("start") or 0.0)
            qe = float(q.get("end") or 0.0)
            if qs <= ev_end and qe >= ev_start:
                candidates_overlap.append((qs, qid))
        candidates_overlap.sort(key=lambda t: t[0])
        for _, qid in candidates_overlap:
            if qid in quote_id_to_group_index:
                gi = quote_id_to_group_index[qid]
                if gi != unthemed_group_index:
                    return gi
        return unthemed_group_index

    for event in events:
        eid = str(event.get("event_id") or "")
        if not eid:
            continue
        gi = _assign_event_to_group(event)
        if gi == unthemed_group_index:
            continue
        if 0 <= gi < len(groups):
            groups[gi].conflict_event_ids.append(eid)

    unthemed = ThemeGroup(
        label="Unthemed",
        phrase_score=0.0,
        phrase_index=-1,
        is_unthemed=True,
        quote_ids=list(unthemed_ids),
        conflict_event_ids=[],
        representative_quote_id=_rep_quote_id(unthemed_ids),
    )
    # Conflict events that mapped only to unthemed (no themed quote overlap)
    themed_event_ids: Set[str] = set()
    for g in groups:
        themed_event_ids.update(g.conflict_event_ids)
    for event in events:
        eid = str(event.get("event_id") or "")
        if not eid or eid in themed_event_ids:
            continue
        unthemed.conflict_event_ids.append(eid)

    groups.append(unthemed)
    return groups


def attach_themes_to_highlights(results: Dict[str, Any]) -> None:
    """Mutate highlights dict with top-level ``themes`` key (list of dicts)."""
    results["themes"] = [asdict(tg) for tg in assign_themes(results)]
