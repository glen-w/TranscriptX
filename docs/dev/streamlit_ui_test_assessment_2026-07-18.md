# Streamlit UI Testing Assessment

**Date:** 2026-07-18  
**Scope:** Assess how the Streamlit GUI is tested today; map surfaces to layers; rank residual risk; lock a testing strategy.  
**Out of scope:** Broad AppTest of every page; Playwright-for-GUI before 1.0; core pipeline correctness outside `web/`.

---

## 1. Verdict

TranscriptX has a **mature L1–L3 contract/unit suite** for the Streamlit GUI under `tests/web/`, built on Streamlit doubles, session-state contracts, and source/AST guards. **L4 AppTest** covers seven primary acceptance journeys under `tests/web/gui_acceptance/` (`make test-gui-acceptance` / `heavy`); residual AppTest-blind items live in [`gui_acceptance_residual_checklist.md`](gui_acceptance_residual_checklist.md). There is **no Playwright-for-GUI** before 1.0. [`.coveragerc`](../../.coveragerc) still **omits** `transcriptx/web/*` from the default coverage gate (manual gap-finder documented in §11).

---

## 2. Surface inventory

### 2.1 Entry and routing

| Piece | Path | Notes |
|-------|------|-------|
| Canonical app | `src/transcriptx/web/app.py` | Session defaults, sidebar, context bar, route |
| Launcher | `src/transcriptx/web/__main__.py` / console `transcriptx` | Spawns `streamlit run …/app.py` |
| Page catalog | `navigation.py` `PAGE_SPECS` | Single source of truth for sidebar + prereqs |
| Router | `router.py` | Lazy page renderers + Corrections Studio gate |
| Shell | `shell.py` | `set_page_config`, brand CSS |

Flow: `app.py` → sidebar → context bar (when allowed) → `router.route_current_page` → `page_modules.<page>.render_*`.

Public contract: [`docs/public_surfaces.md`](../public_surfaces.md) — Streamlit GUI is the primary supported interface.

### 2.2 `PAGE_SPECS` pages

| Key | Section | Context / gate | Feature flag |
|-----|---------|----------------|--------------|
| Home | primary | — | — |
| Library | primary | may mutate context | — |
| Search | primary | — | — |
| Transcribe Audio | workflow | may mutate context | — |
| Import Transcript | workflow | may mutate context | — |
| Speaker ID | workflow | may mutate context | — |
| Corrections Studio | workflow | — | `TRANSCRIPTX_ENABLE_CORRECTIONS_STUDIO` (default `"1"`) |
| Run Analysis | workflow | may mutate context | Group radio gated by `group_analysis.enabled` |
| Batch Ops | workflow | — | — |
| Groups | workflow | may mutate context | — |
| Overview | view | `run_scoped` → fallback home | — |
| Transcript | view | `transcript_or_group` → home | — |
| Insights | view | `run_scoped` → overview | — |
| Charts | view | `run_scoped` → overview | — |
| Artifacts | view | `run_scoped` → overview | — |
| Data | view/legacy | redirect → Artifacts Preview | — |
| Explorer | view/legacy | redirect → Artifacts Browse | — |
| Audio Prep | tools | — | — |
| Audio Merge | tools | — | — |
| Settings | settings | — | — |
| Profiles | settings | — | — |
| Dashboard Builder | settings | — | — |
| Diagnostics | settings | — | — |

### 2.3 Major interactive subsystems (non-page)

| Subsystem | Key modules |
|-----------|-------------|
| Sidebar / workspace pickers | `sidebar*.py` — nav sections, transcript/group/run hydration |
| Context bar | `components/context_bar.py`, subject context helpers |
| Action menus | `action_menus/{ids,catalog,prefs,handlers,render,services}.py` |
| Settings Interface prefs | `ui/settings/interface_panel.py` |
| Progress panels | `components/progress_panel.py` |
| Blocks / layouts | `blocks/`, `layouts/` |
| Transcript viewer | `transcript_viewer/` |
| Web services behind UI | `web/services/` (subjects, artifacts, run index, cleanup, search, rename, …) |

