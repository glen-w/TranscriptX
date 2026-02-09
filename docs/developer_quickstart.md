# Developer Quick Start — TranscriptX

This guide is for developers who want to understand how TranscriptX is structured internally and how to extend it safely, without reading the entire codebase.

It prioritises mental models, execution flow, and stable extension points over exhaustive reference.

## 1. Mental model

TranscriptX is a deterministic analysis pipeline for transcripts.

At a high level:

1. A canonical transcript (JSON) is the single source of truth.
2. An analysis run executes a set of modules over that transcript.
3. Modules execute in dependency-aware order (a DAG).
4. Modules share data only via a PipelineContext.
5. Each module produces structured artifacts.
6. Artifacts are written through a shared OutputService.
7. Each run is isolated, reproducible, and traceable.

Narrative flow:

canonical transcript  
→ dependency resolution (DAG)  
→ module execution  
→ artifact writing + manifest  
→ inspection (CLI / WebUI / downstream tools)

If an output exists, it can always be traced back to the input transcript, the effective configuration, and the modules that produced it.

## 2. Repository layout

src/transcriptx/  
├── cli/ — Typer-based CLI workflows  
├── core/  
│   ├── analysis/ — Analysis modules (primary extension surface)  
│   ├── pipeline/ — DAG construction & execution  
│   ├── output/ — Artifact writing & manifest tracking  
│   ├── transcript/ — Canonical transcript structures  
│   └── config/ — Configuration resolution  
├── web/ — Streamlit WebUI (reads run outputs)  

data/  
├── recordings/ — Input audio  
├── transcripts/ — Canonical transcript JSON  
└── outputs/ — Analysis run outputs  

.transcriptx/ — Local runtime state  
scripts/ — Utility scripts  
tests/ — Pytest-based tests

## 3. How an analysis run works

Runs are initiated via the CLI or programmatically. Configuration is resolved from defaults, environment variables, config files, and CLI overrides, then snapshotted for reproducibility.

Each module declares its dependencies. The pipeline builds a DAG, sorts it, and executes modules deterministically. Modules communicate only through the shared PipelineContext.

Failures stop dependent modules but preserve completed artifacts.

## 4. Adding a new analysis module

1. Create a new module under src/transcriptx/core/analysis/.
2. Define a module class inheriting from AnalysisModule.
3. Implement run_from_context(context, output).
4. Read inputs from context.
5. Write artifacts via output.
6. Register the module in the module registry.
7. Add a minimal test under tests/analysis/.

## 5. Outputs and artifacts

Each run produces a directory containing configuration snapshots, a manifest, and module folders. Directory structure and artifact schemas are treated as stable contracts.

## 6. Configuration & conventions

TranscriptX uses env-first configuration. Unknown speakers are excluded from most per-speaker analyses by default to avoid misleading outputs.

## 7. Performance & dependencies

Modules are loosely grouped into light, medium, and heavy. Heavy modules should be gated and degrade gracefully if optional dependencies are missing.

**BERTopic status:** BERTopic is currently unwired due to dependency conflicts (scikit-learn/transformers/sentence-transformers/huggingface_hub). The code is retained under `core/analysis/bertopic/` and `core/analysis/aggregation/bertopic.py`. Re-enabling requires re-registering the module and aggregation, restoring a `bertopic` extra, and verifying the dependency stack in a dedicated environment.

## 8. Development workflow

Use editable installs, run tests with pytest, inspect manifest.json and run_config_effective.json when debugging.

## 9. What not to do

Do not write directly to disk, mutate canonical transcripts, rely on global state, or introduce undeclared cross-module coupling.
