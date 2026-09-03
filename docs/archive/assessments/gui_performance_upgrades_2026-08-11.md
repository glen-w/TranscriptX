> **Archived / superseded.** Historical context only. Current authority: [performance_envelopes_1_0.md](../../dev/performance_envelopes_1_0.md). Do not treat as live roadmap or support policy.

> Follow-up to the GUI performance review. Live envelopes: [performance_envelopes_1_0.md](../../dev/performance_envelopes_1_0.md).

# GUI performance upgrades (top 4)

**Date:** 2026-08-11  
**Branch / PR:** `cursor/gui-perf-upgrades-248d`

Implements the top four recommendations from the Streamlit GUI performance assessment:

| ID | Change |
|----|--------|
| F1/F2 | Charts gallery no longer auto-iframes dynamic Plotly HTML; `load_html_artifact(..., max_read_bytes=)` stats before read |
| F3 | Transcript progressive window (50 segments + Show more); jump expands window; warm uses `visible_count` |
| F4 | `render_active_clip` + karaoke clip path use cache-or-enqueue (no sync `get_clip_bytes` on the Streamlit path) |
| F5 | App cold import no longer pulls `web.blocks` implementations, Corrections Studio, or Transcript page module |

Deferred (not in this change): Search debounce without `time.sleep`, shell inject-once / logo cache, Plotly shared-JS viewer, CCv2 default-on, extended perf scenario capture.
