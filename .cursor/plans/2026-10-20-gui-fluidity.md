# GUI fluidity programme (2026-10-20)

Measured follow-on to [gui_performance_upgrades_2026-08-11](../../docs/archive/assessments/gui_performance_upgrades_2026-08-11.md). Goal: robustly cut full-app and first-paint cost without nested-fragment thrash or an SPA rewrite.

## Diagnosis (from codebase review)

Every non-fragment interaction re-runs the shell: ~35KB CSS + chrome JS, base64 logos (~350KB), N× `context_readiness` → `SubjectService.resolve_current_subject`, always-on workspace pickers. Settings/Tools `st.tabs` execute **all** panel bodies every visit. Search still blocks the worker with `time.sleep`. Library paints an unpaged dataframe. Speakers rebuilds aggregation snapshot every visit. Charts fullscreen still embeds Plotly JS per file. Aug 2026 fixes (gallery no auto-iframe, transcript window 50, non-blocking cold ▶, cold-import deferral) stay in place.

## Workstreams

| Wave | Scope | CCv2? |
|------|--------|-------|
| A | Shell tax (logo cache, CSS inject-once, readiness memo, config hydrate once) | No |
| B | Settings/Tools active-tab-only; Search non-blocking debounce | No |
| C | Library paging; Speakers snapshot cache; Artifacts fragment; Insights Full window | No |
| D | Charts shared Plotly.js for fullscreen | No |
| E | Measurement: extend `capture_streamlit_perf_scenarios` | No |
| F | New CCv2 **only** if Speakers appearances / Charts scrub still fail after A–D | Maybe `speakers_appearances_workspace` |

## Stop lines

- No SPA / Streamlit replacement (Theme I gate).
- No endless nested fragments for last flicker (ROADMAP Theme C).
- No manuscript editor CCv2.
- New CCv2 only with remount/bytes/focus evidence after classic fixes.

## CCv2 proposal (deferred — evidence gate)

Do **not** ship a new workspace until Waves A–D are measured on a large library.

| Candidate | Interaction | Why wait |
|-----------|-------------|---------|
| `speakers_appearances_workspace` | Per-appearance Open / Unlink / Accept / Relink trees | Classic Speakers now: snapshot cache + active detail tab only. Revisit if Appearances tab still remounts heavily. |
| Charts filter strip CCv2 | Pills + module/tag scrubbing | Gallery already fragment-scoped; measure before investing. |
| Speaker ID managed-identify chrome | Suggest-names selectbox beside CCv2 | Small win vs Speakers list. |

Escalate only with written remount/bytes/focus failure after classic fixes ([theme_c_invest_narrow_defer.md](../../docs/dev/theme_c_invest_narrow_defer.md)).

## Success signals

- Settings open paints one panel, not nine.
- Typing in Search does not sleep the Streamlit worker.
- Full-app nav no longer re-base64s logos or re-injects full CSS every time (session/process cache).
- Library / Insights Full stay bounded under large corpora.
- Perf scenarios cover Settings, Transcript, Speakers, Artifacts.
- New Plotly HTML defaults to CDN JS (`TX_PLOTLY_INCLUDE_JS=inline` for offline).
