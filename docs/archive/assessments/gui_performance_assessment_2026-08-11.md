> **Archived / superseded.** Historical context only. Current authority: [performance_envelopes_1_0.md](../../dev/performance_envelopes_1_0.md). Do not treat as live roadmap or support policy.

Type: PRODUCT
Authority: self

> Historical assessment. Live envelopes: [performance_envelopes_1_0.md](../../dev/performance_envelopes_1_0.md). Analysis-run timing is a separate track: [run_performance.md](../../dev/run_performance.md). Do not treat this document as a release gate by itself.

# GUI Performance Assessment

**Date:** 2026-08-11  
**Package:** TranscriptX `0.9.9` · Streamlit `1.61.1` · Python `3.10.20`  
**Environment:** Linux x86_64 cloud agent VM (4 vCPU, ~15 GiB RAM), native `.venv` (not Docker)  
**Scope:** Streamlit GUI load / rerun / interaction responsiveness  
**Out of scope:** Analysis DAG wall times (`run_performance.json`, View → Performance page)

---

## 1. Verdict

The Streamlit GUI is **structurally prepared for responsiveness** (lazy page routers, deferred Home hydration, ~27 `@st.fragment` boundaries, listing caches, Speaker ID / Corrections paging). Headless load scenarios on a small epoch-1 data root show **cheap shell reruns** (Home warm ~1.5–1.7 ms script wall; Library ~28 ms including discovery). Residual risk is concentrated in four places: **unbounded transcript widget trees** (1007-segment fixture has no display cap), **Plotly HTML that inlines ~4.85 MB of JS per chart**, **synchronous cold clip decode on ▶**, and **eager `web.blocks` import (~1.7 s) undermining cold-start lazy routing**. No data-corrupting GUI blocker was found.

---

## 2. Method

| Step | What we did |
|------|-------------|
| Baseline capture | `scripts/capture_streamlit_perf_scenarios.py` + `scripts/streamlit_perf_report.py` against a fresh epoch-1 root (`.local/perf_data/`) |
| Cold import split | Fresh subprocess timings for `streamlit`, bootstrap, `web.blocks`, transcript/corrections imports |
| Live server smoke | `streamlit run …/app.py` headless; `/_stcore/health` reached in ~2 s; HTTP `/` 200 |
| Hotspot microbench | `filtered_display_segments` on `_deep_test_large_norm.json` (1007 segments); Plotly `to_html` size matrix |
| Static audit | Shell, cache helpers, transcript viewer, playback/clip service, charts/artifacts, Speakers / Speaker ID, Search debounce |
| Envelope reconcile | Compared to [performance_envelopes_1_0.md](../../dev/performance_envelopes_1_0.md) GUI rows |

**Not re-measured here:** interactive browser jank; 200+ library soak (prior **pass** 2026-08-07); cold ▶ ffmpeg wall (no representative recording wired in this VM).

**Instrumentation note:** `app.import_bootstrap` records elapsed since module import (`_APP_IMPORT_STARTED_AT`), so it **accumulates across scenarios in one process**. Prefer `total_wall_time_ms` for per-rerun cost; treat import_bootstrap as a cold-import signal from the first scenario only.

**First capture attempt** against repo `data/` failed closed with `schema_epoch_blocked` (occupied root, missing `schema_epoch.json`). Review capture used a dedicated compatible root instead of mutating repo data.

---

## 3. Measured baselines

### 3.1 Headless scenario capture (epoch-1 root, dummy Streamlit session)

| Scenario | Total wall (ms) | Notes |
|----------|----------------:|-------|
| first_browser_load_after_cold_start | 32.1 | Home; first main after import |
| warm_refresh_within_cache_ttl | 1.6 / 1.5 | Home |
| refresh_after_cache_ttl_expires | 1.7 | Home; `st.cache_data.clear()` |
| navigation_rerun_library | 27.9 | Transcript discovery ~24.6 ms; picker cache **miss** |
| navigation_rerun_search | 6.3 | |
| navigation_rerun_charts | 14.3 | `cached_list_viewable_session_names` **hit** |

Raw JSON copies under the review root were **not** admitted as managed transcripts (`valid_managed_transcripts=0`); Library/Charts timings reflect shell + discovery against an empty managed corpus, not a Medium/Large library paint.

### 3.2 Cold import (fresh subprocess)

