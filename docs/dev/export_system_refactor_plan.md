<!-- Planning doc: review only. No implementation committed with this file. -->

# TranscriptX Export System — Incremental Refactor Plan

**Last reviewed:** 2026-07-14 (post 0.3.5 / 0.3.6). Core refactor steps 1–9 are **not started**.

## Status vs plan (changelog)

| Release | What changed for export | Plan impact |
|---|---|---|
| **0.3.5** | Added `utils/export_markdown.py`; expanded `export_index.py` with `_executive_summary_markdown` / `_action_items_markdown`, speaker-summary grouping in nav/body, MD→HTML via safe subset | Step 7 is more urgent (new parallel markdown builders). `export_markdown` is the right home for later `markdown_html.py` move. |
| **0.3.6** | Extracted `web/components/export_panel.py`; Artifacts page hosts export UI; Overview block delegates to shared panel; layout block id `export_panel`; `charts_export` imports `web.module_ui_groups.order_strings_like_modules` | Update entry-point map. Third `HARD_CAP_BYTES` copy in `export_panel.py`. Extra utils→web edge (module ordering). |

**Still true / unchanged:** `_ExportableItem` private cross-package use; `charts_export` imports `ArtifactService` + `HARD_CAP_BYTES` + chart view-model; no `transcriptx.export` package; LOC ~985 `export_index.py`, ~254 `charts_export.py`, ~179 `export_markdown.py`.

---

## 1. Current map (entry points → call graph)

### UI entry points

| Entry | File | Call |
|---|---|---|
| Home “export recent run” | `src/transcriptx/web/page_modules/home.py` | `ExportService.zip_artifacts` → `ArtifactService.zip_artifacts` |
| Shared export panel (Overview block) | `web/components/export_panel.py` via `blocks/implementations/overview.py` (`render_export_panel`) | `ExportService.zip_artifacts` |
| Shared export panel (Artifacts page) | `web/page_modules/artifacts.py` → `render_export_panel_ui` | same |
| Layout presets | `export_panel` block in `layouts/presets/{default,executive,developer_debug}.yaml` | same panel |
| Charts “Export Visible Charts” | `src/transcriptx/web/page_modules/charts.py` | `ExportService.zip_charts` → `prepare_charts_export_zip` |

`ExportService` (`web/services/export_service.py`) is a thin facade only. Selection UX lives in `export_panel.py` (`resolve_export_selection` is pure/testable).

### Data flow A — Overview / full-run ZIP

```
UI → ExportService.zip_artifacts
  → ArtifactService.zip_artifacts
       • _artifacts_for_export + HARD_CAP_BYTES (2GB)
       • stage copies under artifact.id[:16]/rel_path
       • ArtifactService._write_export_index
            → resolve_export_transcript_data / resolve_export_text_summaries / resolve_export_page_title
            → constructs private charts_export._ExportableItem
            → build_export_index_html
       • shutil.make_archive → Path to temp zip
  → ArtifactService.read_for_download → Streamlit download
```

### Data flow B — Charts-only ZIP

```
UI → ExportService.zip_charts
  → charts_export.prepare_charts_export_zip
       • imports ArtifactService + HARD_CAP_BYTES  ← utils → web inversion
       • imports resolve_chart_display_description from chart_view_model_service
       • _resolve_exportable → copy → generate_charts_index_html
       • returns ChartsExportResult(bytes, filename, counts)
```

### Internal dependency graph (problem edges bold)

```
export_index.py
  ├── charts_export (_EXPORT_INDEX_CSS, _ExportableItem, render_chart_sections)
  ├── export_markdown.summary_markdown_to_html
  ├── io.speaker_map_resolver
  └── utils.text_utils

charts_export.py
  ├── **web.models.artifact.Artifact**
  ├── **web.services.artifact_service (ArtifactService, HARD_CAP_BYTES)**
  ├── **web.services.chart_view_model_service**
  └── **web.module_ui_groups.order_strings_like_modules**  (added 0.3.6)

artifact_service.py
  ├── **charts_export._ExportableItem**  (private across packages)
  └── export_index (build_* / resolve_*)

export_panel.py
  └── **local HARD_CAP_BYTES duplicate** (same 2GB literal as artifact_service)

export_index also reimplements:
  • executive / action-items MD vs core render_summary_markdown / render_action_items_markdown
    (expanded in 0.3.5 — includes commitments/speaker-summary sectioning)
  • contiguous speaker grouping vs web/transcript_viewer/segments.py
  • HTML shell + omitted-charts banner (duplicated with generate_charts_index_html)
```

### Out of scope (do not fold in)

