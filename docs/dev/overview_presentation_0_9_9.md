Type: PRODUCT
Authority: docs/dev/pre_release_roadmap_1_0.md

# 0.9.9 — Overview / results presentation polish

**Status:** cut as **`0.9.9`** (2026-08-09) — Analysis tab retired; Overview EPUB + batch progress honesty landed; Overview hierarchy + Charts catalogue residuals deferred for pre-unfamiliar-user follow-up  
**Slot:** after **maintainer acceptance** findings settle; **before** unfamiliar-user validation  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md)  
**Related:** [manual_acceptance_1_0.md](manual_acceptance_1_0.md) §3.3 (Overview works; presentation debt parked here)

Presentation-only theme. No new analysis modules. Prefer coherent organisation and clearer hierarchy over feature expansion.

## Why this slot

Maintainer pass proved Overview navigation, summaries, Actions, Highlights, and Analysis panels are **usable**. Organisation and presentation need a deliberate pass so unfamiliar users are not blocked by density or weak hierarchy — without delaying the rest of the maintainer kit.

## Proposed IA decision (2026-08-07)

**Delete Analysis as a distinct user-facing Insights tab.** Keep the underlying analysis modules and block renderers; redistribute their presentation into homes that answer clear user questions.

### Diagnosis

Insights → Analysis has become a catch-all for analytical outputs without an obvious home (lexical diversity, epistemic markers, politeness, keyphrases, content/style). Technically rich, conceptually weak: there is no clear user question that “Analysis” answers.

### Target Insights nav

**Summary · Speakers · Actions · Highlights**

(Charts and Artifacts remain sibling pages, not Insights sections.)

### Redistribution map (modules stay; section placement changes)

| Destination | Receives | User question |
|-------------|----------|---------------|
| **Summary** | Themes, keyphrases, salient content from `insights` / `keyphrases`; optionally 2–4 notable analytical observations | What is this conversation about? |
| **Speakers** | Lexical diversity, interaction style, politeness, epistemic behaviour where speaker comparison is meaningful | How do speakers differ in how they talk? |
| **Highlights** | Interesting / extreme passages already discoverable from those analyses (link or surface; do not invent new detectors in this theme) | What stands out in the wording? |
| **Charts** | Distributions and comparative visualisations (already a sibling page) | How do the numbers look? |
| **Artifacts** | Raw tables, scores, provenance, full module outputs | I want the evidence / dump |

### Implementation shape (when cut)

- Layout-driven: reassign `section:` on Insights placements in `default.yaml` (and any section-aware presets); drop `analysis` from Insights section nav + `LayoutSection`.
- Split `insights_contract` presentation if needed: **content** (themes / ideas) → Summary; **style markers** → Speakers (or a short Speakers sub-block), rather than one “Content vs Style” orphan.
- Preserve consolidated provenance / “view raw” paths by pointing people to Artifacts (and quiet per-block raw links where useful) — do not recreate an Analysis dump tab.
- Overview: stay curated (summary / speakers / actions / highlights / run status). Do not reintroduce an Analysis panel there.
- No new modules, presets, or highlight detectors in this theme. If analysis-derived “extreme passages” lack a clean existing feed into Highlights, defer that slice or ship only soft cross-links — do not block the tab removal on new detectors.

### Why redistribute rather than redesign Analysis

A renamed or regrouped Analysis tab still answers “miscellaneous metrics.” Moving each module to a question-shaped section makes Insights navigation immediately understandable for unfamiliar users (the next gate after this theme).

---

## Scope (in)

- Overview (and closely related results surfaces that share the same presentation patterns)
- Insights information architecture: **retire Analysis section**; redistribute existing Analysis blocks per map above
- Visual hierarchy and scannability of Summary / Speakers / Actions / Highlights on Overview and Insights
- Honest partial-run signalling where it affects first paint (e.g. timed-out LLM modules)
- **Charts quality pass** — every chart output across 1-speaker, 2-speaker, and multi-speaker transcripts (look / usefulness / empty or misleading states)

## Scope (out)

