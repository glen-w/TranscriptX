# Local scratch convention

Future local-only developer material belongs under **`.local/`** at the repository root.

## What belongs in `.local/`

- Temporary audit outputs and release evidence not intended for commits
- Generated screenshots before curation
- Private corpus helpers and machine-specific notes
- Local copies of Compose overrides (prefer `docker-compose.override.yml` which is already gitignored)
- Local benchmark output
- One-off scratch scripts

## Local code reviews (`docs/reviews/`)

Unpublished architecture and code reviews belong under **`docs/reviews/`** (gitignored) so they can be built with `make docs` without entering hosted navigation. They are not a substitute for tracked assessments under `docs/dev/` or `docs/archive/`.

## What does **not** belong in `.local/`

- Product documentation (use `docs/` and the archive policy)
- Supported or maintainer scripts (use `scripts/` / `scripts/release/`)
- Historical material that should remain searchable in git (use `docs/archive/` or `archive/scripts/`)

## Policy

- `.local/` is listed in `.gitignore`. Do **not** use gitignore as an archive for already-tracked files.
- Tracked obsolete docs go to `docs/archive/` with an archived banner.
- Tracked obsolete scripts go to `archive/scripts/` with an `[ARCHIVED]` banner.
- Do not broadly ignore `*.md` or `scripts/*.py`.

See Phase 0A inventories: [documentation_inventory_1_0.md](documentation_inventory_1_0.md), [script_inventory_1_0.md](script_inventory_1_0.md).
