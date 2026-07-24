Type: PRODUCT
Authority: self

# Manual acceptance suite (1.0) — maintainer runbook

**Status:** executable kit for the human-testing wave (implementation for Guided/demo/onboarding shipped **0.9.6**; kits prepared **0.9.8**)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §15  
**Related:** [gui_acceptance_residual_checklist.md](gui_acceptance_residual_checklist.md) (R1–R6 must stay in sync), [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [install_verification_matrix.md](../runtime/install_verification_matrix.md), [unfamiliar_user_validation_1_0.md](unfamiliar_user_validation_1_0.md), [known_limitations.md](../known_limitations.md)

Authoritative **maintainer** acceptance checklist. Automated GUI acceptance (`make test-gui-acceptance`) is complementary, not a substitute. This runbook must be executable without inventing steps mid-session.

---

## 0. Prerequisites (before day-of)

| Check | Criterion |
|-------|-----------|
| Candidate identity | Record **package version** + **exact git SHA** under test |
| Clean worktree intent | Prefer a tagged/candidate commit; note dirty files if any |
| Backup | Owner backup of personal data roots before using shared machines |
| Disposable data root | Use a fresh / disposable managed data directory (do not contaminate production corpora) |
| Install profile | Choose from [install_verification_matrix.md](../runtime/install_verification_matrix.md): Docker Compose (recommended) and/or native `core`/`full`/`web` as claimed |
| Automated GUI acceptance | `make test-gui-acceptance` **passed on the same SHA** (record exit + date) |
| Streamlit version | Record installed Streamlit version (`python -c "import streamlit; print(streamlit.__version__)"`) |
| Supported browsers | Record Streamlit’s **officially supported browser set** for that Streamlit version (from Streamlit docs for that release). Test those browsers — do not leave “supported browsers” as a floating phrase |

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

### 3.1 Installation and launch — **required**

- [ ] Install / launch web UI per chosen profile
- [ ] Home loads without traceback; schema-epoch gate allows the disposable root

### 3.2 Import and Library — **required**

- [ ] Single-file import into managed library
- [ ] Folder import (multi-file) when profile supports it
- [ ] Library shows new transcript(s) with expected identity

### 3.3 Guided Balanced analysis — **required**

- [ ] Presentation mode **Guided**
- [ ] Run analysis with **Balanced** (default policy)
- [ ] Confirm experimental emotion modules are **not** required for the default path (`fine_grained_emotion` / `contextual_emotion` absent from Balanced defaults)
- [ ] Overview, Insights, Charts, Artifacts each open for the run without crash

### 3.4 Failure recovery — **required** (at least two cases)

Deliberate failures — expected recovery / severity:

| Case | Expected | Severity if broken |
|------|----------|--------------------|
| Missing Ollama when Local AI module selected | Clear actionable message; no silent hang; pipeline continues or fails closed with message | must-fix |
| Malformed / missing path | Rejected with clear error; no partial corrupt index | must-fix / blocker |
| Unavailable optional module (e.g. BERTopic without extra) | Stable skip / missing_extra reason; pipeline continues | must-fix |
| Cancelled operation | Cancel acknowledged; no corrupt half-committed demo/run ownership | must-fix |
| Partial module failure | Run outcomes honest; other modules usable | must-fix |

- [ ] Exercise ≥2 cases above; record outcomes

### 3.5 Export — **required**

- [ ] Create export / download artifacts (see also residual **R2**)

### 3.6 Guided / Full controls — **required**

- [ ] Switch Guided ↔ Full on Home/Settings
- [ ] Full-only page shows unlock banner in Guided; switching to Full loads page content
- [ ] Custom selection preserved across Full → Guided → Full (no silent wipe)

### 3.7 Demo lifecycle — **required** (when demo pack shipped)

- [ ] Load demo project (transactional success)
- [ ] Remove demo project; ownership cleanup copy accurate; no leftover demo-owned inventory

### 3.8 Onboarding lifecycle — **required**

- [ ] Checklist visible for new disposable root
- [ ] Dismiss / skip / complete / reopen from Help/Settings behave independently

### 3.9 Transcribe command generation — **required**

- [ ] Command generator shows copyable commands; **no** Streamlit shell execution
- [ ] Dry-run / docs honesty matches [transcription.md](../runtime/transcription.md)

### 3.10 Residual AppTest-blind (R1–R6) — **required**

Incorporate by **stable IDs** from [gui_acceptance_residual_checklist.md](gui_acceptance_residual_checklist.md). If that checklist adds R7+, update this section in the same change.

| ID | Item | Pass criteria (summary) |
|----|------|-------------------------|
| R1 | Import file picker | Real file admit; Library shows transcript |
| R2 | Export browser download | Usable zip from browser save |
| R3 | Export open-on-disk / `file://` | Lands in expected viewer if offered |
| R4 | Hover / focus reveal | Labels readable; no clipped tooltips |
| R5 | Popovers / expanders | Critical expanders readable |
| R6 | Visual alignment | Overview/Insights/Charts first paint aligned |

- [ ] R1 … R6 recorded

### 3.11 Accessibility / browsers — **required**

- [ ] Keyboard reachability of principal controls (Home, Import, Run, Insights, Settings)
- [ ] Visible focus indicators
- [ ] Text / control contrast spot-check
- [ ] Narrow-window usability (mobile-ish width) for Home + Run
- [ ] Chart readability + downloadable alternative for important visual outputs
- [ ] Each browser in the recorded Streamlit-supported set smoked

### 3.12 Performance — **conditional / strongly expected**

- [ ] **Medium** corpus: run [performance envelope recipe](performance_envelopes_1_0.md) when hardware allows (**strongly expected**)
- [ ] **Large-library**: record **pass** / **fail** / **approved soft-cut** — never silently omit

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