---

## 3. Test layers in use

| Layer | Meaning | Present? |
|-------|---------|----------|
| **L0 Smoke** | Import / launcher `--help` | Yes — `tests/smoke/test_cli_help.py`; `make docker-smoke` for container launcher |
| **L1 Service** | Pure web services, no Streamlit | Yes — dense (`tests/web/services/*`, search, rename, group delegation) |
| **L2 Contract** | Session keys, source bans, import laziness, deep links | Yes — sidebar/nav/router/state/settings draft contracts |
| **L3 Page glue** | Render helpers via `DummyStreamlit` / monkeypatch | Yes — home, library, speaker_id, upload, transcribe, run_analysis, batch_ops, audio_prep, corrections pending-generate, charts helpers, action-menu navigation |
| **L4 Runtime** | Live Streamlit `AppTest` / browser E2E | **Partial** — seven primary journeys under `tests/web/gui_acceptance/` (`make test-gui-acceptance`); no Playwright-for-GUI before 1.0 |

Shared doubles: [`tests/web/streamlit_doubles.py`](../../tests/web/streamlit_doubles.py).  
Gate placement: unmarked / `@pytest.mark.unit` web tests ride **`make test-fast`**. Coverage measurement via `make test-coverage` **does not include** `web/` (`.coveragerc` omit). No in-repo GitHub Actions workflows; PR order is documented Make convention only.

Prior decision (still accurate): AppTest intentionally skipped in favor of doubles ([`tests/TEST_SUITE_ASSESSMENT.md`](../../tests/TEST_SUITE_ASSESSMENT.md) expansions).

---

## 4. Coverage matrix (Surface × highest layer × confidence)

Confidence: **Strong** = dedicated tests that assert the surface’s contracts; **Thin** = partial glue/helpers or adjacent only; **None** = no meaningful page/subsystem pin at that layer.

### 4.1 Pages (`PAGE_SPECS`)

| Surface | Highest useful layer | Confidence | Evidence (representative) |
|---------|----------------------|------------|---------------------------|
| Home | L3 | Strong | `test_home_page.py`, action links/menus |
| Library | L3 | Strong | `test_library_page.py`, rename UI, audio resolution, action-menu nav |
| Search | L1 | Thin | `test_search_service*.py`, matching helpers — **no** `page_modules.search` render tests |
| Transcribe Audio | L3 | Thin–Strong | `test_transcribe_audio_page.py` (orchestration slice) |
| Import Transcript | L3 | Strong | `test_upload_transcript_page.py` + import-success action wiring |
| Speaker ID | L3 | Strong | `test_speaker_id_page.py` |
| Corrections Studio | L3 | Thin–Strong | `test_corrections_studio_pending_generate.py`, selectbox index in `test_action_menu_navigation.py`; accept/reject/fragment UI not fully covered |
| Run Analysis | L3 | Thin–Strong | `test_run_analysis_page.py` (empty / in-progress); group target via action-menu nav; full module-pick + launch thinner |
| Batch Ops | L3 | Thin | `test_batch_ops_page.py` |
| Insights | L3 | Strong | `test_insights_page.py` (+ AppTest journey) |
| Charts | L3 | Thin–Strong | `test_charts_page_helpers.py` (+ AppTest journey) |
| Speakers | L3 | Strong | `test_speakers_page.py` (empty/listing/detail glue) + methodology helpers; AppTest journey |
| Artifacts | L2–L3 | Thin–Strong | nav/deep-link + `test_artifacts_page.py`; page render thinner |
| Groups | L3 | Strong | `test_groups_page.py` (+ AppTest journey) |
| Overview | L3 | Strong | `test_overview_page.py` (+ AppTest partial/failed status journey) |
| Data / Explorer (legacy) | L2 | Strong (redirect) | `test_artifacts_navigation.py` |
| Audio Prep | L3 | Thin | `test_audio_prep_page.py` (labels/empty path) |
| Audio Merge | — | **None** | rename/serial mentions only — **no** page tests |
| Settings | L2 | Thin | draft/profile/storage cleanup contracts — **no** full Configuration/Interface panel render suite |
| Profiles | L2 | Thin | `test_profiles_page_contracts.py` |
| Dashboard Builder | L3 | Thin | `test_dashboard_builder.py` |
| Diagnostics | — | **None** | no page tests |

