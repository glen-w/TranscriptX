# TranscriptX Roadmap

**Current version:** 0.42

**North star:** ship a credible **beta → v0.42** core transcription + analysis toolkit with stable contracts, great UX, and a safe path to extensibility.

> **Status legend (GitHub-style):**  
> - [ ] planned / not started  
> - [x] done  
> - [~] in progress

---

## Principles (locked)

- Core-first: transcription + analysis correctness > breadth
- Stability over novelty: contracts + tests before new features
- Observable outputs: every module produces machine-readable artifacts
- Deferred platformisation: adapters/plugins are designed, not prematurely built
- Low-regret UX: CLI is the canonical execution surface; Web Viewer is first-class for read-only exploration (see [CLI/GUI Strategy](CLI_GUI_STRATEGY.md))

---

## Product direction (CLI-first)

The CLI remains the canonical execution surface; the Web Viewer is a read-only gallery. See [CLI/GUI Strategy](CLI_GUI_STRATEGY.md) for boundaries and guardrails. The following horizons guide prioritization without adding new product commitments.

**Near-term (v0.1 – v0.42)**

- Harden CLI experience
- Improve run summaries and explainability
- Improve speaker identification workflow
- Improve installation reliability
- Stabilize output contracts

**Later (v0.3+)**

- Enhanced Web Viewer capabilities: run comparison, artifact filtering, group-level browsing
- Potential GUI for complex editing workflows (e.g. advanced speaker curation)
- No commitment to full GUI replacement of CLI

---

## Phases (priority order)

### Phase 1 — Beta-ready (now)

**Goal:** Install, core flows, and docs work for a beta user with no bugs.

- Install path: one canonical sequence (venv → requirements.txt → pip install -e .); script and README aligned
- Core flows: interactive CLI, web-viewer, analyze (single + non-interactive), groups — all run and produce outputs
- Docs: README Quickstart, manual install, verify-install step, env vars, troubleshooting
- Dependencies: version consistency (requirements.txt, lock, launcher, CI)
- CI: smoke, contracts, fast gates pass; build_sanity validates “install then run”

**No new features;** stability and “it works” for a first-time clone/install.

---

### Phase 2 — UX + stability (next)

**Goal:** CLI and Web Viewer feel intentional; outputs and contracts are solid.

- UX v1: CLI ergonomics (fast file selection, progress, clear errors)
- Web Viewer parity and guardrails (probe-gated startup, canonical paths, read-only viewer)
- Stats consolidation (unified stats MD/JSON, module status table)
- Contract tests and output schema stability
- Internal cleanup: error types, pipeline failure semantics, config/secrets via env only

---

### Phase 3 — Optional / advanced (later)

**Goal:** Richer analysis and tooling without blocking beta or stability.

- **Longitudinal speaker tracking v1 and v2** — including **web visualization** (speaker-over-time charts, cross-session views). Current `transcriptx cross-session` and `transcriptx database` commands remain **CLI-only**; no Web Viewer for speaker-over-time or DB-backed analytics yet.
- Emotion/sentiment convergence (multi-label, tension metrics, divergence summaries)
- NER-driven insight (entity–sentiment, concordance, timelines)
- Interaction and network analysis (graphs, network outputs)
- Adapters and plugins (design only; no marketplace)
- Architecture cleanup and module contract docs

---

## Deferred to post-beta

The following are explicitly **not** part of the beta-ready scope; they are planned for a later release:

- **Longitudinal speaker identity with web visualization** — speaker-over-time charts, cross-session views, and richer DB-backed analytics in the Web Viewer. The CLI commands (`transcriptx cross-session`, `transcriptx database`) exist and are CLI-only; visualization and full DB UX are deferred.
- Database and cross-session speaker commands are available today (CLI only). Speaker-over-time **visualization** and full database-backed analytics are planned for a later release.

### ConvoKit analysis (archived)

**ConvoKit** coordination/accommodation analysis is **archived** (not removed) due to **dependency conflicts** with the current stack. Re-enablement is planned for later once version constraints are resolved.

