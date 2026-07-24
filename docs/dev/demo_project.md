Type: PRODUCT
Authority: self

# Demo project (1.0)

**Status:** implemented (**0.9.6** — synthetic pack + transactional load/remove)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) demo section  
**Related:** [ui_presentation_modes.md](ui_presentation_modes.md), [schema_epoch_inventory.md](schema_epoch_inventory.md)

## Decision (locked)

Explicit **Load demo project** / **Explore examples**; isolated demo ownership inventory; one-click remove; **canonical transcripts + scripted generate-demo-runs** over large committed run trees.

## Shipped behaviour (0.9.6)

- Bundled pack under `transcriptx.demo.pack` (3 `demo__*` JSON transcripts + manifest + PROVENANCE)
- Transactional install/remove via `transcriptx.demo.service` (journal before mutate; ownership inventory; compare-and-delete index; bounded deletes; no `create_or_get_group` reuse)
- Synthetic deterministic runs (no network / Ollama); Home + Settings CTAs; stale vs pack hash / schema epoch
- Maintainer CLI: `scripts/generate_demo_runs.py --validate-only` / `--install`
- Onboarding checklist (`onboarding.json`) on Home — item IDs, pending/completed/skipped, derived completion

## Design

- [x] Entry points: Home + Settings
- [x] 3 redistributable examples (meeting/decisions; interview; multi-speaker) + owned demo group
- [x] Isolated ownership inventory — never claim foreign slugs / ALREADY_MANAGED
- [x] One-click remove (runs on owned demo identities included)
- [x] Ship transcripts + `scripts/generate_demo_runs.py`
- [x] Detect stale demo vs schema epoch / pack hash
- [x] Label synthetic demo outputs
- [x] Keep image/repo size small (no large run trees)

## Non-goals

- Mixing demo artifacts into the user’s default data root without isolation
- Committing large completed run trees by default
- Voice-licensed audio examples (deferred)