### 4.2 Subsystems

| Surface | Highest useful layer | Confidence | Evidence |
|---------|----------------------|------------|----------|
| App cold start / init | L3 | Strong | `test_app_startup.py`, `test_app_init_defaults.py`, `test_app_imports.py` |
| Navigation / router | L2 | Strong | `test_navigation_*.py`, `test_router*.py`, deep links |
| Sidebar | L2 | Strong | hydration, options, state, nav source contracts, statistics |
| Context bar / subject | L2 | Strong | `test_context_bar.py`, `test_subject_context.py`, `test_state_unit.py` |
| Action menus (catalog/prefs/handlers) | L2–L3 | Strong | `test_action_menus_core.py`, `test_action_menu_navigation.py`, `test_action_links.py` |
| Settings Interface panel UI | L1–L2 | Thin | prefs load/save in `test_action_menus_core.py` — **not** `interface_panel` render |
| Blocks / layouts | L1–L3 | Strong | `tests/web/blocks/*`, `tests/web/layouts/*`, composition minimal run |
| Transcript viewer | L1–L3 | Strong | `tests/web/transcript_viewer/*` |
| Web services / run cleanup | L1 | Strong | `tests/web/services/*` (+ characterisation goldens, adversarial FS) |
| Web entry smoke | L0 | Strong | smoke `--help`; docker-smoke script |

### 4.3 Spot-check: what L3 actually asserts

| File | Asserts | Mocks away |
|------|---------|------------|
| `test_home_page.py` | Recent-run load orchestration, slug labels, empty state, action navigation helpers | Real Streamlit widgets; shell; filesystem via `Path.exists` |
| `test_run_analysis_page.py` | Empty transcripts → empty_state; in-progress skips launch fragment | Module lists, config, fragment body, real widgets |
| `test_action_menu_navigation.py` | `navigate_with_identity` lands on correct page + clears stale pickers; library rename one-shot; Corrections selectbox `index` | Live sidebar/rerun; most page renders |

These are valuable **session/orchestration contracts**, not proof that widgets, fragments, or multi-rerun UX work in a running app.

---

## 5. Critical journeys — risk scores

Scale: Impact / Likelihood / Gap each 1–5; **Risk** ≈ product of the three (higher = worse). **UI-blind** = only L1 (or less) for the interactive path.

| # | Journey | Impact | Likelihood | Gap | Risk | UI-blind? | Notes |
|---|---------|--------|------------|-----|------|-----------|-------|
| 1 | Cold start → Home → select run → Overview/Transcript/Charts | 5 | 3 | 2 | 30 | Partial | Home/nav strong; Overview page thin; Charts helpers only |
| 2 | Import/Transcribe → post-success action menu → target page + subject/run | 5 | 3 | 2 | 30 | No | Upload/transcribe + action-menu nav covered; live upload widget not |
| 3 | Speaker ID → completion actions | 4 | 2 | 2 | 16 | No | Page + SectionId wiring covered |
| 4 | Run Analysis (transcript + group) → progress → completion | 5 | 3 | 3 | 45 | Partial | Empty/in-progress glue; group gate / full launch thinner |
| 5 | Library rename / selection → Interface prefs round-trip | 4 | 3 | 3 | 36 | Partial | Prefs persist Strong; Interface **panel** Thin; rename nav Strong |
| 6 | Corrections Studio accept/reject/regenerate (fragments) | 4 | 3 | 3 | 36 | Partial | Pending-generate Strong; fragment review loop Thin |
| 7 | Groups CRUD → sidebar subject → Run Analysis group gate | 5 | 4 | 5 | 100 | **Yes** | E4 confirmed open: service Strong, page **None** |
| 8 | Settings Configuration / Storage / Interface save-restore | 4 | 3 | 3 | 36 | Partial | Draft/storage contracts; full panels Thin |
| 9 | Audio Prep large upload path | 3 | 2 | 4 | 24 | Partial | Helper/empty Thin; upload/runtime None |
| 10 | Deep links / legacy Data\|Explorer → Artifacts | 3 | 2 | 1 | 6 | No | Redirect contracts Strong |

