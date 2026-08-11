Type: PRODUCT
Authority: self

# Documentation architecture (1.0)

**Status:** Sphinx revived (**0.9.5**); modest `website/` + Pages workflow (**0.9.7**); screenshot workflow walkthroughs (**2026-08**); RTD project go-live still owner-gated  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md); Phase 0A inventories  
**Inventories:** [documentation_inventory_1_0.md](documentation_inventory_1_0.md), [script_inventory_1_0.md](script_inventory_1_0.md)

## Surfaces

| Surface | Role | Authority |
|---------|------|-----------|
| README | Entry + quickstart | Summarizes; links PRODUCT |
| [PRODUCT.md](../PRODUCT.md) | Product definition | Self |
| [ROADMAP.md](../ROADMAP.md) | Long-term + 0.9 themes | Self |
| [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) | Short-term 0.9→1.0 programme | Self |
| Contracts + [CONTRACT_INDEX.md](../CONTRACT_INDEX.md) | Behavioural invariants | Contracts |
| `docs/runtime/` | Task-oriented user guides | Guide (link contracts) |
| `docs/workflows/` | Outcome-focused walkthroughs (screenshots/GIFs) | Guide (PRODUCT) |
| `docs/dev/` | Developer / programme | Developer |
| `docs/archive/` | Historical (banners) | Historical |
| Read the Docs (scaffold) | Hosted user/dev nav | Built from docs; Sphinx + `.readthedocs.yml` |
| `website/` | Modest public landing | Marketing; not contract — GitHub Pages |

## Indexes

- User: [USER_INDEX.md](../USER_INDEX.md)
- Developer: [DEV_INDEX.md](../DEV_INDEX.md)
- Archive: [ARCHIVE_INDEX.md](../ARCHIVE_INDEX.md)

## Hosted docs / Sphinx

- [x] Revive Sphinx tree (`docs/conf.py`, MyST, Furo) rooted on curated user/runtime pages + DEV index
- [x] Wire `make docs` → [scripts/release/build_docs.sh](../../scripts/release/build_docs.sh); CI `docs` job
- [x] Add `.readthedocs.yml` scaffold (install `.[docs]`)
- [ ] Confirm RTD project + nav when owner supplies slug/domain (§20) — [rtd_go_live_checklist.md](rtd_go_live_checklist.md)
- [ ] Flip `scripts/release/stale_refs.sh` RTD hostname denylist when a live URL is intentional
- Keep entry surfaces concise; detail stays in contracts/runtime/dev
- Archive excluded from hosted navigation (`exclude_patterns`)

## Open

- [ ] RTD project go-live + hostname allowlist update
- [x] Modest `website/` / GitHub Pages (**0.9.7**)
- [x] Screenshot-based user guides — five workflow walkthroughs under [docs/workflows/](../workflows/index.md) with media in `docs/_static/workflows/` (capture notes: [workflow_media_capture.md](workflow_media_capture.md))
