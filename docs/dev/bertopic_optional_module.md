Type: GUIDE
Authority: self

# BERTopic module

BERTopic is a first-class topic-modeling path alongside LDA/NMF `topic_modeling`.

## Install (current)

BERTopic packages (`bertopic`, `hdbscan`, `umap-learn`) are in the **default** install for now:

```bash
pip install transcriptx
# Compat alias (packages already satisfied from base):
# pip install 'transcriptx[bertopic]'
```

Sentence Transformers remains a base dependency (shared with semantic/echoes).

> **Public release:** install profiles will split more clearly (e.g. basic / full / llm) so this stack can move back behind an opt-in profile. See [installation.md](../runtime/installation.md).

## Lifecycle states

| State | Detection | Heavy import? |
|-------|-----------|---------------|
| Registered | Specs + `MODULE_CLASS_MAP` | No |
| Package detected | `is_extra_distribution_present("bertopic")` via `importlib.metadata` | No |
| Import verified | Execution preflight `import bertopic` | Yes |
| Attempted / completed | Module run finished | Yes |

Catalogue/UI must **not** call importing `is_extra_available("bertopic")`.

Missing vs broken (degraded installs / broken natives):

- `missing_extra:bertopic` — distribution metadata absent
- `broken_extra:bertopic` — metadata present, import/native load fails

Auto-install is **off** (`auto_install=False`).

## Group aggregation

Group BERTopic **refits from pooled source segments** (via `TranscriptService`), not from transcript-level topic IDs. Member artifacts are activation/status only. Aggregation registry: `selector=any_of(["bertopic"])`, `deps=[]`.

Ordering:

- Transcript: `segment_index` ascending
- Group: `(transcript_id, segment_index)` ascending

Duplicates are retained as separate documents. All-outlier fits are **succeeded** with `meta.all_outlier=true` and emit **no** chart specifications.

## UI / charts / export surfaces

| Surface | Wiring |
|---------|--------|
| Module picker | `module_ui_groups` → Language & Meaning; `exclude_from_default=True` (opt-in) |
| Chart registry | `bertopic.topic_word_heatmap.global`, `bertopic.topic_prevalence.global`, `group.bertopic.pooled.topic_share.global` in `chart_definitions.json` |
| Charts page | Manifest artifacts with `meta.viz_id` resolve descriptions via `resolve_chart_display_description` |
| Artifacts / zip export | Standard manifest discovery under `bertopic/`; charts zip includes any selected chart artifacts (no module denylist) |
| Summary extractor | `web/summary_extractors/bertopic.py` |
| Group charts | `BertopicGroupChartGenerator` + [pooled contract](../groups/group_charts_bertopic_pooled_contract.md) |
| Catalog | [generated/modules.md](../generated/modules.md) |

## Configurable knobs

All knobs live under `analysis.bertopic` (config.json / Settings UI) and have matching env overrides. Defaults match `BERTopicSettingsModel`.

| Knob | Default | Env | Notes |
|------|---------|-----|-------|
| `embedding_model` | `all-MiniLM-L6-v2` | `TRANSCRIPTX_BERTOPIC_EMBEDDING_MODEL` | Primary quality/speed trade-off |
| `min_topic_size` | `5` (≥2) | `TRANSCRIPTX_BERTOPIC_MIN_TOPIC_SIZE` | Smaller → more topics |
| `nr_topics` | `auto` | `TRANSCRIPTX_BERTOPIC_NR_TOPICS` | `auto` or positive integer string |
| `top_n_words` | `10` | `TRANSCRIPTX_BERTOPIC_TOP_N_WORDS` | Words kept per topic |
| `label_words` | `3` | `TRANSCRIPTX_BERTOPIC_LABEL_WORDS` | Words joined into display labels |
| `calculate_probabilities` | `false` | `TRANSCRIPTX_BERTOPIC_CALCULATE_PROBABILITIES` | Soft probs; slower |

Cache fingerprints include all six paths. `label_words` is label-shaping only (not a BERTopic ctor arg).

## Offline / models

Package install ≠ model download. Hub embedding IDs get syntax checks only; local paths are existence-checked. Real model usability is known at load/fit. Set `TRANSCRIPTX_DISABLE_DOWNLOADS=1` in CI; provision a controlled cache for real offline smoke.

## Verify

```bash
python -c "from bertopic import BERTopic; print('ok')"
pytest tests/core/analysis/test_bertopic_shaping_helpers.py tests/contracts/test_bertopic_optional_extra.py -q
# Optional real-model smoke (downloads allowed, isolated HF cache):
# TRANSCRIPTX_DISABLE_DOWNLOADS=0 HF_HOME=/tmp/tx-hf-cache pytest tests/optional/test_bertopic_real_model_smoke.py -q
```

## Release platforms (blocking)

| Platform | Python | Role |
|----------|--------|------|
| Linux x86_64 | 3.10, 3.11, 3.12 | Blocking — install + smoke |
| macOS Apple Silicon | 3.11 | Blocking |
| macOS Intel | any | Non-blocking |

Record wheel vs source compilation (esp. HDBSCAN) per platform run.
