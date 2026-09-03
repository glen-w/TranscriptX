> **Archived / superseded.** Historical context only. Current authority: [developer_quickstart.md](../../developer_quickstart.md). Do not treat as live roadmap or support policy.

# Pydantic config migration checklist

Incremental adoption pattern for moving config subtrees to Pydantic as the single source of truth for field definitions (defaults, types, validation, bounds, choices, UI metadata).

## Prerequisites

- Keep `TranscriptXConfig` dataclass runtime facade until many subtrees are migrated.
- Keep `env_key_registry.py` as the env compatibility adapter.
- Do not replace resolver temp-file loading until most sections are Pydantic-backed.
- Do not introduce Hydra, Dynaconf, or OmegaConf.

## Freeze policy (enforce now)

1. **No new literal defaults** in `utils/config/analysis.py` / `system.py` / `workflow.py` / `main.py` unless the knob is one of the permanent **10** legacy keys (`active_*_profile` ×7, `active_workflow_profile`, `use_emojis`, `core_mode`).
2. **New product knobs:** add/extend a Pydantic model → register/update pilot in `pydantic_bridge.py` (hand review) → regenerate goldens → update `to_dict()` / `file_overrides` visibility if a new subtree → env key only if needed in `env_key_registry.py`.
3. **No new registry pilots** for vanity; only when product adds keys. Prefer extending an existing model.
4. **No new validators** (Cerberus/Marshmallow/jsonschema/ad-hoc). Validation goes through Pydantic pilots + existing `validate_config`.
5. **Do not grow** a second facade — only `main.TranscriptXConfig` is constructible.
6. PR checklist: ownership snapshot invariant **41 / 598 / 10** (608 total registry keys; or update fixture intentionally) + `tests/core/config/` gate.

Canonical freeze / registry checklist: [`docs/config/config_knobs_refactor_plan.md`](config_knobs_refactor_plan.md).  
**Authoritative for runtime delegation, file-override, and `to_dict()` sequencing:** [`docs/config/config_ownership_collapse_plan.md`](config_ownership_collapse_plan.md).

## Generator scripts (regen helpers only)

- [`scripts/generate_pydantic_pilots.py`](../scripts/generate_pydantic_pilots.py) — default (no flags): regenerates model files and golden fixtures; **never** modifies [`pydantic_bridge.py`](../src/transcriptx/core/config/pydantic_bridge.py) (hand-maintained only).
- [`scripts/generate_pydantic_pilots.py --write-bridge`](../scripts/generate_pydantic_pilots.py) — prints **scaffold only** for mechanical `PydanticPilotSpec` rows (imports + tuple entries). Paste into `PYDANTIC_REGISTRY_PILOTS` after review. Does not emit behavioral bridge logic.
- [`pydantic_bridge_helpers.py`](../src/transcriptx/core/config/pydantic_bridge_helpers.py) — shared behavioral helpers (`dotpath_belongs_to_model`, `extract_subtree_overrides`). Covered by [`test_pydantic_bridge_helpers.py`](../../tests/core/config/test_pydantic_bridge_helpers.py).
- [`scripts/generate_dict_profile_models.py`](../scripts/generate_dict_profile_models.py) — regenerates dictionary-profile model files only; never touches the bridge.
- Bridge registration in `pydantic_bridge.py` is **hand-reviewed** in each PR.
- Structural ownership tests in `test_registry_ownership.py` are canonical; `test_pydantic_pilot_parity.py` covers defaults parity only.

## Checklist per subtree

1. **Capture golden snapshot** (before deleting manual enrichers):
   - `tests/core/config/fixtures/<pilot_id>_registry_golden.json`
   - `tests/core/config/fixtures/<pilot_id>_defaults_golden.json` (subtree from `get_default_config_dict()`)

2. **Add Pydantic model** under `src/transcriptx/core/config/models/`.