**Top risks:** (7) Groups page UI-blind; (4) Run Analysis group/full launch; (5)/(6)/(8) prefs panel + Corrections fragments + Settings panels; (1) Overview page orchestration thinner than Home.

---

## 6. Strategy decision

**Stay doubles-first (L2/L3) for the fast lane.** Targeted AppTest covers the seven primary acceptance journeys behind `make test-gui-acceptance` / `heavy`. Do not add AppTest to the fast lane. Do not introduce browser E2E (Playwright/Selenium for GUI) before 1.0.

### Rationale

1. The repo already has a large, working doubles + contract culture for page glue; fast-lane budget must stay lean.
2. Stocktake gap: GUI is the primary surface while `web/` is omitted from coverage measurement — acceptance of critical journeys is the corrective, not flipping `.coveragerc` `fail_under` over `web/`.
3. AppTest validates navigation, state transitions, validation/success/error rendering, service call boundaries, and persistence into an isolated data dir without browser orchestration.
4. Residual AppTest-blind behaviours (file picker, browser download, hover/focus, popovers, visual alignment) stay on a short manual checklist: [`gui_acceptance_residual_checklist.md`](gui_acceptance_residual_checklist.md).

### Locked policy

| Approach | Decision |
|----------|----------|
| Streamlit doubles + session/source contracts | **Default** for page glue, nav, action menus, settings prefs logic (fast lane) |
| Targeted `AppTest` | **Adopted** for the seven journeys in `tests/web/gui_acceptance/` — marker `gui_acceptance` + `heavy`; `make test-gui-acceptance`. Not on default fast addopts |
| Browser E2E (Playwright/Selenium for GUI) | **Reject until post-1.0 reconsideration** — only if the residual checklist stays release-critical or repeatedly catches regressions |
| `web/` coverage measurement | **Gap-finder only:** optional report without raising `fail_under` until a baseline exists. Do not flip `.coveragerc` omit + fail_under in one step |
| Residual manual checklist | **Adopted** — AppTest-blind items only; recommended release-evidence pointer in [`release_governance.md`](release_governance.md) |

---

## 7. Prioritized backlog (≤15)

Status updated **2026-07-18** after doubles-first suite build-out. AppTest (item 13) remains deferred.

### P0 (close UI-blind primary paths)

1. ~~**L3 Groups page CRUD**~~ **Closed** — `tests/web/test_groups_page.py`
2. ~~**L3 Run Analysis group gate**~~ **Closed** — extended `tests/web/test_run_analysis_page.py`
3. ~~**L3 Search page glue**~~ **Closed** — `tests/web/test_search_page.py`

### P1 (thin primary UX)

4. ~~**L3 Insights page**~~ **Closed** — `tests/web/test_insights_page.py`
5. ~~**L3 Overview page**~~ **Closed** — `tests/web/test_overview_page.py`
6. ~~**L3 Settings Interface panel**~~ **Closed** — `tests/web/test_interface_panel.py`
7. ~~**L3 Corrections Studio review loop**~~ **Closed** — `tests/web/test_corrections_studio_review.py`
8. ~~**L2 search-under-group subject**~~ **Closed** — `test_search_group_subject_does_not_scope_session_slugs` pins current fail-open (no session_slugs for group subject)

