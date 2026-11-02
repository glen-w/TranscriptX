# GUI upgrade / hardening wave (2026-11-02)

Evidence: [assessments/gui-ux-assessment-2026-11-02.md](../../assessments/gui-ux-assessment-2026-11-02.md) (finding ids F1–F19 below refer to §5 there). Successor to [gui-fluidity 2026-10-20](2026-10-20-gui-fluidity.md): two of its Wave A "shell tax" cuts regressed the shell; this wave repairs them, adds the test lane that would have caught them, then upgrades what users hit most.

**Stance (unchanged from ROADMAP Themes C / I):** Streamlit stays the shell; no SPA, no Gradio/NiceGUI, no new CCv2 unless remount/bytes/focus evidence. Everything here is classic Streamlit + tests + one theme file.

## Goals

1. Navigation is trustworthy: every sidebar click lands, the sidebar stays complete, the page is styled, the URL survives a refresh.
2. Shell regressions cannot ship again: a PR-gated browser smoke exists and is fast.
3. Cold pages are bounded and visible: no 20 s+ paint without a skeleton; DOM budgets enforced.
4. Presentation is consistent and brand-correct: one header system, one theme, humanised copy, no dead controls.
5. Baseline accessibility is measured, not assumed.

## Non-goals / stop lines

- No SPA / API / PWA (Theme I gate). No rewrite of `shell.py` CSS into a design system beyond what the theme file removes.
- No new analysis modules, no Settings taxonomy redesign (Settings Phase 2 H1–H6 stays its own plan; W3 only fixes density/copy).
- Do not re-introduce Guided/Full modes or onboarding tours (removed 0.9.6).
- Do not "fix" Streamlit a11y upstream issues with brittle DOM hacks; mitigate where a wrapper is cheap, document the rest.

## Waves

### W0 — Hotfix (ship as 1.1.1; days, not weeks)

| # | Slice | Finding | Acceptance |
|---|-------|---------|------------|
| W0.1 | `core/observability/perf.py::section` and `instrument_cached_call`: never `return` inside `finally`; compute `metrics`/`_enabled()` first, guard the body. Unit test: `RerunException`, `StopException`, `ValueError` propagate with telemetry off **and** on. | F1 | Sidebar complete after 10 random nav clicks (E2E); unit test green |
| W0.2 | `shell.inject_global_styles`: emit every run (drop `_GLOBAL_STYLES_SESSION_KEY`). Keep base64 logos cached (`lru_cache` already). Measure cost: static ~35 KB string per run is acceptable; if not, split CSS into a static file served via `st.html` + theme (W3.1). | F2 | `style[tx-sidebar-brand]` count == 1 after nav (E2E); single logo visible |
| W0.3 | **Shell smoke E2E** (`tests/e2e_gui/test_shell_smoke.py`, marker `gui_e2e` + new `gui_shell_smoke`): headless 1440×900, seeded tiny library; nav to every `PAGE_SPECS` page; assert sidebar button count constant, no `stException`, zero `pageerror` console events, CSS probe == 1, page title element present, DOM nodes ≤ budget per page. Target < 3 min. Wire into **PR CI** (ci.yml) behind the existing Playwright install step; bump `playwright` pin to a build that runs on current macOS/Linux (1.40 Chromium 1091 crashes on macOS 26). | F6 | Runs on PR; fails on either W0.1/W0.2 regression when reverted |
| W0.4 | `python -m transcriptx.web`: pass `--server.fileWatcherType none` unless `TRANSCRIPTX_DEV=1`; keep `streamlit_watcher_noise.py` for dev. | F12 | Server log free of `Examining the path` tracebacks in default launch |
| W0.5 | CHANGELOG 1.1.1: "Fixed: sidebar navigation truncated / unstyled after first click (1.1.0 regression)". | — | |

Rollback: none needed; both fixes restore pre-1.0.3 behaviour.

### W1 — Navigation trust (1.1.x)

