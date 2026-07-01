# Dictionary profile stores — design spike (Wave 8)

## Context

Three config areas store large nested dictionaries that flatten into many registry keys:

- `analysis.quality_filtering_profiles` (~162 keys)
- `analysis.semantic_similarity_v2_profiles` (~22 keys)
- `analysis.quick_analysis_settings` / `analysis.full_analysis_settings` (~22 keys)

## Decisions

### 1. Registry flattening

**Keep** the existing registry behavior: `build_registry()` flattens the default config snapshot, so profile dicts continue to appear as dot-path leaf keys (e.g. `analysis.quality_filtering_profiles.balanced.weights.length_optimal`).

Pydantic pilots mirror the same nested shape; `pydantic_registry.collect_model_leaf_dotpaths()` owns those leaf paths after migration.

### 2. Model shape

Use **profile-root nested models** generated from default payloads:

- `QualityFilteringProfilesSettingsModel` with one field per named profile (`balanced`, `academic`, …), each a nested entry model (`description`, `weights`, `thresholds`, `indicators`).
- `SemanticSimilarityV2ProfilesSettingsModel` with one field per named v2 profile.
- `QuickAnalysisSettingsModel` / `FullAnalysisSettingsModel` as flat preset models.

Nested `dict[str, scalar]` buckets (e.g. `moments.weight_map`, `speaker_exemplars.weights`) become explicit sub-models so flattened registry keys stay aligned with Pydantic ownership.

### 3. Source of truth

- **Adapter profile JSON files** remain authoritative for profile-backed module targets (`topic_modeling`, `acts`, `semantic_similarity_v2`, etc.).
- **Project config inline dicts** remain valid for `quality_filtering_profiles` and preset dicts; `file_overrides.py` keeps the special-case tuple normalization for quality profile thresholds.

### 4. Out of scope

- `active_*_profile` activation keys stay legacy (not Pydantic pilots).
- Resolver temp-file loading and Settings UI auto-generation unchanged.

## Implementation

Models live under `src/transcriptx/core/config/models/` and are registered in `PYDANTIC_REGISTRY_PILOTS`. Generators:

- `scripts/generate_pydantic_pilots.py` — dataclass-backed pilots
- `scripts/generate_dict_profile_models.py` — dictionary profile stores

## Post-migration baseline

Non-pydantic registry baseline is **10 keys**: seven `active_*_profile` selectors, `active_workflow_profile`, `use_emojis`, and `core_mode`. Wave 9 (global flags) intentionally keeps `use_emojis` and `core_mode` legacy rather than adding empty-prefix bridge pilots.

## Status

**Implemented** — dictionary profile models, nested analysis subtree pilots, structural ownership tests, file-override merge semantics, and validation consolidation are in tree. See [pydantic_migration.md](pydantic_migration.md) for the final regression gate.