### P2 (secondary surfaces / measurement)

9. ~~**L3 Audio Merge page**~~ **Closed** — `tests/web/test_audio_merge_page.py`
10. ~~**L3 Diagnostics page**~~ **Closed** — `tests/web/test_diagnostics_page.py`
11. ~~**L3 Artifacts page**~~ **Closed** — `tests/web/test_artifacts_page.py`
12. ~~**Optional web coverage report**~~ **Documented** — see §11 (gap-finder command; default `.coveragerc` still omits `web/`; no `fail_under`)
13. ~~**If doubles miss a real bug class:** one `heavy`-marked AppTest smoke~~ **Closed / superseded** — seven-journey AppTest acceptance lane (`make test-gui-acceptance`) + residual checklist; not broad page AppTest

---

## 8. Explicit non-goals

- Full browser E2E of the Streamlit GUI (Playwright/Selenium) before 1.0.
- Broad AppTest coverage of every page (only the seven acceptance journeys).
- Measuring `web/` under the default `fail_under = 70` gate without a separate baseline phase.
- Replacing L1 run-cleanup characterisation with UI tests (already strong; size is debt, not missing coverage).
- Visual/accessibility snapshot testing.
- Testing core analysis pipelines via Streamlit (belongs in core/integration lanes; AppTest stubs the controller).

---

## 9. Counts and verification (2026-07-18)

| Check | Result |
|-------|--------|
| `page_modules/*.py` (excl. `__init__`) | 23 modules |
| `tests/web` `test_*.py` (after build-out) | ~140+ |
| New/extended page tests this build-out | Groups, Search, Insights, Overview, Interface, Corrections review, Audio Merge, Diagnostics, Artifacts; Run Analysis group gate |
| `AppTest` / `streamlit.testing` in `tests/` | **Present** — `tests/web/gui_acceptance/` (seven journeys; `make test-gui-acceptance`) |
| `.coveragerc` omits `*/transcriptx/web/*` | **Yes** (unchanged; gap-finder uses a separate cov config) |
| Groups page E4 | **Closed** (page + Run Analysis gate + search-under-group contract) |
| Residual manual GUI checklist | [`gui_acceptance_residual_checklist.md`](gui_acceptance_residual_checklist.md) |

---

## 10. Related docs

- [`docs/public_surfaces.md`](../public_surfaces.md) — GUI as primary surface
- [`docs/dev/stocktake_2026-07-17.md`](stocktake_2026-07-17.md) — `web/` coverage omit called out
- [`docs/dev/group_functionality_audit_2026-07-17.md`](group_functionality_audit_2026-07-17.md) — E4 page-level gap
- [`tests/TEST_SUITE_ASSESSMENT.md`](../../tests/TEST_SUITE_ASSESSMENT.md) — expansion history; AppTest skip rationale
- [`tests/README.md`](../../tests/README.md) — Make lanes / markers
- [`docs/dev/web_blocks.md`](web_blocks.md) — block authoring + smoke under `tests/web/blocks/`

---

## 11. Web coverage gap-finder (no fail_under)

Default `make test-coverage` still **omits** `transcriptx/web/*` via [`.coveragerc`](../../.coveragerc). To measure UI code as a **manual** gap-finder (do not wire into CI fail_under yet):

```bash
# Write a throwaway config that does NOT omit web/
cat > /tmp/web_cov.ini <<'EOF'
[run]
source = src/transcriptx/web

[report]
fail_under = 0
show_missing = True
skip_empty = True
EOF

pytest tests/web -q \
  --cov=transcriptx.web \
  --cov-config=/tmp/web_cov.ini \
  --cov-report=term-missing
```

**Baseline note (2026-07-18):** a partial page-test slice with the gap-finder config reported roughly **~21%** TOTAL for `transcriptx.web` (not a suite-wide baseline). Re-run after large UI changes and record TOTAL %; do not change `.coveragerc` `fail_under` until a stable full-`tests/web` baseline exists.
