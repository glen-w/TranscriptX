# BERTopic module

BERTopic is a first-class topic-modeling path alongside LDA/NMF `topic_modeling`.
The **module code is always registered**; the **native stack is optional** at install time.

## Install posture (read this first)

**What worked:** For a stretch the BERTopic Python stack (`bertopic` / `hdbscan` / `umap-learn`) lived in **base** deps and ran fine next to the rest of the product — Docker, GUI, and analysis — when that host could install the wheels.

**What broke the release gate:** Clean **core** wheel installs on some hosts (notably macOS without a usable `llvmlite` wheel) try to **build** `umap-learn` → `numba` → `llvmlite` from source and fail. That made “base install” an unreliable release signal even though BERTopic itself was fine where binaries were available.

**Current rule (does not block builds):**

| Path | BERTopic stack? | Notes |
|------|-----------------|-------|
| `pip install -e .` / core wheel | **No** | Core builds and clean-env audits must stay green without the stack |
| `pip install -e '.[bertopic]'` or `'.[full]'` | **Yes** | Same packages as before; may fail on hosts that cannot get `llvmlite` |
| Docker / `requirements.txt` / `./transcriptx.sh` | **Yes** | Production image still ships the stack |

Runtime behaviour when packages are missing: module stays in the catalogue; runs report `missing_extra:bertopic` / `broken_extra:bertopic` — pipeline continues. This is intentional optional-extra posture, not a broken product.

```bash
pip install -e '.[bertopic]'
# or
pip install -e '.[full]'
```

Sentence Transformers remains a **base** dependency (shared with semantic/echoes). BERTopic reuses that embedding stack once the optional packages are present.

### Host macOS segfault note (OpenMP / Numba oversubscription)

On Apple Silicon host Python, BERTopic’s default UMAP (`n_jobs=-1`) / HDBSCAN (`core_dist_n_jobs=-1`) can **segfault** during `fit_transform` (process exit -11) when OpenMP and Numba pools oversubscribe — especially after other modules have already loaded natives.

Mitigations shipped in runtime:

- Early `ensure_native_thread_env_defaults()` (pipeline / web entry / bootstrap)
- Explicit UMAP/HDBSCAN backends with `n_jobs=1` / `core_dist_n_jobs=1` via `build_model_kwargs()`
- **Subprocess-isolated fit** (`transcriptx.core.utils.bertopic_fit`) so a residual SIGSEGV after a long in-process pipeline becomes a soft module failure instead of killing the parent run
- `limited_native_threads(1)` inside the worker

The package is **not on PyPI**; install from this repository (see [install_verification_matrix.md](../runtime/install_verification_matrix.md)).

> **Public release:** runtime install markers are **`core` | `full` only**. See [installation.md](../runtime/installation.md) and [dependency_audit.md](dependency_audit.md). Host `.[bertopic]` / `.[full]` is **not** a blocking clean-env proof when `llvmlite` cannot install; Docker `image_pip_check` is the production-image proof for the fuller stack.

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
| Module picker | `module_ui_groups` → Language & Meaning; included in recommended defaults |
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
| `timeout_seconds` | `3600` | `TRANSCRIPTX_BERTOPIC_TIMEOUT_SECONDS` | Wall-clock fit budget; timeout continues pipeline |

Cache fingerprints include the shaping knobs plus `timeout_seconds`. `label_words` is label-shaping only (not a BERTopic ctor arg).

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

Record wheel vs source compilation (esp. HDBSCAN) per platform run. Hosts that cannot install `llvmlite` skip the optional stack; they must not fail **core** / clean-env gates.
