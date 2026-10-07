"""Conservative fuzzy merge of 2–3 token person-name variants."""

from __future__ import annotations

from typing import Sequence

from rapidfuzz.distance import Levenshtein
from rapidfuzz.fuzz import ratio as fuzz_ratio


def _tokens(name: str) -> list[str]:
    return [p for p in str(name or "").split() if p]


def names_are_fuzzy_same_person(left: str, right: str) -> bool:
    """True when two full names look like STT spelling variants of one person.

    Single-token names are never merged. First tokens must be close; last
    tokens may differ by a couple of letters (Hannock / Hennick). Distinct
    given names with the same surname are kept apart.
    """
    a = _tokens(left)
    b = _tokens(right)
    if len(a) < 2 or len(b) < 2:
        return False
    if abs(len(a) - len(b)) > 1:
        return False
    first_a, first_b = a[0].casefold(), b[0].casefold()
    last_a, last_b = a[-1].casefold(), b[-1].casefold()
    if abs(len(first_a) - len(first_b)) > 4 or abs(len(last_a) - len(last_b)) > 4:
        return False
    if not first_a or not last_a or not first_b or not last_b:
        return False
    if first_a[0] != first_b[0] or last_a[0] != last_b[0]:
        return False
    first_dist = Levenshtein.distance(first_a, first_b)
    last_dist = Levenshtein.distance(last_a, last_b)
    first_close = (
        first_a == first_b
        or fuzz_ratio(first_a, first_b) >= 85
        or first_dist <= 1
        or (first_dist <= 2 and abs(len(first_a) - len(first_b)) <= 1)
    )
    last_close = last_a == last_b or fuzz_ratio(last_a, last_b) >= 80 or last_dist <= 2
    return bool(first_close and last_close)


def cluster_people_rows(people: Sequence[dict]) -> list[dict]:
    """Merge fuzzy-equivalent catalog rows; canonical = highest mention_count."""
    rows = [dict(p) for p in people if isinstance(p, dict)]
    n = len(rows)
    if n < 2:
        return rows
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        name_i = str(rows[i].get("display_name") or "")
        for j in range(i + 1, n):
            name_j = str(rows[j].get("display_name") or "")
            if names_are_fuzzy_same_person(name_i, name_j):
                union(i, j)

    buckets: dict[int, list[int]] = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)

    merged: list[dict] = []
    for members in buckets.values():
        ranked = sorted(
            members,
            key=lambda i: (
                -int(rows[i].get("mention_count") or 0),
                -len(str(rows[i].get("display_name") or "")),
                str(rows[i].get("display_name") or "").casefold(),
            ),
        )
        canonical = dict(rows[ranked[0]])
        aliases = {
            str(rows[i].get("normalized_key") or "").casefold()
            for i in ranked
            if str(rows[i].get("normalized_key") or "").strip()
        }
        speakers: set[str] = set()
        mentions: list = []
        total = 0
        for i in ranked:
            total += int(rows[i].get("mention_count") or 0)
            for spk in rows[i].get("mentioned_by_speakers") or ():
                if spk:
                    speakers.add(str(spk))
            mentions.extend(list(rows[i].get("mentions") or []))
        canonical["mention_count"] = total
        canonical["mentioned_by_speakers"] = sorted(speakers)
        canonical["mentions"] = mentions
        canonical["alias_keys"] = sorted(k for k in aliases if k)
        merged.append(canonical)
    merged.sort(
        key=lambda row: (
            -int(row.get("mention_count") or 0),
            str(row.get("display_name") or "").casefold(),
        )
    )
    return merged
