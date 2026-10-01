"""Answer a question from the index via LLM (streaming design).

AnswerStream yields answer text piece-by-piece, with sources known upfront.
Designed for Streamlit st.write_stream() (P0 non-streaming, P1+ real streaming).
"""

from typing import Iterator, List, Optional

from transcriptx.core.llm import get_llm_client
from transcriptx.core.llm.llm_client import LLMClient

from .prompt import Source, build_context, build_prompt
from .retrieve import Hit


class AnswerStream:
    """
    An answer yielded piece-by-piece, with sources computed up front.

    Hits and sources are known before iteration starts; text accumulates as you
    iterate. After iteration, use cited() to get only sources the answer cited.
    """

    def __init__(
        self,
        pieces: Iterator[str],
        hits: List[Hit],
        sources: List[Source],
    ):
        """Internal; use answer() to construct."""
        self._pieces = pieces
        self.hits = hits
        """All retrieved hits (before citation filtering)."""

        self.sources = sources
        """Sources in the context block."""

        self.text = ""
        """Accumulated answer text after iteration."""

    def __iter__(self) -> Iterator[str]:
        """Yield answer pieces one at a time."""
        for piece in self._pieces:
            self.text += piece
            yield piece

    def read(self) -> str:
        """Consume remaining pieces and return full answer."""
        for _ in self:
            pass
        return self.text

    def cited(self) -> List[Source]:
        """Return only the sources the answer actually cited.

        Checks self.text for [S#] markers and filters sources accordingly.
        """
        from .prompt import cited_markers

        by_marker = {source.marker: source for source in self.sources}
        cited_marker_list = cited_markers(self.text)
        return [by_marker[m] for m in cited_marker_list if m in by_marker]

    def turns(self, question: str) -> tuple[dict, dict]:
        """Return this Q&A as history tuples for follow-up questions.

        Args:
            question: The question that was asked.

        Returns:
            (user_turn, assistant_turn) dicts for history parameter.

        Note:
            P1 feature; P0 does not support multi-turn.
        """
        return (
            {"role": "user", "content": question},
            {"role": "assistant", "content": self.text},
        )


def answer(
    question: str,
    *,
    hits: List[Hit],
    max_context_chars: int = 3000,
    llm_model: Optional[str] = None,
    client: Optional[LLMClient] = None,
) -> AnswerStream:
    """
    Answer a question from retrieved hits.

    Retrieval should already be complete (hits passed in). This function
    builds context, prompts the LLM, and returns an AnswerStream.

    Args:
        question: User question.
        hits: Retrieved Hit objects (from search()).
        max_context_chars: Max chars for context block.
        llm_model: Override default chat model (P1).
        client: Override LLMClient (defaults to get_llm_client()).

    Returns:
        AnswerStream (iterate to read answer pieces).

    Raises:
        LLMError: If LLM call fails.
    """
    if not hits:
        # No hits: return empty answer with no sources
        def empty_gen() -> Iterator[str]:
            yield "No relevant passages found in the index."

        return AnswerStream(empty_gen(), [], [])

    # Build context and sources from hits
    context, sources = build_context(hits, max_context_chars)

    # Build prompts for LLM
    system_prompt, user_prompt = build_prompt(question, context)

    # Get LLM client
    if client is None:
        client = get_llm_client()

    # Call LLM (non-streaming for P0; streaming added in P1)
    answer_text = client.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=500,
    )

    # Wrap in AnswerStream (single piece for P0)
    def single_piece_gen() -> Iterator[str]:
        yield answer_text

    return AnswerStream(single_piece_gen(), hits, sources)
