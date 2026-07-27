# Manual acceptance §3 — journey evidence stubs

**Status:** prepared stubs — maintainer drives UI; agent checks off when evidence is clear  
**Not signed-off RC evidence** until curated and promoted.

**Recording mode:** Tell me what you finished (journey id / pass|fail / brief note), or say “check off X”. I will not mark required items without your confirmation or observable evidence.

## Common fields (this pass)

| Field | Value |
|-------|-------|
| environment | Docker Compose |
| OS | macOS 26.5 |
| architecture | arm64 (aarch64) |
| install profile | compose (`transcriptx-web`) |
| package version | 0.9.8.2 |
| SHA | bb6b8fe3fed5171187240ca74a9097277d82bcb4 (`v0.9.8.2`; dirty worktree + live `src/` bind-mount) |
| date | 2026-07-26 |
| tester | maintainer |
| Streamlit version | 1.60.0 (Compose) |
| browsers tested | Safari 26.5; Firefox 152.0.4 (aarch64); Waterfox 6.6.17 (aarch64) — Chrome/Edge still open for §3.11 |

---

## 3.1 Installation and launch — **required**

| Field | Value |
|-------|-------|
| journey id | 3.1 Installation and launch |
| class | required |
| outcome | **pass** |
| skip rationale | — |
| severity | — |
| evidence link | this file §3.1 |
| checklist | [x] launch UI [x] Home no traceback [x] schema-epoch gate allows root |
| notes | Compose `http://127.0.0.1:8501` healthy. Home rendered metrics (e.g. Transcripts 168, Analysed 4) with script state `notRunning`; no Traceback/Exception in page text; no epoch refusal blocking the root. Caveat: data root is existing Compose `/data` bind (not a fresh disposable root; many `schema_error` candidates excluded per container logs). |

---

## 3.2 Import and Library — **required**

| Field | Value |
|-------|-------|
| journey id | 3.2 Import and Library |
| class | required |
| outcome | **partial pass** |
| skip rationale | Folder import not yet exercised |
| severity | — |
| evidence link | this file §3.2; run_R20241026-121652_thorough.md |
| checklist | [x] single-file import [ ] folder import [x] Library identity [x] Delete all runs [x] Corrections Studio usable |
| notes | Individual two-speaker `R20241026-121652` imported; action menu → Speaker Identification targeted the correct transcript. **Delete all runs** (Settings storage) tested — works great (2026-07-26). **Corrections Studio** works but results mixed — early **1.x** wave: word-level free-read + propose in Transcript viewer (ROADMAP §1.1). |

---

## 3.3 Analysis run — **required** (adapted)

| Field | Value |
|-------|-------|
| journey id | 3.3 Analysis run (Thorough runtime; Balanced defaults verified separately) |
| class | required |
| outcome | **complete — partial** |
| skip rationale | Guided N/A (removed). Full Balanced wall-clock GUI run skipped this pass (Thorough used); experimental-emotion absence on Balanced verified via defaults + resolve + unit tests (2026-07-27). |
| severity | — (defaults honesty pass; Medium Balanced recipe remains §3.12) |
| evidence link | run_R20241026-121652_thorough.md; unit `test_balanced_llm_and_heavy_allowlists` |
| checklist | [x] Guided N/A [x] Balanced experimental emotion off defaults [x] Overview + Charts + Artifacts + Insights pass [x] Speaker ID before run [x] Thorough+custom Qs+mixed models finished (partial) |
| notes | Wall ~44.7 min. 46 RUN / 2 FAIL: `llm_action_items` + `llm_custom_qa` hit 600s module timeout; pipeline continued. Models touched: mistral-small, mistral-nemo, phi4, command-r7b (+ granite/gemma in other modules). Overview: summaries good; Actions/Highlights/Analysis functional — organisation/presentation → **0.9.9** list. Charts: filters / open-close / fullscreen / search — robust. Artifacts + Insights: working well (2026-07-27). Deeper Insights/analysis enhance → ROADMAP §1.1. |

---

## 3.4 Failure recovery — **required** (≥2 cases)

