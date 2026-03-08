# TranscriptX Roadmap

**Current version:** 0.42

**North star:** ship a credible **beta → v0.42** analysis toolkit with stable contracts, great UX, and a safe path to extensibility.

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
- Low-regret UX: GUI is the primary interface; CLI provides equivalent capabilities for scripting and automation

---

## Product direction

TranscriptX is evolving toward a **personal audio analysis companion**. The GUI (Streamlit) is the primary interface for interactive use; the CLI provides equivalent capabilities for scripting, automation, and CI.

**Long-term goals:**

- Analyzing transcripts from personal recordings
- Supporting voice note workflows
- Conversational analytics
- Integration with local AI models (Ollama, etc.)

**Near-term (v0.1 – v0.41)**

- Harden GUI and CLI experience
- Improve run summaries and explainability
- Improve speaker identification workflow
- Improve installation reliability
- Stabilize output contracts

**Later (v0.3+)**

- Enhanced GUI capabilities: run comparison, artifact filtering, richer visualizations
- Deeper cross-session and longitudinal views in the GUI
- Personal audio analysis workflows

---

## Local AI roadmap

Future integration with:

- **Local Ollama models** — summarization, conversational insights, semantic analysis
- **Optional remote compute** (e.g. Colab) — for users who prefer cloud-based inference

These would enable summarization, conversational insights, and semantic analysis while keeping TranscriptX local-first and modular.

---

## Phases (priority order)

### Phase 1 — Beta-ready (now)

**Goal:** Install, core flows, and docs work for a beta user with no bugs.

- Install path: one canonical sequence (venv → requirements.txt → pip install -e .); script and README aligned
- Core flows: GUI, interactive CLI, analyze (single + non-interactive), groups — all run and produce outputs
- Docs: README Quickstart, manual install, verify-install step, env vars, troubleshooting
- Dependencies: version consistency (requirements.txt, lock, launcher, CI)
- CI: smoke, contracts, fast gates pass; build_sanity validates "install then run"

**No new features;** stability and "it works" for a first-time clone/install.

---

### Phase 2 — Optional transcription integration (non-goal for v0.1)

TranscriptX is analysis-only; transcription is external. Users bring their own transcript JSON from tools such as WhisperX, AssemblyAI, Deepgram, Otter, or manual export (see [transcription.md](transcription.md)). A future phase could introduce an optional **TranscriptionProvider** protocol for external integrations (e.g. WhisperX via HTTP, AssemblyAI, Colab) — configuration-only, no built-in transcription engine. No provider code ships in v0.1.

---

### Phase 2 — UX + stability (next)

**Goal:** GUI and CLI feel intentional; outputs and contracts are solid.

- UX v1: CLI ergonomics (fast file selection, progress, clear errors)
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

- **Longitudinal speaker identity with visualization** — speaker-over-time charts, cross-session views, and richer DB-backed analytics.
- Speaker-over-time **visualization** and full database-backed analytics are planned for a later release.

### ConvoKit analysis (archived)

**ConvoKit** coordination/accommodation analysis was archived due to **dependency conflicts** with the current stack. Re-enablement is planned for later once version constraints are resolved.

**Dependency issues:** convokit 3.5.0 requires `numpy>=2.0.0`, `spacy>=3.8.2`, and `thinc>=8.3.0,<8.4.0`. These conflict with current project pins (e.g. numpy 1.26.4, spacy 3.7.5, thinc 8.2.5) used by NER and other modules.

To re-enable: resolve convokit/numpy/spacy/thinc versions, then re-implement the module under `src/transcriptx/core/analysis/convokit/` and re-wire the pipeline module registry, analysis config, and aggregation registry.

---

## Milestones (reference)

- **M1:** Beta-ready — install, core flows, docs, CI (Phase 1)
- **M2:** UX v1 — GUI and CLI parity (Phase 2)
- **M3:** v0.42 — current release; calmer architecture (Phase 2 + selected Phase 3 items)

---

## Sprint plan (legacy / backlog)

The detailed sprint plan (Sprints 1–12) is archived at [sprint_archive.md](sprint_archive.md). Focus is Phase 1 then Phase 2.

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
- GUI and CLI for speaker identity exist and do not corrupt data; richer speaker-over-time visualization is deferred to a later release
- You still enjoy working on the codebase