3. **Register pilot** in `PYDANTIC_REGISTRY_PILOTS` in [pydantic_bridge.py](../src/transcriptx/core/config/pydantic_bridge.py):
   - `pilot_id`, `model`, `dotpath_prefix`, `category`, optional `dataclass_type`

4. **Ensure visibility** — subtree must appear in `TranscriptXConfig.to_dict()` and [file_overrides.py](../src/transcriptx/core/utils/config/file_overrides.py) if file-configurable.

5. **Dataclass parity test** (if runtime dataclass remains):
   - Compare **normalized** JSON-safe values from `asdict(Dataclass())` and `Model().model_dump()` (enum/nested representations may differ raw).
   - Separately assert runtime dataclass types and tuple types on the facade / `to_dict()` where consumers depend on them.

6. **Pilot tests**:
   - Registry golden parity (`capture_pilot_schema_golden`)
   - Validation: invalid choices, bounds, coercion, partial overrides
   - Integration: project/run resolve, env apply for registered `TRANSCRIPTX_*` keys

7. **Global drift suite** — run `tests/core/config/test_pydantic_bridge_drift.py` and full regression gate.

8. **Delete manual enricher** (e.g. `_apply_*_registry`) if one existed for this subtree.

9. **Update non-pydantic baseline** only when non-pilot registry keys intentionally change.

## Registered pilots

| pilot_id | dotpath_prefix | Runtime dataclass |
|----------|----------------|-------------------|
| `semantic_similarity_v2` | `analysis.semantic_similarity_v2` | `SemanticSimilarityV2Config` |
| `metadata` | `metadata` | `MetadataConfig` |
| `dashboard_display` | `dashboard` (display fields only) | partial `DashboardConfig` |
| `dashboard_overview` | `dashboard` (overview fields only) | partial `DashboardConfig` |
| `llm` | `llm` | `LLMConfig` |
| `acts` | `analysis.acts` | `ActsConfig` |
| `output` | `output` | `OutputConfig` |
| `input` | `input` | `InputConfig` |
| `logging` | `logging` | `LoggingConfig` |
| `group_analysis` | `group_analysis` | `GroupAnalysisConfig` |
| `audio_preprocessing` | `audio_preprocessing` | `AudioPreprocessingConfig` |
| `topic_modeling` | `analysis.topic_modeling` | `TopicModelingConfig` |
| `qa_analysis` | `analysis.qa_analysis` | `QAAnalysisConfig` |
| `temporal_dynamics` | `analysis.temporal_dynamics` | `TemporalDynamicsConfig` |
| `vectorization` | `analysis.vectorization` | `VectorizationConfig` |
| `tag_extraction` | `analysis.tag_extraction` | `TagExtractionConfig` |
| `llm_summary_settings` | `analysis.llm_summary` | `LLMSummaryConfig` |
| `llm_speaker_summary_settings` | `analysis.llm_speaker_summary` | `LLMSpeakerSummaryConfig` |
| `llm_action_items_settings` | `analysis.llm_action_items` | `LLMActionItemsConfig` |
| `workflow` | `workflow` | `WorkflowConfig` |
| `speaker_exemplars` | `analysis.speaker_exemplars` | `SpeakerExemplarsConfig` |
| `highlights` | `analysis.highlights` | `HighlightsConfig` |
| `summary` | `analysis.summary` | `SummaryConfig` |
| `corrections` | `analysis.corrections` | `CorrectionsConfig` |
| `voice` | `analysis.voice` | `VoiceConfig` |
| `affect_tension` | `analysis.affect_tension` | `AffectTensionConfig` |
| `echoes` | `analysis.echoes` | `EchoesConfig` |
| `momentum` | `analysis.momentum` | `MomentumConfig` |
| `moments` | `analysis.moments` | `MomentsConfig` |
| `pauses` | `analysis.pauses` | `PausesConfig` |
| `bertopic` | `analysis.bertopic` | `BERTopicConfig` |
| `analysis_sentiment` | `analysis` (sentiment/emotion fields) | partial `AnalysisConfig` |
| `analysis_ner` | `analysis` (NER fields) | partial `AnalysisConfig` |
| `analysis_wordcloud` | `analysis` (wordcloud/readability fields) | partial `AnalysisConfig` |
| `analysis_interaction` | `analysis` (interaction/loop fields) | partial `AnalysisConfig` |
| `analysis_entity` | `analysis` (entity fields) | partial `AnalysisConfig` |
| `analysis_legacy_semantic` | `analysis` (legacy semantic limits) | partial `AnalysisConfig` |
| `quality_filtering_profiles` | `analysis.quality_filtering_profiles` | inline dict |
| `semantic_similarity_v2_profiles` | `analysis.semantic_similarity_v2_profiles` | inline dict |
| `quick_analysis_settings` | `analysis.quick_analysis_settings` | inline dict |
| `full_analysis_settings` | `analysis.full_analysis_settings` | inline dict |

