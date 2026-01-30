from __future__ import annotations

import re
from difflib import SequenceMatcher
from hashlib import sha1
from typing import Dict, Iterable, List, Optional, Tuple

from transcriptx.core.corrections.models import Candidate, CorrectionRule, Occurrence
from transcriptx.utils.text_utils import is_named_speaker


def _stable_sha1(value: str) -> str:
    return sha1(value.encode("utf-8")).hexdigest()


def resolve_segment_id(
    segment: Dict,
    transcript_key: str,
    segment_index: Optional[int] = None,
) -> str:
    segment_id = segment.get("id") or segment.get("uuid")
    if segment_id:
        return str(segment_id)
    start = segment.get("start", segment.get("start_time"))
    end = segment.get("end", segment.get("end_time"))
    # Prefer timestamps when present (more stable than index)
    if start is not None and end is not None and isinstance(start, (int, float)) and isinstance(end, (int, float)):
        signature = f"{transcript_key}:{float(start):.3f}:{float(end):.3f}"
        return _stable_sha1(signature)
    if segment_index is not None:
        return _stable_sha1(f"{transcript_key}:{segment_index}")
    speaker = segment.get("speaker", "")
    text = segment.get("text", "")
    signature = f"{transcript_key}:{start}:{end}:{speaker}:{text[:50]}"
    return _stable_sha1(signature)


def _build_snippet(text: str, span: Tuple[int, int], window: int = 40) -> str:
    start = max(0, span[0] - window)
    end = min(len(text), span[1] + window)
    return text[start:end].strip()


def _iter_matches(
    text: str, pattern: re.Pattern
) -> Iterable[Tuple[int, int, str]]:
    for match in pattern.finditer(text):
        yield match.start(), match.end(), match.group(0)


def _compile_pattern(
    wrong: str, case_sensitive: bool, word_boundary: bool
) -> re.Pattern:
    flags = 0 if case_sensitive else re.IGNORECASE
    escaped = re.escape(wrong)
    if word_boundary:
        regex = rf"\b{escaped}\b"
    else:
        regex = escaped
    return re.compile(regex, flags=flags)


def _acronym_variants(value: str) -> List[str]:
    letters = re.sub(r"[^A-Za-z]", "", value)
    if not letters:
        return []
    spaced = " ".join(list(letters))
    dotted = ". ".join(list(letters)) + "."
    return [letters, spaced, dotted]


def detect_memory_hits(
    segments: List[Dict],
    transcript_key: str,
    rules: Iterable[CorrectionRule],
) -> List[Candidate]:
    candidates: List[Candidate] = []
    for rule in rules:
        occurrences: List[Occurrence] = []
        for wrong in rule.wrong:
            if rule.type == "regex":
                flags = 0 if rule.conditions and rule.conditions.case_sensitive else re.IGNORECASE
                pattern = re.compile(wrong, flags=flags)
                match_iter = _iter_matches
            elif rule.type == "acronym":
                variants = _acronym_variants(wrong)
                if not variants:
                    continue
                flags = re.IGNORECASE
                pattern = re.compile(
                    "|".join(re.escape(v) for v in variants), flags=flags
                )
                match_iter = _iter_matches
            else:
                case_sensitive = (
                    rule.conditions.case_sensitive if rule.conditions else False
                )
                word_boundary = rule.conditions.word_boundary if rule.conditions else True
                pattern = _compile_pattern(wrong, case_sensitive, word_boundary)
                match_iter = _iter_matches

            for seg_idx, segment in enumerate(segments):
                text = segment.get("text", "")
                for start, end, matched in match_iter(text, pattern):
                    segment_id = resolve_segment_id(segment, transcript_key, segment_index=seg_idx)
                    occurrences.append(
                        Occurrence(
                            segment_id=segment_id,
                            speaker=segment.get("speaker"),
                            time_start=segment.get("start", segment.get("start_time")),
                            time_end=segment.get("end", segment.get("end_time")),
                            span=(start, end),
                            snippet=_build_snippet(text, (start, end)),
                        )
                    )

        if occurrences:
            candidates.append(
                Candidate(
                    rule_id=rule.id,
                    proposed_wrong=rule.wrong[0],
                    proposed_right=rule.right,
                    kind="memory_hit",
                    confidence=rule.confidence,
                    occurrences=occurrences,
                )
            )
    return candidates


def detect_acronym_candidates(
    segments: List[Dict],
    transcript_key: str,
    known_acronyms: List[str],
    known_org_phrases: Dict[str, List[str]],
) -> List[Candidate]:
    candidates: List[Candidate] = []
    if not known_acronyms and not known_org_phrases:
        return candidates

    acronym_set = {a.upper() for a in known_acronyms}
    acronym_pattern = re.compile(r"\b(?:[A-Za-z]\s+){1,}[A-Za-z]\b")

    for seg_idx, segment in enumerate(segments):
        text = segment.get("text", "")
        segment_id = resolve_segment_id(segment, transcript_key, segment_index=seg_idx)

        for match in acronym_pattern.finditer(text):
            raw = match.group(0)
            normalized = re.sub(r"[^A-Za-z]", "", raw).upper()
            if normalized in acronym_set:
                occurrences = [
                    Occurrence(
                        segment_id=segment_id,
                        speaker=segment.get("speaker"),
                        time_start=segment.get("start", segment.get("start_time")),
                        time_end=segment.get("end", segment.get("end_time")),
                        span=(match.start(), match.end()),
                        snippet=_build_snippet(text, (match.start(), match.end())),
                    )
                ]
                candidates.append(
                    Candidate(
                        proposed_wrong=raw,
                        proposed_right=normalized,
                        kind="acronym",
                        confidence=0.7,
                        occurrences=occurrences,
                    )
                )

        for target, phrases in known_org_phrases.items():
            for phrase in phrases:
                # Boundary: not alnum/underscore (works for punctuation/hyphens)
                escaped = re.escape(phrase)
                pattern = re.compile(
                    rf"(?:^|[^A-Za-z0-9_]){escaped}(?:$|[^A-Za-z0-9_])",
                    re.IGNORECASE,
                )
                occs: List[Occurrence] = []
                for m in pattern.finditer(text):
                    # Match may include leading/trailing boundary char; find phrase span
                    inner = m.group(0)
                    phrase_len = len(phrase)
                    for i in range(len(inner) - phrase_len + 1):
                        if inner[i : i + phrase_len].lower() == phrase.lower():
                            start = m.start() + i
                            end = start + phrase_len
                            occs.append(
                                Occurrence(
                                    segment_id=segment_id,
                                    speaker=segment.get("speaker"),
                                    time_start=segment.get("start", segment.get("start_time")),
                                    time_end=segment.get("end", segment.get("end_time")),
                                    span=(start, end),
                                    snippet=_build_snippet(text, (start, end)),
                                )
                            )
                            break
                if occs:
                    candidates.append(
                        Candidate(
                            proposed_wrong=phrase,
                            proposed_right=target,
                            kind="acronym",
                            confidence=0.65,
                            occurrences=occs,
                        )
                    )

    return candidates


