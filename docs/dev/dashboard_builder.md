# Dashboard Builder

Settings → **Dashboard Builder** edits **layout profiles**: which panels (blocks) appear on **Overview** and **Insights**, and in what order.

It does **not** choose which charts appear in the Charts page Overview strip — that is **Settings → Configuration → Charts overview** (`dashboard.overview_charts`).

## Modes

| Mode | Needs run? | What it does |
|------|------------|--------------|
| **Edit** | No | Add / remove / reorder Overview & Insights blocks (↑↓); save custom layouts in place; clone built-ins |
| **Schema** | No | Lists registered blocks, dumps active layout YAML, validates, Save as custom / Delete custom |
| **Preview** | Yes (subject + run) | Renders a chosen page via the order-based composer |

Visiting Dashboard Builder sets `show_debug_layouts=True` so **Developer debug** appears in the layout picker.

## Built-in presets (immutable)

| Id | Title | When to use |
|----|-------|-------------|
| `default` | Standard | Everyday viewing (product default) |
| `executive` | Executive | Metrics-first Overview; summary / actions / highlights |
| `meeting_followup` | Meeting follow-up | After a meeting: extracts, commitments, highlights |
| `speaker_focus` | Speakers | Who spoke and linguistic style |
| `minimal` | Minimal | Fast scan / low clutter |
| `developer_debug` | Developer debug | Layout/block inspection |
| `all` | All | Every registered block (generated; not YAML) |

Built-ins cannot be overwritten or deleted. Clone with **Save as custom layout**, then edit the custom copy.

## Custom layouts

- Path: `{config_dir}/profiles/ui_layouts/{id}.yaml` (`PROFILES_DIR/ui_layouts/`)
- Edit mode saves in place via `LayoutProfileStore.save_layout(..., overwrite=True)`
- Ids are slugified to `[a-zA-Z0-9_-]+`; path segments and `..` are rejected
- Delete requires confirmation; if the deleted layout was active, active id resets to `default`

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Preview empty | Select a subject and analysis run in the sidebar |
| Cannot save in Edit | Built-in selected — clone first |
| Validation failed | Unknown `block_id`, duplicate `placement_id`, bad `params` / `section` |
| Insights sections missing | Set `section:` on Insights placements (`summary` / `speakers` / `actions` / `highlights`) |

## Related

- [composition_platform.md](composition_platform.md) — architecture
- [web_blocks.md](web_blocks.md) — adding blocks and layouts
- [settings.md](../runtime/settings.md) — Charts overview selector
- Page: `src/transcriptx/web/page_modules/dashboard_builder.py`
- Editor: `src/transcriptx/web/ui/dashboard_builder/layout_editor.py`
