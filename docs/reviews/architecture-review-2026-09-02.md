# TranscriptX architecture review (evidence, not docs)

**Maintainer assessment** under [docs/reviews/](index.md). Dated snapshot (2026-09-02), not a contract. Where this disagrees with contracts or `src/`, **code and contracts win**. Hosted at `/guide/reviews/architecture-review-2026-09-02/` after `make docs`.

Static reconstruction of the TranscriptX tree as of 2026-09-02. No runtime execution, no test run, no code changes. Where docs and code disagree, **code wins**.

---

## A. System model — what the software actually does

TranscriptX is a **single-process, local-first transcript analysis workbench**. It does **not** transcribe audio itself, does **not** expose a REST API, does **not** authenticate users, and does **not** use the SQLite file that exists on disk.

```{mermaid}
flowchart TB
  subgraph host [Host machine]
    Media[Recordings and raw STT JSON]
    STT[whispermlx / WhisperX / WebUI]
    Ollama[Ollama HTTP]
  end
  subgraph process [One Python process]
    GUI[Streamlit pages via session_state page key]
    API[app.workflows Python API]
    Import[Managed import + adapters]
    Stores[JSON stores + FileLock]
    DAG[RunOrchestrator + module DAG]
    Watcher[In-process directory watcher thread]
  end
  Media --> STT
  STT -->|writes originals/| Media
  GUI -->|copyable commands only| STT
  GUI --> Import
  API --> Import
  Watcher --> Import
  Import --> Stores
  GUI --> DAG
  API --> DAG
  DAG --> Ollama
  DAG --> Out[outputs_dir run folders]
  Stores --> GUI
  Out --> GUI
```

**Actual product path:** external STT → managed import (canonical JSON + sidecar + archived original) → optional speaker ID / corrections → in-process DAG analysis → browse/export artifacts.

**Trust domain:** the OS user who runs the process, plus loopback Streamlit bind. `TRANSCRIPTX_BIND_HOST=0.0.0.0` is an unauthenticated LAN bind ([SECURITY.md](../../SECURITY.md)).

**Doc vs code:** [docs/runtime/STORAGE.md](../runtime/STORAGE.md) still lists `state/transcriptx.db`. That file exists locally with Alembic tables. **Live `src/` has zero SQLite/SQLAlchemy/Alembic references.** Persistence is JSON + locks. Theme J (analytics DB) is roadmap, not current architecture.

---

## B. FR list

Outcomes inferred from code, contracts, workflow docs, pages, and tests. Implementation details are DPs, not FRs.

### Core product behaviour

- **FR1** Admit an external transcript into a managed library that later analysis will accept.
- **FR2** Help the user transcribe on the host without TranscriptX executing STT.
- **FR3** Prepare audio (preprocess / merge) before external STT.
- **FR4** Map diarized `SPEAKER_n` labels to durable names/profiles, with optional local voice matching.
- **FR5** Propose and apply transcript text corrections (viewer span edits + Corrections Studio).
- **FR6** Run a selected analysis plan on one transcript and persist a inspectable run.
- **FR7** Run analysis across a named group of transcripts and persist group-level results.
- **FR8** Run the same analysis plan across many transcripts (batch).
- **FR9** Inspect a completed run: overview, transcript, insights, charts, artifacts.
- **FR10** Export selected run artifacts as a downloadable archive.
- **FR11** Create and edit groups of transcripts.
- **FR12** Search phrase text across the corpus.
- **FR13** Rename a managed transcript and keep companions consistent.
- **FR14** Maintain longitudinal speaker profiles (display names, links, optional avatars/voice).
- **FR15** Optionally interpret runs with a local LLM (Ollama).
- **FR16** Browse the library and delete a selected managed transcript after confirmation.

### Supporting operational behaviour

- **FR17** Persist project settings, analysis/UI/STT presets, and dashboard layouts across sessions.
- **FR18** Watch folders and admit new transcripts (audio is queued, not transcribed).
- **FR19** Backup and restore a workspace.
- **FR20** Preview-and-confirm destructive cleanup (duplicate files, old runs).
- **FR21** Refuse to operate on an incompatible data-root schema epoch, with non-destructive remediation.
- **FR22** Run the same GUI via Docker Compose with host mounts.
- **FR23** Diagnose and repair incomplete renames, speaker-profile integrity, and dependency health.
- **FR24** Script import and analysis without the GUI (`app.workflows`, `run_managed_import_workflow`).

### Cross-cutting

- **FR25** Transcript JSON and managed artifacts have a single write authority and survive crash mid-write.
- **FR26** Run success/failure is recorded as typed execution truth, not inferred from leftover files.
- **FR27** Source material and outputs stay on the local machine; there is no product authn/authz layer.
- **FR28** Effective config is layered: environment, run/draft override, project `config.json`, defaults.
- **FR29** Missing optional extras (NLP, voice, LLM, plotly) degrade to skip/block rather than crash the workbench.
- **FR30** Speaker ID and Corrections mutations are revisioned and duplicate-safe across Streamlit reruns.
- **FR31** An operator can tell that a run started, which modules finished, and where logs/perf traces went.

### Ambiguous / inferred / contradictory (flagged)

| ID | Issue |
|----|--------|
| FR2 | Page is named **Transcribe Audio** but only generates copyable commands. Documented in [public_surfaces.md](../public_surfaces.md) and `transcribe_audio.py`; still an affordance mismatch. |
| FR7 vs FR8 | Group vs batch are separate request types and UI targets; “batch” is also a legacy page key (`Batch Ops` → Run Analysis). |
| FR18 | Watcher Phase 1 landed; audio path is **offer/queue**, not STT. Easy to over-read as “auto-transcribe”. |
| FR25 vs `processing_state.json` | Contract says `run_results.json` is run truth; rename/audio-link code still treats processing state as an index. Dual index, not dual product FR. |
| STORAGE vs code | SQLite listed in storage contract; unused. **Inferred that file-backed JSON is the real persistence FR.** |
| FR27 | “Local-first security” is a trust-model FR, not implemented authorization. LAN bind is a supported config that silently drops the trust model. |

