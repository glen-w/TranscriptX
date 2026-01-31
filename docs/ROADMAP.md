# TranscriptX Roadmap (Next 6 Months)

**Cadence:** 2‑week sprints (12 sprints)  
**North star:** ship a credible **v0.1 → v0.2** core transcription + analysis toolkit with stable contracts, great UX, and a safe path to extensibility.

> **Status legend (GitHub-style):**  
> - [ ] planned / not started  
> - [x] done  
> - [~] in progress (use `[ ]` plus “(in progress)” if you prefer strict GitHub rendering)

---

## Principles (locked)

- Core-first: transcription + analysis correctness > breadth
- Stability over novelty: contracts + tests before new features
- Observable outputs: every module produces machine-readable artifacts
- Deferred platformisation: adapters/plugins are designed, not prematurely built
- Low-regret UX: CLI + WebUI remain first-class

---

## Milestones

- **M1:** `v0.1.0` — frozen, stable, public release (Sprint 1)
- **M2:** `UX v1` — CLI experience is fast, predictable, and pleasant (Sprint 2)
- **M3:** Longitudinal speaker identity `v1` — speakers persist across runs (Sprint 4)
- **M4:** `v0.2.0` — calmer second release with stronger architecture (Sprint 12)

---

## Sprint plan

### Sprint 1 (Weeks 1–2) — **v0.1 Freeze + Release**
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
- [ ] Tag `v0.1.0` and write `RELEASE_NOTES.md`

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

### Sprint 3 (Weeks 5–6) — **WebUI Parity + Guardrails**
**Goal:** WebUI mirrors CLI capabilities safely (no surprise subprocesses).

- [ ] Engine forcing (`auto | whisperx`) wired end-to-end (not cosmetic)
- [ ] Probe-gated startup (if WhisperX unavailable, show start command; don’t spawn)
- [ ] Display canonical output paths in UI
- [ ] Read-only viewer mode for existing transcripts (no side effects)

---

### Sprint 4 (Weeks 7–8) — **Longitudinal Speaker Tracking v1 (Foundational)**
**Goal:** track speakers *across transcripts*, conservatively and reversibly.

**Data model + storage**
- [ ] Define persistent `SpeakerIdentity` model (stable ID across runs)
- [ ] Add speaker identity registry storage (JSON and/or SQLite)
- [ ] Maintain backwards-compatible per-run `speaker_id` mapping

**Resolution**
- [ ] Define identity resolution inputs (name hints, optional voice features, placeholder for embeddings)
- [ ] Implement conservative cross-run resolution (opt-in) with clear “unknown” outcomes
- [ ] Export speaker registry + per-run mapping artifacts

**Milestone:** Longitudinal identity layer v1

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

### Sprint 10 (Weeks 19–20) — **Longitudinal Speaker Tracking v2 (Strengthening)**
**Goal:** make identity usable *and* safe (no silent data corruption).

- [ ] Manual merge/split tooling (CLI + optional UI hooks)
- [ ] Confidence scoring + provenance (why a match was made)
- [ ] Stats aggregation per speaker over time
- [ ] Visual indicators for uncertain matches

---

### Sprint 11 (Weeks 21–22) — **v0.2 Hardening**
**Goal:** prepare a calm second release.

- [ ] Expanded contract tests (outputs + module invariants)
- [ ] Performance regression checks (file selection, pipeline runtime)
- [ ] Migration notes: `v0.1 → v0.2`
- [ ] `v0.2.0-rc` tagging / release candidate checklist

---

### Sprint 12 (Weeks 23–24) — **v0.2 Release**
**Goal:** ship `v0.2.0`.

- [ ] Final README updates (features + stability notes)
- [ ] Tag `v0.2.0`
- [ ] Publish release notes + known issues

**Milestone:** `v0.2.0`

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
- Longitudinal speaker analysis works **without** corrupting data
- You still enjoy working on the codebase

