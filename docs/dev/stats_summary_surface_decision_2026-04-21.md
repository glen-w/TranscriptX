Type: DECISION
Authority: maintainer

# Stats Summary Surface Decision (PR0)

Decision scope: `/src/transcriptx/core/analysis/stats/summary.py`

| function | classification | evidence | action |
|---|---|---|---|
| `create_comprehensive_summary` | active | No supported runtime call sites found, but explicitly designated as supported plain-text summary helper in this decision for maintained use; imports cleanly and executes with minimal fixture data. | Retain and refactor for maintainability with output stability constraints. |
| `generate_summary_stats` | dead | No observed supported internal `src` call sites, no supported docs contract, and minimal execution fails (`NameError: compute_speaker_stats` unresolved in module). | Remove from supported surface (delete implementation). |
| `generate_enhanced_html_summary` | compatibility-only | No observed supported internal `src` call sites and no supported docs contract, but function still executes and can be used for manual/legacy export workflows. | Retain temporarily with explicit deprecation warning and migration guidance to `report.json`/`report.md`/`report.txt`. |
| `create_enhanced_html_content` | compatibility-only | Internal helper for `generate_enhanced_html_summary`; no direct supported call sites, but required while compatibility export path is retained. | Keep internal helper only for compatibility path; avoid deep refactor. |

Classification criteria used:

- active = called from supported `src` runtime paths or explicitly documented as supported.
- compatibility-only = not used in current runtime, but retained for external/manual usage or short-term migration.
- dead = no supported call sites, no supported docs contract, no intended migration role.
