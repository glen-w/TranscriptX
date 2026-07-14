Type: CONTRACT
Authority: self

# Public surfaces contract

This document defines which TranscriptX surfaces are **supported** and which are explicitly **not supported**. It is the contract for how users and contributors are expected to interact with the system.

## 1. Supported public surfaces

### 1.1 GUI (Streamlit web app)

- The **Streamlit web interface** (launched via `transcriptx` or `python -m transcriptx.web`) is the **primary supported interface**.
- Supported operations include:
  - Importing transcripts into managed storage (managed import workflow).
  - Running analysis on individual transcripts and groups.
  - Viewing results via **Transcript → Overview → Insights → Charts → Artifacts**.
  - Managing basic settings exposed in the UI.
- Legacy GUI routes `Data` and `Explorer` (File List) redirect to **Artifacts**.
- Built-in layout profile id `default` is displayed as **Standard** and is immutable; clone via Dashboard Builder.
### 1.2 Python API

- The **Python API** is a supported surface for scripting and automation.
- Core entrypoints include:
  - `run_managed_import_workflow` (managed import).
  - `run_analysis` (single-transcript analysis).
  - Batch and group workflows as documented in `docs/generated/cli.md` and dev guides.
- These APIs expect:
  - Canonical or managed transcripts as defined in the storage and terminology contracts.
  - Use of typed request models (e.g. `AnalysisRequest`, `BatchAnalysisRequest`).

### 1.3 Managed import workflow

- The **managed import workflow** is the only supported way to admit transcripts into managed storage for library-valid analysis:
  - It performs canonical validation.
  - It writes sidecars and archival/original artifacts.
  - It enforces the storage and metadata mirroring invariants.
- Importing raw JSON directly into the canonical library without going through a managed import path is not supported for library-valid analysis.

### 1.4 Docker (operational surface)

- **Docker Compose** is a supported way to run the Streamlit web app without a local Python install.
- Supported operations mirror the GUI: import, analysis, browsing results, and settings exposed in the UI.
- Compose mounts and environment variables are operational configuration only; storage layout, output layout, and run-truth rules are defined in the contracts linked from §1.
- See `docs/runtime/docker.md` for build commands, volume mounts, and container-specific pitfalls.

## 2. Not supported surfaces / patterns

The following patterns are **explicitly not supported** and should be avoided in user flows, docs, and contributions:

### 2.1 Direct CLI analysis commands

- There is **no supported** `transcriptx <subcommand>` analysis CLI.
- The `transcriptx` console script:
  - Only launches the web interface.
  - Accepts `--host` and `--port` flags.
- Any usage of `transcriptx analyze ...`, `transcriptx transcript ...`, or similar subcommands is considered deprecated and unsupported.

### 2.2 Legacy Streamlit entry (`web/streamlit_app.py`)

- `src/transcriptx/web/streamlit_app.py` is a **deprecation stub** only (not a supported GUI).
- Canonical GUI module: `transcriptx.web.app`.
- Supported launch commands:
  - `transcriptx`
  - `python -m transcriptx.web`
  - `streamlit run src/transcriptx/web/app.py`
- The stub is scheduled for removal after 1–2 release batches.

### 2.3 Ad hoc JSON ingestion

- Directly pointing analysis at arbitrary JSON files that:
  - Have not gone through canonical validation, and
  - Are not part of the managed transcript set
- is **not supported** as a stable surface.
- Codepaths that “guess” based on filenames or directory placement (e.g. “any `.json` under `transcripts_dir`”) violate the storage and admission contracts.

### 2.4 Direct filesystem operations on managed storage

- Direct filesystem writes, renames, or deletions under:
  - `transcripts_dir` and its metadata subtrees,
  - managed outputs and state defined in the storage and output contracts,
- are **not supported** and may corrupt invariants.
- Supported behavior:
  - Use the storage rename service (`rename_managed_transcript` / web `RenameService`) for managed transcript moves; repair incomplete ops via `repair_managed_rename`.
  - Use public APIs to modify or regenerate artifacts.

## 3. Contributor guidance

- When adding new features or entrypoints:
  - Prefer the GUI and Python API as integration points.
  - Keep new surfaces aligned with this contract; if you introduce a new public surface, document it here.
- When removing or deprecating surfaces:
  - Update this document to reflect what remains supported.
  - Make deprecated patterns clearly visible in docs to avoid reintroduction.
---

## 4. Contract violations

This section describes **public surface contract violations**, how they are detected, and the expected behavior.

- **Invalid states (examples)**:
  - Docs or examples that present unsupported CLI subcommands (for example, `transcriptx analyze ...`) as if they were supported.
  - Features or codepaths that rely on direct filesystem manipulation of managed storage instead of using documented public APIs.
  - Workflows that bypass the managed import workflow while still claiming library-valid analysis guarantees.
- **Detection**:
  - Documentation reviews that compare guides and README against this contract.
  - Tests or linters that scan for references to deprecated or unsupported surfaces.
  - Code review checklists that flag direct filesystem operations on managed storage paths.
- **Expected behavior**:
  - Treat such cases as **fail-fast** documentation or API violations: update docs and/or code to align with this contract before shipping.
  - Where users depend on an unsupported surface, clearly mark it as unsupported and provide a migration path to a supported surface where feasible.

This contract is the reference point for “what is supported” in README, installation docs, and CONTRIBUTING.