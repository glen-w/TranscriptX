Type: ARCHITECTURE
Authority: ARCHITECTURE.md

# Composition platform

TranscriptX viewing pages are composed from **blocks** (reusable render units) and **layout profiles** (YAML ordering of block placements).

## Tracks

1. **Composition core** — `web/blocks/`, `web/layouts/`, Dashboard Builder
2. **Ship-to-user (Track B)** — navigation clusters, layout picker, module metrics, deep links, shared Charts/Data filters
3. **Run bundles** — gated; not part of composition core

## Track B (ship notes)

- **Sidebar**: View section uses static Read / Summarise / Explore headers; **Statistics** lives under View; workspace pickers hydrate only from `PageSpec.required_context`.
- **Layout picker**: Overview and Insights expose `default` and `executive` layouts; `developer_debug` requires `show_debug_layouts` in session.
- **Module metrics**: `module_metrics` block uses `SummaryService` for the sidebar-selected analysis module.
- **Deep links** (``transcriptx.web.navigation``):
  - `navigate_to_charts(module=…)` → `page=Charts`, `filter_module`
  - `navigate_to_data_artifact(artifact_id=…)` → `page=Data`, `data_artifact_preset`
  - Highlights → Transcript via `navigate_highlight_to_transcript` / `navigate_to_segment`
- **Internal**: `SubviewSliceFilter` (`web/blocks/filters/subview_slice.py`), `ExportService` facade, Charts/Data block IDs registered for future layout pages.

## Reuse-first rule

Wrap existing services (`ArtifactService`, `ProfileController`, export helpers). Build in-house abstractions only for TranscriptX-specific composition: `BlockSpec`, `BlockPlacement`, `LayoutSpec`, `LayoutProfileStore`.

## Key paths

- Blocks: `src/transcriptx/web/blocks/`
- Layouts: `src/transcriptx/web/layouts/presets/`
- Dashboard Builder: `src/transcriptx/web/page_modules/dashboard_builder.py`

See [web_blocks.md](web_blocks.md) for how to add a block or layout.