| Piece | ms |
|-------|---:|
| `import streamlit` | ~242 |
| bootstrap | ~42 |
| `import transcriptx.web.blocks` | **~1704** |
| `navigate_to_segment` (pulls transcript page) | ~9 |
| corrections_studio | ~70 |
| **Full `import transcriptx.web.app`** | **~2116** |

`app.py` eagerly imports corrections_studio, `transcriptx.web.blocks` (registers overview/insights/charts/data implementations), and `navigate_to_segment` before any page navigation — so router lazy-loading cannot hide the blocks graph on cold start.

### 3.3 Live Streamlit smoke

- Health endpoint healthy in **~2 s** after process start.
- This is **not** a substitute for the envelope’s “Home interactive under ~30 s” browser clock; full first-paint interactivity was not browser-timed in this run.

### 3.4 Hotspot microbench

| Probe | Result |
|-------|--------|
| `_deep_test_large_norm.json` segments | **1007** |
| `filtered_display_segments` (no unnamed filter) | median **~0.07 ms** (CPU filter is cheap) |
| Display cap / virtualization | **none** — all kept segments are eligible for the widget tree |
| Speaker ID contrast | `_LINES_PER_PAGE = 10` progressive window |
| Plotly `include_plotlyjs=True` tiny bar chart | **~4.86 MB** HTML |
| Same figure `include_plotlyjs='cdn'` | **~7.6 KB** |
| Same figure `include_plotlyjs=False` | **~7.4 KB** |
| Installed `plotly.min.js` | **4 851 164** bytes |
| `@st.fragment` decorators under `web/` | **27** across 18 files (Speakers alone: 10) |

---

## 4. Findings

Severity: **blocker** · **must-fix** · **known-limitation** · **observe**  
Class: **startup** · **navigation/rerun** · **scale** · **interaction** · **asset**

### F1. Dynamic charts embed full Plotly.js per HTML artifact — must-fix (asset, scale)

`src/transcriptx/core/viz/charts.py` writes HTML with `include_plotlyjs=True`, `full_html=True`. Each chart carries ~4.85 MB of JS. Charts gallery iframes content when `size ≤ MAX_INLINE_HTML_BYTES` (5 MiB) and fullscreen up to 10 MiB (`artifact_service.py`, `page_modules/charts.py`). Opening several charts multiplies payload/memory.

### F2. `load_html_artifact` reads full HTML before UI size gating — must-fix (scale, asset)

`ArtifactService.load_html_artifact` stats then `read_text`s the entire file; Charts decides iframe eligibility afterward. Oversized artifacts still allocate in the Streamlit process.

### F3. Transcript viewer: no display cap / no virtualization — must-fix (scale, interaction)

`filtered_display_segments` returns all kept segments. `segments.py` emits per-segment markdown / columns / ▶ / correction UI. Compact text-only path can collapse to one markdown block per turn (healthy); playback/corrections disable that. A 1007-segment corpus can therefore mount thousands of Streamlit nodes on fragment rerun. Speaker ID already pages at 10 lines — Transcript does not.

### F4. Cold ▶ blocks on synchronous ffmpeg / Future join — must-fix / known-limitation (interaction)

Documented in `playback_panel.py`: cold `get_clip_bytes()` waits for warm job or sync generate (timeouts up to 30 s in clip service). Transcript warm defaults to `_WARM_WINDOW = 3` when `visible_count` is omitted, so many ▶ buttons stay cold. CCv2 Speakers ID path is non-blocking (cache + enqueue) but **flag-default off** (`workspaces/flags.py`).

### F5. Eager imports defeat lazy routing on cold start — must-fix (startup)

Measured ~1.7 s for `web.blocks` alone inside ~2.1 s total app import. Router lazy `import_module` for pages cannot offset module-level imports in `app.py`.

### F6. Search debounce uses `time.sleep` on the Streamlit worker — must-fix (interaction)

`page_modules/search.py` sleeps remaining debounce then `st.rerun()` inside a fragment — blocks the script runner (~≤300 ms) on that path. Result cap at 200 is otherwise healthy.

### F7. Global CSS/JS reinjected every full-app rerun — observe → must-fix if full reruns stay common (navigation/rerun, asset)

`shell.inject_global_styles()` (~34 KB `shell.py`, large inline `<style>`/`<script>`) runs every `main()` after the epoch gate. Pure fragment reruns avoid it; navigation/commits pay it.

### F8. Sidebar brand logo re-read + base64 each sidebar paint — observe (asset, navigation/rerun)