**Dependency issues:** convokit 3.5.0 requires `numpy>=2.0.0`, `spacy>=3.8.2`, and `thinc>=8.3.0,<8.4.0`. These conflict with current project pins (e.g. numpy 1.26.4, spacy 3.7.5, thinc 8.2.5) used by NER and other modules. Pip’s resolver reports these conflicts when convokit is installed.

**Archived implementation:** `archived/convokit/` (and tests in `tests/archived/test_convokit.py`). To re-enable: resolve convokit/numpy/spacy/thinc versions, restore the module under `src/transcriptx/core/analysis/convokit/`, and re-wire the pipeline module registry, analysis config, aggregation registry, and lazy imports. See `archived/convokit/README.md` for details.

---

## Milestones (reference)

- **M1:** Beta-ready — install, core flows, docs, CI (Phase 1)
- **M2:** UX v1 — CLI and Web Viewer parity (Phase 2)
- **M3:** v0.42 — current release; calmer architecture (Phase 2 + selected Phase 3 items)

---

## Sprint plan (legacy / backlog)

The following sprint plan is kept for reference. **Sprints 4 and 10 (Longitudinal Speaker Tracking)** are moved to Phase 3 / backlog; focus is Phase 1 then Phase 2.

### Sprint 1 (Weeks 1–2) — **v0.1 Freeze + Release** (done)
**Goal:** lock correctness, contracts, and ship `v0.1.0` without churn.

**Outputs & contracts**
- [ ] Finalise canonical output tree (`transcripts/`, `stats/`, `sentiment/`, `emotion/`, `ner/`, `networks/`, `word_clouds/`)
- [ ] Enforce stable IDs (`segment_id`, `speaker_id`, `occurrence_id`) across modules and exports
- [ ] Add `--print-output-json-path` (single-line, machine-readable) + document it

**Correctness fixes**
- [ ] Enforce `context_any` in corrections apply logic
- [ ] Apply “unidentified speaker exclusion” rules consistently (exclude from all modules except transcript/CSV + NER)

**Stats consolidation**
- [ ] Replace fragmented stats with:
  - [ ] `<base>_stats.md`
  - [ ] `<base>_stats.json`
- [ ] Add module presence/status table
- [ ] Add opening vs closing sentiment delta
- [ ] Remove noisy “No data available” blocks

**Security + docs + release**
- [ ] Remove hard-coded tokens; env/config secrets only
- [ ] README consolidation (single canonical public doc)
- [ ] Archive `docs/` (no Sphinx coupling for v0.1)
- [ ] Minimal contract tests for transcript + stats JSON schemas
- [x] Tag `v0.1.0` and write `RELEASE_NOTES.md`

**Milestone:** `v0.1.0`

---

### Sprint 2 (Weeks 3–4) — **UX v1 (CLI-first)**
**Goal:** make TranscriptX feel intentional to use (fast menus, clear progress, predictable errors).

**CLI ergonomics**
- [ ] Reorder flows: high-level choice first (transcribe vs process existing transcript)
- [ ] Fast file selection (ffprobe-first duration + lazy metadata)
- [ ] Deterministic console output modes (quiet/path-only where needed)
- [ ] Colored speaker mapping prompt (per speaker ID) using `colorama`
- [ ] Spinner/progress indicators during heavy steps

**Robustness**
- [ ] Centralise error types (`TranscriptionError`, `AnalysisError`, etc.)
- [ ] Graceful partial-pipeline failure semantics (best-effort outputs + clear status)

**Milestone:** UX v1

---

### Sprint 3 (Weeks 5–6) — **Web Viewer Parity + Guardrails**
**Goal:** Web Viewer mirrors CLI capabilities safely (no surprise subprocesses).

- [ ] Engine forcing (`auto | whisperx`) wired end-to-end (not cosmetic)
- [ ] Probe-gated startup (if WhisperX unavailable, show start command; don’t spawn)
- [ ] Display canonical output paths in UI
- [ ] Read-only viewer mode for existing transcripts (no side effects)

---

### Sprint 4 (Weeks 7–8) — **Longitudinal Speaker Tracking v1 (Backlog / Phase 3)**
**Goal:** track speakers *across transcripts*, conservatively and reversibly. **Deferred:** CLI layer exists; **web visualization** (speaker-over-time, cross-session views) is planned for later.

