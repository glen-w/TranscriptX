# Public surfaces contract

This document defines which TranscriptX surfaces are **supported** and which are explicitly **not supported**. It is the contract for how users and contributors are expected to interact with the system.

## 1. Supported public surfaces

### 1.1 GUI (Streamlit web app)

- The **Streamlit web interface** (launched via `transcriptx` or `python -m transcriptx.web`) is the **primary supported interface**.
- Supported operations include:
  - Importing transcripts into managed storage (managed import workflow).
  - Running analysis on individual transcripts and groups.
  - Viewing results via **Transcript → Overview → Insights → Charts → Artifacts**.
  - **Correct mode** on Transcript for word/span propose/apply (see [runtime/corrections-viewer.md](runtime/corrections-viewer.md)); Corrections Studio for batch/detector/LLM review.
  - Managing basic settings exposed in the UI.
- Use **Artifacts** (Browse / Preview / Export). Overview / Artifacts ZIP export includes selected files plus generated `index.html` and, when `ebooklib` is available, `index.epub` (see [runtime/export.md](runtime/export.md)). Legacy `Data` / `Explorer` (File List) page keys are no longer supported (removed in 0.9.7).
- Built-in layout profiles are immutable (`default` / **Standard**, `executive`, `meeting_followup`, `speaker_focus`, `minimal`, `developer_debug`, and generated `all`). Switch, preview, edit (custom), and clone via **Settings → Dashboard Builder**; custom layouts live under `{config_dir}/profiles/ui_layouts/` (`PROFILES_DIR/ui_layouts`). Charts Overview strip selection is **Settings → Configuration → Charts overview**, not the Builder.
- **Optional rollback:** Speaker Identification mounts the Streamlit Components v2 workspace by default when `transcriptx-workspaces` is installed. Roll back to the classic fragment UI with `TX_SPEAKER_ID_WORKSPACE_COMPONENT=0`; missing package falls through to classic automatically. See [theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md).
### 1.2 Python API

- The **Python API** is a supported surface for scripting and automation.
- Core entrypoints include:
  - `run_managed_import_workflow` (managed import) — canonical import path: `from transcriptx.io.managed_import_workflow import run_managed_import_workflow`.
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

### 1.5 First-run experience (not extra entrypoints)

- Prefer **task documentation** and a **clear, complete GUI** over reduced presentation modes or in-app tours.
- Guided / Full controls, Getting started checklist, and bundled demo-project load/remove were **trialled in 0.9.6 and removed** (see [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md) §16). They are not supported product surfaces.

### 1.6 Transcription command generation (GUI capability)

- Generating shell/CLI commands for **external** transcription tools (whispermlx, whispermlx-missing, WhisperX Docker, Whisper-WebUI Gradio deploy) is a shipped **GUI capability** (**0.9.4**+): copyable only; Streamlit does not execute transcription. Whisper-WebUI is an **optional interoperability recipe** only — ownership disclaimer and smoke-test limits: [recipes/whisper-webui/README.md](recipes/whisper-webui/README.md).
- Supported product path remains: external transcript → managed import → analysis.
- Corpus helpers such as `scripts/whispermlx-missing.py` and `scripts/inbox-watch.py` are documented user-facing scripts when referenced from runtime docs; they are not a replacement for managed import. `inbox-watch` converts/copies on the host and may invoke `whispermlx-missing`; Streamlit does not execute it.
- Audio **preprocess** / **merge** are available in the GUI under **System → Tools** (Preprocessing and Merge tabs), with CLI helpers `scripts/audio_preprocess.py` / `scripts/audio_merge.py` for automation. Documented in transcription docs; 1.x theme **G1** still decides invest in transcript-part stitching vs remove helpers ([ROADMAP.md](ROADMAP.md)).
- **Workspace backup / restore** is available in the GUI under **Settings → Storage**, with helper script `scripts/workspace_backup.py` and Python API `transcriptx.services.workspace_backup` for large corpora. Normative rules: [contracts/workspace-backup.md](contracts/workspace-backup.md). This is **not** a `transcriptx <subcommand>` CLI.

## 2. Not supported surfaces / patterns

The following patterns are **explicitly not supported** and should be avoided in user flows, docs, and contributions:

### 2.1 Direct CLI analysis commands

- There is **no supported** `transcriptx <subcommand>` analysis CLI.
- The `transcriptx` console script:
  - Only launches the web interface.
  - Accepts `--host` and `--port` flags.
- Any usage of `transcriptx analyze ...`, `transcriptx transcript ...`, or similar subcommands is considered deprecated and unsupported.

### 2.2 Legacy Streamlit entry (`web/streamlit_app.py`)

- The former `src/transcriptx/web/streamlit_app.py` stub has been **removed**.
- Canonical GUI module: `transcriptx.web.app`.
- Supported launch commands:
  - `transcriptx`
  - `python -m transcriptx.web`
  - `streamlit run src/transcriptx/web/app.py`

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