"""Multi-model LLM response corpus for deterministic intake tests.

Bodies are synthetic or distilled from observed local-model shapes. Each entry
records the family/size class it represents and the expected intake outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DiscoveryExpect = Literal["parse_ok", "parse_error"]
TextExpect = Literal["non_empty", "empty"]
EnvelopeExpect = Literal["client_ok", "client_empty_response"]
NarrativeExpect = Literal["parse_ok", "parse_error"]


@dataclass(frozen=True)
class DiscoveryFixture:
    id: str
    model_id: str
    family: str
    size_class: str
    thinking: bool
    body: str
    expect: DiscoveryExpect
    min_candidates: int = 0


@dataclass(frozen=True)
class TextSummaryFixture:
    id: str
    model_id: str
    family: str
    size_class: str
    thinking: bool
    body: str
    expect: TextExpect


@dataclass(frozen=True)
class OllamaEnvelopeFixture:
    id: str
    model_id: str
    family: str
    size_class: str
    thinking: bool
    envelope: dict
    expect: EnvelopeExpect


@dataclass(frozen=True)
class NarrativeFixture:
    id: str
    model_id: str
    family: str
    size_class: str
    thinking: bool
    body: str
    expect: NarrativeExpect


DISCOVERY_FIXTURES: tuple[DiscoveryFixture, ...] = (
    DiscoveryFixture(
        id="gemma3_mid_bare_array_short_rationale",
        model_id="gemma3:12b",
        family="gemma3",
        size_class="mid",
        thinking=False,
        # Production bug: bare array + short_rationale alias.
        body="""```json
[
  {
    "source_text": "Foo",
    "replacement_text": "Bar",
    "segment_ref": 0,
    "short_rationale": "phonetic ASR error",
    "certainty_label": "tentative",
    "evidence_signals": ["model_suggestion", "homophone_pattern"]
  }
]
```""",
        expect="parse_ok",
        min_candidates=1,
    ),
    DiscoveryFixture(
        id="gemma3_mid_canonical_object",
        model_id="gemma3:12b",
        family="gemma3",
        size_class="mid",
        thinking=False,
        body="""```json
{
  "candidates": [
    {
      "source_text": "Foo",
      "replacement_text": "Bar",
      "segment_ref": 0,
      "rationale": "Likely transcription error.",
      "certainty_label": "tentative",
      "evidence_signals": ["model_suggestion"]
    }
  ]
}
```""",
        expect="parse_ok",
        min_candidates=1,
    ),
    DiscoveryFixture(
        id="llama32_small_empty_candidates",
        model_id="llama3.2:3b",
        family="llama",
        size_class="small",
        thinking=False,
        body='{"candidates": []}',
        expect="parse_ok",
        min_candidates=0,
    ),
    DiscoveryFixture(
        id="qwen25_mid_unfenced_bare_array",
        model_id="qwen2.5:7b",
        family="qwen2.5",
        size_class="mid",
        thinking=False,
        body=(
            '[{"source_text":"Foo","replacement_text":"Bar","segment_ref":0,'
            '"rationale":"x","certainty_label":"tentative",'
            '"evidence_signals":["model_suggestion"]}]'
        ),
        expect="parse_ok",
        min_candidates=1,
    ),
    DiscoveryFixture(
        id="mistral_mid_corrections_nest",
        model_id="mistral:latest",
        family="mistral",
        size_class="mid",
        thinking=False,
        body=(
            '{"corrections":[{"source_text":"Foo","replacement_text":"Bar",'
            '"segment_ref":"0","reason":"homophone"}]}'
        ),
        expect="parse_ok",
        min_candidates=1,
    ),
    DiscoveryFixture(
        id="large_truncated_mid_object",
        model_id="qwen3.6:27b",
        family="qwen3.6",
        size_class="large",
        thinking=True,
        body='{"candidates":[{"source_text":"Foo","replacement_text":"Ba',
        expect="parse_error",
    ),
    DiscoveryFixture(
        id="bare_array_trailing_junk",
        model_id="gemma3:12b",
        family="gemma3",
        size_class="mid",
        thinking=False,
        # raw_decode may peel the first object out of a junked array; that object
        # is not a DiscoveryResponseModel, so discovery parse still fails.
        body='[{"source_text":"Foo","replacement_text":"Bar","segment_ref":0}] trailing',
        expect="parse_error",
    ),
    DiscoveryFixture(
        id="qwen_unescaped_inner_quotes",
        model_id="qwen3:8b",
        family="qwen3",
        size_class="mid",
        thinking=False,
        # Nested multi-field schema: no recovery; fail loudly like narrative
        # used to before single-field recovery existed.
        body=(
            '{"candidates":[{"source_text":"Foo "Bar"","replacement_text":"Baz",'
            '"segment_ref":0,"rationale":"x"}]}'
        ),
        expect="parse_error",
    ),
    DiscoveryFixture(
        id="llama_trailing_comma",
        model_id="llama3.2:3b",
        family="llama",
        size_class="small",
        thinking=False,
        body=(
            '{"candidates":[{"source_text":"Foo","replacement_text":"Bar",'
            '"segment_ref":0,"rationale":"x",}],}'
        ),
        expect="parse_ok",
        min_candidates=1,
    ),
)

TEXT_SUMMARY_FIXTURES: tuple[TextSummaryFixture, ...] = (
    TextSummaryFixture(
        id="llama32_small_prose",
        model_id="llama3.2:3b",
        family="llama",
        size_class="small",
        thinking=False,
        body="Alice and Bob agreed to ship the report by Friday.",
        expect="non_empty",
    ),
    TextSummaryFixture(
        id="gemma3_mid_prose",
        model_id="gemma3:12b",
        family="gemma3",
        size_class="mid",
        thinking=False,
        body="The speakers planned next steps for the budget review.",
        expect="non_empty",
    ),
    TextSummaryFixture(
        id="qwen3_thinking_whitespace",
        model_id="qwen3:8b",
        family="qwen3",
        size_class="mid",
        thinking=True,
        body="   ",
        expect="empty",
    ),
)

OLLAMA_ENVELOPE_FIXTURES: tuple[OllamaEnvelopeFixture, ...] = (
    OllamaEnvelopeFixture(
        id="qwen3_thinking_empty_response",
        model_id="qwen3:8b",
        family="qwen3",
        size_class="mid",
        thinking=True,
        envelope={
            "response": "",
            "thinking": "Let me reason about the transcript before answering...",
            "done": True,
        },
        expect="client_empty_response",
    ),
    OllamaEnvelopeFixture(
        id="deepseek_r1_thinking_empty_response",
        model_id="deepseek-r1:8b",
        family="deepseek-r1",
        size_class="mid",
        thinking=True,
        envelope={
            "response": "  ",
            "thinking": "step 1... step 2...",
            "done": True,
        },
        expect="client_empty_response",
    ),
    OllamaEnvelopeFixture(
        id="llama32_normal_response",
        model_id="llama3.2:3b",
        family="llama",
        size_class="small",
        thinking=False,
        envelope={"response": "A concise summary.", "done": True},
        expect="client_ok",
    ),
)

NARRATIVE_FIXTURES: tuple[NarrativeFixture, ...] = (
    NarrativeFixture(
        id="llama_canonical",
        model_id="llama3.2:3b",
        family="llama",
        size_class="small",
        thinking=False,
        body='{"narrative": "The team agreed on next steps."}',
        expect="parse_ok",
    ),
    NarrativeFixture(
        id="gemma_fenced",
        model_id="gemma3:12b",
        family="gemma3",
        size_class="mid",
        thinking=False,
        body='```json\n{"narrative": "Executive update."}\n```',
        expect="parse_ok",
    ),
    NarrativeFixture(
        id="qwen_unescaped_inner_quotes",
        model_id="qwen3:8b",
        family="qwen3",
        size_class="mid",
        thinking=False,
        # Distilled from runtime failure: Expecting ',' delimiter mid-narrative
        # when the model embeds literal double quotes in the prose string.
        body=(
            '{\n  "narrative": "'
            + ("The supervision meeting covered progress on the thesis draft. " * 6)
            + 'Ana said "the methods chapter still needs work" and Federico agreed."\n}'
        ),
        expect="parse_ok",
    ),
    NarrativeFixture(
        id="mistral_literal_newlines_in_narrative",
        model_id="mistral:latest",
        family="mistral",
        size_class="mid",
        thinking=False,
        body='{\n  "narrative": "First paragraph.\n\nSecond paragraph continues."\n}',
        expect="parse_ok",
    ),
    NarrativeFixture(
        id="llama_trailing_comma",
        model_id="llama3.2:3b",
        family="llama",
        size_class="small",
        thinking=False,
        body='{"narrative": "Trailing comma is repaired.",}',
        expect="parse_ok",
    ),
    NarrativeFixture(
        id="truncated_narrative",
        model_id="qwen3.6:27b",
        family="qwen3.6",
        size_class="large",
        thinking=True,
        body='{"narrative": "The team agreed on ne',
        expect="parse_error",
    ),
    NarrativeFixture(
        id="bare_string_reject",
        model_id="mistral:latest",
        family="mistral",
        size_class="mid",
        thinking=False,
        body='"just a string"',
        expect="parse_error",
    ),
)
