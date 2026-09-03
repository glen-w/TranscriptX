# Composition platform

TranscriptX viewing pages are composed from **blocks** (reusable render units) and **layout profiles** (YAML ordering of block placements).

## Viewing IA

Transcript → Overview → Insights → Charts → Artifacts

- **Overview / Insights** use the active layout profile (default id `default`, display title **Standard**). Ordinary pages do **not** show a layout picker.
- **Insights** uses conditional section navigation (`insights_section`), not `st.tabs`.
- **Artifacts** merges former Data, File List, and Overview Export (`Browse | Preview | Export` via `artifacts_section`).
- Legacy `Data` / `Explorer` page keys were removed in **0.9.7** (use Artifacts Preview / Browse). `Statistics` still migrates to Home; `Batch Ops` remains a router-owned redirect to Run Analysis (Batch).

## Layout profiles

Public layout envelope is **schema_version 1** only (`CURRENT_LAYOUT_SCHEMA_VERSION = 1`). Placement `section` is optional on v1 and drives Insights local navigation (`summary` | `speakers` | `actions` | `highlights`).

Built-in presets are **immutable**:

| Id | Title | Role |
|----|-------|------|
| `default` | Standard | Curated everyday Overview + sectioned Insights |
| `executive` | Executive | Metrics / health / export Overview; summary + actions + highlights |
| `meeting_followup` | Meeting follow-up | Extracts, commitments, and highlights first |
| `speaker_focus` | Speakers | Speaker cards + linguistic Insights |
| `minimal` | Minimal | Fast scan: hero, glance, quiet status |
| `developer_debug` | Developer debug | Inspection layout (shown after visiting Dashboard Builder) |
| `all` | All | Generated from the block registry (every block, alphabetical) — not a YAML file |

Dashboard Builder **Edit** mode reorders Overview/Insights blocks (↑↓); **Save as custom** / delete live under `{config_dir}/profiles/ui_layouts/` (`PROFILES_DIR/ui_layouts`). Builder does **not** select Charts overview charts (`dashboard.overview_charts` — Settings → Configuration). See [dashboard_builder.md](dashboard_builder.md).

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

See [web_blocks.md](web_blocks.md) for how to add a block or layout, and [dashboard_builder.md](dashboard_builder.md) for Builder workflows.
