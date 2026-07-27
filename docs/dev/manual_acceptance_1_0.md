Type: PRODUCT
Authority: self

# Manual acceptance suite (1.0) — maintainer runbook

**Status:** executable kit for the human-testing wave (implementation for Guided/demo/onboarding shipped **0.9.6**; kits prepared **0.9.8**)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §15  
**Related:** [gui_acceptance_residual_checklist.md](gui_acceptance_residual_checklist.md) (R1–R6 must stay in sync), [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [install_verification_matrix.md](../runtime/install_verification_matrix.md), [unfamiliar_user_validation_1_0.md](unfamiliar_user_validation_1_0.md), [known_limitations.md](../known_limitations.md)

Authoritative **maintainer** acceptance checklist. Automated GUI acceptance (`make test-gui-acceptance`) is complementary, not a substitute. This runbook must be executable without inventing steps mid-session.

---

## 0. Prerequisites (before day-of)

**§0 status (2026-07-26):** done for Docker Compose maintainer pass start. Scratch evidence: `.local/release_evidence/bb6b8fe3fed5171187240ca74a9097277d82bcb4/prerequisites_section0.md` (gitignored; not signed-off RC evidence).

| Check | Criterion | Recorded |
|-------|-----------|----------|
| Candidate identity | Record **package version** + **exact git SHA** under test | **done** — package `0.9.8.2` (`pyproject` / Compose container); git `bb6b8fe3fed5171187240ca74a9097277d82bcb4` (`v0.9.8.2`); Compose bind-mounts live `src/` so UI reflects dirty worktree |
| Clean worktree intent | Prefer a tagged/candidate commit; note dirty files if any | **noted** — worktree **dirty** vs that SHA (docs + demo/presentation removals and related test churn among other local edits). Journeys are against dirty tree + Compose mounts, not a clean tag checkout |
| Backup | Owner backup of personal data roots before using shared machines | **owner** — assumed before shared-machine use; not re-verified in this pass log |
| Disposable data root | Use a fresh / disposable managed data directory (do not contaminate production corpora) | **noted** — Compose `/data` ← host `./data` (contains deep-test probe artifacts). Prefer a fresh disposable root before required journeys if this tree is not disposable |
| Install profile | Choose from [install_verification_matrix.md](../runtime/install_verification_matrix.md): Docker Compose (recommended) and/or native `core`/`full`/`web` as claimed | **done** — Docker Compose (`transcriptx-web` healthy; UI up) |
| Automated GUI acceptance | `make test-gui-acceptance` **passed on the same SHA** (record exit + date) | **done** — 2026-07-26; exit **0**; **7 passed** / 7837 deselected (~12s). Ran on host Python against tree at that SHA tip (dirty worktree present) |
| Streamlit version | Record installed Streamlit version (`python -c "import streamlit; print(streamlit.__version__)"`) | **done** — Compose container **1.60.0** (authoritative for this profile); host test env **1.52.2** (AppTest only) |
| Supported browsers | Record Streamlit’s **officially supported browser set** for that Streamlit version (from Streamlit docs for that release). Test those browsers — do not leave “supported browsers” as a floating phrase | **noted** — Streamlit docs: two most recent of **Chrome, Firefox, Edge, Safari** ([supported browsers](https://docs.streamlit.io/knowledge-base/using-streamlit/supported-browsers)). Maintainer smoke (compose UI): **Safari 26.5**, **Firefox 152.0.4 (aarch64)**, **Waterfox 6.6.17 (aarch64)**. Waterfox is not on Streamlit’s official list (Firefox-family). **Chrome** and **Edge** not yet recorded for §3.11 |

---

## 1. Journey classification

Classify every journey below as **required**, **conditional**, or **optional** for the chosen install profile (matrix).

| Class | Rule |
|-------|------|
| **required** | Must pass for this profile, or RC is blocked |
| **conditional** | Required when the profile claims the capability (e.g. voice, bertopic, native GUI) |
| **optional** | Strongly expected when practical; skip needs reason + severity |

Skipping a **supported required** journey requires: skip rationale, severity ([release_severity_triage_1_0.md](release_severity_triage_1_0.md)), and evidence link.

---

## 2. Clean-state between journeys

Before each major journey (and after demo remove / Full↔Guided flips):

1. Confirm data root is the disposable root for this pass.
2. Clear or note Streamlit session: refresh / rerun; do not rely on stale widgets.
3. Prefer resetting presentation prefs / onboarding prefs only via documented UI actions for the journey under test (do not hand-edit prefs mid-pass unless recovering).
4. After **demo remove**, verify inventory no longer lists demo-owned transcripts/groups before the next journey.
5. Do not reuse prior run folders as “fresh” evidence without noting contamination risk.
6. Model caches may persist on disk — note when a journey depends on cold vs warm cache.

---

## 3. Ordered journeys

Record each row in the evidence table (§6). Class defaults assume Docker Compose GUI + core analysis.

**This pass stubs (2026-07-26):** `.local/release_evidence/bb6b8fe3fed5171187240ca74a9097277d82bcb4/journeys_section3_stubs.md` — one §6 table per journey below; fill outcomes as you go (prepared ≠ measured ≠ signed-off).

### 3.1 Installation and launch — **required**

- [x] Install / launch web UI per chosen profile — **pass** 2026-07-26 (Compose)
- [x] Home loads without traceback; schema-epoch gate allows the disposable root — **pass** (existing `/data` bind; not a fresh disposable root — see stubs)

### 3.2 Import and Library — **required**

- [x] Single-file import into managed library — **pass** 2026-07-26 (individual two-speaker `R20241026-121652`)
- [ ] Folder import (multi-file) when profile supports it
- [x] Library shows new transcript(s) with expected identity — **pass** (action menu → Speaker Identification landed on correct transcript)
- [x] Related: **Delete all runs** (Settings / storage) — **pass** 2026-07-26 (works as expected)
- [x] Related: **Corrections Studio** — **pass (usable)** 2026-07-27; quality/results **mixed**. Not a 1.0 blocker; dedicated strengthen wave → [ROADMAP.md](../ROADMAP.md) §1.1 (word-level propose from Transcript viewer)

### 3.3 Analysis run — **required** (adapted: Guided UI removed post-0.9.6)

- [x] ~~Presentation mode Guided~~ — **N/A** (Guided/Full presentation layer removed; docs + clear GUI)
- [x] Default **Balanced** path (experimental emotion off defaults) — **pass** 2026-07-27. Builtin `analysis.ui_presets.balanced.heavy_module_ids` = `semantic_similarity` only; `resolve_analysis_preset("balanced")` excludes `contextual_emotion` / `fine_grained_emotion` (lexical `emotion` remains). Covered by `test_balanced_llm_and_heavy_allowlists` + golden defaults. Full Balanced wall-clock GUI run not this pass (Thorough used for §3.3 runtime); Medium Balanced recipe still §3.12
- [x] Overview, Insights, Charts, Artifacts each open for the run without crash — **Overview** / **Charts** / **Artifacts** / **Insights** all **pass** (Insights working well, 2026-07-27). Presentation organisation debt → **[0.9.9](overview_presentation_0_9_9.md)**; deeper Insights/analysis enhance → [ROADMAP.md](../ROADMAP.md) §1.1
- [x] Related: Speaker Identification → ignore one speaker; name speakers; create profile; identify all — **pass** before Run Analysis
- [x] Related: Thorough + custom Qs + mixed LLM models + saved profile — **complete (partial)** run `20260726_015208_30728241` · wall **~44.7 min** · 46 RUN / 2 FAIL (`llm_action_items`, `llm_custom_qa` timed out at 600s) · see `run_R20241026-121652_thorough.md`

### 3.4 Failure recovery — **required** (at least two cases)

Deliberate failures — expected recovery / severity:

| Case | Expected | Severity if broken |
|------|----------|--------------------|
| Missing Ollama when Local AI module selected | Clear actionable message; no silent hang; pipeline continues or fails closed with message | must-fix |
| Malformed / missing path | Rejected with clear error; no partial corrupt index | must-fix / blocker |
| Unavailable optional module (e.g. BERTopic without extra) | Stable skip / missing_extra reason; pipeline continues | must-fix |
| Cancelled operation | Cancel acknowledged; no corrupt half-committed demo/run ownership | must-fix |
| Partial module failure | Run outcomes honest; other modules usable | must-fix |

- [x] Exercise ≥2 cases above; record outcomes — **2/2** 2026-07-27: (1) partial module failure on Thorough run (`llm_action_items` + `llm_custom_qa` 600s timeout → FAIL; pipeline continued; `final_status=partial`); (2) malformed/missing path — folder-import scan rejects empty/relative/missing/file-not-dir with clear `AdmissionError` / scan banner text; no admit; no corrupt index. Evidence: `.local/release_evidence/bb6b8fe3fed5171187240ca74a9097277d82bcb4/failure_recovery_3_4.md`

### 3.5 Export — **required**

- [x] Create export / download artifacts (see also residual **R2**) — **pass** 2026-07-26 (export visible → zip; HTML index looks good)

### 3.6 Transcribe command generation — **required**

- [x] Command generator shows copyable commands; **no** Streamlit shell execution — **pass** 2026-07-26 (whispermlx-missing “transcribe all remaining”; host run succeeded)
- [x] Dry-run / docs honesty matches [transcription.md](../runtime/transcription.md) — **pass** (generator handoff; Streamlit did not execute transcription)

### 3.7 Residual AppTest-blind (R1–R6) — **required**

Incorporate by **stable IDs** from [gui_acceptance_residual_checklist.md](gui_acceptance_residual_checklist.md). If that checklist adds R7+, update this section in the same change.

| ID | Item | Pass criteria (summary) |
|----|------|-------------------------|
| R1 | Import file picker | Real file admit; Library shows transcript |
| R2 | Export browser download | Usable zip from browser save |
| R3 | Export open-on-disk / `file://` | Lands in expected viewer if offered |
| R4 | Hover / focus reveal | Labels readable; no clipped tooltips |
| R5 | Popovers / expanders | Critical expanders readable |
| R6 | Visual alignment | Overview/Insights/Charts first paint aligned |

- [~] R1 … R6 recorded — **R1 pass**; **R2 pass**; **R4 pass**; **R6 pass** (Overview/Insights/Charts/Artifacts first paint). R3, R5 still open

### 3.11 Accessibility / browsers — **required**

- [ ] Keyboard reachability of principal controls (Home, Import, Run, Insights, Settings)
- [ ] Visible focus indicators
- [ ] Text / control contrast spot-check
- [ ] Narrow-window usability (mobile-ish width) for Home + Run
- [ ] Chart readability + downloadable alternative for important visual outputs
- [ ] Each browser in the recorded Streamlit-supported set smoked

### 3.12 Performance — **conditional / strongly expected**

- [x] Opportunistic **Thorough** single-transcript timings recorded for `R20241026-121652` (~44.7 min wall, partial; see `run_R20241026-121652_thorough.md`)
- [ ] **Medium** corpus Balanced recipe — still owed
- [ ] **Large-library**: record **pass** / **fail** / **approved soft-cut** — never silently omit (Home previously showed ~168 library transcripts — soak still open)

---

## 4. Environments

| Env | Notes |
|-----|-------|
| Docker Compose (recommended) | Fresh volumes where practical |
| Native (if claiming support) | After install-profile audit; MPS caveats apply |

---

## 5. Working notes vs release evidence

| Location | Allowed |
|----------|---------|
| `.local/` | Private scratch, raw notes, incomplete drafts (gitignored) |
| Release-evidence location | **Accepted** RC evidence only — copy curated tables/logs tied to the tested SHA (e.g. `.local/release_evidence/<SHA>/` then promote per [release_governance.md](release_governance.md) / ops policy). Do not treat templates as measured evidence. |

Prepared evidence ≠ measured evidence ≠ signed-off evidence.

---

## 6. Standard evidence table

Copy one row per journey (or attach a filled sheet under the SHA folder):

| Field | Value |
|-------|-------|
| environment | Docker / native |
| OS | |
| architecture | |
| install profile | core / full / web / compose |
| package version | |
| SHA | |
| date | |
| tester | |
| Streamlit version | |
| browsers tested | |
| journey id | e.g. 3.3 Guided Balanced |
| class | required / conditional / optional |
| outcome | pass / fail / skip |
| skip rationale | required if skip |
| severity | blocker / must-fix / known limitation / post-1.0 / — |
| evidence link | path under release-evidence or ticket |

Severity authority: [release_severity_triage_1_0.md](release_severity_triage_1_0.md).
