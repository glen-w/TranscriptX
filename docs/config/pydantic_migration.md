Type: PRODUCT
Authority: self

# Pydantic config migration checklist

Incremental adoption pattern for moving config subtrees to Pydantic as the single source of truth for field definitions (defaults, types, validation, bounds, choices, UI metadata).

## Prerequisites

- Keep `TranscriptXConfig` dataclass runtime facade until many subtrees are migrated.
- Keep `env_key_registry.py` as the env compatibility adapter.
- Do not replace resolver temp-file loading until most sections are Pydantic-backed.
- Do not introduce Hydra, Dynaconf, or OmegaConf.

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
| `dashboard_display` | `dashboard` (display fields only) | `DashboardConfig` (partial) |
| `llm` | `llm` | `LLMConfig` |
| `acts` | `analysis.acts` | `ActsConfig` |

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

## Future candidates

- `output.*` — replace manual `dynamic_charts` / `dynamic_views` enrichers
- `dashboard.*` overview — `overview_charts`, `overview_missing_behavior`, `overview_max_items`
- Other `analysis.*` nested configs