---

## C. DP list with code evidence

| ID | Design parameter | Evidence |
|----|------------------|----------|
| **DP1** | Streamlit shell: bootstrap, session page key, sidebar, lazy page import | [`web/app.py`](../../src/transcriptx/web/app.py) `main` path; [`router.py`](../../src/transcriptx/web/router.py); [`navigation.py`](../../src/transcriptx/web/navigation.py) `PAGE_SPECS`; [`state.py`](../../src/transcriptx/web/state.py) |
| **DP2** | Managed import workflow + adapters + admission | [`io/managed_import_workflow.py`](../../src/transcriptx/io/managed_import_workflow.py) `run_managed_import_workflow`; [`admit_and_register.py`](../../src/transcriptx/io/admit_and_register.py); [`io/import_admission.py`](../../src/transcriptx/io/import_admission.py) `sanitize_upload_basename` |
| **DP3** | `TranscriptStore` sole transcript JSON writer | [`core/store/transcript_store.py`](../../src/transcriptx/core/store/transcript_store.py); contract test [`tests/contracts/test_write_authority.py`](../../tests/contracts/test_write_authority.py) |
| **DP4** | Import sidecars / managed-transcript gate | `sidecar_path_for_transcript`, `validate_managed_transcript`; [`pipeline_legacy_compat.enforce_managed_transcript_gate`](../../src/transcriptx/core/pipeline/pipeline_legacy_compat.py) |
| **DP5** | File-backed groups | [`core/store/group_manifest_store.py`](../../src/transcriptx/core/store/group_manifest_store.py) `uuid4` ids, **names not unique** |
| **DP6** | Speaker profile tree + `assert_safe_relpath` | [`core/speaker_profiles/`](../../src/transcriptx/core/speaker_profiles/); [`path_safety.py`](../../src/transcriptx/core/speaker_profiles/path_safety.py) |
| **DP7** | Speaker ID page + action protocol + optional CCv2 | [`web/page_modules/speaker_id.py`](../../src/transcriptx/web/page_modules/speaker_id.py) (~2k LOC); [`web/workspaces/speaker_id_bridge.py`](../../src/transcriptx/web/workspaces/speaker_id_bridge.py); [`packages/transcriptx_workspaces`](../../packages/transcriptx_workspaces) |
| **DP8** | Corrections revisioned commands | [`app/corrections/protocol.py`](../../src/transcriptx/app/corrections/protocol.py) `CorrectionsActionService`; [`core/store/corrections_session_store.py`](../../src/transcriptx/core/store/corrections_session_store.py) |
| **DP9** | Analysis workflow + thin controller | [`app/workflows/analysis.py`](../../src/transcriptx/app/workflows/analysis.py) `run_analysis`; [`app/controllers/analysis_controller.py`](../../src/transcriptx/app/controllers/analysis_controller.py) |
| **DP10** | RunOrchestrator + DAG execution | [`run_orchestrator.py`](../../src/transcriptx/core/pipeline/run_orchestrator.py); [`pipeline.py`](../../src/transcriptx/core/pipeline/pipeline.py) `run_analysis_pipeline`; `dag_pipeline_*.py` |
| **DP11** | Module registry + analysis packages | [`module_registry.py`](../../src/transcriptx/core/pipeline/module_registry.py); [`core/analysis/`](../../src/transcriptx/core/analysis/) |
| **DP12** | Write-side run persistence | [`pipeline_write_phases.py`](../../src/transcriptx/core/pipeline/pipeline_write_phases.py) order: `run_results.json` then `manifest.json`; [`run_outcome_truth.py`](../../src/transcriptx/core/pipeline/run_outcome_truth.py) |
| **DP13** | Path roots / env path resolution | [`core/utils/paths.py`](../../src/transcriptx/core/utils/paths.py) `PathSettings`, `PATHS`; import fan-in ~111 |
| **DP14** | Dual config: live dataclass facade + pydantic project config | [`core/utils/config/__init__.py`](../../src/transcriptx/core/utils/config/__init__.py) `_global_config`; [`core/config/persistence.py`](../../src/transcriptx/core/config/persistence.py); `apply_project_config_to_live_facade()` in `web/app.py` |
| **DP15** | Module/workflow `ProfileManager` JSON files | [`core/utils/profile_manager.py`](../../src/transcriptx/core/utils/profile_manager.py) `get_profile_path` concatenates `profile_name` **with no `..` rejection** |
| **DP16** | STT command generation (never executed) | [`services/transcription/command_gen.py`](../../src/transcriptx/services/transcription/command_gen.py); [`web/page_modules/transcribe_audio.py`](../../src/transcriptx/web/page_modules/transcribe_audio.py) |
| **DP17** | Directory watcher thread + file `JobStore` | [`services/watcher/service.py`](../../src/transcriptx/services/watcher/service.py) process singleton |
| **DP18** | Ollama client | [`core/llm/ollama_client.py`](../../src/transcriptx/core/llm/ollama_client.py) tenacity retries, Docker host remap |
| **DP19** | Export ZIP/EPUB | [`web/components/export_panel.py`](../../src/transcriptx/web/components/export_panel.py); `HARD_CAP_BYTES` in `export/types.py` |
| **DP20** | Managed rename journal + `processing_state.json` | [`rename_transaction.py`](../../src/transcriptx/core/utils/rename_transaction.py); [`processing_state.py`](../../src/transcriptx/core/utils/processing_state.py); Diagnostics repair |
| **DP21** | Recordings upload + preprocess/merge | [`web/services/recordings_service.py`](../../src/transcriptx/web/services/recordings_service.py) `save_uploaded_file` uses **raw `uploaded_file.name`**; `app/workflows/preprocess.py`, `merge.py` |
| **DP22** | Workspace backup/restore | [`services/workspace_backup.py`](../../src/transcriptx/services/workspace_backup.py) |
| **DP23** | Schema-epoch gate | [`web/schema_epoch_gate.py`](../../src/transcriptx/web/schema_epoch_gate.py); `core/utils/schema_epoch.py` |
| **DP24** | `FileLock` + atomic `.tmp`/`os.replace` | [`file_lock.py`](../../src/transcriptx/core/utils/file_lock.py); store writers |
| **DP25** | Logging + optional Streamlit perf JSONL + Prometheus textfile | [`core/utils/logger.py`](../../src/transcriptx/core/utils/logger.py); [`core/observability/perf.py`](../../src/transcriptx/core/observability/perf.py); `run_performance/exporter.py` |
| **DP26** | Docker Compose one service | [`docker-compose.yml`](../../docker-compose.yml) publish `127.0.0.1:8501`, health `/_stcore/health` |
| **DP27** | Host scripts (not in-app orchestration) | `scripts/inbox-watch.py`, `scripts/whispermlx-missing.py` write `originals/` only |
| **DP28** | Interface action strips | [`docs/contracts/interface-menus.md`](../contracts/interface-menus.md); `web/action_menus/` |
| **DP29** | Streamlit `@st.cache_data` corpus/module caches | [`web/cache_helpers.py`](../../src/transcriptx/web/cache_helpers.py) |
| **DP30** | Typed-phrase destructive authorization | `CleanupAuthorization`, `DuplicateAuthorization` — **not identity auth** |
| **DP31** | Analysis GUI worker thread + session snapshots | [`run_analysis.py`](../../src/transcriptx/web/page_modules/run_analysis.py) daemon `tx-run-analysis`, `analysis_run_in_progress` |
| **DP32** | Env key registry (partial) | [`env_key_registry.py`](../../src/transcriptx/core/utils/config/env_key_registry.py); **unregistered** `TX_SPEAKER_ID_WORKSPACE_COMPONENT` in [`web/workspaces/flags.py`](../../src/transcriptx/web/workspaces/flags.py) |