Dark logo ≈158 KB → ~210 KB data-URL markdown per full sidebar render.

### F9. Library paints full dataframe (no paging) — known-limitation (scale)

Light metadata discovery first (good). Envelope large-library UI soak **pass** at 200+ (2026-08-07). Watch multi-thousand libraries; Corrections Studio already pages at 50.

### F10. Session / speaker discovery can walk many manifests/JSON on cache miss — observe (scale)

TTL-cached (120 s). First Charts/Speakers visit after miss can stall on disk-wide reads; Home correctly skips hydration.

### F11. CCv2 Speaker ID default-off — known-limitation (interaction)

Intentional Phase gate. Legacy workspace nests playback body in one fragment and inherits F4.

### F12. Envelope / test gaps for GUI capacity — observe (process)

Covered well: Home hydration skip, Recent Runs expensive-call boundary, clip warm/backpressure, nested-fragment guard, CCv2 non-blocking contracts.  
Missing: transcript display-cap contract; Plotly include / read-before-cap; shell inject-once; search sleep avoidance; logo caching; FPS/jank CI.

---

## 5. Envelope reconcile

| Envelope row | Status this review |
|--------------|--------------------|
| Cold Home interactive ~30 s | **Partial.** Server health ~2 s; cold app import ~2.1 s. Full browser “interactive Home” clock **not re-measured**. Prior host-bound known-limitation still applies. |
| UI responsiveness @ 200+ library | **Not re-measured** (no 200+ managed corpus here). Prior **pass** 2026-08-07 stands. Static Library pattern still O(N) dataframe. |
| Analysis preset / LLM walls | Out of scope (separate track). |

---

## 6. Already healthy (non-findings)

- Lazy page renderers in `router.py`
- Deferred workspace hydration for Home (`page_requires_workspace_hydration`)
- Listing cache tiers in `cache_helpers.py`
- Broad `@st.fragment` coverage (27 real decorators)
- Corrections paging (50); Search hard cap (200); Speaker ID progressive lines (10)
- Clip warm backpressure (`_MAX_INFLIGHT = 8`, worker pool)
- CCv2 local playhead / sparse `setStateValue` design (when enabled)
- HTML iframe size policy (5 MiB / 10 MiB) — policy exists; see F1/F2 for holes
- Streamlit UI load JSONL + scenario/report scripts are usable once the data root is epoch-compatible

---

## 7. Ranked recommendations

1. **F1/F2 — Charts payload:** Prefer shared/CDN/once Plotly JS; gate on `stat().st_size` (or streaming) **before** `read_text`; consider thumbnail-only gallery until open.
2. **F3 — Transcript windowing:** Add a display window / virtualization parity with Speaker ID’s progressive lines; keep jump-to-segment able to bring target into window.
3. **F4/warm window — Playback:** Non-blocking play UX on legacy path (spinner + enqueue); pass `visible_count` from Transcript; keep CCv2 enablement as the Speakers ID escape hatch.
4. **F5 — Cold import:** Defer `web.blocks` registration and Corrections/transcript navigation imports until first need.
5. **F6 — Search debounce:** Replace `time.sleep` with timer/fragment pattern that does not block the worker.
6. **F7/F8 — Shell:** Inject-once / session-cached logo data-URL for full-app reruns.
7. **Process:** Extend scenario capture to Transcript (large segments) and Charts-with-artifacts; add contract tests for display cap and `include_plotlyjs` policy; document that capture requires an epoch-1 data root.

**This assessment does not implement the fixes** — measurement and ranking only.

---

## 8. Scratch artifacts (gitignored)

| Path | Contents |
|------|----------|
| `.local/perf_data/` | Epoch-1 review data root used for capture |
| `data/perf/*.jsonl` | Scenario JSONL (gitignored) |
| `.local/perf/streamlit_perf_report_compat_2026-08-11.md` | Report markdown copy |

---

## 9. Related docs

- [performance_envelopes_1_0.md](../../dev/performance_envelopes_1_0.md)
- [run_performance.md](../../dev/run_performance.md) (analysis-run, not GUI FPS)
- [theme_c_workspaces_ccv2.md](../../dev/theme_c_workspaces_ccv2.md)
- [web_fragment_pr_audit_table.md](web_fragment_pr_audit_table.md) (archived fragment audit)
- [streamlit_ui_test_assessment_2026-07-18.md](streamlit_ui_test_assessment_2026-07-18.md) (GUI test strategy)