- New analysis modules or preset changes
- New highlight / extreme-passage detectors (presentation of existing feeds only)
- Reintroducing Guided/Full / demo / onboarding checklist
- Website / RTD polish unrelated to in-app results
- Unrelated Artifacts redesign (unless findings from the Charts pass clearly share the same fix)

---

## Backlog (seeded from maintainer pass 2026-07-26)

Evidence run: `R20241026-121652` / `20260726_015208_30728241` (Thorough, **partial**). Charts page smoke (filters/fullscreen/search) already **pass** on that two-speaker run — not a substitute for the full chart catalogue audit below.

### Insights IA — retire Analysis tab

- [x] **Remove Insights → Analysis** from section nav; keep modules/blocks
- [x] **Summary** — place keyphrases + content themes / recurring ideas; keep summary body primary; avoid a second wall of tables
- [x] **Speakers** — place lexical diversity, politeness, epistemic (and style markers) as speaker-comparison content alongside LLM speaker summaries
- [ ] **Highlights** — surface or link any existing analysis-backed extreme / notable passages; defer new detectors
- [x] **Artifacts / provenance** — ensure raw JSON/CSV and provenance remain reachable without an Analysis section
- [x] Layout contracts / GUI tests updated for four-section Insights nav

### Overview organisation & presentation

- [ ] **Actions / Highlights / Summaries / Speakers** — clearer organisation and presentation (grouping, priority order, less wall-of-content); no Analysis panel
- [ ] **Summaries** — content looks good; confirm placement/weight vs Actions/Highlights so the page scans as one composition
- [ ] **Section hierarchy** — consistent headings, expand/collapse defaults, and “what to look at first” for a completed (or partial) run
- [ ] **Partial-run honesty on Overview** — timed-out / FAIL modules (e.g. `llm_action_items`, `llm_custom_qa`) should not look like silent gaps; surface status without burying successes

### Charts — full catalogue assessment

- [ ] **Every chart output** on a **1-speaker** transcript — open each chart; assess look, readability, empty/error states, and whether the chart is useful / honest for that speaker layout
- [ ] **Every chart output** on a **2-speaker** transcript — same (can reuse maintainer Thorough run `R20241026-121652` as the two-speaker corpus if still available)
- [ ] **Every chart output** on a **multi-speaker** transcript — same (≥3 speakers)
- [ ] Record per-chart notes (keep / fix / hide / known limitation) with severity; feed must-fix items into this theme cut, defer the rest

### Capture more during remaining maintainer pass

Add bullets here as Insights / Artifacts / Settings findings appear — keep each item concrete and severity-tagged when known (`must-fix` vs presentation polish).

| ID | Finding | Surface | Severity (draft) | Notes |
|----|---------|---------|------------------|-------|
| P1 | Insights Analysis is a catch-all without a user question; retire tab and redistribute | Insights | must-fix for unfamiliar-user comfort | Implemented 2026-08-07; supersedes “organise Analysis in place” |
| P2 | Thorough chart catalogue review (1 / 2 / multi-speaker) | Charts | TBD per chart | Seeded 2026-07-26; page chrome already smoked |
| P3 | Overview Actions/Highlights/Summaries hierarchy | Overview | polish → likely must-fix | Seeded 2026-07-26; align with four question-shaped surfaces |

---

## Exit criteria

- [x] Insights nav is Summary · Speakers · Actions · Highlights (no Analysis section)
- [x] Former Analysis blocks redistributed per map, or explicitly deferred with severity
- [ ] Seeded Overview items implemented or explicitly deferred with severity (known limitation / post-1.0)
- [ ] Charts catalogue assessed for 1-speaker, 2-speaker, and multi-speaker; must-fix chart issues fixed or severity-triaged
- [ ] Maintainer re-check of Overview + Insights (and sample Charts) on a real run (pass or documented residual)
- [ ] No new release blockers introduced
- [x] Theme cut tagged (`v0.9.9`); unfamiliar-user kit may proceed (Charts/Overview hierarchy residuals tracked above)
