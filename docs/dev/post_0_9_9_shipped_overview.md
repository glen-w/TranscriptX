Type: PRODUCT
Authority: docs/dev/pre_release_roadmap_1_0.md

# Post-0.9.9 shipped wave — overview

**Status:** summary of work on `main` **after** the **0.9.9** cut, packaged as interim **`0.9.9.5`**  
**Baseline:** `45a235d` — *Release 0.9.9: Overview presentation cut with EPUB and batch progress honesty* (2026-08-09)  
**Through:** `0.9.9.5` tip (includes merge profiles, backup/restore, unnamed-speaker ungate, Playwright GUI E2E, CI/docs hygiene)  
**Programme home:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md)  
**Long-term theme status:** [docs/ROADMAP.md](../ROADMAP.md)

Package version **`0.9.9.5`** is an **interim cut** of this wave — not a new 0.9.x programme theme. It is early **1.x capacity pulled forward** — plus operator UX and hygiene — while the mandatory gate is still **unfamiliar-user validation → RC → 1.0**.

Rough scale since the baseline: **~32 commits** (PRs **#2–#31** plus direct lands), **~470+ files**, **~33k+ insertions**.

---

## Why this wave exists

The 1.0 programme had already closed maintainer acceptance, the Thorough stress pass, and the **0.9.9** Overview presentation cut (Analysis IA redistributed; selection-scoped EPUB; batch progress honesty). The next *mandatory* programme step is the clean-room unfamiliar-user round — not another feature freeze.

Capacity between 0.9.9 and that round was used to:

1. Land early **ROADMAP** themes that reduce Streamlit friction on the primary journeys (correct, name speakers, follow playback, read Insights).
2. Restore and deepen **audio / library operator** paths that unfamiliar users and power operators both hit (Tools, rename, merge, watcher).
3. Harden **composition / Settings clarity** and **GUI performance** so density and latency are less likely to block the next gate.
4. Leave **assessments** (GUI perf, test suite, settings/knobs) as living evidence rather than silent debt.

None of this replaces unfamiliar-user evidence. Severity triage still decides what must fix before RC.

---

## Theme map (what landed)

Status language matches [docs/ROADMAP.md](../ROADMAP.md): **done** / **[~] in progress** / Phase-N residuals remain.

| Cluster | ROADMAP | Shipped shape | Follow-ons still open |
|---------|---------|---------------|------------------------|
| Insights quality | **A** | Deterministic floors, schema-v3 composer (evidence / confidence / abstention), quieter empty states | Overview hierarchy polish; Charts catalogue audit; B18 LLM narratives deferred |
| Corrections in reader | **B** | Transcript **Correct** mode: word/span propose, atomic accept-and-apply, scoped sidecar | Studio remains batch/review; CCv2 selection polish |
| High-interaction workspaces | **C** | CCv2 Speaker ID **default-on** (`TX_SPEAKER_ID_WORKSPACE_COMPONENT=0` rollback); shared action services; Corrections command protocol | Phase 9 legacy retirement; richer edit surfaces |
| Playback / karaoke | **D** | Clip-scoped Transcript karaoke + honesty when timings missing; Playing badge / follow-along | Continuous full-file karaoke; CCv2-native reader |
| GUI performance | **E**-adjacent | Charts HTML gate; transcript windowing; non-blocking cold ▶; cold-import deferrals | Envelope reconcile; further scale work per assessment |
| Audio / inbox | **G / G2** | System → Tools (Preprocess + Merge); merge profiles + auto-merge; G2 Phase 1 directory watcher (default-off); Merge serial honesty + optional post-merge cleanup | Transcript stitch merge; watcher → host STT (theme **H**) |
| Workspace ops | (ops) | Full-workspace backup / verify / replace-restore | — |
| Speaker eligibility | (honesty) | Named speakers required by default; `allow_unnamed_speakers` ungate | — |
| STT / import polish | **K**-adjacent | WebVTT export; folder import clarity; STT command-gen presets (no secrets) | Broader host CLIs as needed |
| Composition | (0.9.9 residual path) | Dashboard Builder presets + Edit mode; Charts overview strip selector | Residual Overview hierarchy / full Charts catalogue from [overview_presentation_0_9_9.md](overview_presentation_0_9_9.md) |
| Test / CI | (hygiene) | Playwright GUI E2E lane; CI lint + nightly integration; Sphinx-on-push Pages | Residual AppTest-blind items |

---

## Workstreams (moderately detailed)

### 1. Early 1.x interaction themes (B / C / D)

**Theme B — corrections in the Transcript viewer** ([corrections-viewer.md](../runtime/corrections-viewer.md)). Operators can free-read, propose at word/span level, and apply without silent overwrite of the managed original. Corrections Studio stays the batch / detector / LLM review surface; Start/Resume no longer auto-generates.

**Theme C — Components v2 workspaces** ([theme_c_workspaces_ccv2.md](theme_c_workspaces_ccv2.md)). Shared `SpeakerIdActionService`, non-blocking clip APIs, packaged `transcriptx-workspaces` Speaker ID surface (default-on; missing package falls through to classic `@st.fragment`). Corrections revisioned protocol on the studio page; PlaybackHost handoff for Theme D. Legacy path retained until Phase 9 criteria.

**Theme D — karaoke MVP** ([karaoke-playback.md](../runtime/karaoke-playback.md)). Browser-local clip player with word highlight when imported `words[]` cover the clip; segment-level fallback + honesty caption otherwise; seek-from-word inside the karaoke panel without streaming `current_time` to Python.

### 2. Insights quality (Theme A)

Shared phrase / eligibility floors raised; insights composer deepened (schema v3 with evidence, confidence, abstention); deterministic summary/highlights honesty tightened; greeting-dominated noise reduced on large transcripts. Design: [theme_a_insights_quality.md](theme_a_insights_quality.md). This strengthens the deterministic base unfamiliar users see on Overview / Insights without adding modules (freeze still holds).

### 3. Operator workflows: rename, Tools, merge, watcher

- **Rename Transcript** workflow page with preview clips and date-prefix prefill; later **deterministic smart rename** from common device filename patterns (configurable pattern; auto / suggest / rename-only / off).
- **System → Tools** restores audio **Preprocessing** and **Merge** under the renamed System sidebar (CLI helpers remain for automation). Merge: concatenate-by-default; optional preprocess-while-merge; improved serial detection (hide false voice-note / messaging runs); optional delete of originals + linked transcripts after success.
- **Directory watcher (G2 Phase 1)** ([directory_watcher.md](../runtime/directory_watcher.md)): default-off inbox watcher with debounce/stability; auto-admit transcripts; queue audio as `queued_transcription` (no silent STT). Settings → Watcher + Import status.

### 4. Import / export / Transcribe easy wins

WebVTT beside TXT/CSV/SRT; folder import eligibility / Rescan / same-stem audio hints; Transcribe Audio **saved command-gen presets** under `stt_commands` profiles (host paths/flags only — never `HF_TOKEN`).

### 5. Settings scale and clarity

- Library-wide **bulk correction generation** on Settings → Corrections.
- Batch **voice enrol-all** and suggestion **pre-load** on Settings → Speakers (when local voice matching is enabled).
- Settings / profiles / knobs **assessment + hardening** ([settings_knobs_assessment.md](settings_knobs_assessment.md), [config_architecture.md](config_architecture.md), live [settings.md](../runtime/settings.md)): load-order honesty, stale semantic-v2 label cleanup, motif field alignment, rejected legacy audio env warnings.
- Adjacent **ⓘ** tooltips across GUI touchpoints; configurable via Settings → Interface (`show_info_tooltips`, default on). Run-id identity tip stays always available.

### 6. Dashboard Builder and Charts overview selection

Three built-in layouts (**Meeting follow-up**, **Speakers**, **Minimal**) plus validation / overwrite / delete hardening. **Edit** mode to add/remove/reorder Overview and Insights blocks. Settings → Configuration exposes ordered **Charts overview** selection (distinct from layout composition). Guides: [dashboard_builder.md](dashboard_builder.md), [composition_platform.md](composition_platform.md).

### 7. GUI performance

Measured assessment then upgrades ([gui_performance_assessment_2026-08-11.md](../archive/assessments/gui_performance_assessment_2026-08-11.md), [gui_performance_upgrades_2026-08-11.md](../archive/assessments/gui_performance_upgrades_2026-08-11.md)): stop auto-iframing large Plotly HTML; size-gate artifact HTML; window Transcript segments (50 + Show more); warm only visible clips; cache-or-enqueue cold play; defer heavy imports off cold start.

### 8. Docs and assessments (not product features)

- Five outcome-focused **workflow walkthroughs** with screenshots/GIFs ([docs/workflows/](../workflows/index.md)).
- Entry/docs sync for 0.9.9 + Theme B/C/D status ([CHANGELOG](../../CHANGELOG.md), ROADMAP theme map, inventories).
- Living **test suite review** ([test_suite_review_2026-08-12.md](test_suite_review_2026-08-12.md)): lane gaps, NLP env brittleness, web omit from coverage, P0–P2 backlog — remediation tracked separately.

---

## Relation to the 1.0 programme

| Programme item | Effect of this wave |
|----------------|---------------------|
| **0.9.9 Overview presentation** | Cut already done at baseline. Builder Edit + Charts overview selector help residual presentation debt; full Charts catalogue + Overview hierarchy polish remain deferred. |
| **Unfamiliar-user validation** | Still mandatory and **not executed**. This wave should make principal journeys clearer (Correct, Speaker ID, karaoke honesty, Tools, rename, tooltips, workflows) but does not count as clean-room evidence. |
| **Module freeze** | Held — no new analysis modules. Theme A deepens existing deterministic insights. |
| **1.0 success criterion** | Unchanged: unfamiliar user can install → useful result → export without undocumented developer knowledge. |
| **Safe-to-defer list (historical)** | Themes **B/C/D** and **G2 Phase 1** were listed as post-1.0 in older programme text; they are now partially or Phase-1 shipped on the 0.9.9 line. Treat ROADMAP theme status as authority for those items. |

---

## Still ahead (programme-critical)

1. **Unfamiliar-user clean-room round** — [unfamiliar_user_validation_1_0.md](unfamiliar_user_validation_1_0.md); cohort who/when still owner judgement (§20).
2. **Severity triage** of findings from that round (and any residual maintainer debt).
3. **RC → 1.0** gates: release ops/support publish, trust/perf sign-off, governance evidence on exact commit, RTD slug (owner-gated).
4. **Deferred presentation residuals** from [overview_presentation_0_9_9.md](overview_presentation_0_9_9.md) if they become unfamiliar-user blockers.
5. **Theme C Phase 9**, continuous karaoke, transcript-stitch merge, watcher→STT — post-1.0 or severity-justified only.

---

## Commit / PR index (chronological)

| When | Ref | Summary |
|------|-----|---------|
| 2026-08-10 | #3 `11ebb09` | Theme C CCv2 workspaces |
| 2026-08-10 | #2 `1495916` | Theme B viewer propose/apply |
| 2026-08-10 | #4 `7593d63` | Five workflow walkthroughs |
| 2026-08-11 | #5 `d6cb9c0` | Theme D karaoke MVP |
| 2026-08-11 | #7 `c0d8917` | Speaker ID CCv2 default-on |
| 2026-08-11 | #8 `f047301` | WebVTT, folder import, STT presets |
| 2026-08-11 | #6 `e66ca63` | Theme A deterministic insights |
| 2026-08-11 | `67b4c39` | Bulk corrections + Rename Transcript |
| 2026-08-11 | #9 `e0596f8` | Docs sync 0.9.9 + themes/workflows |
| 2026-08-11 | #12 `fdb8a5a` | GUI performance upgrades |
| 2026-08-11 | #10 `ec6c2e4` | Directory watcher G2 Phase 1 |
| 2026-08-11 | #11 `65c2679` | GUI performance assessment |
| 2026-08-11 | #13 `3aaf354` | Batch voice enrol / suggestion pre-load |
| 2026-08-11 | #14 `dc3b9b9` | Settings/knobs clarity |
| 2026-08-12 | #15 / #16 | Dashboard Builder presets + deep-test |
| 2026-08-12 | #17 `296aed9` | System → Tools (Preprocess / Merge) |
| 2026-08-12 | #18 `ce5e184` | Smart rename from device patterns |
| 2026-08-12 | #19 `227cbe7` | Layout Edit mode + Charts overview selector |
| 2026-08-12 | #20 `7b99b62` | ⓘ tooltip helpers |
| 2026-08-13 | #21 `da742f9` | Test suite review assessment |
| 2026-08-15 | `2afe3ad` | Merge serial detection + post-merge cleanup |
| 2026-08-15 | #22 `570d1b5` | Merge source profiles + auto-merge |
| 2026-08-15 | #23 `8d0ec64` | Playwright GUI E2E (workflows 1–3) |
| 2026-08-15 | #24 `f2e2fe0` | PRODUCT.md continuous LT reframe |
| 2026-08-15 | #25–#27 | Workflow concept links; CI YAML fix; Sphinx-on-push |
| 2026-08-15 | #28 `62fb241` | Unnamed-speaker ungate |
| 2026-08-15 | #29 `cc2a40d` | Speaker-identification workflow rename |
| 2026-08-15 | #31 `91befe5` | Full-workspace backup/restore |
| 2026-08-15 | #30 `f6ca422` | Light CI expansion (lint, `[web]`, nightly) |
| 2026-08-15 | — | **Cut `0.9.9.5`** interim release |

Refresh this table when cutting the next version or archiving this file after 1.0.
