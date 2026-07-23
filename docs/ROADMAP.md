Type: PRODUCT
Authority: self

# TranscriptX Roadmap

**Current version:** See [pyproject.toml](../pyproject.toml) for the package version.

**Stocktake (decision foundation):** [docs/dev/stocktake_2026-07-17.md](dev/stocktake_2026-07-17.md) — status, finished/unfinished matrix, release readiness, pitfalls, and recommended next decisions.

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
- **GPU-accelerated inference** where the host can expose it (CUDA on Linux; Apple MPS on native Mac)
- **First-class native installation** alongside Docker (venv / `./transcriptx.sh`), especially where Docker cannot use the host GPU

**Near-term (0.7.x)**

- Harden GUI and Python API ergonomics (Run Analysis presets; Settings → Models / Analysis)
- Improve run summaries and explainability
- Speaker profiles: file-backed identity, Speakers UI, voice match, locations (DB/group `profile_id` remainder deferred)
- Improve installation reliability
- Stabilize output contracts
- **CI matrix (Python 3.10–3.12) + release-checks** — see `.github/workflows/ci.yml`
- **Transcript-first by default** (especially Docker); optional orchestrated transcribe→import workflow later — see [Transcription architecture](#phase-2--transcription-architecture-analysis-first-integration-deferred)

**Later (0.8+)**

- Enhanced GUI capabilities: run comparison, artifact filtering, richer visualizations
- Deeper cross-session and longitudinal views (DB analytics / group `profile_id` gallery)
- Personal audio analysis workflows
- Optional **ask-this-transcript** chat in the viewer GUI — see [Deferred to post-beta](#deferred-to-post-beta)
- GPU and native install paths — see [Runtime acceleration & native install](#runtime-acceleration--native-install-long-term)

---

## Local AI roadmap

**Shipped today:** local **Ollama** only (`provider` = `null` | `ollama`).

**Deferred (post-beta / Phase 2+):**

- [ ] **OpenAI and other remote LLM providers** — beyond Ollama; reintroduce when local-first beta is stable
- **Host-side transcription services (optional)** — same bridge pattern as Ollama: HTTP provider on the Mac, GUI in Docker calls `host.docker.internal`; see [Transcription architecture](#phase-2--transcription-architecture-analysis-first-integration-deferred)
- **Optional remote compute** (e.g. Colab) — for users who prefer cloud-based inference

These would enable summarization, conversational insights, and semantic analysis while keeping TranscriptX local-first and modular.

---

## Runtime acceleration & native install (long-term)

**Today:** Docker Compose is the recommended install. On Mac, Compose builds a **CPU-only** torch image (`TRANSCRIPTX_TORCH_VARIANT=cpu`) because Docker Desktop does not expose the host GPU (CUDA or Apple MPS) to Linux containers. HF classifiers and related inference therefore log `Device set to use cpu`. Device selection already prefers CUDA → MPS → CPU when available (see `hf_text_classification` runtime). Native Mac/Linux install exists (`./transcriptx.sh`, venv) but is secondary to Docker in docs and support.

**Long-term (post-beta):** treat acceleration and native install as first-class product paths, not undocumented side doors.

- [ ] **Documented native install** — one canonical Mac/Linux sequence (venv → deps → `pip install -e .` / launcher) with parity to Docker for paths, env, and verify-install; clear when to choose native vs Compose
- [ ] **Apple Silicon MPS (native Mac)** — run analysis on Metal via native install; keep Docker-on-Mac as the CPU path
- [ ] **Linux CUDA (Docker)** — documented Compose + `nvidia-container-toolkit` recipe with CUDA torch wheels (`TRANSCRIPTX_TORCH_VARIANT=default`); device class remains part of inference cache identity
- [ ] **Linux CUDA (native)** — optional host venv path for users who prefer bare-metal GPU without containers
- [ ] **Honest defaults & docs** — Mac Docker stays CPU-by-design; GPU expectations live in [docker.md](runtime/docker.md) / install docs so users do not chase acceleration inside Mac containers

**Non-goals for this track:** forcing GPU into Mac Docker; requiring NVIDIA hardware for beta; changing the analysis-first / external-transcription split.

---

## Phases (priority order)

### Phase 1 — Beta-ready (0.6.x honesty → 0.7.x packaging)

**Goal:** Install, core flows, docs, and **in-repo CI** work for a beta user.

- Install path: Docker Compose (recommended) or editable git install per [install_verification_matrix.md](runtime/install_verification_matrix.md) — **not PyPI**
- Core flows: GUI, single-transcript analysis (API), batch analysis (API), groups — all run and produce outputs
- Docs: README Quickstart, manual install, env vars, troubleshooting, SECURITY.md
- Dependencies: clean-env audit + image `pip check` (see `docs/dev/dependency_audit.md`)
- CI: `.github/workflows/ci.yml` — smoke, contracts, fast on Python 3.10–3.12; release-checks job

Feature delivery continues under beta; “no new features” language is retired. Wave 0 eng criteria (A1–A10 + Config 1.7/1.8 + docs/inventory parity) are **closed**; Top-3 eng programs are **Done**. Waves 1–2 product items are **shipped** (BERTopic, `transcript_quality`, equity, `topic_shift`, B6/B7, B10, B13, Speakers 1.5/1.6/voice/locations, analysis presets; see [analysis module backlog](dev/analysis_module_backlog_2026-07-17.md)). The next public tag still requires the evidence checklist in [`docs/dev/release_governance.md`](dev/release_governance.md).

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

**Current state (0.7.x)**

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

- **Longitudinal speaker tracking v1 and v2** — **v1 identity store + Speakers UI (Phase 1.5) + Phase 1.6 analytics + avatars + voice R2 + locations pack shipped**. Richer cross-session / DB-backed analytics views and group gallery keyed by `profile_id` remain planned.
- Emotion family deepen (Phase 5 calibration for `contextual_emotion` / `fine_grained_emotion`; tension metrics; divergence summaries) — not “converge into one emotion module”
- NER-driven insight (entity–sentiment, concordance, timelines); Speakers **Locations** map from NER location mentions is shipped
- Interaction and network analysis — **B13 shipped** on `interactions` (GraphML/JSON + `interactions.network_graph.global`); turn-taking **equity pack already shipped**
- **Ask-this-transcript (viewer chat)** — optional Streamlit panel; prefer stuffed-context / lexical-retrieve-then-LLM + jump-to-segment citations over a full RAG + streaming ReAct workspace (see competitive note W1). **Shipped lighter path:** analysis-time `llm_custom_qa` (Settings library + Run/Batch picker → Insights citation cards).
- Adapters and plugins (design only; no marketplace)
- Architecture cleanup and module contract docs
- **GPU + native install** — first-class docs and recipes for MPS (native Mac) and CUDA (Linux Docker/native); see [Runtime acceleration & native install](#runtime-acceleration--native-install-long-term)

---

## Deferred to post-beta

The following are explicitly **not** part of the beta-ready scope; they are planned for a later release:

- **WhisperX Docker GUI orchestration** (+ host HTTP transcribe service and orchestrated Transcribe → Import → Analyze UI) — see Phase 2 transcription architecture above.
- **OpenAI and other remote LLM providers** — Ollama only until then.
- **Longitudinal speaker tracking / Speakers UI** — Phase 1.5–1.6 Speakers UI/analytics and Phase 2 R2 local voice suggested matches shipped (incl. file-backed residuals: accept query-evidence, eval harness, chunked merge transfer, Stage 9 digest-keyed file matrix under `.cache/voice/indexes/`). Deferred remainder: SQLite/DB analytics views, group gallery keyed by `profile_id`.
- **Ask-this-transcript (viewer GUI)** — optional chat panel over the loaded run (Ollama + existing prompt budgeting / Search jump). **Not** a Retrievia-style RAG + streaming ReAct product; that remains competitive awareness only ([competitive inspiration W1](dev/competitive_inspiration_2026-07-22.md)). Prefer local stuffed-context or lexical-retrieve-then-LLM with segment citations.
- **GPU acceleration & first-class native install** — MPS on native Mac; CUDA on Linux Docker/native; documented install parity — see [Runtime acceleration & native install](#runtime-acceleration--native-install-long-term).
- **Eng backlog (not Phase 1):** pooled wordcloud deferred variant matrix, recordings upload retention policy, ConvoKit rewire, large export Jinja2/Artifact Protocol follow-ups, optional config **1.9** structural split. **Shipped recently (not eng blockers):** BERTopic; interactions equity; `transcript_quality`; emotion-family classifiers; group LLM synthesis; Waves 1–2 analysis (B6/B7/B9/B10/B12/B13); speaker profiles + voice + locations; configurable analysis presets. Public release will clarify basic/full/llm install profiles (see [installation.md](runtime/installation.md)).

### ConvoKit analysis (archived)

**ConvoKit** coordination/accommodation analysis was archived due to **dependency conflicts** with the current stack. Re-enablement is planned for later once version constraints are resolved.

**Dependency issues:** convokit 3.5.0 requires `numpy>=2.0.0`, `spacy>=3.8.2`, and `thinc>=8.3.0,<8.4.0`. These conflict with current project pins (e.g. numpy 1.26.4, spacy 3.7.5, thinc 8.2.5) used by NER and other modules.

To re-enable: resolve convokit/numpy/spacy/thinc versions, then re-implement the module under `src/transcriptx/core/analysis/convokit/` and re-wire the pipeline module registry, analysis config, and aggregation registry.

---

## Milestones (reference)

- **M1:** Beta-ready — install, core flows, docs, CI (Phase 1)
- **M2:** UX v1 — GUI polish and API/docs parity (Phase 2)
- **M3:** 0.7.x — current packaging line (**0.7.5**); Wave 0 eng criteria closed; Top-3 eng programs Done; Waves 1–2 product items shipped (through B13 + Speakers 1.5/1.6/voice/locations + analysis presets); Wave 3 open (B5 DB/group remainder, B14, B18/P2); public tags still via release governance evidence

---

## Sprint plan (archived backlog)

Historical sprint notes (Sprints 1–12) live in [docs/archive/sprint_archive.md](archive/sprint_archive.md) (historical backlog only — not live). Focus: Phase 1 beta machinery is in place; Wave 3 analysis capacity and Phase 2 transcription stance follow. See the [stocktake](dev/stocktake_2026-07-17.md) and [analysis module backlog](dev/analysis_module_backlog_2026-07-17.md) for current packaging and product truth.

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
- GUI and Python workflows for speaker identity exist (file-backed Speakers + voice); richer DB-backed / group `profile_id` analytics remain deferred
- You still enjoy working on the codebase