---

## D. Current design matrix

`X` = changing that DP could reasonably affect that FR. Only couplings evidenced by imports, shared files, session keys, or write paths.

Abbreviated: rows = FRs, columns = DPs. Full grid is sparse; **shown as FR → DP sets**. Non-obvious Xs noted.

**Core**

- FR1 → DP2, DP3, DP4, DP13, DP24, DP1 (GUI upload), DP17 (watcher), DP27 (host drop to originals)
- FR2 → DP16, DP1, DP13 (path defaults in commands), DP32
- FR3 → DP21, DP13, DP1, DP9-adjacent workflows
- FR4 → DP7, DP3, DP6, DP1, DP30-protocol (`action_id`), DP32 (CCv2 flag)
- FR5 → DP8, DP3, DP1, DP14 (corrections LLM flags)
- FR6 → DP9, DP10, DP11, DP12, DP13, DP14, DP4 (managed gate), DP18, DP31, DP1, DP25
- FR7 → FR6 DPs + DP5 + `group_analysis_runner`
- FR8 → FR6 DPs + `app/workflows/batch.py` + `batch_ops.py`
- FR9 → DP1, DP12, DP13, DP29, DP28, DP11 (module presentation)
- FR10 → DP19, DP1, DP12, DP13
- FR11 → DP5, DP1, DP13
- FR12 → DP1, DP3 (read), DP13, DP29
- FR13 → DP20, DP3, DP4, DP13, DP24, DP1, DP23-adjacent Diagnostics
- FR14 → DP6, DP1, DP13, DP22 (backup includes PII)
- FR15 → DP18, DP11, DP14, DP1
- FR16 → DP1, DP3, DP4, DP5 (tidy membership), DP20 (`drop_processing_state`), DP30

**Operational / cross-cutting**

- FR17 → DP14, DP15, DP13, DP1, DP32
- FR18 → DP17, DP2, DP13, DP1
- FR19 → DP22, DP13, DP1
- FR20 → DP30, DP13, DP1, DP12 (run dirs)
- FR21 → DP23, DP13, DP1
- FR22 → DP26, DP13, DP32, DP1
- FR23 → DP20, DP6, DP1, DP25
- FR24 → DP2, DP9, DP10 (no DP1 required)
- FR25 → DP3, DP24, DP2, DP5, DP20
- FR26 → DP12, DP10, DP9
- FR27 → DP26, DP1 (no auth), DP15/DP21 path containment gaps
- FR28 → DP14, DP32, DP13
- FR29 → DP11, DP10, DP14
- FR30 → DP7, DP8, DP1 (reruns)
- FR31 → DP25, DP12, DP31 (in-memory job; **not durable**)

**Hidden coupling called out**

- **DP13 PATHS** sits under almost every FR that touches disk (shared mutable *roots*, not shared mutable *values* after freeze — but env is read at import time via `_bootstrap`).
- **DP14 `_global_config`** is process-wide mutable; Settings hydrates it; pipeline `get_config()` reads it. Changing a Settings field can change FR6/FR15/FR7 without touching those modules.
- **DP20 `processing_state.json`** is a second index for rename/audio-link/delete (FR13/FR16) while FR26 forbids treating file presence as run truth.
- **DP1 `st.session_state`** is the only UI store: navigation, subject/run identity, in-flight analysis, flashes, CCv2 overrides.
- **DP31 daemon thread** shares snapshot dicts with the Streamlit script thread; process death drops UX state while leaving `outputs_dir` partial.
- **Duplicate `path_safety`** in speaker_profiles, llm_feedback, chart_descriptions — FR14/FR15/FR9 can drift independently.
- **DP15 vs DP6** both called “profiles”; different trees (`config_dir/profiles` vs `speaker_profiles_dir`). Naming collision is an implicit contract.

---

## E. Coupling and blast-radius findings

### Matrix thought experiments (missed or under-marked Xs)

