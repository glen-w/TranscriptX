Type: GUIDE
Authority: docs_architecture_1_0.md

# Read the Docs go-live checklist

**Status:** prep only (**0.9.7**) — do **not** publish a live RTD project hostname in-repo until the project exists.  
`scripts/release/stale_refs.sh` still denylists the public RTD hostname pattern until then.

## Prerequisites

- [x] Sphinx tree builds locally / CI (`make docs`, `.readthedocs.yml`)
- [ ] Owner creates RTD project and chooses slug / custom domain ([roadmap §20](pre_release_roadmap_1_0.md))

## Flip steps (when slug is ready)

1. Confirm RTD builds from `.readthedocs.yml` on the default branch.
2. Note the public docs URL for the chosen slug (RTD project homepage).
3. Update `scripts/release/stale_refs.sh`: remove or narrow the RTD hostname denylist so the intentional URL is allowed.
4. Point README, `website/index.html` docs CTA, and [docs_architecture_1_0.md](docs_architecture_1_0.md) at the live URL.
5. Optionally enable Sphinx `linkcheck` in CI against the published tree.
6. Run `bash scripts/release/stale_refs.sh` and docs CI green before tagging.

## Until then

- User docs remain in-repo via [USER_INDEX.md](../USER_INDEX.md).
- Sphinx HTML is rebuilt from the same `docs/` tree on every CI run, and published to GitHub Pages under `/guide/` on docs-affecting `main` pushes ([assemble_pages_site.sh](../../scripts/release/assemble_pages_site.sh)).
- Website Docs / Workflows CTAs point at that Pages guide until an intentional RTD URL replaces them.
