Type: GUIDE
Authority: tests/README.md

# GUI acceptance — residual manual checklist

**Purpose:** Behaviours the Streamlit AppTest lane (`make test-gui-acceptance`) cannot credibly validate.  
**Not a dumping ground:** only AppTest-blind items. Navigation, validation text, stubbed service success/error, and library/group/profile persistence are covered by AppTest.

**Automated lane:** `make test-gui-acceptance` (marker `gui_acceptance`, also selected by `make test-heavy`).  
**Policy:** No Playwright for the Streamlit GUI before 1.0; reconsider post-1.0 if this list stays release-critical or repeatedly catches regressions.

---

## How to run

1. Start the GUI (`make run` or local `streamlit run src/transcriptx/web/app.py`) against a disposable data dir when practical.
2. Walk each item below; record `pass` / `fail` / `skip` (with reason) in the release-evidence notes.
3. Prefer skipping with reason over a silent pass when the environment cannot exercise the item (e.g. no OS file picker in headless CI).

---

## Checklist (AppTest-blind only)

| # | Item | Pass criteria |
|---|------|----------------|
| R1 | **Import file picker** | OS / Streamlit uploader chooses a real file; admit succeeds; Library shows the new transcript |
| R2 | **Export browser download** | Create Export → browser download / save dialog yields a usable zip (not only in-app download widget presence) |
| R3 | **Export open-on-disk / `file://`** (if offered) | Opening the zip or index from the UI lands in the expected viewer without a broken path |
| R4 | **Hover / focus reveal** | Sidebar / context-bar / action-menu hover or focus reveals match the intended labels (no clipped tooltips) |
| R5 | **Popovers / expanders visual** | Critical expanders (e.g. Aggregation notices, Full log) open and content is readable without layout collapse |
| R6 | **Visual alignment** | Overview / Insights / Charts first paint: title, description, and primary content align; no overlapping widgets on desktop width |
| R7 | **Weak Streamlit hooks** | Any control discovered during AppTest work that cannot be driven via AppTest (document the widget + page here when added) |

**Current R7 entries:** none beyond R1–R6. Add rows when AppTest hits a hard stop on a release-critical control.

---

## Explicitly out of scope here

- Full visual regression / accessibility snapshots
- Real ML / Ollama / heavy model runs (core/integration lanes)
- Playwright / Selenium GUI automation (deferred until post-1.0 reconsideration)
- Anything already asserted by `tests/web/gui_acceptance/`
