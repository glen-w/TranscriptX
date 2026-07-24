Type: PRODUCT
Authority: self

# UI presentation modes (Guided / Full controls)

**Status:** implemented (**0.9.6**)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) locked decisions + Guided section  
**Surfaces:** [public_surfaces.md](../public_surfaces.md)

## Decision (locked)

Presentation / config layer only — **one execution system**. Labels **Guided** / **Full controls**.

Guided / Full are **not** a new public surface.

## Intent

| Mode | Intent |
|------|--------|
| **Guided** | Principal workflow; recommended presets; reduced registry complexity; plain AI requirements; actionable errors; clear import→results path |
| **Full controls** | Full module registry, advanced settings, specialist knobs |

## Shipped behaviour (0.9.6)

- Prefs file `presentation_mode.json` (envelope + hash + CAS), same strength as interface-menus prefs
- Empty workspace seeds **Guided**; existing workspace (config/index/runs) seeds **Full controls** once
- Single resolver before sidebar/routing; visibility filter separate from access; Full-only pages banner + unlock
- Guided Settings tab set + curated `GUIDED_SETTINGS_SCHEMA`; Custom analysis under Guided is read-only with “Edit in Full controls”
- Mode switch on Home / Settings; presentation never mutates analysis Custom/preset keys

## Design checklist

- [x] Single preference / config key for mode
- [x] Guided materially reduces first-run complexity
- [x] Full does not fork pipeline execution
- [x] Mode switch discoverable from Home / Settings
- [x] Docs use Guided/Full; Simple/Advanced only as synonyms if needed

## Non-goals

- Duplicate page logic trees per mode
- Separate analysis engines
- Elaborate coach-mark tour (deferrable to 1.1)
