Type: GUIDE
Authority: tests/README.md

# GUI acceptance — residual manual checklist

**Purpose:** Behaviours the Streamlit AppTest lane (`make test-gui-acceptance`) cannot credibly validate.  
**Not a dumping ground:** only AppTest-blind items. Navigation, validation text, stubbed service success/error, and library/group/profile persistence are covered by AppTest.

**Automated lane:** `make test-gui-acceptance` (marker `gui_acceptance`, also selected by `make test-heavy`).  
**Browser E2E lane:** Playwright live-Streamlit under `tests/e2e_gui/` (marker `gui_e2e`) — runnable via `make test-gui-e2e`. Covers the ten documented key flows ([docs/workflows/](../workflows/index.md)): import/analyse, speaker identification, investigate, local-AI surface, export, Charts, Groups, Corrections (Correct mode), Rename Transcript, Speakers. AppTest remains the structural acceptance suite; Playwright covers AppTest-blind browser behaviour (e.g. real file uploader, export download UI, Correct-mode propose).  
**Policy:** Playwright GUI E2E is a first-class automated lane (not deferred / not banned). Theme C CCv2 browser checks remain under `make test-theme-c-browser`.

---

## How to run

1. Start the GUI (`make run` or local `streamlit run src/transcriptx/web/app.py`) against a disposable data dir when practical.
2. Walk each item below; record `pass` / `fail` / `skip` (with reason) in the release-evidence notes.
3. Prefer skipping with reason over a silent pass when the environment cannot exercise the item (e.g. no OS file picker in headless CI).

---

## Checklist (AppTest-blind only)

| # | Item | Pass criteria |
|---|------|----------------|
| R1 | **Import file picker** | OS / Streamlit uploader chooses a real file; admit succeeds; Library shows the new transcript. Covered by Playwright `test_first_analysis_import_run_overview`. |
| R2 | **Export browser download** | Create Export → browser download / save dialog yields a usable zip (not only in-app download widget presence). Partially covered by Playwright `test_export_results` (Create Export / Download Export UI); OS save dialog remains manual when present. |
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
- OS-native file-save dialogs beyond in-app Download Export (see R2)
- Anything already asserted by `tests/web/gui_acceptance/` or `tests/e2e_gui/`