- `services/corrections_studio/export_service.py` — different product path
- `core/pipeline/module_specs/exports.py` — pipeline module registry, not ZIP/HTML export
- `utils/html_utils.py` — legacy analysis HTML reports (`create_html_report` / NER tooltips); only NER uses `wrap_tooltip_text` today
- `io/import_adapters/html_export/` — import of vendor HTML, not outbound export

### Existing tests (anchors for each step)

- `tests/utils/test_export_index.py` — resolution, render, `_write_export_index`, `zip_artifacts` + index.html
- `tests/utils/test_charts_export.py` — resolve, index HTML, zip, hard-cap, omitted counts
- `tests/utils/test_export_markdown.py` — safe MD→HTML

---

## 2. Target architecture

### Package boundary (end state)

Prefer a real package over growing `utils/`:

```
src/transcriptx/export/
  __init__.py          # public API only
  types.py             # ExportableItem, ChartsExportResult, ExportTextSummary, HARD_CAP_BYTES
  zipping.py           # staging, hard-cap check, make_archive helpers
  html_shell.py        # EXPORT_INDEX_CSS, wrap_export_html(), omitted_charts_banner()
  markdown_html.py     # summary_markdown_to_html (move)
  charts.py            # render_chart_sections, build_charts_index_html, prepare_charts_zip
  index.py             # resolve_* + build_export_index_html (split later if still large)
  transcript_html.py   # grouping + render_transcript_section
  summary_bodies.py    # JSON→markdown adapters calling core renderers where possible
```

Web stays orchestration-only:

```
web/services/export_service.py          # only UI-facing facade
web/services/artifact_service.py        # list/resolve/read; zip delegates staging+index to export/
web/components/export_panel.py          # selection UX + download (imports HARD_CAP from export/)
web/page_modules/{home,charts,artifacts}.py
web/blocks/implementations/overview.py  # thin wrapper → export_panel
```

### Public types (no more `_ExportableItem` across packages)

| Type | Role |
|---|---|
| `ExportableItem` | artifact + source_path + export_rel_path + size_bytes |
| `ChartsExportResult` | zip bytes + filename + counts (unchanged contract for Streamlit) |
| `ExportTextSummary` | TypedDict already in export_index — keep public |
| `HARD_CAP_BYTES` | **one** definition in `export/types.py` (or `export/zipping.py`); `artifact_service`, `charts_export`, and `export_panel` all import it |

`Artifact` can remain in `web.models` for early PRs (pure dataclass). Longer-term optional: Protocol/`ChartExportView` with only fields charts need (`id`, `kind`, `module`, `rel_path`, `title`, `tags`, `storage_root`, `meta`) so chart HTML rendering does not import Streamlit-adjacent services.

### Shared helpers

1. **HTML shell** — one CSS string + `wrap_export_page(title, nav_html, content_html)` + `omitted_charts_banner(n)`
2. **Zip/staging** — one hard-cap check + copy-to-staging + `make_archive` used by both artifact and charts paths
3. **Chart descriptions** — inject callable / thin adapter so `export/charts.py` does not import `chart_view_model_service` (web passes `resolve_chart_display_description` or a precomputed `description` field on `ExportableItem`)
4. **Module ordering** — inject `order_modules` callable (or pre-sorted module ids) so charts export does not import `web.module_ui_groups`
5. **Summary bodies** — prefer core `render_*_markdown` with an export-oriented strip/adapter; keep fallbacks for legacy shapes (speaker-summary grouping stays in export)
6. **Speaker grouping** — one pure function over `list[dict]` (export signature); transcript viewer adapts its `(idx, seg)` list to that

### Naming convention (adopt going forward)

| Verb | Meaning |
|---|---|
| `resolve_*` | locate/normalize inputs from disk/staging |
| `render_*` | produce HTML/markdown fragments |
| `build_*` | assemble a full page/document |
| `prepare_*_zip` / `zip_*` | staging + archive (facade may keep `zip_*` for UI) |

Avoid adding new `generate_*` for the same job as `build_*`.

---

## 3–5. Ordered shippable steps

### Step 0 — Baseline freeze (docs-only / test inventory)

| | |
|---|---|
| **Goal** | Confirm green tests and list public vs private symbols before moves |
| **Files** | none (or a short comment in PR description) |
| **Risk** | low |
| **Test** | `pytest tests/utils/test_export_index.py tests/utils/test_charts_export.py tests/utils/test_export_markdown.py` |
| **Rollback** | n/a |

---

### Step 1 — Promote public types; stop cross-package private imports

