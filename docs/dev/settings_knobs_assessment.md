Type: PRODUCT
Authority: self

# Settings / profiles / knobs — assessment and programme

**Date:** 2026-08-11  
**Scope:** Config knobs, module/workflow profiles, Settings UI, install-profile clarity, env catalog.  
**Out of scope:** Speaker identity/voice profile subsystem (except Speakers tab pointer).  
**Live architecture:** [config_architecture.md](config_architecture.md) · **User guide:** [settings.md](../runtime/settings.md)

## Verdict

TranscriptX has a working dual-stack config system (**53 / 718 / 16 / 734** ownership) and a capable Settings hub, but taxonomy and docs lagged the code: overloaded “profile”, orphaned `data/profiles` fixtures, dual validation paths, and no dedicated settings guide. This programme restores clarity, then cleans and hardens without restarting a full Pydantic migration.

## Assessment findings

| ID | Finding | Severity |
|----|---------|----------|
| F1 | No live `docs/runtime/settings.md`; USER_INDEX pointed only at installation | High (accessibility) |
| F2 | “Profile” means install / UI preset / disk module profile / in-config semantic map / STT / speaker | High (clarity) |
| F3 | `data/profiles/*/default.json` tracked but **not** seeded into `PROFILES_DIR`; virtual `default` is code defaults | Medium |
| F4 | PROFILE targets `semantic_similarity` and `llm_models` lack tracked fixture dirs (others have fixtures) | Low |
| F5 | Dual `validate_config` stacks (object + leaf) both live on file load | Medium (hardening) |
| F6 | Resolver tempfile rebuild debt remains | Medium (hardening) |
| F7 | `TranscriptXConfig.__init__` docstring disagreed with load order (file → profile → env) | Low (fixed this PR) |
| F8 | Common Settings still labelled “Semantic Similarity v2” after public rename | Medium (UX; fixed this PR) |
| F9 | Motif B14 keys in Common but missing from semantic profile guided_fields | Low (fixed this PR) |
| F10 | Legacy `TRANSCRIPTX_AUDIO_*_ENABLED` in `.env.example` without reject warning | Medium (hardening; fixed this PR) |
| F11 | `FieldMetadata.advanced` unused by Settings form partition | Low (follow-up) |
| F12 | Archived plans still advertise stale **41/598/10** metrics | Docs trap (call out only) |

## Programme phases

### Phase 0 — Organisation (this PR)

- Live user settings guide + developer architecture + this assessment
- Taxonomy in TERMS / STORAGE / installation cross-links
- Index wiring (USER_INDEX, DEV_INDEX, Sphinx `docs/index.md`)

### Phase 1 — Cleanup (this PR + small follow-ups)

- Docstring / UX label honesty; motif guided_fields alignment
- `.env.example` legacy reject comments; allowlist purpose honesty
- Dual-validation and dual-semantic-store **comments** (no behaviour change yet)
- Follow-up: decide whether to delete, relocate, or document-only keep `data/profiles` fixtures

### Phase 2 — Hardening (follow-up PRs)

| Track | Goal | Risk |
|-------|------|------|
| H1 | Collapse object + leaf validation behind one API | Medium — file load behaviour |
| H2 | Replace resolver tempfile rebuild | Medium — run/Settings parity |
| H3 | Use `FieldMetadata.advanced` in Common/Advanced partition | Low |
| H4 | Clarify or merge in-config `semantic_similarity_profiles` vs ProfileManager target | High product decision |
| H5 | Optional bootstrap of seed profiles into `PROFILES_DIR` (if product wants disk defaults) | Product decision |
| H6 | Install-profile marker simplification (pre_release residual) | Low if docs stay honest |

## Done criteria (Phase 0–1)

- [x] User can find Settings guidance from USER_INDEX / Sphinx
- [x] Developer can find live architecture without reading archive plans
- [x] Load-order docstring matches tested behaviour
- [x] Semantic Similarity Common groups no longer say “v2”
- [x] Legacy audio `*_ENABLED` env keys marked rejected in `.env.example`
- [ ] Phase 2 tracks H1–H6 tracked but not required for this PR

## Non-goals

- New analysis knobs or registry count churn for its own sake
- Speaker profiles contract changes
- Re-opening full ownership migration / `analysis.py` structural split