| # | Slice | Finding | Acceptance |
|---|-------|---------|------------|
| W1.1 | **URL state**: mirror `page`, `subject_type`, `subject_id`, `run_id` into `st.query_params` on change; hydrate from URL in `_init_defaults` before prerequisites; one-shot keys stay out of the URL. Deep-link helpers (`navigate_to_*`) write both. | F5 | Reload on Overview keeps page+run; pasted URL opens same view; E2E case |
| W1.2 | Nav buttons use `on_click=` callback that sets `PAGE_KEY` (callbacks execute before the script body) instead of `if st.button(): st.rerun()` inside the sidebar; remove the in-sidebar `st.rerun()`. | F1, F3 | No `st.rerun` in `sidebar.py`; shell smoke unchanged |
| W1.3 | Lost-click investigation on Rename Transcript: log fragment reruns (`_render_preview` autoplay / clip enqueue) vs full-app clicks for one session; then either gate autoplay to an explicit ▶ or debounce clip-ready reruns. | F3 | 50 scripted nav clicks from Rename Transcript → 50 page changes (E2E loop, nightly) |
| W1.4 | Session-state hygiene: move the 10 cross-module ad-hoc keys into `state.py` with `consume_*` helpers; pop `NAV_REQUEST_KEY`, `run_analysis_target`, `speakers_selected_profile` after use; test that `navigation.py` writes only registered keys. | F15 | grep: 0 literal cross-module keys outside `state.py` |
| W1.5 | Remove orphan `Speaker Detail` route; delete empty `web/pages/`, `web/navigation/` packages. | F19 | |

### W2 — Cold-path and density budgets (1.1.x)

| # | Slice | Finding | Acceptance |
|---|-------|---------|------------|
| W2.1 | Speakers: cache the aggregation snapshot (`@st.cache_data` keyed on library fingerprint + inclusion toggles); paint header + `st.status("Building speaker index…")` before compute. | F4 | Speakers ≤ 5 s warm, ≤ 15 s cold on 345-transcript library; skeleton visible within 1 s |
| W2.2 | Corpus inventory: cache lookup **before** `discover_transcript_refs()`; fingerprint from cheap `os.scandir` mtimes; Search reuses it. | F4 | `cached_corpus_inventory` section ≤ 1 s on hit |
| W2.3 | Settings hub: render only the active panel body (finish fluidity Wave B); Diagnostics: paginate never-finished runs (50/page) and add "Clean never-finished runs" action via `services/run_cleanup`. | F7, F13 | Settings ≤ 4k DOM nodes / ≤ 120 buttons on open; Diagnostics ≤ 3k |
| W2.4 | Extend `scripts/capture_streamlit_perf_scenarios.py` with Speakers / Settings / Diagnostics / Search; assert budgets in nightly (advisory first, gate after two green weeks). | F4, F7 | Budget table in `docs/dev/performance_envelopes_1_0.md` |
| W2.5 | Tests: `conftest` forces isolated `TRANSCRIPTX_DATA_DIR`/`OUTPUT_DIR` for every GUI/AppTest/E2E lane (fail loudly if they resolve inside the owner library). | F13 | No `mini_transcript_*` / `simple` fixtures appear in a real library after `make test-heavy` |

### W3 — Presentation consistency and theme (1.2)

