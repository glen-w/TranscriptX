# TranscriptX

TranscriptX is a place to think with transcripts and converse with conversations.

It is an exploratory analysis toolkit for working with conversations when you do not yet know what will matter. Sometimes that means fast, multi-angle inspection. Other times it means slower, longitudinal work across many transcripts over time.

Transcripts are treated as canonical data. Analyses are reproducible, traceable, and configuration-aware.

## Finding the right workflow

### Exploratory — “What’s going on here?”

Run a transcript through multiple analysis modules to surface speaker dynamics, tone, emotion, and structure.

### Longitudinal — “How is this changing over time?”

Run comparable analyses across many transcripts to track trends and evolution.

### Audit/trace  — “Where did this result come from?”

Inspect manifests, configuration snapshots, and module outputs.

These flows describe intent, not enforced modes.

## Inputs & scope

TranscriptX currently treats transcripts as its canonical input. The conceptual focus is on conversations and interactions.

## Quickstart

Fast path:

./transcriptx.sh

Manual install:

python3.10 -m venv .venv  
source .venv/bin/activate  
pip install -e .

WebUI:

transcriptx web-viewer

## What TranscriptX does today

- Modular, dependency-aware analysis pipeline
- Speaker and interaction analysis
- Sentiment, emotion, NER, topics, similarity
- Structured, traceable outputs
- Optional audio transcription via WhisperX

## Outputs & guarantees

Each run produces a self-contained directory with configuration snapshots, a manifest, and module outputs. Outputs are deterministic and traceable.

## Configuration & conventions

Configuration is env-first with explicit overrides. Unknown speakers are excluded from most per-speaker analyses by default.

## Power users & developers

TranscriptX is built around a DAG-based pipeline, a shared context, and strict artifact contracts. See docs/developer_quickstart.md for extension guidance.

## What’s next

See the roadmap for near-term direction and non-goals.
