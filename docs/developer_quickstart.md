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
│   ├── config/ — Configuration resolution  
│   └── domain/ — Canonical transcript and group structures  
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

## 4. Adding a new analysis module (worked example)

**1. Create the module** under `src/transcriptx/core/analysis/<module_name>/`. Define a class inheriting from `AnalysisModule`, set `self.module_name = "<module_name>"`, and implement `run_from_context(self, context)`.

**2. Requirements and optional deps.** In your module, use `context.get_segments()` and other context APIs. If the module needs speaker labels or audio, declare `Requirement.SPEAKER_LABELS` or use the pipeline’s requirement resolver. For optional heavy deps (e.g. voice, NLP), use `optional_import("package_name", "Description", "package_name", auto_install=False)` and skip or degrade when missing. Add an extra in `pyproject.toml` (e.g. `[voice]`, `[nlp]`) and document it so installs stay deterministic.

**3. Output contract.** Do not build paths by hand. Use `create_output_service(context.transcript_path, self.module_name, run_id=..., output_dir=..., runtime_flags=...)` from the pipeline’s output helpers, then `output_service.save_data(payload, base_name, format_type="json")` or `save_text(...)`. For versioned namespaces (e.g. `voice/v1/`), set `output_namespace` and `output_version` in the registry entry so the run root gets `<namespace>/<version>/` (see `docs/output_conventions.md`).

**4. Registry entry.** In `src/transcriptx/core/pipeline/module_registry.py`, inside `_setup_modules()`, add an entry to `module_definitions` with at least: `description`, `dependencies` (list of other module names or `[]`), `category` (`"light"` | `"medium"` | `"heavy"`), `determinism_tier` (e.g. `"T0"`), `requirements` (e.g. `[Requirement.SEGMENTS]` or `[Requirement.SEGMENTS, Requirement.SPEAKER_LABELS]`), `enhancements` (often `[]`). Optionally: `requires_audio`, `requires_multiple_speakers`, `exclude_from_default`, `output_namespace`, `output_version`. Then add the module’s lazy loader to the `module_definitions` → `ModuleInfo` construction (see existing entries for the pattern: `function` is a callable that imports and returns the module class or run function).

**5. Test.** Add a test under `tests/analysis/` or `tests/contracts/` that either mocks the pipeline and checks your module’s `analyze()` output shape, or runs the pipeline with `selected_modules=["<module_name>"]` on `tests/fixtures/mini_transcript.json` and asserts expected files under the run dir (see `tests/contracts/test_run_results_and_manifest_contracts.py` for a pipeline run + manifest check).

**6. Validate registry.** Run `python scripts/validate_registry.py` to ensure no duplicate names, valid categories, and every dependency is a registered module.

## 5. Outputs and artifacts

Each run produces a directory containing configuration snapshots, a manifest, and module folders. Directory structure and artifact schemas are treated as stable contracts.

## 6. Configuration & conventions

TranscriptX uses env-first configuration. Unknown speakers are excluded from most per-speaker analyses by default to avoid misleading outputs.

## 7. Performance & dependencies

Modules are loosely grouped into light, medium, and heavy. Heavy modules should be gated and degrade gracefully if optional dependencies are missing.

**BERTopic status:** BERTopic is currently unwired due to dependency conflicts (scikit-learn/transformers/sentence-transformers/huggingface_hub). The code is retained under `core/analysis/bertopic/` and `core/analysis/aggregation/bertopic.py`. Re-enabling requires re-registering the module and aggregation, restoring a `bertopic` extra, and verifying the dependency stack in a dedicated environment.

## 8. Development workflow

Use editable installs, run tests with pytest, inspect manifest.json and run_config_effective.json when debugging.

**Docker:** The image uses `ENTRYPOINT ["transcriptx"]` and expects the host data tree mounted at `/data` (same layout as the repo: `data/recordings`, `data/transcripts`, `data/outputs`). When changing the Dockerfile or dependency constraints, build and run a quick smoke (e.g. `docker run ... analyze -t /data/transcripts/... --modules stats --skip-confirm`) to avoid "works locally, fails in container" drift. The builder stage installs with `-c constraints.txt`; do not add pip installs in the runtime stage or without constraints. Full details: [docker.md](docker.md) and the [Architecture](ARCHITECTURE.md#docker-runtime--deployment) Docker section.

## 9. What not to do

Do not write directly to disk, mutate canonical transcripts, rely on global state, or introduce undeclared cross-module coupling.

## 10. Follow-up / technical debt

- **CLI duplication:** Batch workflows, file selection, and `analysis_workflow` share repeated patterns (progress, skip/confirm, path resolution). The WAV workflow refactor (`wav_processing_workflow/` + `wav_workflow_ui`) is the template for extracting shared helpers; consider auditing other CLI entry points and consolidating where it hurts most.
