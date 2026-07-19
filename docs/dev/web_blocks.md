Type: ARCHITECTURE
Authority: ARCHITECTURE.md

# Web blocks

## BlockSpec

Registered in `web/blocks/registry.py`. Each block has `id`, `group`, `description`, optional `module_deps` / `artifact_patterns`, and a `render(ctx, placement)` function.

## BlockPlacement

Layout YAML uses `placement_id` (unique instance) and `block_id` (reusable type).

## Adding a block

1. Implement `render_*` in `web/blocks/implementations/` — adapt an existing page renderer; do not duplicate `ArtifactService` logic.
2. Register in `web/blocks/builtin.py`.
3. Add placement to a curated preset under `web/layouts/presets/` (the built-in `all` layout picks up new blocks automatically).
4. Add a smoke test under `tests/web/blocks/`.

## Insights blocks for new analysis modules

| Block id | Module | Layouts |
|----------|--------|---------|
| `llm_summary_block` | `llm_summary` / `narrative_summary` (parametric) | `default` |
| `llm_speaker_summary_block` | `llm_speaker_summary` (group runs: synthesised index via resolver) | `default` |
| `llm_action_items_block` | `llm_action_items` | `default`, `executive` |
| `lexical_diversity_block` | `lexical_diversity` | `default` |
| `insights_contract` | `insights` | `default` |
| `highlights` | `highlights` | `default`, `executive` |
| `executive_summary` / `commitments_table` | `summary` | `default`, `executive` |

### Group runs (dual presentation)

Group analysis already executes selected modules on **each member** transcript, then finalizes aggregates. Insights/Overview blocks must not assume only single-transcript stems under the group run root.

Shared helpers: [`web/blocks/group_content.py`](../../src/transcriptx/web/blocks/group_content.py). Loader: [`ArtifactContentLoader`](../../src/transcriptx/web/blocks/loader.py) resolves via `storage_root` (member run dirs).

On **group** runs, content blocks show:

1. **Group rollup** — aggregate `*_rows.json` / blobs / [group LLM synthesis](../groups/group_llm_synthesis_contract.md)
2. **Per session** — session picker loads that member’s single-transcript contract (`_insights.json`, `_highlights.json`, etc.)

| Surface | Group rollup source | Per-session source |
|---------|---------------------|--------------------|
| Highlights | `highlights/highlight_rows.json` | member `_highlights.json` |
| Insights contract | `insights/insight_rows.json` | member `_insights.json` |
| Action items | `llm_action_items/action_item_rows.json` | member `_llm_action_items.json` |
| Executive summary / commitments | blob `summary/summary.json` | member `_summary.json` |
| LLM summary (block) | synthesis / collect blob | member `_llm_summary` |
| LLM speaker summaries | synthesis index | member speaker index + files |
| Lexical diversity | `session_rows` / `speaker_rows` | member `_lexical_diversity.json` |

`transcript_summary_hero` / `resolve_primary_summary` still prefer committed cross-session synthesis as the **primary** prose hero (no member `_llm_summary` primary fallback). Member summaries remain available under Per session on Insights LLM blocks.

Overview **module metrics** use summary extractors under `web/summary_extractors/`. Zip export summaries for LLM prose/list modules are resolved in `transcriptx.export.resolve`.

## Adding a layout

1. Copy `presets/default.yaml` to `data/profiles/ui_layouts/my_layout.yaml` (or add a new preset).
2. Validate via Dashboard Builder **Schema** mode or `LayoutProfileStore.validate_layout_dict`.
3. Set `active_layout_profile_id` in session state or use the Dashboard Builder selector.

## BlockContext

Built by `build_context_from_session()` — blocks never receive raw `st.session_state`.
