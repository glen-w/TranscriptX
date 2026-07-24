Type: PRODUCT
Authority: self

# Demo project (1.0)

**Status:** planning  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) demo section  
**Related:** [ui_presentation_modes.md](ui_presentation_modes.md), [schema_epoch_inventory.md](schema_epoch_inventory.md)

## Decision (locked)

Explicit **Load demo project** / **Explore examples**; isolated demo namespace; one-click remove; prefer **canonical transcripts + scripted generate-demo-runs** over large committed run trees. Large bundled completed runs deferrable to 1.1 if risky.

## Design

- [ ] Entry points: first launch + Home
- [ ] 3–5 redistributable examples (meeting/decisions; interview; multi-speaker; optional voice if licence/size OK; small cross-session group)
- [ ] Isolated namespace — never touch user library data
- [ ] One-click remove
- [ ] Ship transcripts + deterministic `scripts/generate_demo_runs.py` (or equivalent)
- [ ] Detect stale demo vs schema epoch / package version
- [ ] Label any AI demo outputs
- [ ] Keep image/repo size small

## Non-goals

- Mixing demo artifacts into the user’s default data root without isolation
- Committing large completed run trees by default