def _tokenize_entities(text: str) -> List[str]:
    pattern = re.compile(r"\b[A-Z][A-Za-z0-9]+\b")
    return pattern.findall(text)


_ENTITY_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]+\b")


_SENTENCE_STARTERS = frozenset({"the", "but", "so", "and", "or", "if", "it", "is", "as", "at", "be", "by", "for", "in", "of", "on", "to", "we"})

def detect_consistency_candidates(
    segments: List[Dict],
    transcript_key: str,
    similarity_threshold: float,
) -> List[Candidate]:
    counts: Dict[str, int] = {}
    occurrences_map: Dict[str, List[Occurrence]] = {}

    for seg_idx, segment in enumerate(segments):
        text = segment.get("text", "")
        segment_id = resolve_segment_id(segment, transcript_key, segment_index=seg_idx)
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9]+\b", text):
            token = match.group(0)
            counts[token] = counts.get(token, 0) + 1
            occurrences_map.setdefault(token, []).append(
                Occurrence(
                    segment_id=segment_id,
                    speaker=segment.get("speaker"),
                    time_start=segment.get("start", segment.get("start_time")),
                    time_end=segment.get("end", segment.get("end_time")),
                    span=(match.start(), match.end()),
                    snippet=_build_snippet(text, (match.start(), match.end())),
                )
            )

    # Prune: drop very short, digits only, no alpha, sentence starters (allow single occurrence as minority)
    def keep_token(t: str) -> bool:
        if len(t) <= 2:
            return False
        if t.isdigit():
            return False
        if not any(c.isalpha() for c in t):
            return False
        if t.lower() in _SENTENCE_STARTERS:
            return False
        return True

    tokens = [t for t in counts.keys() if keep_token(t)]
    # Bucket by length for cheaper comparison
    by_len: Dict[int, List[str]] = {}
    for t in tokens:
        by_len.setdefault(len(t), []).append(t)

    candidates: List[Candidate] = []
    for i, token in enumerate(tokens):
        for other in tokens[i + 1 :]:  # halve: one direction per pair
            if token == other:
                continue
            dominant = token if counts[token] >= counts[other] else other
            minority = other if dominant == token else token
            if counts[dominant] < 3 or counts[minority] < 1:
                continue
            # Optional: only compare within length bucket ±2
            if abs(len(dominant) - len(minority)) > 2:
                continue
            score = SequenceMatcher(
                None, dominant.lower(), minority.lower()
            ).ratio()
            if score < similarity_threshold:
                continue
            candidates.append(
                Candidate(
                    proposed_wrong=minority,
                    proposed_right=dominant,
                    kind="consistency",
                    confidence=score,
                    occurrences=occurrences_map.get(minority, []),
                )
            )
    return candidates


def detect_fuzzy_candidates(
    segments: List[Dict],
    transcript_key: str,
    speaker_names: List[str],
    similarity_threshold: float,
    enabled: bool,
) -> List[Candidate]:
    if not enabled or not speaker_names:
        return []

    candidates: List[Candidate] = []
    names = [name for name in speaker_names if is_named_speaker(name)]
    for seg_idx, segment in enumerate(segments):
        text = segment.get("text", "")
        segment_id = resolve_segment_id(segment, transcript_key, segment_index=seg_idx)
        # Span-aware: use finditer so each token occurrence gets correct (start, end)
        for match in _ENTITY_PATTERN.finditer(text):
            token = match.group(0)
            start, end = match.start(), match.end()
            token_lower = token.lower()
            # Prune: compare only to names with same first letter and length ±2
            for name in names:
                name_lower = name.lower()
                if abs(len(token_lower) - len(name_lower)) > 2:
                    continue
                if token_lower[0] != name_lower[0]:
                    continue
                score = SequenceMatcher(None, token_lower, name_lower).ratio()
                if score < similarity_threshold or token_lower == name_lower:
                    continue
                occurrences = [
                    Occurrence(
                        segment_id=segment_id,
                        speaker=segment.get("speaker"),
                        time_start=segment.get("start", segment.get("start_time")),
                        time_end=segment.get("end", segment.get("end_time")),
                        span=(start, end),
                        snippet=_build_snippet(text, (start, end)),
                    )
                ]
                candidates.append(
                    Candidate(
                        proposed_wrong=token,
                        proposed_right=name,
                        kind="fuzzy",
                        confidence=score,
                        occurrences=occurrences,
                    )
                )
    return candidates