- **If DP13 (PATHS) is replaced:** FR1–FR24 almost all break. Matrix already marks this **systemic**.
- **If DP14 (config facade) is replaced without the pydantic package:** Settings (FR17) and pipeline (FR6/FR15) diverge. First-pass matrix understated **FR9** (dashboard/overview knobs live in config models).
- **If DP3 (TranscriptStore) is bypassed:** FR4/FR5 silently corrupt library JSON. Write-authority tests exist; UI pages must keep delegating.
- **If DP12 write order changes:** FR9/FR26 consumers that still peek at `manifest.json` or charts folders will lie. Contract is explicit; some GUI paths may still be file-presence based (`on_missing_run_dir=None` legacy in [`run_scoped_page.py`](../../src/transcriptx/web/components/run_scoped_page.py)).
- **If DP31 worker is removed:** FR6 GUI cancel/skip dies; Python API FR24 is unaffected. Matrix should show DP31 as **GUI-only sequential**, not engine-wide.
- **If DP15 ProfileManager path join changes:** FR17 plus **any JSON file the process can write** (security), not just presets. First-pass matrix missed this **FR27** blast.

### DP classification

| Class | DPs |
|-------|-----|
| **Independent** (mostly one FR) | DP16 (FR2), DP19 (FR10), DP22 (FR19), DP23 (FR21), DP27 (FR2/FR1 handoff only) |
| **Sequentially coupled** (deliberate pipeline) | DP2→DP3→DP4; DP9→DP10→DP11→DP12; DP8/DP7→DP3; DP17→DP2 |
| **Cross-coupled** (unrelated FRs meet) | DP14 (settings vs analysis vs LLM vs group flags); DP20 (rename vs delete vs audio links vs processing_state); DP1 session keys; DP29 caches invalidation |
| **Systemic** | DP13 PATHS; DP14 live config; DP11 registry (adding a module ID touches GUI, presets, contracts, tests); DP24 locks (all writers); DP26 bind host (all FRs become network-reachable) |

**Dangerous “local change” DPs**

1. [`profile_manager.get_profile_path`](../../src/transcriptx/core/utils/profile_manager.py) — looks like a filename helper; writes arbitrary JSON paths.
2. [`RecordingsService.save_uploaded_file`](../../src/transcriptx/web/services/recordings_service.py) — looks like an upload helper; uses unsanitized `UploadedFile.name` (transcript import **does** sanitize).
3. [`get_config()` / `TranscriptXConfig`](../../src/transcriptx/core/utils/config) — looks like a getter; process-global behaviour switch.
4. [`module_registry`](../../src/transcriptx/core/pipeline/module_registry.py) — looks like a list; drives DAG, defaults, GUI pickers, extras, retired IDs.
5. [`PAGE_SPECS` / session `page`](../../src/transcriptx/web/navigation.py) — looks like nav chrome; gates which FRs are reachable and which caches hydrate.
6. `processing_state.json` helpers — looks like bookkeeping; rename/delete/audio association depend on it remaining consistent with the filesystem.

### Pressure points (smallest set)

- **God modules:** `logger` (~191 importers), `paths` (~111), `config` (~102), `text_utils` (~83). High fan-in is **expected** for paths/logger in a file-backed monolith; the problem is **behaviour change**, not the import count.
- **Leaky dual config:** `core.utils.config` (runtime bag) vs `core.config` (pydantic/registry/persistence). Two sources of truth for “what is settings”.
- **God pages:** `speaker_id.py`, `speakers.py` (~2k LOC each) own UI + orchestration. Domain services exist but pages still couple FR4/FR14 to Streamlit.
- **Web import cycles:** `navigation` ↔ transcript page; `cache_helpers` ↔ `file_service`. File separation ≠ architectural separation.
- **Business rules in transport:** admission size/path in IO (good); recording upload **not** using the same admission sanitizer (bad). Analysis launch flags live in session_state (necessary for Streamlit; fragile).
- **Persistence leaking upward:** PATHS imported everywhere instead of handles; group members store project-relative paths resolved against multiple bases ([`_project_relative_path`](../../src/transcriptx/core/store/group_manifest_store.py)).
- **Duplicated rules:** `normalize_language_code` ×4; path_safety ×3; two destructive-auth dataclasses.
- **Vestigial:** `data/state/transcriptx.db`; STORAGE.md “DB”; `keyring` unused in `src/`; `archive/`.
- **Not a problem merely because unfashionable:** in-process DAG, JSON stores, Streamlit as GUI, no REST API. Those match FR1–FR27.

---

## F. UI/state findings

Streamlit has **no URL routes**. State machine is `st.session_state["page"]` + subject/run keys. Shared primitives: [`empty_state.py`](../../src/transcriptx/web/components/empty_state.py) (five kinds), [`page_flash`](../../src/transcriptx/web/page_flash.py), [`run_scoped_page.py`](../../src/transcriptx/web/components/run_scoped_page.py), [`progress_panel.py`](../../src/transcriptx/web/components/progress_panel.py).

