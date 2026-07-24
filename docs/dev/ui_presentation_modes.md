Type: PRODUCT
Authority: self

# UI presentation modes (Guided / Full controls)

**Status:** planning (design only — not implemented; deferred past **0.9.5**)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) locked decisions + Guided section  
**Surfaces:** [public_surfaces.md](../public_surfaces.md)

## Decision (locked)

Presentation / config layer only — **one execution system**. Prefer labels **Guided** / **Full controls** (Simple / Advanced are acceptable doc aliases).

Guided / Full are **not** a new public surface.

## Intent

| Mode | Intent |
|------|--------|
| **Guided** | Principal workflow; recommended presets; reduced registry complexity; plain AI requirements; actionable errors; clear import→results path |
| **Full controls** | Full module registry, advanced settings, specialist knobs |

## Design checklist

- [ ] Single preference / config key for mode
- [ ] Guided materially reduces first-run complexity
- [ ] Full does not fork pipeline execution
- [ ] Mode switch discoverable from Home / Settings / Help
- [ ] Docs use Guided/Full; Simple/Advanced only as synonyms if needed

## Non-goals

- Duplicate page logic trees per mode
- Separate analysis engines
- Elaborate coach-mark tour (deferrable to 1.1)