Dictionary profile design notes: [dict_profile_stores_spike.md](dict_profile_stores_spike.md).

## Regression gate

```bash
pytest \
  tests/core/config/ \
  tests/core/utils/config/test_env_key_registry.py \
  tests/web/config/test_semantic_v2_settings_registry.py \
  tests/core/utils/test_config_validation.py \
  tests/integration/extended/test_config_cli_web.py \
  tests/analysis/semantic_similarity_v2/ \
  tests/io/test_metadata_stats.py \
  tests/io/test_transcript_schema.py \
  tests/core/store/test_transcript_store.py \
  -q
```

## End state (registry ownership complete)

**41 Pydantic pilots** originally owned **598** flattened registry leaf keys (historical Wave 9 baseline). **Current invariant** (authoritative): see `tests/core/config/test_registry_ownership.py::test_ownership_invariant_counts` — **51 / 705 / 16** (721 total) as of 0.8.0 (+B14 motif knobs + B16 `keyphrases`).

Historical Wave 9 non-pydantic baseline (**10** keys) was:

| Key | Reason |
|-----|--------|
| `active_*_profile` (7) | Profile activation selectors — permanent legacy |
| `active_workflow_profile` | Workflow profile activation — permanent legacy |
| `use_emojis` | Simple global flag — kept legacy (Wave 9: no empty-prefix bridge) |
| `core_mode` | Install/runtime mode flag — kept legacy (Wave 9: no empty-prefix bridge) |

**Current** permanent legacy set is **16** keys (same activation/global flags plus additional nested `analysis.active_*_profile` selectors and a small `analysis.chart_descriptions.*` holdout — see `non_pydantic_registry_baseline.json`).

Wave 9 evaluated two single-key pilots and empty-prefix bridge hacks; **legacy retention** was chosen to avoid destabilizing `collect_model_leaf_dotpaths`, `find_pilot_for_dotpath_key`, and env drift tests.

**Do not add new registry pilots** unless product scope explicitly requires new config keys. Registry leaf migration is complete; further work is runtime delegation and safety hardening.

Ownership snapshot fixture: [`tests/core/config/fixtures/registry_ownership_snapshot.json`](../../tests/core/config/fixtures/registry_ownership_snapshot.json) (guarded by `test_ownership_snapshot_matches_committed_fixture`).

## Phase 2: Runtime delegation (Batch 5+)

Registry ownership and runtime dataclass defaults are **separate phases**:

| Phase | Status | Meaning |
|-------|--------|---------|
| Registry ownership | Complete (see live invariant **51 / 705 / 16**; historical Wave 9 was **41 / 598 / 10**) | Pydantic models own field definitions, validation, registry metadata |
| Runtime delegation | Partial — see [`config_ownership_collapse_plan.md`](config_ownership_collapse_plan.md) | Thin dataclasses hydrate from Pydantic models; duplicate literals removed per subtree |