| Workflow | Goal | Affordance | Success | Failure | Recovery | States evidenced |
|----------|------|------------|---------|---------|----------|------------------|
| Import | FR1 | Uploader + folder scan | `st.success` + action strip | Per-file `st.error` | Retry; folder repair statuses | Empty submit, mixed success/fail, recording optional — [`upload_transcript.py`](../../src/transcriptx/web/page_modules/upload_transcript.py) |
| Transcribe | FR2 | Tool + paths + Copy | Preset banners | Preset load/delete errors | Edit/load another | **No job/loading for STT** (correct). Page **signifier says Transcribe**; behaviour is command gen. Explicit caption that Streamlit never executes. |
| Run analysis | FR6–8 | Run / Skip / Cancel | flash success + last-success strip | flash error | Re-run; chip returns to panel | Initial empty (no transcripts/groups), loading (fragment poll 0.5s), cancel, validation errors. **Offline/disk:** generic exception flash. **Double submit:** `analysis_run_in_progress` + `pending.started`. **Two browser tabs:** two sessions → two runs (unhandled). |
| Speaker ID | FR4 | Name/ignore/clips | “All speakers identified” + acks | mapping/schema errors | Re-import; CCv2 rollback env | Loading spinners for voice; empty speaker list info. Offline audio: clip failures in bridge. |
| Corrections | FR5 | Propose/apply; Studio accept/reject | ack `ok`; apply_export committed flag | stale revision, validation | Resume session | Protocol handles stale/duplicate `action_id`. Viewer vs Studio concurrency: tests exist for loser-raises. |
| Export | FR10 | Mode radio + Create | download button | size cap `st.error` | Narrow selection | No selection info; >500MB confirm; >2GB hard cap. **No partial ZIP resume.** |
| Run-scoped views | FR9 | Sidebar pickers | render body | missing subject/run empty_state | Library/Overview CTAs | Loading spinner on transcript page. **`on_missing_run_dir=None`** still allows some pages to proceed without a folder. |
| Settings/cleanup | FR17/20 | Save; typed phrase | panel success | lock/corrupt errors | Retry | Schema-epoch **blocks entire app** (FR21) — not a flash, a gate. |
| Watcher | FR18 | Enable in Settings | status dict | `last_errors` on service | Disable/retry | No durable GUI job list comparable to analysis progress. |

**Affordance mismatches**

- **Transcribe Audio** does not transcribe (intentional, documented, still misleading).
- **Run Analysis** looks like a form submit; actual execution is a **daemon thread** after rerun. Refreshing the browser mid-run loses the worker handle; artifacts may still be writing.
- **Library delete** confirms; **linked recordings and run folders remain** ([`library_delete.py`](../../src/transcriptx/app/library_delete.py) docstring). Visible “delete transcript” does not mean “delete analysis”. Easy to read as full purge.
- Cleanup “authorization” looks like security; it is a **typed confirmation phrase**.

**Ambiguous UI states**

- Global progress chip vs Run Analysis page can disagree after session loss.
- Caches (30–60s TTL on recordings list) can show stale files after upload until TTL/clear.
- Group names collide with no uniqueness error.

---

## G. Production failure findings

| Failure | User sees | Leftover state | Retry safe? | Idempotent? | Loss/corruption | Recovery | Operator knows |
|---------|-----------|----------------|-------------|-------------|-----------------|----------|----------------|
| Disk full mid-import | Admission/OS error | Attempt rollback of created archive/json/sidecar (`_AttemptCreated`) | Usually yes | Duplicate stem → `FileExistsError` | Original user file untouched if staging | Retry | Logs; incomplete managed set if rollback fails |
| Disk full mid-run persist | Analysis failed flash | Partial run dir; `run_results.json` may be missing (FR26 consumers must not infer from files) | New run (`rerun_mode`) | New run id | Incomplete artifacts | Re-run | Logs; Diagnostics does **not** clearly list “interrupted runs” as first-class |
| DB unavailable | N/A — no app DB | — | — | — | — | — | Orphan `transcriptx.db` unused |
| Ollama timeout/down | LLM modules failed/skipped; picker errors | Run continues for other modules (`CONTINUE_ON_ERROR` exists on contracts) | Module re-run | LLM non-deterministic | No transcript corruption | Fix Ollama, re-run | LLM errors; metrics sink default noop |
| HF Hub timeout | Extra/module blocked | None beyond failed module | Retry (one Hub retry in `hf_hub_load`) | Downloads | — | Retry / disable downloads | Logs |
| Malformed import JSON | Admission error, fail-closed | Staging cleanup policy | Yes | Yes | No library write | Fix file | UI error |
| Auth expires | N/A | — | — | — | — | — | — |
| Authorization fail | Typed phrase mismatch | No delete | Yes | N/A | None | Re-type | UI |
| Watcher crash / process restart | Watcher stopped until Settings/app start | JobStore files; in-flight import rollback or incomplete | Re-detect | Job states on disk | Possible incomplete admit | Restart app; enable watcher | `last_errors`; job files under `data/watcher/jobs/` |
| Analysis thread crash | flash `Analysis failed: …` | Partial `outputs_dir/<slug>/<run>` | New run | Not same run_id | Partial artifacts | Re-run | Exception in UI; logs. **No crash report file tied to run_id unless logging configured to file.** |
| Two concurrent analyses | Possible overlapping writes to same slug if two sessions | Two run dirs if new-run; processing_state races | Unsafe on same transcript | No | processing_state / lock timeouts | FileLock 15s typical on store | Logs `LockAcquisitionError` |
| Network gone | LLM/HF fail; local import/analysis OK | Same as module fail | Yes for local | — | — | — | |
| Missing config | Defaults / coded config errors | Draft lock timeout | Retry | — | Corrupt `config.json` → `ConfigCorruptError` | Restore backup / Settings | UI + logs |
| Unexpected schema epoch | Full-app gate | Data untouched unless user picks reset | N/A | — | Reset path is explicit and optional | Remediation UI | Gate screen |
| Double-click Run | Second launch blocked by `analysis_run_in_progress` **in that session** | One worker | — | — | — | — | |
| Docker recordings `:ro` | Uploads go to `RECORDINGS_IMPORTS_DIR` fallback | Files not in user library root | Yes | Overwrite **same dest name** | Can overwrite prior upload of same name | Unique names not enforced | Logs “Saved uploaded file” |

---

## H. Data integrity / security findings (evidenced)

**Authoritative sources**

| Data | Authority |
|------|-----------|
| Canonical transcript | Files under `transcripts_dir` **only if** managed sidecar validates; writer = `TranscriptStore` |
| Run execution truth | `outputs/.../run_results.json` via DP12 |
| Artifact inventory | `manifest.json` (not status) |
| Groups | `{group_id}.group.json` |
| Speaker profiles | JSON tree under `speaker_profiles_dir` |
| Settings | `{config_dir}/config.json` + env + draft/run override |
| Processing index | `processing_state.json` — **not** run truth; still used for rename/audio |

