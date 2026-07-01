Type: PRODUCT
Authority: self

# Pydantic config migration checklist

Incremental adoption pattern for moving config subtrees to Pydantic as the single source of truth for field definitions (defaults, types, validation, bounds, choices, UI metadata).

## Prerequisites

- Keep `TranscriptXConfig` dataclass runtime facade until many subtrees are migrated.
- Keep `env_key_registry.py` as the env compatibility adapter.
- Do not replace resolver temp-file loading until most sections are Pydantic-backed.
- Do not introduce Hydra, Dynaconf, or OmegaConf.

## Generator scripts (regen helpers only)

- [`scripts/generate_pydantic_pilots.py`](../scripts/generate_pydantic_pilots.py) — default (no flags): regenerates model files and golden fixtures; **never** modifies [`pydantic_bridge.py`](../src/transcriptx/core/config/pydantic_bridge.py) (hand-maintained only).
- [`scripts/generate_pydantic_pilots.py --write-bridge`](../scripts/generate_pydantic_pilots.py) — prints **scaffold only** for mechanical `PydanticPilotSpec` rows (imports + tuple entries). Paste into `PYDANTIC_REGISTRY_PILOTS` after review. Does not emit behavioral bridge logic.
- [`pydantic_bridge_helpers.py`](../src/transcriptx/core/config/pydantic_bridge_helpers.py) — shared behavioral helpers (`dotpath_belongs_to_model`, `extract_subtree_overrides`). Covered by [`test_pydantic_bridge_helpers.py`](../../tests/core/config/test_pydantic_bridge_helpers.py).
- [`scripts/generate_dict_profile_models.py`](../scripts/generate_dict_profile_models.py) — regenerates dictionary-profile model files only; never touches the bridge.
- Bridge registration in `pydantic_bridge.py` is **hand-reviewed** in each PR.
- Structural ownership tests in `test_registry_ownership.py` and `test_pydantic_pilot_parity.py` are the source of truth; goldens are snapshot guards only.

## Checklist per subtree

1. **Capture golden snapshot** (before deleting manual enrichers):
   - `tests/core/config/fixtures/<pilot_id>_registry_golden.json`
   - `tests/core/config/fixtures/<pilot_id>_defaults_golden.json` (subtree from `get_default_config_dict()`)

2. **Add Pydantic model** under `src/transcriptx/core/config/models/`.

3. **Register pilot** in `PYDANTIC_REGISTRY_PILOTS` in [pydantic_bridge.py](../src/transcriptx/core/config/pydantic_bridge.py):
   - `pilot_id`, `model`, `dotpath_prefix`, `category`, optional `dataclass_type`

4. **Ensure visibility** — subtree must appear in `TranscriptXConfig.to_dict()` and [file_overrides.py](../src/transcriptx/core/utils/config/file_overrides.py) if file-configurable.

5. **Dataclass parity test** (if runtime dataclass remains):
   - `asdict(Dataclass()) == Model().model_dump()`

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

## End state (migration complete)

**38 Pydantic pilots** own **585** registry leaf keys. The non-pydantic baseline is **10 keys** by design:

| Key | Reason |
|-----|--------|
| `active_*_profile` (7) | Profile activation selectors — permanent legacy |
| `active_workflow_profile` | Workflow profile activation — permanent legacy |
| `use_emojis` | Simple global flag — kept legacy (Wave 9: no empty-prefix bridge) |
| `core_mode` | Install/runtime mode flag — kept legacy (Wave 9: no empty-prefix bridge) |

Wave 9 evaluated two single-key pilots and empty-prefix bridge hacks; **legacy retention** was chosen to avoid destabilizing `collect_model_leaf_dotpaths`, `find_pilot_for_dotpath_key`, and env drift tests.

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