| # | Slice | Finding | Acceptance |
|---|-------|---------|------------|
| W3.1 | `.streamlit/config.toml` theme: brand `primaryColor` (blue), sidebar colours, fonts, light/dark via `[theme]`/`[theme.sidebar]`. Remove the CSS that only existed to override the red default; keep chrome-sync JS only if the logo swap still needs it. | F8 | Active nav/primary buttons brand-blue in both colour schemes; `!important` count in `shell.py` down ≥ 50 % |
| W3.2 | One header system: migrate Tools, Settings, Diagnostics, Profiles, Transcribe, Import, Speaker ID, Corrections, Ask to `render_page_shell`; lint test forbids `main-header` / `st.title` in `page_modules`. | F14 | 24/24 pages via `render_page_shell`/`render_run_scoped_page` |
| W3.3 | Empty-state copy: Overview/Insights block empties say what is missing in user terms ("This run has no summary yet") with Run Analysis / Overview actions (copy Charts' pattern); never list filenames outside an expander. | F10 | No `.json` / `rows.json` strings in default empty-state text (test over block registry) |
| W3.4 | Humanise Settings → Configuration section titles via `FieldMetadata` titles (`LLM`, `Audio preprocessing`, `Group analysis`). | F10 | |
| W3.5 | Transcript: do not render the audio player when no media; show the existing caption only. | F11 | |
| W3.6 | Picker labels: reuse Library title/date decoration in `decorate_transcript_picker_label`; keep stem in `help=`. | F17 | |
| W3.7 | Terminology pass from `docs/TERMS.md`: rename nav label/key mismatch (`Tools` ↔ "Audio Preprocessing"), Import vs Admit copy, session/transcript/run placeholders. | F16 | |
| W3.8 | Narrow width: wrap Library filter chips / stack Sort under 1024 px via CSS in the theme-era stylesheet. | F18 | 768 px Library shows all Workflow chips |

### W4 — Accessibility baseline (1.2)

| # | Slice | Finding | Acceptance |
|---|-------|---------|------------|
| W4.1 | Add `axe-core` pass to the shell smoke (Playwright `page.evaluate` with bundled axe) on Home, Library, Overview, Run Analysis, Settings; report serious/critical; gate on "no new criticals" after baseline. | F9 | Baseline report committed under `docs/dev/a11y_baseline_<date>.md` |
| W4.2 | Icon buttons: wrap `action_links` rows in `st.html` with explicit `aria-label` where Streamlit exposes the ligature, or switch to Streamlit `icon=` tokens that render `aria-hidden` (verify per Streamlit version); file upstream issue with repro. | F9 | Accessible names read "Open", "Charts" (axe `button-name` clean) |
| W4.3 | Reduce `label_visibility="collapsed"` to cases with an adjacent visible label; add `caption` alt text for chart iframes (module + chart title). | F9 | ≤ 5 collapsed labels; every chart iframe preceded by a caption |
| W4.4 | Shell keyboard: `/` focuses Search, `g` then letter for nav groups (only when no input focused), documented in `docs/runtime/settings.md` Interface section; CCv2 maps unchanged. | — | |

## Ordering and sizing

```
W0 (hotfix, 1.1.1)  ──►  W1 nav trust  ──►  W2 budgets  ──►  W3 theme/consistency  ──►  W4 a11y
   ~1–2 days             ~1 week            ~1 week            ~1–2 weeks               ~1 week
```

W0 is independent and must ship first. W1.1 (URL state) and W2.x are independent of each other. W3.1 (theme file) should land before W3.2–W3.8 so header/empty-state work is styled once.

## Test additions (summary)

| Lane | New |
|------|-----|
| unit | `section()`/`instrument_cached_call` exception transparency; `navigation.py` registered-keys test; header-system lint; empty-state filename lint |
| AppTest | nav via callback changes `page`; URL hydrate from query params |
| Playwright (PR gate) | `test_shell_smoke.py`: all pages, sidebar count, CSS probe, console errors, DOM budgets, axe criticals |
| Playwright (nightly) | lost-click loop from Rename Transcript; cold-path budgets on seeded 300-item library |

## Decision forks

| Fork | Options | Call |
|------|---------|------|
| CSS delivery | (a) re-emit per run · (b) theme file + minimal CSS · (c) static asset via `st.html` | **(a) now in W0, (b) in W3**; (c) only if (a) measures > 20 ms/run |
| Nav mechanism | (a) `on_click` callbacks · (b) `st.navigation`/multipage · (c) keep `if st.button(): rerun` | **(a)**; (b) would fight the prerequisite/picker model and the custom sidebar |
| URL state scope | (a) page only · (b) page + subject + run · (c) also filters | **(b)**; (c) later per page if cheap |
| A11y gate | advisory report · block on new criticals | advisory for one release, then block |

## Success signals

- A fresh install user clicks ten sidebar entries and sees ten styled pages with a complete sidebar; refresh keeps them where they were.
- PR CI fails within 3 minutes if the shell loses CSS, drops nav buttons, logs a console error, or exceeds DOM budgets.
- Speakers/Search on a 300+ library paint a skeleton immediately and finish in single-digit seconds warm.
- Settings opens with one panel's widgets, not ten.
- Primary colour is brand blue in both colour schemes without `!important`.
- axe reports zero critical issues on the five core pages.