Delegated subtrees use hand-written `@dataclass` wrappers in [`analysis.py`](../src/transcriptx/core/utils/config/analysis.py) that call `_hydrate_dataclass_from_pydantic()` in `__post_init__`. Nested dict dumps are reconstructed as nested dataclasses when field annotations require it. Direct programmatic `setattr` on leaf fields does **not** revalidate through Pydantic; profile application via `apply_profile_to_config` may call the target’s `validate()` after applying fields. Validation also remains at `validate_config()` / file-load boundaries.

**Validation consolidation** and **resolver redesign** are separate from ownership collapse — do not mix them into Candidate 1 PRs.

Pre-delegation shape snapshots: `tests/core/config/fixtures/delegation_shape_{pauses,voice,corrections,summary,highlights,llm_*}_pre.json`.

### Delegation status

| Pilot | Prefix | Keys | Runtime target | Tests | Status |
|-------|--------|------|----------------|-------|--------|
| `pauses` | `analysis.pauses` | 3 | `PausesConfig` | `test_pauses_config_delegation.py` | delegated |
| `voice` | `analysis.voice` | 18 | `VoiceConfig` | `test_voice_config_delegation.py` | delegated |
| `corrections` | `analysis.corrections` | 12 | `CorrectionsConfig` | `test_corrections_config_delegation.py` | delegated |
| `summary` | `analysis.summary` | 13 | `SummaryConfig` | `test_summary_config_delegation.py` | delegated |
| `highlights` | `analysis.highlights` | 30 | `HighlightsConfig` | `test_highlights_config_delegation.py` | delegated |
| `llm_summary_settings` | `analysis.llm_summary` | 1 | `LLMSummaryConfig` | `test_llm_summary_config_delegation.py` | delegated |
| `llm_speaker_summary_settings` | `analysis.llm_speaker_summary` | 1 | `LLMSpeakerSummaryConfig` | `test_llm_speaker_summary_config_delegation.py` | delegated |
| `llm_action_items_settings` | `analysis.llm_action_items` | 1 | `LLMActionItemsConfig` | `test_llm_action_items_config_delegation.py` | delegated |

### Delegation follow-ups

- Remaining nested dataclasses: `acts`, `topic_modeling`, `speaker_exemplars`, partial flat `analysis_*` slices, dict-profile stores, top-level `LLMConfig` / `OutputConfig`, etc.
- No greenfield module config keys without explicit product scope

### Batch 5 safety rails

| Artifact | Purpose |
|----------|---------|
| `test_registry_ownership.py` | Ownership inventory snapshot; live invariant **51/705/16** (721 total) |
| `test_delegation_shape_snapshots.py` | Pre-delegation default shapes |
| `test_registry_metadata_constraints.py` | Bounded choices/defaults/type agreement |
| `test_pydantic_bridge_drift.py` | Registry + defaults golden completeness (all registry pilots) |
| `test_pydantic_pilot_parity.py` | Dataclass / partial-analysis defaults parity |

### Hardening gates (completed)

| Wave | Artifact |
|------|----------|
| H0 | `test_registry_ownership.py`, generator never rewrites bridge |
| H1 | `test_pydantic_pilot_parity.py` (structural ownership + defaults) |
| H2a | `test_profile_modules_config_integration.py` |
| H2b | `test_nested_file_overrides_probe.py`, `test_analysis_config_visibility.py` roundtrips |
| H3 | `test_validation_consolidation.py` (speaker_gate percentage cap, audio modes) |
| Audit | `test_registry_ownership` visibility, `test_pydantic_bridge_drift` golden completeness, `test_pydantic_registry_converter`, `test_pydantic_bridge_helpers`, `test_generate_pydantic_pilots_policy`, validation error fan-out |
| Settings | `test_settings_pilot_validation.py`, `test_settings_file_load_pilots.py`, `test_validation_fanout.py` |

### Final regression gate

```bash
pytest tests/core/config/ \
  tests/core/utils/config/test_env_key_registry.py \
  tests/core/utils/test_config_loading_contracts.py \
  tests/core/utils/test_config_validation.py \
  tests/integration/extended/test_config_cli_web.py \
  -q
```