| Field | Value |
|-------|-------|
| journey id | 3.4 Failure recovery |
| class | required |
| outcome | **pass** (≥2 cases) |
| skip rationale | — |
| severity | — |
| evidence link | `failure_recovery_3_4.md` |
| cases exercised | [ ] missing Ollama [x] malformed/missing path [ ] unavailable optional module [ ] cancelled operation [x] partial module failure |
| notes | **2/2** 2026-07-27. (1) Thorough partial: `llm_action_items` + `llm_custom_qa` 600s timeout → FAIL; pipeline continued; `final_status=partial`. (2) Folder-import path rejects (empty / relative / missing abs / file-not-dir) via Compose `scan_folder_for_import` — clear errors, zero candidates, no admit. |

---

## 3.5 Export — **required**

| Field | Value |
|-------|-------|
| journey id | 3.5 Export |
| class | required |
| outcome | **pass** |
| skip rationale | — |
| severity | — |
| evidence link | this file §3.5 |
| checklist | [x] create export / download artifacts (ties to R2) |
| notes | Export visible → zip; HTML index inspected and looks good (2026-07-26). |

---

## 3.6 Transcribe command generation — **required**

| Field | Value |
|-------|-------|
| journey id | 3.6 Transcribe command generation |
| class | required |
| outcome | **pass** |
| skip rationale | — |
| severity | — |
| evidence link | this file §3.6 |
| checklist | [x] copyable commands [x] no Streamlit shell execution [x] dry-run / docs honesty vs transcription.md |
| notes | In-app Transcribe Audio generator produced a working **whispermlx-missing** “transcribe all remaining” command; maintainer ran it on the Mac host successfully. Streamlit did not shell-exec transcription. **Post-1.0 follow-up** (not a 1.0 fail): broaden command templates for other Whisper backends/platforms and other **local** transcription options — see ROADMAP §1.1. MLX/`whispermlx` remains Apple Silicon macOS-oriented. |

---

## 3.7 Residual AppTest-blind (R1–R6) — **required**

| Field | Value |
|-------|-------|
| journey id | 3.7 Residual AppTest-blind R1–R6 |
| class | required |
| outcome | _pending_ |
| skip rationale | — |
| severity | — |
| evidence link | this file §3.7 + gui_acceptance_residual_checklist.md |
| R1 Import file picker | **pass** (`R20241026-121652`) |
| R2 Export browser download | **pass** (export visible → usable zip; HTML index looks good) |
| R3 Export open-on-disk / file:// | _pending_ (HTML index viewed from zip; confirm dedicated open-on-disk/`file://` path if offered) |
| R4 Hover / focus reveal | **pass** — labels / hovers work well (2026-07-27) |
| R5 Popovers / expanders | _pending_ |
| R6 Visual alignment | **pass** — Overview / Insights / Charts / Artifacts first paint OK (2026-07-27) |
| notes | R1 covered by single-file import journey. R2 covered with §3.5. R4 maintainer smoke. |

---

## 3.11 Accessibility / browsers — **required**

| Field | Value |
|-------|-------|
| journey id | 3.11 Accessibility / browsers |
| class | required |
| outcome | _pending_ |
| skip rationale | — |
| severity | — |
| evidence link | this file §3.11 |
| checklist | [ ] keyboard Home/Import/Run/Insights/Settings [ ] visible focus [ ] contrast spot-check [ ] narrow-window Home+Run [ ] chart readability + downloadable alt [ ] each Streamlit-supported browser smoked |
| browsers smoked | Safari 26.5; Firefox 152.0.4; Waterfox 6.6.17 (extra). Chrome / Edge: _pending_ |
| notes | Official set = two most recent Chrome, Firefox, Edge, Safari |

---

## 3.12 Performance — **conditional / strongly expected**

| Field | Value |
|-------|-------|
| journey id | 3.12 Performance |
| class | conditional / strongly expected |
| outcome | _pending_ |
| skip rationale | — |
| severity | — |
| evidence link | this file §3.12 |
| Medium corpus (envelope recipe) | _pending_ (Balanced Medium recipe still owed) |
| Large-library | _pending_ (~168 transcripts on Home earlier — soak still open) |
| notes | Thorough `R20241026-121652` wall **2682.9s (~44.7 min)**, `final_status=partial`; LLM logical wall ~2122s; top fails = 600s timeouts on action_items + custom_qa. |
