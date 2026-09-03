Type: GUIDE
Authority: docs/PRODUCT.md

# Using TranscriptX

Short, outcome-focused walkthroughs for real jobs in the web UI. They complement the reference guides; they do not replace them.

Use the same sample transcript across the set so the story stays continuous: [planning_review.json](fixtures/planning_review.json) (synthetic three-speaker launch planning meeting).

## Common workflows

Start here. First-time users should follow **1 → 5** in order.

| # | Workflow | Outcome |
|---|----------|---------|
| 1 | [First analysis](first-analysis.md) | [Import](../runtime/transcription.md) a transcript, run [Balanced](../runtime/installation.md#analysis-presets) analysis, and read Overview |
| 2 | [Identify and name speakers](speaker-identification.md) | Turn diarized labels into readable names before using speaker-level results |
| 3 | [Investigate with evidence](investigate-evidence.md) | Answer a concrete question and trace it back to the transcript |
| 4 | [Local AI synthesis](local-ai-synthesis.md) | Use optional local [AI](../runtime/llm.md) for summary and meeting extracts |
| 5 | [Export results](export-results.md) | Package a finished run as a [ZIP export](../runtime/export.md) with HTML (and EPUB when available) |

Workflows 1–3 and 5 do **not** require local AI. Workflow 4 does.

## More workflows

Jump in when you need these tasks.

| # | Workflow | Outcome |
|---|----------|---------|
| 6 | [Explore Charts](charts.md) | Open run-scoped Charts for visual module outputs |
| 7 | [Bundle into a group](groups.md) | Analyse several transcripts together |
| 8 | [Correct while reading](corrections.md) | Propose word/span fixes in Transcript [Correct mode](../runtime/corrections-viewer.md) |
| 9 | [Rename a transcript](rename-transcript.md) | Give a library transcript a clearer file name |
| 10 | [Browse speaker profiles](speakers.md) | Open speaker profiles linked across transcripts |

## Prerequisites

- TranscriptX web UI installed and running ([Installation](../runtime/installation.md) or [Docker](../runtime/docker.md)).
- For workflow 4 only: local Ollama configured ([LLM](../runtime/llm.md)).
- For workflow 10: at least one longitudinal profile (create via Speaker Identification link), or follow the empty-state path in that guide.
