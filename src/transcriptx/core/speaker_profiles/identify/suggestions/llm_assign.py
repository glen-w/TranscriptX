"""Optional LLM pass to assign roster names to diarized speakers."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from transcriptx.core.llm.llm_client import LLMClient
from transcriptx.core.speaker_profiles.identify.mentions import (
    normalize_person_key,
    title_person_name,
)
from transcriptx.core.speaker_profiles.identify.suggestions.models import NameOption
from transcriptx.core.speaker_profiles.identify.suggestions.roster import (
    _segment_speaker,
    _segment_text,
)
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

_SYSTEM = (
    "You assign human names from a fixed roster to diarized speaker IDs in a "
    "webinar or panel transcript. Reply with JSON only."
)

_BASIS_MAP = {
    "self_intro": "self_intro",
    "moderator_intro": "moderator_intro",
    "peer_reference": "peer_reference",
}


def _early_turns(
    segments: Sequence[Mapping[str, Any]],
    *,
    max_lines_per_speaker: int = 6,
) -> dict[str, list[str]]:
    counts: dict[str, int] = {}
    out: dict[str, list[str]] = {}
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        speaker = _segment_speaker(segment)
        text = _segment_text(segment)
        if not speaker or not text:
            continue
        n = counts.get(speaker, 0)
        if n >= max_lines_per_speaker:
            continue
        counts[speaker] = n + 1
        out.setdefault(speaker, []).append(text[:240])
    return out


def _roster_mention_turns(
    segments: Sequence[Mapping[str, Any]],
    roster_names: Sequence[str],
    *,
    limit: int = 24,
) -> list[str]:
    needles = [n.casefold() for n in roster_names if n]
    lines: list[str] = []
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        speaker = _segment_speaker(segment)
        text = _segment_text(segment)
        if not text:
            continue
        lower = text.casefold()
        if any(n in lower for n in needles):
            lines.append(f"{speaker}: {text[:200]}")
        if len(lines) >= limit:
            break
    return lines


def build_llm_prompt(
    segments: Sequence[Mapping[str, Any]],
    speaker_ids: Sequence[str],
    roster_names: Sequence[str],
) -> str:
    early = _early_turns(segments)
    mention_lines = _roster_mention_turns(segments, roster_names)
    roster_block = "\n".join(f"- {n}" for n in roster_names)
    early_block = "\n".join(
        f"{sid}:\n  " + "\n  ".join(lines)
        for sid, lines in sorted(early.items())
        if sid in speaker_ids
    )
    mention_block = "\n".join(mention_lines)
    ids_block = ", ".join(speaker_ids)
    return f"""<<<ROSTER>>>
{roster_block}
<<<END ROSTER>>>

Speaker IDs: {ids_block}

<<<EARLY_TURNS>>>
{early_block}
<<<END EARLY_TURNS>>>

<<<ROSTER_MENTIONS>>>
{mention_block}
<<<END ROSTER_MENTIONS>>>

Return JSON:
{{
  "moderator_speaker_id": string or null,
  "assignments": [
    {{
      "speaker_id": string,
      "display_name": string (must be from ROSTER or a clear self-introduction in EARLY_TURNS),
      "basis": "self_intro" | "moderator_intro" | "peer_reference",
      "quote": string (short excerpt copied from the packs above)
    }}
  ]
}}
Only include assignments you are reasonably confident about. Use null moderator when unknown."""


def parse_llm_response(
    raw: str,
    *,
    allowed_keys: set[str],
    speaker_ids: set[str],
) -> dict[str, NameOption]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    assignments = payload.get("assignments")
    if not isinstance(assignments, list):
        return {}
    out: dict[str, NameOption] = {}
    for row in assignments:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("speaker_id") or "").strip()
        if sid not in speaker_ids:
            continue
        name = title_person_name(
            str(row.get("display_name") or ""),
            apply_gazetteer=False,
        )
        if not name or normalize_person_key(name) not in allowed_keys:
            continue
        basis_raw = str(row.get("basis") or "peer_reference")
        basis = _BASIS_MAP.get(basis_raw, "peer_reference")
        quote = str(row.get("quote") or "")[:160]
        out[sid] = NameOption(
            display_name=name,
            basis=basis,  # type: ignore[arg-type]
            confidence="likely",
            quote=quote,
            source="llm",
        )
    return out


def merge_llm_options(
    deterministic: dict[str, tuple[NameOption, ...]],
    llm_by_speaker: dict[str, NameOption],
) -> dict[str, tuple[NameOption, ...]]:
    """Insert LLM options ahead of weaker deterministic ones; keep disagreements."""
    merged: dict[str, tuple[NameOption, ...]] = {}
    for sid, options in deterministic.items():
        llm_opt = llm_by_speaker.get(sid)
        if llm_opt is None:
            merged[sid] = options
            continue
        bucket: list[NameOption] = [llm_opt]
        seen = {normalize_person_key(llm_opt.display_name)}
        agree = any(
            normalize_person_key(o.display_name) == normalize_person_key(llm_opt.display_name)
            for o in options
        )
        for opt in options:
            key = normalize_person_key(opt.display_name)
            if key in seen:
                if agree and opt.basis in {"vocative", "roster"}:
                    continue
                continue
            seen.add(key)
            bucket.append(opt)
        merged[sid] = tuple(bucket[:8])
    return merged


def run_llm_assignments(
    client: LLMClient,
    segments: Sequence[Mapping[str, Any]],
    speaker_ids: Sequence[str],
    roster_names: Sequence[str],
    allowed_keys: set[str],
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    max_input_chars: int | None = None,
) -> dict[str, NameOption]:
    if not client.is_available():
        return {}
    prompt = build_llm_prompt(segments, speaker_ids, roster_names)
    if max_input_chars is not None and len(prompt) > max_input_chars:
        prompt = prompt[: max(0, max_input_chars)]
    try:
        raw = client.generate(
            prompt=prompt,
            system_prompt=_SYSTEM,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format="json",
        )
    except Exception as exc:
        logger.warning("Speaker name suggestion LLM failed: %s", exc)
        return {}
    return parse_llm_response(
        raw,
        allowed_keys=allowed_keys,
        speaker_ids=set(speaker_ids),
    )
