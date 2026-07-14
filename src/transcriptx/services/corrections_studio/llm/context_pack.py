"""Compact context pack for corrections discovery prompts."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from transcriptx.services.corrections_studio.llm import CONTEXT_PACK_VERSION

CONTEXT_PACK_VERSION_EXPORT = CONTEXT_PACK_VERSION


def build_context_pack(
    *,
    speaker_names: Sequence[str],
    memory_pairs: Sequence[tuple[str, str]],
    known_acronyms: Sequence[str],
    known_org_phrases: Dict[str, List[str]],
    repeated_forms: Sequence[tuple[str, str, int]],
    max_chars: int = 4000,
) -> str:
    lines: List[str] = [
        f"context_pack_version={CONTEXT_PACK_VERSION}",
        "SPEAKERS:",
    ]
    for name in list(speaker_names)[:40]:
        lines.append(f"- {name}")
    lines.append("MEMORY_RULES:")
    for wrong, right in list(memory_pairs)[:40]:
        lines.append(f"- {wrong} -> {right}")
    lines.append("KNOWN_ACRONYMS:")
    for a in list(known_acronyms)[:40]:
        lines.append(f"- {a}")
    lines.append("ORG_PHRASES:")
    for target, variants in list(known_org_phrases.items())[:20]:
        joined = ", ".join(variants[:5])
        lines.append(f"- {target}: {joined}")
    lines.append("REPEATED_FORMS:")
    for a, b, count in list(repeated_forms)[:30]:
        lines.append(f"- {a} / {b} (n={count})")
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…[truncated]"
    return text


def collect_repeated_capitalized_pairs(
    segments: Sequence[Dict[str, Any]],
    *,
    limit: int = 30,
) -> List[tuple[str, str, int]]:
    """Lightweight frequency pairs of similar capitalized tokens (best-effort)."""
    from collections import Counter

    counts: Counter[str] = Counter()
    for seg in segments:
        text = str(seg.get("text") or "")
        for tok in text.split():
            cleaned = tok.strip(".,;:!?\"'()[]")
            if len(cleaned) >= 3 and cleaned[0].isupper():
                counts[cleaned] += 1
    items = [t for t, c in counts.most_common(80) if c >= 2]
    pairs: List[tuple[str, str, int]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if a.casefold() == b.casefold():
                continue
            if a.casefold()[:3] == b.casefold()[:3] or (
                abs(len(a) - len(b)) <= 2 and a.casefold()[0] == b.casefold()[0]
            ):
                pairs.append((a, b, counts[a] + counts[b]))
            if len(pairs) >= limit:
                return pairs
    return pairs
