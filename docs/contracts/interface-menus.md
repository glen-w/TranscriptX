Type: CONTRACT
Authority: self

# Interface menus v1

Persisted Streamlit action-strip configuration. Edited under **Settings →
Interface** and stored at `{config_dir}/interface_menus.json`.

Related: [settings.md](../runtime/settings.md), [STORAGE.md](../runtime/STORAGE.md).

---

## Envelope

`schema_version` is integer **`1`**. Unknown or missing appearance fields sanitise
to install defaults — **no schema bump** for additive prefs such as
`show_info_tooltips` and `action_display`.

```
{
  "schema_version": 1,
  "prefs": { ... },
  "prefs_hash": "<sha256 of canonical prefs JSON>"
}
```

| Field | Rules |
|-------|--------|
| `schema_version` | Must be `1`. Any other value is recovery (file preserved; Save disabled until Replace with built-in defaults). |
| `prefs` | Object. Missing file → built-in prefs (not written until Save). |
| `prefs_hash` | SHA-256 of `prefs` serialised with `sort_keys=True` and compact separators. Mismatch → recovery. |

Malformed JSON, a non-object root, or a missing `prefs` object also enter
recovery. Compare-and-swap Save uses the raw-file SHA-256 revision.

---

## Prefs object

| Field | Default | Rules |
|-------|---------|--------|
| `standard_menu_mode` | `built_in` | `built_in` \| `custom`. Invalid → `built_in`. |
| `standard_menu` | `[]` | Known `ActionId`s only; duplicates dropped; catalogue order. Used when mode is `custom`. |
| `show_info_tooltips` | `true` | Boolean. Invalid → `true`. Gates instructional ⓘ / Streamlit `help=` tips. Run-id identity ⓘ stays on. |
| `action_display` | `both` | Global appearance: `icon` \| `text` \| `both`. Invalid or missing → `both`. |
| `sections` | all known sections | Keys are `SectionId` values. Unknown keys ignored. Missing known sections take built-ins. |

### Section object

| Field | Default | Rules |
|-------|---------|--------|
| `show_menu` | `true` | Boolean. Invalid → `true`. When false the strip is empty; mode/selections/appearance are kept. |
| `mode` | `section_default` | `use_standard` \| `section_default` \| `manual`. Invalid → `section_default`. |
| `selected` | `[]` | Manual picks, intersected with the section allowlist. |
| `action_display` | `inherit` | `inherit` \| `icon` \| `text` \| `both`. Missing → that section’s built-in (`inherit`). Invalid → that section’s built-in. |

Install / Restore built-ins / missing file: every section is `inherit`, so
strips resolve to the global `both` (icon and text). Non-menu
`render_action_link` callers (Charts downloads, Search jumps, and similar)
stay icon+text via the helper default.

### Appearance resolution

```
section.action_display == inherit  →  prefs.action_display
section.action_display in {icon, text, both}  →  that value
```

Icon-only buttons always use the action name as the hover tooltip (accessible
name), even when `show_info_tooltips` is false. Text / both still wrap
instructional help with `widget_help()`.

---

## Sections

| `SectionId` | Surface |
|-------------|---------|
| `home_recent_runs` | Home recent-run rows |
| `library_selected` | Library inspector for the selected transcript |
| `import_success` | Import Transcript after success |
| `speaker_id_complete` | Speaker ID after completion |
| `run_analysis_complete` | Run Analysis after completion |

Runtime still hides unavailable actions (for example Charts without a completed
run) without turning the menu off.