| | |
|---|---|
| **Goal** | Rename `_ExportableItem` → `ExportableItem`; export `_EXPORT_INDEX_CSS` as `EXPORT_INDEX_CSS` (or keep private but stop importing underscore names from `artifact_service` / tests). Update `artifact_service._write_export_index` and tests to use public names. |
| **Files** | `utils/charts_export.py`, `utils/export_index.py`, `web/services/artifact_service.py`, `tests/utils/test_*.py` |
| **Risk** | low |
| **Test** | existing utils export tests; grep for `_ExportableItem` / `_EXPORT_INDEX_CSS` outside charts_export |
| **Rollback** | revert single PR; no behavior change |

---

### Step 2 — Break utils → web inversion (hard-cap + path resolve + module order)

| | |
|---|---|
| **Goal** | Move `HARD_CAP_BYTES` to a neutral module (`utils/export_constants.py` or early `export/types.py`) and **delete the duplicate** in `export_panel.py`. Have `charts_export` accept a path-resolver callable (default: `ArtifactService.resolve_artifact_source_path` injected from `ExportService` / web) and an optional module-order callable (default injected from `order_strings_like_modules`). Charts zip no longer imports `ArtifactService` / `module_ui_groups` at module top-level. |
| **Files** | `charts_export.py`, `export_service.py`, `artifact_service.py`, `export_panel.py`, tests |
| **Risk** | med (wire-up mistakes break charts export / hard-cap / module sort order) |
| **Test** | `test_charts_export.py` hard-cap + omitted + module order; smoke `ExportService.zip_charts`; Overview + Artifacts panel zip still works |
| **Rollback** | restore imports; keep constant duplicated briefly if needed |

---

### Step 3 — Deduplicate HTML shell + omitted banner

| | |
|---|---|
| **Goal** | Extract shared CSS + `omitted_charts_banner` + page wrapper used by `generate_charts_index_html` and `build_export_index_html`. |
| **Files** | new `utils/export_html_shell.py` (or `export/html_shell.py`), `charts_export.py`, `export_index.py`, tests asserting banner/CSS once |
| **Risk** | low–med (HTML string diffs; golden assertions may need update) |
| **Test** | charts + export_index HTML tests; assert single banner wording; visual spot-check one zip over `file://` |
| **Rollback** | inline restore in both callers |

---

### Step 4 — Shared zip/staging helper

| | |
|---|---|
| **Goal** | One helper: validate cap → copy items to staging → optional `write_index(staging)` → archive. Align charts path (returns bytes) and artifacts path (returns Path) on the same primitive. |
| **Files** | new helper module, `artifact_service.zip_artifacts`, `prepare_charts_export_zip`, tests |
| **Risk** | med (temp-dir lifetime, Path vs bytes API) |
| **Test** | `test_zip_artifacts_includes_index_html`; charts zip round-trip; ensure no staging leaks (tmp cleanup) |
| **Rollback** | keep helper but call old paths via thin wrappers |

---

### Step 5 — Inject chart description; drop chart_view_model import from utils

| | |
|---|---|
| **Goal** | Add optional `description: str | None` on `ExportableItem`, or pass `description_fn` into `render_chart_sections`. Web fills descriptions before calling export. |
| **Files** | `charts_export.py`, `artifact_service._write_export_index`, `export_service` / charts page path, tests |
| **Risk** | low |
| **Test** | charts export HTML still includes description when meta present; unit test with stub description_fn |
| **Rollback** | re-import resolve function temporarily |

---

### Step 6 — Speaker grouping shared with transcript viewer

| | |
|---|---|
| **Goal** | Extract pure `group_contiguous_segments_by_speaker(segments: list[dict])` to a shared non-Streamlit module (e.g. `web/transcript_viewer/grouping.py` or `export/transcript_html.py` + viewer import). Delete duplicate in `export_index`. Viewer wraps indexed tuples. |
| **Files** | `export_index.py`, `web/transcript_viewer/segments.py`, small unit tests |
| **Risk** | low–med (viewer display regressions) |
| **Test** | export transcript section tests; add/adjust viewer unit test if present; manual transcript page smoke |
| **Rollback** | keep thin wrappers calling old local copies |

---

### Step 7 — Align summary/action-item markdown with core renderers

| | |
|---|---|
| **Goal** | Replace `_action_items_markdown` / `_executive_summary_markdown` (added/expanded in 0.3.5) with adapters over `render_action_items_markdown` / `render_summary_markdown` **without** dumping provenance/intensity chrome into the export HTML unless desired. Prefer: call core → strip leading `# Title` / provenance footer for export display, OR add `include_meta: bool = True` to core renderers (small, explicit API). Keep legacy payload fallbacks and **speaker-summary section grouping** from 0.3.5. Continue routing bodies through `export_markdown.summary_markdown_to_html`. |
| **Files** | `export_index.py` (summary_bodies), possibly `core/analysis/summary/__init__.py`, `core/analysis/llm_support/action_items_render.py`, `test_export_index.py` |
| **Risk** | med (export HTML content changes; emoji/provenance differences; commitments shape) |
| **Test** | action-items / executive / speaker-summary fixtures in `test_export_index.py`; golden body snippets; ensure `.md` sidecars still preferred over JSON when present |
| **Rollback** | feature-flag or keep old private renderers behind fallback |

