Type: ARCHITECTURE
Authority: ARCHITECTURE.md

# Composition platform

TranscriptX viewing pages are composed from **blocks** (reusable render units) and **layout profiles** (YAML ordering of block placements).

## Viewing IA

Transcript → Overview → Insights → Charts → Artifacts

- **Overview / Insights** use the active layout profile (default id `default`, display title **Standard**). Ordinary pages do **not** show a layout picker.
- **Insights** uses conditional section navigation (`insights_section`), not `st.tabs`.
- **Artifacts** merges former Data, File List, and Overview Export (`Browse | Preview | Export` via `artifacts_section`).
- Legacy `Data` / `Explorer` page keys were removed in **0.9.7** (use Artifacts Preview / Browse). `Statistics` still migrates to Home; `Batch Ops` remains a router-owned redirect to Run Analysis (Batch).

## Layout profiles

- Built-in presets (`default`, `executive`, `developer_debug`, `all`) are **immutable**.
  - `all` is generated from the block registry (every block, alphabetical) — not a YAML preset.
- Dashboard Builder can **Save as custom layout** under `data/profiles/ui_layouts/`.
- Schema version **2** adds optional placement `section` for Insights local navigation; v1 layouts still load.

## Deep links

- `navigate_to_charts(module=…)` → `page=Charts`, `filter_module`
- `navigate_to_data_artifact(artifact_id=…)` → `page=Artifacts`, Preview section, one-shot preset
- Highlights → Transcript via `navigate_highlight_to_transcript` / `navigate_to_segment`

## Module presentation order

Single source: `web/module_ui_groups.py` (Summary & Synthesis first). Artifact Browse also uses role ranks via `web/services/artifact_index.py`.

## Key paths

- Blocks: `src/transcriptx/web/blocks/`
- Layouts: `src/transcriptx/web/layouts/presets/`
- Dashboard Builder: `src/transcriptx/web/page_modules/dashboard_builder.py`
- Artifact index: `src/transcriptx/web/services/artifact_index.py`

See [web_blocks.md](web_blocks.md) for how to add a block or layout.