**Risks with evidence**

1. **Profile name path traversal (open)** — `get_profile_path` joins unsanitized `profile_name`. Same finding as [docs/dev/security_review_2026-08-23.md](../dev/security_review_2026-08-23.md) SR-01. Guardrail tests do **not** include `../`. Under loopback this is a local footgun (overwrite JSON the process can write). If LAN-bound, it is unauthenticated filesystem write. **Do not inflate to unconditional P0** given documented single-user trust; **does escalate to P0 on non-loopback bind.**
2. **Recording upload path traversal (open)** — `dest = RECORDINGS_IMPORTS_DIR / uploaded_file.name` with **no** `sanitize_upload_basename`. Transcript upload **does** sanitize. No tests of `save_uploaded_file`. Same SR-02 class. Overwrite/escape depends on client filename (browsers sometimes send paths).
3. **No app auth** — by design (FR27). Destructive UI is phrase-gated only. Binding `0.0.0.0` is the real security boundary ([SECURITY.md](../../SECURITY.md)).
4. **Secrets** — STT profiles strip token keys; `HF_TOKEN` intended in host `whisperx.env`. Optional `LLM_BASE_URL` can be any HTTP endpoint (SSRF-to-self / data exfil only if user configures it — local-first).
5. **Uniqueness** — filesystem paths; group **names** not unique; speaker **display names** not globally unique. No DB constraints.
6. **Library delete** leaves runs and recordings — intentional; creates orphans (integrity vs storage cost, not silent corruption).
7. **HTML** — `unsafe_allow_html` widely; `empty_state` escapes. XSS matters only if untrusted parties reach the UI.
8. **Deserialization** — JSON everywhere; voice `np.load(allow_pickle=False)` is the careful path. No `shell=True` found in prior review; not re-audited line-by-line here.
9. **Trust boundary** — managed import is the only library-valid admission; `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS` bypasses the gate (explicit escape hatch).

---

## I. Observability findings

| Workflow | Did it run? | Succeed? | Where failed? | Who/what? | Reproduce? | Repair? |
|----------|-------------|----------|---------------|-----------|------------|---------|
| Import | UI + logs | Admit outcomes | Per-file errors; watcher `last_errors` | Path/stem | Re-upload | Rollback/retry |
| Analysis | Progress snapshot **in session**; `run_results.json` **if persist finished** | FR26 if file written | Module rows in run_results | run_id in path | Re-run with same request **if** config snapshotted in manifest | Re-run; no surgical module repair GUI |
| Analysis crash before persist | Session flash only | **Blind** after refresh | Logs if file logging on | Weak run correlation | Hard | Manual inspect `outputs/` |
| Watcher | JobStore on disk | Job state machine | last_errors (ring buffer) | Path | Replay file | Re-enable |
| LLM | Module fail + ollama errors | Partial run | Error strings | Model name in config | Re-run | Change model |
| Docker | Compose health = Streamlit core, **not** app epoch/import | Process up ≠ data compatible | — | — | — | |

**Concrete blind spots (only where they hurt)**

- Default logger is console; `DEFAULT_LOG_FILE` exists but is optional — operators may have **no durable log**.
- LLM metrics sink defaults to noop.
- No tracing. Fine for single-user; hurts “which module hung”.
- Interrupted runs are not a first-class Diagnostics list (FR23 covers rename/speaker integrity, not half-written runs).
- Web excluded from `.coveragerc` — CI will not tell you GUI observability/regressions.

---

## J. Test gaps

Strong: contracts (write authority, run outcomes, speaker voice stages, retired IDs), import workflow, pipeline DAG, corrections concurrency, many analysis modules, ~10 GUI E2E journeys **opt-in**.

| FR | Test character |
|----|----------------|
| FR1 | Strong (`tests/io/`, gui_acceptance import) |
| FR2 | Thin (few `transcribe_audio` tests) |
| FR4/FR5 | Protocol/unit + some E2E; CCv2 FE has 2 vitest files |
| FR6–FR8 | Strong engine; GUI worker/cancel less so in default pytest |
| FR9 | Presentation tests + E2E charts; run_scoped missing-dir legacy undertested |
| FR13 | Rename tests exist; processing_state dual-index undertested as invariant |
| FR17 | Profile guardrails **omit traversal** |
| FR18 | Service tests; process-restart incomplete jobs thinner |
| FR21 | Epoch tests likely in core/utils; GUI gate less |
| FR25 | Store atomic + import rollback tests |
| FR26 | Contract tests |
| FR27/path | Speaker path_safety tested; **ProfileManager and recordings upload not** |
| Concurrency/idempotency | Corrections/speaker ops yes; **two Streamlit sessions / two analyses** no |
| Default `pytest` | Excludes smoke, integration, gui_e2e, gui_acceptance — **false confidence if you only watch the fast lane** |

Tests coupled to internals: `apply_legacy_resolver_compat` exists **to preserve monkeypatched tests** — that is a real compatibility DP, not product FR.

---

## K. Prioritised findings

**P0** — none under the **documented** loopback/single-user model that are independently “severe production outage”. The product is not a multi-tenant service.

**P0-if-LAN-exposed** (config is documented): DP15 + DP21 path traversal + unauthenticated destructive UI. Scenario: `TRANSCRIPTX_BIND_HOST=0.0.0.0` + crafted profile name or upload filename writes/deletes JSON/audio outside intended dirs.

**P1**

- **Recording upload uses unsanitized names** while import sanitizes. Scenario: file named `../../something.wav` or same-basename overwrite in `imports/`. Evidence: [`recordings_service.py`](../../src/transcriptx/web/services/recordings_service.py) vs [`sanitize_upload_basename`](../../src/transcriptx/io/import_admission.py).
- **ProfileManager path join**. Scenario: user types `../../config` as profile name; save/delete hits unexpected JSON. Evidence: `get_profile_path`.
- **In-flight analysis is session-memory**. Scenario: browser refresh or process restart during DAG: user thinks run vanished; disk has partial outputs; no Diagnostics inventory. Evidence: DP31 + persist-at-end write phases.
- **Two sessions, same transcript** can race writers (FileLock timeout / processing_state). Likely local-only but a correctness hole.