---

### Step 8 — Split `export_index.py` by responsibility (no behavior change)

| | |
|---|---|
| **Goal** | Mechanical split of ~987 LOC: resolve/transcript/summaries/render/build. Public functions keep same names via re-exports. |
| **Files** | `export_index.py` → multiple modules + `__init__` re-exports; tests import paths may stay stable |
| **Risk** | low if re-exports preserved; med if import paths change without shims |
| **Test** | full `test_export_index.py`; no assertion changes expected |
| **Rollback** | reassemble file; keep shims one release |

---

### Step 9 — Move into `transcriptx.export` package + deprecate `utils/export_*`

| | |
|---|---|
| **Goal** | Physical package move; `utils/export_index.py` etc. become thin re-export shims for one release. Update web imports to `transcriptx.export`. |
| **Files** | new package tree, shims, web services, tests paths |
| **Risk** | med (import churn) |
| **Test** | full utils export suite + any web tests; grep old import sites |
| **Rollback** | shims keep old paths working |

---

### Step 10 (optional, later) — Jinja2 templates for shells only

| | |
|---|---|
| **Goal** | Replace string-concat page shells with Jinja2 templates (already in lockfile). Keep fragment renderers in Python. Do **not** require markdown-it-py unless exporting richer MD and escaping is proven equivalent. |
| **Files** | `export/templates/*.html.j2`, `html_shell.py` |
| **Risk** | med |
| **Test** | HTML structure tests; escape regression tests |
| **Rollback** | keep string builder behind flag |

---

## 6. What NOT to do

- **Do not** add WeasyPrint / PDF / Playwright print pipelines for this refactor.
- **Do not** merge legacy `utils/html_utils.py` reporters into the Overview/charts export package in the same PRs.
- **Do not** add `pathvalidate` / `nh3` unless a concrete path-injection or XSS gap is demonstrated; current approach is `html.escape` + safe MD subset.
- **Do not** rewrite `export_index.py` in one PR (resolve + render + MD + speaker map together).
- **Do not** move `Artifact` out of `web.models` as a prerequisite; invert dependencies first.
- **Do not** change Corrections Studio export or pipeline `module_specs/exports.py` under this banner.
- **Do not** replace custom `summary_markdown_to_html` with markdown-it-py until escape/safety parity is proven (underscore emphasis vs run IDs is intentional).
- **Do not** blindly call core `render_summary_markdown` without stripping/meta flags — it adds intensity lines, emoji flags, and provenance footers that will change export UX.

---

## 7. Suggested PR sequence & effort

| PR | Steps | Effort | Notes |
|---|---|---|---|
| **PR1** | 1 | 0.5–1 d | Public types only; unlocks clean follow-ups |
| **PR2** | 2 | 1–2 d | Dependency inversion; highest leverage |
| **PR3** | 3 | 0.5–1 d | Shell/banner dedupe |
| **PR4** | 4 | 1–2 d | Shared zip/staging |
| **PR5** | 5 | 0.5 d | Description injection |
| **PR6** | 6 | 0.5–1 d | Speaker grouping |
| **PR7** | 7 | 1–2 d | Core markdown alignment; review HTML carefully |
| **PR8** | 8 | 1 d | Split file; behavior-neutral |
| **PR9** | 9 | 1 d | Package move + shims |
| **PR10** | 10 | optional 1–2 d | Jinja2 shells only if string concat remains painful |

**Total realistic:** ~1.5–2 weeks calendar for PR1–9 at part-time review pace; PR1–5 alone remove the worst architectural smell.

### Success criteria

- No `transcriptx.utils.*` module imports `transcriptx.web.services.*` or `transcriptx.web.module_ui_groups`
- No private `_`-prefixed export types imported outside their defining module
- One HTML shell + one omitted-banner implementation
- One hard-cap constant (shared by artifact zip, charts zip, and export panel)
- Overview / Artifacts ZIP and charts ZIP share staging/archive primitives
- Existing three test modules stay green with only intentional assertion updates in PR7

### Manual QA checklist (once per PR that touches HTML/zip)

1. Overview export panel with transcript + summary + charts → open `index.html` via `file://`
2. Artifacts page export panel (All / Module / Charts Only / Custom)
3. Charts-only export with static + dynamic charts (module order matches UI grouping)
4. Hard-cap / large selection messaging still correct in export panel
5. Omitted chart notice when a chart file is missing
6. Speaker summaries appear under their own nav/section when present
