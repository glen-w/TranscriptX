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

On **group** runs, `transcript_summary_hero` / `resolve_primary_summary` prefer committed [group LLM synthesis](../groups/group_llm_synthesis_contract.md) via the central resolver (no member `_llm_summary` primary fallback). `llm_speaker_summary_block` likewise loads `group_llm_speaker_summary_index` when ACTIVE/COMMIT validate.

Overview **module metrics** use summary extractors under `web/summary_extractors/`. Zip export summaries for LLM prose/list modules are resolved in `transcriptx.export.resolve`.

## Adding a layout

1. Copy `presets/default.yaml` to `data/profiles/ui_layouts/my_layout.yaml` (or add a new preset).
2. Validate via Dashboard Builder **Schema** mode or `LayoutProfileStore.validate_layout_dict`.
3. Set `active_layout_profile_id` in session state or use the Dashboard Builder selector.

## BlockContext

Built by `build_context_from_session()` — blocks never receive raw `st.session_state`.