**Data model + storage**
- [ ] Define persistent `SpeakerIdentity` model (stable ID across runs)
- [ ] Add speaker identity registry storage (JSON and/or SQLite)
- [ ] Maintain backwards-compatible per-run `speaker_id` mapping

**Resolution**
- [ ] Define identity resolution inputs (name hints, optional voice features, placeholder for embeddings)
- [ ] Implement conservative cross-run resolution (opt-in) with clear “unknown” outcomes
- [ ] Export speaker registry + per-run mapping artifacts

**Milestone:** Longitudinal identity layer v1 (when prioritized)

---

### Sprint 5 (Weeks 9–10) — **Emotion & Sentiment Convergence**
**Goal:** move from raw metrics to interpretable affect signals.

- [ ] Multi-label emotion support (e.g., GoEmotions option)
- [ ] Store full emotion distributions per segment (not only top label)
- [ ] Add affect–sentiment “tension” metrics
- [ ] Cross-speaker emotional divergence summaries in stats

---

### Sprint 6 (Weeks 11–12) — **NER-Driven Insight**
**Goal:** entities become first-class analytical objects.

- [ ] Entity–sentiment matrix (framing analysis)
- [ ] Concordance export per entity (segments mentioning entity)
- [ ] Top-entity timelines (global + per speaker)
- [ ] Tighten NER data contracts + naming conventions

---

### Sprint 7 (Weeks 13–14) — **Interaction & Network Analysis**
**Goal:** structural understanding of conversation dynamics.

- [ ] Finalise `networks/` outputs:
  - [ ] interruption graph (directed, weighted edge list CSV)
  - [ ] response adjacency graph (who speaks after whom)
- [ ] Static PNG network visualisations (optional but useful)
- [ ] Add network summary block to stats artifacts

---

### Sprint 8 (Weeks 15–16) — **Internal Architecture Cleanup**
**Goal:** make future work cheaper, safer, and more boring.

- [ ] Finalise `src/` layout consistency + imports
- [ ] Reduce side-effects in CLI entrypoints
- [ ] Clarify `PipelineContext` API boundaries and lifecycle
- [ ] Document module contracts + module registry patterns

---

### Sprint 9 (Weeks 17–18) — **Adapters & Plugins: Design (Not Build)**
**Goal:** design clearly; do not platformise prematurely.

- [ ] Write Adapter RFC:
  - [ ] supported ingestion candidates (Slack, Telegram export, notebooks)
  - [ ] adapter responsibilities + normalization contracts
  - [ ] output artifact contract (what becomes “a transcript”)
- [ ] Define plugin registration mechanism (design only)
- [ ] Draw hard line: what stays core vs optional

**Deliverable:** `docs/architecture/adapters.md` (in-repo)

---

### Sprint 10 (Weeks 19–20) — **Longitudinal Speaker Tracking v2 (Backlog / Phase 3)**
**Goal:** make identity usable *and* safe; **web visualization** (speaker-over-time, uncertain matches) deferred to later.

- [ ] Manual merge/split tooling (CLI + optional UI hooks)
- [ ] Confidence scoring + provenance (why a match was made)
- [ ] Stats aggregation per speaker over time
- [ ] Visual indicators for uncertain matches (CLI first; Web Viewer later)

---

### Sprint 11 (Weeks 21–22) — **v0.42 Hardening**
**Goal:** prepare a calm release (current version 0.42).

- [ ] Expanded contract tests (outputs + module invariants)
- [ ] Performance regression checks (file selection, pipeline runtime)
- [ ] Migration notes: `v0.1 → v0.42`
- [ ] Release candidate checklist when preparing next tag

---

### Sprint 12 (Weeks 23–24) — **v0.42 Release**
**Goal:** ship current version as tagged release.

- [ ] Final README updates (features + stability notes)
- [ ] Tag `v0.42`
- [ ] Publish release notes + known issues

**Milestone:** `v0.42` (current)

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
- CLI and DB layer for speaker identity exist and do not corrupt data; **visualization** (speaker-over-time, cross-session views in Web Viewer) is deferred to a later release
- You still enjoy working on the codebase
