# Documentation architecture (1.0)

**Status:** Sphinx revived (**0.9.5**); modest `website/` + Pages workflow (**0.9.7**); screenshot workflow walkthroughs (**2026-08**); RTD project go-live still owner-gated  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md); Phase 0A inventories  
**Inventories:** [documentation_inventory_1_0.md](documentation_inventory_1_0.md), [script_inventory_1_0.md](script_inventory_1_0.md)

## Surfaces

| Surface | Role | Authority |
|---------|------|-----------|
| README | Public first-run entry (product, screenshot, first analysis, install) | Summarizes; links PRODUCT |

| [PRODUCT.md](../PRODUCT.md) | Product definition | Self |
| [ROADMAP.md](../ROADMAP.md) | Long-term + 0.9 themes | Self |
| [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) | Short-term 0.9→1.0 programme | Self |
| Contracts + [CONTRACT_INDEX.md](../CONTRACT_INDEX.md) | Behavioural invariants | Contracts |
| `docs/runtime/` | Task-oriented user guides | Guide (link contracts) |
| `docs/workflows/` | Outcome-focused walkthroughs (screenshots/GIFs) | Guide (PRODUCT) |
| `docs/dev/` | Developer / programme | Developer |
| `docs/reviews/` | Dated architecture / code assessments | Assessment (not contracts) |
| `docs/archive/` | Historical (banners) | Historical |
| Read the Docs (scaffold) | Hosted user/dev nav | Built from docs; Sphinx + `.readthedocs.yml` |
| `website/` + Pages `/guide/` | Modest public landing **and** auto-published Sphinx HTML from the same `docs/` tree | Marketing + interim hosted guide — GitHub Pages |

## Indexes

- User sitemap: [USER_INDEX.md](../USER_INDEX.md) (exhaustive list, not a start page)
- Developer: [DEV_INDEX.md](../DEV_INDEX.md)
- Archive: [ARCHIVE_INDEX.md](../ARCHIVE_INDEX.md)

## Voices

Three registers — same facts, different density. Do not rewrite archive, reviews, or contracts to sound friendly.

| Voice | Audience | Surfaces |
|-------|----------|----------|
| **User guide** | First-time and returning operators | README, `website/`, `docs/index.md`, `docs/workflows/`, lead of transcription / installation / llm |
| **Technical reference** | People configuring or scripting | `docs/runtime/` detail, `docs/generated/`, TERMS, contracts, STORAGE, public_surfaces |
| **Maintainer** | Contributors and release owners | `docs/dev/`, `docs/archive/`, `docs/reviews/`, internal package/test READMEs |

README is the user entry, not a release brief. Do not put `Type:` / `Authority:` headers on Markdown pages (they render on hosted docs). Schema epoch, install-profile markers, and programme history belong in ROADMAP / `docs/dev/`, not the first screen.

The public landing, README, and Sphinx “Start here” toctree should tell the same story: what it is → screenshots → what you can do → privacy → first analysis → install.

## Hosted docs / Sphinx

- [x] Revive Sphinx tree (`docs/conf.py`, MyST, Furo) rooted on curated user/runtime pages + DEV index
- [x] Wire `make docs` → [scripts/release/build_docs.sh](../../scripts/release/build_docs.sh); CI `docs` job
- [x] Add `.readthedocs.yml` scaffold (install `.[docs]`)
- [x] **Content parity:** Sphinx has no separate doc corpus — it builds the Markdown under `docs/` directly. CI regenerates `docs/generated/` (`make docs-gen`) and fails on drift; every docs-affecting `main` push rebuilds and publishes HTML to GitHub Pages `/guide/` via [assemble_pages_site.sh](../../scripts/release/assemble_pages_site.sh)
- [x] **Nav parity:** `docs/index.md` Start-here / Workflows / Using TranscriptX toctrees stay aligned with the README and website first-run story. Advanced toctree holds split reference pages; [USER_INDEX.md](../USER_INDEX.md) is the exhaustive sitemap. Developers toctree holds contracts, generated catalogs, and module notes. Footer version on the website matches `pyproject.toml`.
- [ ] Confirm RTD project + nav when owner supplies slug/domain (§20) — [rtd_go_live_checklist.md](rtd_go_live_checklist.md)
- [ ] Flip `scripts/release/stale_refs.sh` RTD hostname denylist when a live URL is intentional
- Keep entry surfaces concise; detail stays in contracts/runtime/dev
- Archive excluded from hosted navigation (`exclude_patterns`)

## Open

- [ ] RTD project go-live + hostname allowlist update
- [x] Modest `website/` / GitHub Pages (**0.9.7**); Sphinx guide auto-publish on Pages (**interim until RTD**)
- [x] Screenshot-based user guides — workflow walkthroughs under [docs/workflows/](../workflows/index.md) (five featured on the README; full set in the index) with media in `docs/_static/workflows/` (capture notes: [workflow_media_capture.md](workflow_media_capture.md); public hero also at `website/images/overview.png`)
