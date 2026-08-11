Type: GUIDE
Authority: docs/dev/composition_platform.md

# Dashboard Builder

Settings → **Dashboard Builder** inspects the composition platform: registered view blocks, layout profile YAML, validation, Preview against a selected run, and clone/delete of **custom** layouts.

## Modes

| Mode | Needs run? | What it does |
|------|------------|--------------|
| **Schema** | No | Lists registered blocks (availability without a run), dumps active layout YAML, validates, **Save as custom layout**, **Delete custom layout** |
| **Preview** | Yes (subject + run in sidebar) | Block availability for the current run; renders a chosen page (`overview` / `insights` / `charts`) via the order-based composer |

Visiting Dashboard Builder sets `show_debug_layouts=True` for the session so **Developer debug** appears in the layout picker. Built-in **All** remains listed regardless.

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

Built-ins cannot be overwritten or deleted. Clone with **Save as custom layout**.

## Custom layouts

- Path: `data/profiles/ui_layouts/{id}.yaml` (under the project profiles directory)
- Ids are slugified to `[a-zA-Z0-9_-]+` (must start with a letter or digit); path segments and `..` are rejected
- Saving over an existing custom id requires an explicit overwrite confirmation in the UI (`overwrite=False` at the store rejects silently replacing)
- Delete requires a confirmation checkbox; if the deleted layout was active, the active id resets to `default`

Validate programmatically:

```python
from transcriptx.web.layouts.store import LayoutProfileStore

spec = LayoutProfileStore.load_layout("meeting_followup")
LayoutProfileStore.validate_layout(spec)
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Preview empty / info banner | Select a subject and analysis run in the sidebar |
| Validation failed | Unknown `block_id`, duplicate `placement_id`, unsupported / mistyped `params` for blocks that declare `params_schema` |
| Cannot save | Id collides with a built-in, or overwrite not confirmed |
| Cannot delete | Target is a built-in id |
| Insights sections missing | Curated presets should set `section:` on Insights placements (`summary` / `speakers` / `actions` / `highlights`) |

## Related

- [composition_platform.md](composition_platform.md) — architecture
- [web_blocks.md](web_blocks.md) — adding blocks and layouts
- Store: `src/transcriptx/web/layouts/store.py`
- Page: `src/transcriptx/web/page_modules/dashboard_builder.py`
