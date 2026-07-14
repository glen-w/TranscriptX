Type: PRODUCT
Authority: self

# TranscriptX Roadmap

**Current version:** See [pyproject.toml](../pyproject.toml) for the package version.

**North star:** ship a credible **beta** analysis toolkit with stable contracts, great UX, and a safe path to extensibility.

> **Status legend (GitHub-style):**  
> - [ ] planned / not started  
> - [x] done  
> - [~] in progress

---

## Principles (locked)

- Core-first: analysis correctness > breadth
- Stability over novelty: contracts + tests before new features
- Observable outputs: every module produces machine-readable artifacts
- Deferred platformisation: adapters/plugins are designed, not prematurely built
- Low-regret UX: GUI is the primary interface; the **Python API** (`app.workflows`, `io.*`) is the supported path for scripting and automation

---

## Product direction

TranscriptX is evolving toward a **personal audio analysis companion**. The GUI (Streamlit) is the primary interface for interactive use; scripting, automation, and CI use the **Python API** directly (no separate terminal analysis CLI).

**Long-term goals:**

- Analyzing transcripts from personal recordings
- Supporting voice note workflows
- Conversational analytics
- Integration with local AI models (Ollama, etc.)

**Near-term (v0.1 – v0.41)**

- Harden GUI and Python API ergonomics
- Improve run summaries and explainability
- Improve speaker identification workflow
- Improve installation reliability
- Stabilize output contracts
- **Transcript-first by default** (especially Docker); optional orchestrated transcribe→import workflow later — see [Transcription architecture](#phase-2--transcription-architecture-analysis-first-integration-deferred)

**Later (v0.3+)**

- Enhanced GUI capabilities: run comparison, artifact filtering, richer visualizations
- Deeper cross-session and longitudinal views in the GUI
- Personal audio analysis workflows

---

## Local AI roadmap

**Shipped today:** local **Ollama** only (`provider` = `null` | `ollama`).

**Deferred (post-beta / Phase 2+):**

- [ ] **OpenAI and other remote LLM providers** — beyond Ollama; reintroduce when local-first beta is stable
- **Host-side transcription services (optional)** — same bridge pattern as Ollama: HTTP provider on the Mac, GUI in Docker calls `host.docker.internal`; see [Transcription architecture](#phase-2--transcription-architecture-analysis-first-integration-deferred)
- **Optional remote compute** (e.g. Colab) — for users who prefer cloud-based inference

These would enable summarization, conversational insights, and semantic analysis while keeping TranscriptX local-first and modular.

---

## Phases (priority order)

### Phase 1 — Beta-ready (now)

**Goal:** Install, core flows, and docs work for a beta user with no bugs.

- Install path: one canonical sequence (venv → requirements.txt → pip install -e .); script and README aligned
- Core flows: GUI, single-transcript analysis (API), batch analysis (API), groups — all run and produce outputs
- Docs: README Quickstart, manual install, verify-install step, env vars, troubleshooting
- Dependencies: version consistency (requirements.txt, lock, launcher, CI)
- CI: smoke, contracts, fast gates pass; build_sanity validates "install then run"

**No new features;** stability and "it works" for a first-time clone/install.

---

### Phase 2 — Transcription architecture (analysis-first; integration deferred)

**Default stance:** TranscriptX is **analysis-first**. Users arrive with transcript JSON from WhisperX, whispermlx, AssemblyAI, Deepgram, Otter, manual export, etc. Managed import is the admission gate; analysis runs on library-valid canonical transcripts. See [transcription.md](runtime/transcription.md).

**Keep transcription separate from the analysis runtime.** This is intentional, not a temporary gap:

| Layer | Role | Typical host |
|-------|------|----------------|
| Transcription | Audio → JSON (segments, speakers, timestamps) | Mac host venv (whispermlx), WhisperX Docker, SaaS |
| TranscriptX | Import → analyze → artifacts | Docker (`transcriptx-web`) or native `./transcriptx.sh` |

**Why not one integrated engine?**

- **Docker (recommended install)** runs Linux. **whispermlx** requires macOS + Apple MLX; a Mac venv binary cannot run inside the container (see [transcription.md](runtime/transcription.md#design-why-transcription-stays-outside-the-gui)).
- An earlier **Transcribe Audio** experiment invoked whispermlx via `subprocess` on the same native macOS host as Streamlit. That broke down for Docker users and duplicated what a shell loop or `whispermlx-missing` already does well—so the page is now an **instruction hub** only.
- Merging stacks would couple analysis releases to transcription toolchains (ffmpeg, HF tokens, model weights, platform quirks).

**Current state (v0.1.x)**

- [x] **Transcribe Audio** GUI — instruction hub (shell examples, `whispermlx-missing`); no in-app transcription forms.
- [x] **Import Transcript** GUI + `run_managed_import_workflow()` — all platforms; primary handoff after external transcribe.
- [x] **`whispermlx` provider** (services layer) — retained for programmatic/CLI use; not wired to Streamlit forms.
- [ ] **WhisperX (Docker) GUI orchestration** — **deferred** (not beta). External recipe at `docs/recipes/whisperx/`; provider file kept unregistered until this lands.
- [ ] Remote / HTTP `TranscriptionProvider` implementations — **deferred** with WhisperX GUI / host service work.

**Recommended workflows today**

- **Docker + Mac:** transcribe on the host (`whispermlx`, `whispermlx-missing`, or WhisperX recipe) → **Import Transcript** in the web UI (or programmatic managed import). Do not expect `docker exec` or sourcing `whisperx.env` inside `transcriptx-web` to run whispermlx.
- **Native Mac:** same host transcribe → **Import Transcript**; use **Transcribe Audio** in the UI for copy-paste commands.

**Future: integrated *workflow*, not integrated *engine***

For non-technical users, the goal is a **single guided pipeline** in the GUI — not running MLX inside the Linux container. Pattern: same as **Ollama** today (`TRANSCRIPTX_LLM_BASE_URL` → `http://host.docker.internal:11434`): the container calls a **host-side HTTP service**; it does not execute the host binary.

Planned direction (optional Phase 2+):

- [ ] **HTTP `TranscriptionProvider`** — e.g. `WHISPERMLX_BASE_URL` / `WHISPERX_SERVICE_URL` pointing at a daemon on the host (`host.docker.internal` from Docker on Mac/Windows).
- [ ] **Host transcribe service** — thin wrapper around whispermlx CLI or WhisperX; health check + job status + JSON output compatible with existing import adapters (WhisperX-style segments; diarization preserved).
- [ ] **Orchestrated UI flow** — Transcribe → managed import → optional auto-analyze, with progress and presets; no terminal, venv, or manual upload step for casual users.
- [ ] **WhisperX Docker GUI orchestration** — compose/exec or HTTP against the reference recipe, not a bespoke engine in the main image.

**Explicit non-goals for transcription integration**

- Running whispermlx or MLX inside `transcriptx-web` on Mac Docker.
- Replacing external tools with a built-in transcription engine in the core package.
- Realtime / streaming transcription (see [Out of scope](#out-of-scope-next-6-months)).

Configuration remains env-driven (`whisperx.env`, provider registry); no transcription engine ships as a required dependency of the analysis core.

---

### Phase 2 — UX + stability (next)

**Goal:** GUI and automation APIs feel intentional; outputs and contracts are solid.

- UX v1: smoother GUI flows (file selection, progress, clear errors) and stable Python API examples
- GUI polish and guardrails (probe-gated startup, canonical paths)
- Stats consolidation (unified stats MD/JSON, module status table)
- Contract tests and output schema stability
- Internal cleanup: error types, pipeline failure semantics, config/secrets via env only

---

### Phase 3 — Optional / advanced (later)

**Goal:** Richer analysis and tooling without blocking beta or stability.

- **Longitudinal speaker tracking v1 and v2** — including **web visualization** (speaker-over-time charts, cross-session views). Richer speaker-over-time and DB-backed analytics views are planned.
- Emotion/sentiment convergence (multi-label, tension metrics, divergence summaries)
- NER-driven insight (entity–sentiment, concordance, timelines)
- Interaction and network analysis (graphs, network outputs)
- Adapters and plugins (design only; no marketplace)
- Architecture cleanup and module contract docs

---

## Deferred to post-beta

The following are explicitly **not** part of the beta-ready scope; they are planned for a later release:

- **WhisperX Docker GUI orchestration** (+ host HTTP transcribe service and orchestrated Transcribe → Import → Analyze UI) — see Phase 2 transcription architecture above.
- **OpenAI and other remote LLM providers** — Ollama only until then.
- **Longitudinal speaker tracking / Speakers UI** — speaker-over-time charts, cross-session views, restored Speakers / Speaker Detail pages, and related extended speaker features.
- **Eng backlog (not Phase 1):** pooled wordcloud deferred variant matrix, recordings upload retention policy, ConvoKit/BERTopic rewire, large export-system and config-knobs refactors.

### ConvoKit analysis (archived)

**ConvoKit** coordination/accommodation analysis was archived due to **dependency conflicts** with the current stack. Re-enablement is planned for later once version constraints are resolved.

**Dependency issues:** convokit 3.5.0 requires `numpy>=2.0.0`, `spacy>=3.8.2`, and `thinc>=8.3.0,<8.4.0`. These conflict with current project pins (e.g. numpy 1.26.4, spacy 3.7.5, thinc 8.2.5) used by NER and other modules.

To re-enable: resolve convokit/numpy/spacy/thinc versions, then re-implement the module under `src/transcriptx/core/analysis/convokit/` and re-wire the pipeline module registry, analysis config, and aggregation registry.

---

## Milestones (reference)

- **M1:** Beta-ready — install, core flows, docs, CI (Phase 1)
- **M2:** UX v1 — GUI polish and API/docs parity (Phase 2)
- **M3:** v0.42 — current release; calmer architecture (Phase 2 + selected Phase 3 items)

---

## Sprint plan (archived backlog)

Historical sprint notes (Sprints 1–12) were previously linked from this file; the archive file is no longer in-tree. Focus remains Phase 1 (beta harden) then Phase 2.

---

## Out of scope (next 6 months)

- Full plugin marketplace
- Realtime transcription
- Cloud hosting / SaaS
- Heavy ML model training
- Mobile apps

---

## Success criteria (6-month horizon)

- A serious researcher can trust the outputs and cite the artifacts
- Stats outputs are coherent (MD + JSON) and stable across versions
- Adding a new analysis module feels low-risk
- GUI and Python workflows for speaker identity exist and do not corrupt data; richer speaker-over-time visualization is deferred to a later release
- You still enjoy working on the codebase
