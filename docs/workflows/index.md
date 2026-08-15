Type: GUIDE
Authority: docs/PRODUCT.md

# Using TranscriptX: five workflows

Short, outcome-focused walkthroughs that show how to accomplish real jobs in TranscriptX. They complement the reference guides; they do not replace them.

Use the same sample transcript across the set so the story stays continuous: [planning_review.json](fixtures/planning_review.json) (synthetic three-speaker launch planning meeting).

## Recommended order

First-time users should follow **1 → 5**. Returning users can jump straight to the workflow that matches their task.

| # | Workflow | Outcome |
|---|----------|---------|
| 1 | [First analysis](first-analysis.md) | [Import](../runtime/transcription.md) a transcript, run [Balanced](../runtime/installation.md#analysis-presets) analysis, and read the [Overview](../public_surfaces.md) |
| 2 | [Identify and name speakers](speaker-identification.md) | Turn diarized labels into readable names before using speaker-level results |
| 3 | [Investigate with evidence](investigate-evidence.md) | Answer a concrete question and trace it back to the transcript |
| 4 | [Local AI synthesis](local-ai-synthesis.md) | Use optional local [LLM](../runtime/llm.md) modules for summary and meeting extracts |
| 5 | [Export results](export-results.md) | Package a finished run as a [ZIP export](../runtime/export.md) with HTML (and EPUB when available) |

## Prerequisites

- TranscriptX web UI installed and running ([Installation](../runtime/installation.md) or [Docker](../runtime/docker.md)).
- For workflow 4 only: local Ollama configured ([LLM](../runtime/llm.md)).

Workflows 1–3 and 5 do **not** require local AI.
