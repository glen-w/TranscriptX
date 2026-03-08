# Sprint Plan (Legacy / Backlog)

The following sprint plan is kept for reference. Focus is on Phase 1 then Phase 2 as described in [ROADMAP.md](ROADMAP.md). **Sprints 4 and 10 (Longitudinal Speaker Tracking)** are moved to Phase 3 / backlog.

> **Status legend (GitHub-style):**  
> - [ ] planned / not started  
> - [x] done  
> - [~] in progress

---

### Sprint 1 (Weeks 1–2) — **v0.1 Freeze + Release** (done)
**Goal:** lock correctness, contracts, and ship `v0.1.0` without churn.

**Outputs & contracts**
- [ ] Finalise canonical output tree (`transcripts/`, `stats/`, `sentiment/`, `emotion/`, `ner/`, `networks/`, `word_clouds/`)
- [ ] Enforce stable IDs (`segment_id`, `speaker_id`, `occurrence_id`) across modules and exports
- [ ] Add `--print-output-json-path` (single-line, machine-readable) + document it

**Correctness fixes**
- [ ] Enforce `context_any` in corrections apply logic
- [ ] Apply "unidentified speaker exclusion" rules consistently (exclude from all modules except transcript/CSV + NER)

**Stats consolidation**
- [ ] Replace fragmented stats with:
  - [ ] `<base>_stats.md`
  - [ ] `<base>_stats.json`
- [ ] Add module presence/status table
- [ ] Add opening vs closing sentiment delta
- [ ] Remove noisy "No data available" blocks

**Security + docs + release**
- [ ] Remove hard-coded tokens; env/config secrets only
- [ ] README consolidation (single canonical public doc)
- [ ] Archive `docs/` (no Sphinx coupling for v0.1)
- [ ] Minimal contract tests for transcript + stats JSON schemas
- [x] Tag `v0.1.0` and write `RELEASE_NOTES.md`

**Milestone:** `v0.1.0`

---

### Sprint 2 (Weeks 3–4) — **UX v1**
**Goal:** make TranscriptX feel intentional to use (fast menus, clear progress, predictable errors).

**CLI ergonomics**
- [ ] Reorder flows: high-level choice first (analyze single vs batch/group operations)
- [ ] Fast file selection (ffprobe-first duration + lazy metadata)
- [ ] Deterministic console output modes (quiet/path-only where needed)
- [ ] Colored speaker mapping prompt (per speaker ID) using `colorama`
- [ ] Spinner/progress indicators during heavy steps

**Robustness**
- [ ] Centralise error types (`TranscriptionError`, `AnalysisError`, etc.)
- [ ] Graceful partial-pipeline failure semantics (best-effort outputs + clear status)

**Milestone:** UX v1

---

### Sprint 3 (Weeks 5–6) — **GUI Polish + Guardrails**
**Goal:** GUI workflows are robust and predictable.

- [ ] Display canonical output paths in UI
- [ ] Probe-gated startup for optional dependencies (show start command when deps unavailable; don't spawn)
- [ ] GUI polish and guardrails (canonical paths, clear error messages)

---

### Sprint 4 (Weeks 7–8) — **Longitudinal Speaker Tracking v1 (Backlog / Phase 3)**
**Goal:** track speakers *across transcripts*, conservatively and reversibly. **Deferred:** speaker-over-time and cross-session visualization is planned for later.

**Data model + storage**
- [ ] Define persistent `SpeakerIdentity` model (stable ID across runs)
- [ ] Add speaker identity registry storage (JSON and/or SQLite)
- [ ] Maintain backwards-compatible per-run `speaker_id` mapping

**Resolution**
- [ ] Define identity resolution inputs (name hints, optional voice features, placeholder for embeddings)
- [ ] Implement conservative cross-run resolution (opt-in) with clear "unknown" outcomes
- [ ] Export speaker registry + per-run mapping artifacts

**Milestone:** Longitudinal identity layer v1 (when prioritized)

---

### Sprint 5 (Weeks 9–10) — **Emotion & Sentiment Convergence**
**Goal:** move from raw metrics to interpretable affect signals.

- [ ] Multi-label emotion support (e.g., GoEmotions option)
- [ ] Store full emotion distributions per segment (not only top label)
- [ ] Add affect–sentiment "tension" metrics
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
  - [ ] output artifact contract (what becomes "a transcript")
- [ ] Define plugin registration mechanism (design only)
- [ ] Draw hard line: what stays core vs optional

**Deliverable:** `docs/architecture/adapters.md` (in-repo)

---

### Sprint 10 (Weeks 19–20) — **Longitudinal Speaker Tracking v2 (Backlog / Phase 3)**
**Goal:** make identity usable *and* safe; speaker-over-time visualization deferred to later.

- [ ] Manual merge/split tooling (CLI + optional UI hooks)
- [ ] Confidence scoring + provenance (why a match was made)
- [ ] Stats aggregation per speaker over time
- [ ] Visual indicators for uncertain matches

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