**P2**

- Dual config packages + process-global `get_config()` (FR6/FR15/FR17 cross-coupled).
- `processing_state.json` as a parallel index to filesystem + `run_results.json`.
- God pages + web import cycles (change cost for FR4/FR9).
- Duplicated path_safety / language normalize (drift).
- `TX_*` flags outside env registry (FR4/FR32 surprise).
- Module registry as systemic hub (unavoidable, but edits need a checklist).

**P3**

- “Transcribe Audio” naming vs command-gen.
- STORAGE.md SQLite / unused DB file.
- Non-unique group and display names.
- Library delete leaving runs (document more loudly in UI).
- Web omitted from coverage; E2E not in default CI.
- `unsafe_allow_html` volume (only matters if trust model changes).

**P4**

- Logger docstring vs `core/utils/logger.py` path comment.
- Fashionable rewrite to React/jobs/SQLite/event bus.

---

## L. Minimum viable architectural changes

No rewrite. No job queue framework, no SQLite Theme J, no new plugin bus. Preserve observable behaviour except the path-traversal defects.

### L1. Close write-path sanitization (defect, highest leverage)

- **Problem:** Two writers do not use the admission basename rules.
- **FRs:** FR3, FR17, FR27.
- **DPs:** DP15, DP21, DP2 (reuse sanitizer).
- **Boundary:** “Any user-supplied filename becomes a single path segment under a known root” — already true for import.
- **Independent:** profile/recording writes vs rest of pipeline.
- **Remains coupled:** PATHS roots (legitimate).
- **Files:** `profile_manager.py`, `recordings_service.py`, `import_admission.py` (shared helper or wrap), tests.
- **Unchanged:** valid single-segment names; import behaviour.
- **Tests first:** traversal `../`, separators, overwrite policy for recordings.
- **Migration:** none. **Rollback:** revert the two call sites.

### L2. One `assert_safe_relpath` implementation

- **Problem:** three copies of security-relevant path rules.
- **FRs:** FR9/FR14/FR15.
- **Boundary:** `core` path-safety helper; callers keep domain `what=` labels.
- **Do not** introduce a “VFS framework”.
- **Tests:** existing speaker_profiles tests become shared.

### L3. Config ownership without merging packages

- **Problem:** two config systems; `_global_config` is a blast radius.
- **FRs:** FR17, FR6, FR28.
- **Boundary:** `core.config` owns on-disk schema + resolver; `get_config()` is a **documented live snapshot** hydrated only at app start and Settings save (already `apply_project_config_to_live_facade`).
- **Change:** contract test that every Settings-persisted key has a pydantic field; stop adding dataclass-only knobs; register `TX_*` in `env_key_registry`.
- **Deliberately keep:** dual packages for now (merge is a rewrite).
- **Unchanged:** precedence FR28.
- **Rollback:** drop the contract test / env aliases.

### L4. Stop growing `processing_state` as truth

- **Problem:** FR26 vs rename/delete index.
- **Boundary:** treat processing_state as a **derived cache**; new features read filesystem + `run_results.json`.
- **Small positive:** Diagnostics list run dirs missing `run_results.json` (interrupted-run repair UX) — uses DP12, no new queue.
- **Keep:** existing rename journal until a later incremental migration.
- **Tests:** “listing/status must use run_results when present”.

### L5. Break the worst web cycles only when touching those files

- **Problem:** `navigation` ↔ transcript; cache_helpers cycles.
- **Do not** extract a frontend framework.
- **Boundary:** navigation must not import page modules (app.py already lazy-reexports `navigate_to_segment`). Finish that split; move remaining cycle edges to `web/services`.
- **Unchanged:** page keys and UX.

### L6. Explicitly out of scope (would add concepts FR do not require)

- Durable job service / Redis / Celery (Theme H).
- SQLite analytics (Theme J) — would add a second persistence model beside working JSON.
- Replacing Streamlit.
- Unifying speaker profiles and module profiles into one “Profile” abstraction (naming collision is annoying; merging trees would couple FR14 to FR17).

---

## M. Revised design matrix

After L1–L5, **intentional sequential chains remain**. Off-diagonals to keep:

| Remaining X | Why keep |
|-------------|----------|
| FR6 → DP13 PATHS | File-backed runs must know `outputs_dir`. Injecting handles everywhere is more abstraction than this app needs. |
| FR6 → DP14 config | Analysis behaviour is settings. Direction should stay **Settings save → hydrate facade → run**, not modules reading `os.environ` ad hoc. |
| FR1 → DP13 | Library lives on disk roots. |
| FR4 → DP3 | Speaker names are transcript mutations; single writer is the point of FR25. |
| FR13 → DP20 | Rename is multi-file; a journalled transaction is proportionate. |
| FR6 → DP11 registry | One catalogue for DAG+GUI is sequential coupling, not an accident. |
| FR27 → DP26 bind host | Network exposure is an ops switch; do not add fake auth to “fix” matrix diagonality. |
| FR9 → DP12 | Views must read run truth. |

**Removed/narrowed Xs**

- FR27 ↛ DP15/DP21 arbitrary filesystem (after sanitization).
- FR3 ↛ “any path the browser sends”.
- FR17 ↛ undocumented `TX_*` (after registry).
- New features ↛ processing_state (after L4 policy).

Matrix will **not** be diagonal. A local file workbench **should** have PATHS and config as wide columns.

---

## N. Change-risk map (use while developing)

