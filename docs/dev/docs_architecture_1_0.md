Type: PRODUCT
Authority: self

# Documentation architecture (1.0)

**Status:** planning  
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
| `docs/dev/` | Developer / programme | Developer |
| `docs/archive/` | Historical (banners) | Historical |
| Read the Docs (planned) | Hosted user/dev nav | Built from docs; revive Sphinx |
| `website/` (planned) | Modest public landing | Marketing; not contract |

## Indexes

- User: [USER_INDEX.md](../USER_INDEX.md)
- Developer: [DEV_INDEX.md](../DEV_INDEX.md)
- Archive: [ARCHIVE_INDEX.md](../ARCHIVE_INDEX.md)

## Hosted docs / Sphinx

- Sphinx extras exist in `pyproject.toml` (`[docs]`); live `docs/conf.py` / Makefile may still be missing or partial after 0.9.1 hygiene.
- `scripts/build_docs.sh` was archived/stale — do not treat as supported until revived.
- `scripts/release/stale_refs.sh` currently denylists the ReadTheDocs hostname — **update when RTD goes live**.

## Open

- [ ] Confirm RTD project + nav rooted on USER/DEV indexes
- [ ] Revive Sphinx tree when hosted-docs theme starts
- [ ] Keep entry surfaces concise; detail stays in contracts/runtime/dev
