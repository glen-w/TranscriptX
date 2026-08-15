Type: GUIDE
Authority: docs/PRODUCT.md

# Using TranscriptX: ten workflows

Short, outcome-focused walkthroughs that show how to accomplish real jobs in TranscriptX. They complement the reference guides; they do not replace them.

Use the same sample transcript across the set so the story stays continuous: [planning_review.json](fixtures/planning_review.json) (synthetic three-speaker launch planning meeting).

Playwright live-Streamlit coverage for these ten flows lives under `tests/e2e_gui/` (`make test-gui-e2e`).

## Recommended order

First-time users should follow **1 → 5**, then pick from **6 → 10** as needed. Returning users can jump straight to the workflow that matches their task.

| # | Workflow | Outcome |
|---|----------|---------|
| 1 | [First analysis](first-analysis.md) | [Import](../runtime/transcription.md) a transcript, run [Balanced](../runtime/installation.md#analysis-presets) analysis, and read the [Overview](../public_surfaces.md) |
| 2 | [Identify and name speakers](speaker-identification.md) | Turn diarized labels into readable names before using speaker-level results |
| 3 | [Investigate with evidence](investigate-evidence.md) | Answer a concrete question and trace it back to the transcript |
| 4 | [Local AI synthesis](local-ai-synthesis.md) | Use optional local [LLM](../runtime/llm.md) modules for summary and meeting extracts |
| 5 | [Export results](export-results.md) | Package a finished run as a [ZIP export](../runtime/export.md) with HTML (and EPUB when available) |
| 6 | [Explore Charts](charts.md) | Open run-scoped [Charts](../public_surfaces.md) for visual module outputs |
| 7 | [Bundle into a group](groups.md) | Create a file-backed group for multi-transcript analysis |
| 8 | [Correct while reading](corrections.md) | Propose word/span fixes in Transcript [Correct mode](../runtime/corrections-viewer.md) |
| 9 | [Rename a transcript](rename-transcript.md) | Give a managed library transcript a clearer file name |
| 10 | [Browse speaker profiles](speakers.md) | Open longitudinal [Speakers](../runtime/settings.md) profiles linked across transcripts |

## Prerequisites

- TranscriptX web UI installed and running ([Installation](../runtime/installation.md) or [Docker](../runtime/docker.md)).
- For workflow 4 only: local Ollama configured ([LLM](../runtime/llm.md)).
- For workflow 10: at least one longitudinal profile (create via Speaker Identification link), or follow the empty-state path in that guide.

Workflows 1–3, 5–9 do **not** require local AI.