1. **`core/utils/paths.py` / PATHS** — Appears to be constants. Breaks every disk FR and Docker mounts. **Tests:** import/path contract, docker compose bind assert, any test using tmp roots.
2. **`get_config()` / `core.config` models** — Appears to be a settings tweak. Can change module defaults, LLM, group enablement, charts, corrections. **Tests:** config resolver, the affected module’s unit tests, Settings round-trip.
3. **`module_registry.py` / `retired_public_ids.py`** — Appears to add a module. Breaks presets, GUI lists, DAG deps, extras gating, contracts. **Tests:** `tests/contracts/test_retired_*`, registry smoke, one pipeline run with the module.
4. **`TranscriptStore` / managed import / sidecar validation** — Appears to be IO. Breaks FR1/FR4/FR5/FR6 gate. **Tests:** `tests/io/`, write_authority, managed gate.
5. **`run_results.json` write phases / `run_outcome_truth.py`** — Appears to be reporting. Breaks Overview/Insights/status. **Tests:** contracts + pipeline finalize tests.
6. **`st.session_state` keys (`page`, `subject_*`, `run_id`, `analysis_run_in_progress`)** — Appears local to a page. Breaks nav, global progress, action strips. **Tests:** web navigation tests, gui_acceptance if behaviour changed.
7. **`profile_manager.py`** — Appears to be preset CRUD. Until L1, filesystem escape. **Tests:** new traversal tests + existing guardrails.
8. **Rename transaction + `processing_state`** — Appears to be rename. Breaks audio links, delete, Diagnostics repair. **Tests:** rename pipeline tests, library delete, linked_transcripts.
9. **`PAGE_SPECS` / router prerequisites** — Appears to be IA. Can hide pages or crash run-scoped views. **Tests:** navigation access tests.
10. **Speaker mapping services** — Appears to be Speaker ID UI. Must keep writing via store. **Tests:** write_authority, speaker ID e2e/deep.

---

## O. Recommended implementation sequence

Stop here until you approve. Then, in order:

1. **L1 tests then sanitization** (profile names + recording uploads). Highest defect leverage, tiny surface.
2. **L2** share path-safety helper; point the two other copies at it.
3. **Register `TX_*` in env registry** (L3 slice); document bind-host blast in Settings if a bind control exists, else leave SECURITY.md as source.
4. **L4 policy + Diagnostics “incomplete run dirs”** (read-only listing first, no auto-delete).
5. **L3 contract test** for settings keys ↔ pydantic (prevents further dual-write).
6. **L5** only as a follow-up when editing navigation/transcript (do not open a cycle-break epic).
7. **Do not** start SQLite, in-app STT, or Streamlit replacement as part of this sequence.

Optional later (not required to satisfy current FRs): incremental extraction of remaining logic from `speaker_id.py` into services already used by CCv2 — only when that page is already being changed.

---

## P. Implementation note (2026-09-02)

Sections A–O above are the pre-change reconstruction. L1–L5 from section L were implemented the same day. Observable behaviour is unchanged except the path-traversal defects (reject `../` and separators; recording names take the last path segment, matching import). L6 stayed out of scope.

### L1 — Write-path sanitization

- `ProfileManager.get_profile_path` sanitizes both `module_name` and `profile_name` via `assert_safe_path_segment`, then `assert_path_under_root`. Save/load/delete/import/export/rename return `False`/`None` on unsafe names instead of raising through the public API.
- `RecordingsService.save_uploaded_file` uses `sanitize_upload_basename` and containment under `RECORDINGS_IMPORTS_DIR`. Same-basename overwrite in that directory is unchanged.
- Tests: `tests/core/utils/test_profile_manager_guardrails.py` (traversal + separators), `tests/web/test_recordings_upload_sanitize.py`.

### L2 — One path-safety helper

- Shared implementation: `src/transcriptx/core/utils/path_safety.py` (`assert_safe_relpath`, `assert_safe_path_segment`, `assert_path_under_root`, `resolve_real`, `assert_not_symlink`).
- Domain wrappers keep their error types: `core/speaker_profiles/path_safety.py`, `core/llm_feedback/path_safety.py`. Chart descriptions reuse `resolve_real` only.
- Tests: `tests/core/utils/test_path_safety.py` plus existing speaker-profile / LLM-feedback / chart-description path tests.

### L3 — Config ownership (no package merge)

- Registered in `INFRA_ENV_ALLOWLIST` and documented in `.env.example`: `TX_SPEAKER_ID_WORKSPACE_COMPONENT`, `TX_CORRECTIONS_WORKSPACE_COMPONENT`, `TX_SID_CLIP_POLL`.
- Contract: `tests/contracts/test_settings_config_ownership.py` — every Settings registry key is a pydantic field or listed in `tests/core/config/fixtures/non_pydantic_registry_baseline.json`. Dual packages (`core.utils.config` live facade vs `core.config`) remain.

### L4 — `processing_state` as derived index

- Docstring on `core/utils/processing_state.py`: derived cache for rename/audio-link/delete; run truth stays `run_results.json`. Existing rename journal kept.
- Diagnostics lists run dirs missing `run_results.json` (read-only, no delete): `core/pipeline/incomplete_runs.py` + `_render_incomplete_runs_section` on the Diagnostics page.
- Tests: `tests/pipeline/test_incomplete_runs.py`.

### L5 — Navigation cycle only

- `navigate_to_segment` moved to `web/transcript_navigation.py`. `navigation.py` imports that module, not the Transcript page. `web/app.py` and `page_modules/transcript.py` re-export it. Page keys and UX unchanged.
- `cache_helpers` ↔ `file_service` / `sidebar_options` cycles were **not** opened (no epic rewrite).

### Verification

Targeted pytest: 103 passed (path safety, profile guardrails, recordings upload, incomplete runs, settings ownership, app imports, transcript navigation contracts, speaker-profile / chart-description / LLM-feedback path tests, env-key registry).

### Matrix items now true in code

- FR27 ↛ DP15/DP21 arbitrary filesystem.
- FR3 ↛ any path the browser sends.
- FR17 ↛ undocumented `TX_*`.
- New features ↛ `processing_state` as run truth.

SQLite Theme J, in-app STT, job queues, and Streamlit replacement were not started.