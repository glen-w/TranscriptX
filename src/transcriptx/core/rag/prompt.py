"""Build citation context and prompts from retrieved hits.

Assign markers [S#] per chunk (not per transcript like Paperful),
so each timestamped citation jumps to a specific segment.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from transcriptx.core.models.navigation import SegmentRef

from .retrieve import Hit


# System prompt for RAG (adapted from Paperful for transcripts)
SYSTEM_PROMPT = """You are a helpful assistant answering questions about meeting transcripts.

Answer using only the provided excerpts. Cite them with [S#] markers.
If retrieved passages do not support your answer, still use the excerpt numbers.
Keep answers concise and grounded in the text."""

_USER_TEMPLATE = """Excerpts from the transcript:

{context}

Question: {question}"""

_BRACKETS = re.compile(r"\[([^\]\[]*)\]")
_MARKER = re.compile(r"\bS(\d+)\b")


@dataclass
class Source:
    """One transcript chunk behind an answer, with navigation."""

    marker: str
    """Citation marker e.g. 'S1'."""

    hit: Hit
    """The underlying Hit (has segment_ref for navigation)."""

    @property
    def timecode_span(self) -> str:
        """Format start-end as MM:SS–MM:SS."""
        def seconds_to_mmss(sec: float) -> str:
            m = int(sec // 60)
            s = int(sec % 60)
            return f"{m}:{s:02d}"

        return f"{seconds_to_mmss(self.hit.t_start)}–{seconds_to_mmss(self.hit.t_end)}"

    @property
    def citation(self) -> str:
        """Human-readable citation: speaker · timecode · title."""
        parts = []
        if self.hit.speakers:
            parts.append(" & ".join(self.hit.speakers))
        parts.append(self.timecode_span)
        if self.hit.transcript_title:
            parts.append(self.hit.transcript_title)
        return " · ".join(parts)

    @property
    def segment_ref(self) -> SegmentRef:
        """Return the SegmentRef from the underlying hit."""
        return self.hit.segment_ref


def build_context(hits: List[Hit], max_chars: int) -> Tuple[str, List[Source]]:
    """
    Build excerpt block for prompt and return associated sources.

    Assigns one marker per hit, numbered in order of appearance.
    Excerpts are added best-first until max_chars; first is always kept.

    Args:
        hits: Retrieved Hit objects ranked by score.
        max_chars: Max characters for context block.

    Returns:
        (context_text, sources_list) ready for prompt.
    """
    sources: dict[str, Source] = {}
    blocks: List[str] = []
    used = 0

    for hit in hits:
        # Assign marker per chunk (not per transcript)
        marker = f"S{len(sources) + 1}"
        source = Source(
            marker=marker,
            hit=hit,
        )

        # Format block with marker and citation
        head = f"[{marker}] {source.citation}"
        block = f"{head}\n{hit.text}"

        # Stop if adding this would exceed budget (unless it's the only one)
        if blocks and used + len(block) > max_chars:
            break

        sources[marker] = source
        blocks.append(block)
        used += len(block) + 2  # +2 for separator

    context_text = "\n\n".join(blocks)
    sources_list = list(sources.values())
    return context_text, sources_list


def build_prompt(
    question: str,
    context: str,
    history: List[Tuple[str, str]] = None,
) -> Tuple[str, str]:
    """
    Construct prompt strings for LLM (system and user).

    Args:
        question: User question.
        context: Excerpt block from build_context().
        history: Earlier (role, content) tuples, oldest first (P1 multi-turn).

    Returns:
        (system_prompt_string, user_prompt_string) ready for LLM.generate().
    """
    if history is None:
        history = []

    user_content = _USER_TEMPLATE.format(context=context, question=question.strip())

    # P1: Fold history into user_content if needed
    # For now, P0 single-shot only (no multi-turn history).

    return SYSTEM_PROMPT, user_content


def cited_markers(text: str) -> List[str]:
    """
    Extract markers the answer cited, in order of first appearance.

    Only markers inside square brackets count (e.g., [S1, S2]), so prose
    like "the S1 protein" is ignored.

    Args:
        text: Answer text.

    Returns:
        List of marker strings e.g. ['S1', 'S2'].
    """
    seen: List[str] = []
    for group in _BRACKETS.findall(text):
        for number in _MARKER.findall(group):
            marker = f"S{number}"
            if marker not in seen:
                seen.append(marker)
    return seen
