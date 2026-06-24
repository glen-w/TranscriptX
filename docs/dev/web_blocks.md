# Web blocks

## BlockSpec

Registered in `web/blocks/registry.py`. Each block has `id`, `group`, `description`, optional `module_deps` / `artifact_patterns`, and a `render(ctx, placement)` function.

## BlockPlacement

Layout YAML uses `placement_id` (unique instance) and `block_id` (reusable type).

## Adding a block

1. Implement `render_*` in `web/blocks/implementations/` — adapt an existing page renderer; do not duplicate `ArtifactService` logic.
2. Register in `web/blocks/builtin.py`.
3. Add placement to a preset under `web/layouts/presets/`.
4. Add a smoke test under `tests/web/blocks/`.

## Adding a layout

1. Copy `presets/default.yaml` to `data/profiles/ui_layouts/my_layout.yaml` (or add a new preset).
2. Validate via Dashboard Builder **Schema** mode or `LayoutProfileStore.validate_layout_dict`.
3. Set `active_layout_profile_id` in session state or use the Dashboard Builder selector.

## BlockContext

Built by `build_context_from_session()` — blocks never receive raw `st.session_state`.
