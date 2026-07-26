Type: PRODUCT
Authority: docs/dev/pre_release_roadmap_1_0.md

# 0.9.9 — Overview / results presentation polish

**Status:** backlog list (not started)  
**Slot:** after **maintainer acceptance** findings settle; **before** unfamiliar-user validation  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md)  
**Related:** [manual_acceptance_1_0.md](manual_acceptance_1_0.md) §3.3 (Overview works; presentation debt parked here)

Presentation-only theme. No new analysis modules. Prefer coherent organisation and clearer hierarchy over feature expansion. Cut as **`0.9.9`** (or next free 0.9.x patch) when the list is actionable and tested.

## Why this slot

Maintainer pass proved Overview navigation, summaries, Actions, Highlights, and Analysis panels are **usable**. Organisation and presentation need a deliberate pass so unfamiliar users are not blocked by density or weak hierarchy — without delaying the rest of the maintainer kit.

## Scope (in)

- Overview (and closely related results surfaces that share the same presentation patterns)
- Information architecture: grouping, order, headings, collapse defaults
- Visual hierarchy and scannability of Actions / Highlights / Analysis / Summaries
- Honest partial-run signalling where it affects first paint (e.g. timed-out LLM modules)
- **Charts quality pass** — every chart output across 1-speaker, 2-speaker, and multi-speaker transcripts (look / usefulness / empty or misleading states)

## Scope (out)

- New analysis modules or preset changes
- Reintroducing Guided/Full / demo / onboarding checklist
- Website / RTD polish unrelated to in-app results
- Unrelated Artifacts redesign (unless findings from the Charts pass clearly share the same fix)

---

## Backlog (seeded from maintainer pass 2026-07-26)

Evidence run: `R20241026-121652` / `20260726_015208_30728241` (Thorough, **partial**). Charts page smoke (filters/fullscreen/search) already **pass** on that two-speaker run — not a substitute for the full chart catalogue audit below.

### Overview organisation & presentation

- [ ] **Actions / Highlights / Analysis** — works functionally; needs clearer organisation and better presentation (grouping, priority order, less wall-of-content)
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
| P1 | Actions/Highlights/Analysis need organisation + better presentation | Overview | polish → likely must-fix for unfamiliar-user comfort | Seeded 2026-07-26 |
| P2 | Thorough chart catalogue review (1 / 2 / multi-speaker) | Charts | TBD per chart | Seeded 2026-07-26; page chrome already smoked |

---

## Exit criteria

- [ ] Seeded Overview items implemented or explicitly deferred with severity (known limitation / post-1.0)
- [ ] Charts catalogue assessed for 1-speaker, 2-speaker, and multi-speaker; must-fix chart issues fixed or severity-triaged
- [ ] Maintainer re-check of Overview (and sample Charts) on a real run (pass or documented residual)
- [ ] No new release blockers introduced
- [ ] Theme cut tagged; unfamiliar-user kit may proceed
