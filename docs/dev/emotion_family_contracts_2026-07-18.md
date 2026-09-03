# Emotion family contracts — 2026-07-18

Three analytically independent modules:

| Module ID | Method | Channel |
|-----------|--------|---------|
| `emotion` | NRCLex lexical vocabulary association | stable (lexical v2) |
| `contextual_emotion` | Softmax broad classifier | experimental until Phase 5 |
| `fine_grained_emotion` | Sigmoid multi-label (GoEmotions-style) | experimental until Phase 5 |

No silent cross-method fallback. Legacy NRC-filled `context_emotion_*` is UI/report-only and must never feed contagion, affect_tension, classifier logic, or group pooling. Modules clear/write **only** their owned projection fields.

## Dual versioning

- `schema_version` — wire/shape (`transcriptx.emotion_result.v1`, `contextual_transcriptx.emotion_result.v1`, `fine_grained_transcriptx.emotion_result.v1`)
- `semantics_version` — analytical meaning (`emotion_lexical_v2`, `contextual_emotion_v1`, `fine_grained_emotion_v1`); no bump for identity/persistence hardening
- Store schemas: `transcriptx.emotion_family_artifact_index.v1`, `transcriptx.emotion_family_generation_manifest.v1`
- Cache schemas: `emotion_family_inference_cache_v3`, `emotion_family_aggregation_cache_v3` (reject older versions without aliasing)

## Generation identity

- `artifact_generation_id` — fresh 32-hex UUID per attempt; names the immutable generation directory and canonical refs
- `inference_generation_id` — stable id of the scoring attempt that produced inference rows; reused on inference-cache hits
- Never replace `artifact_generation_id` with a cached id
- Idempotent persist: existing complete generation with matching `rows_integrity_digest` + `manifest_integrity_checksum` succeeds; conflicting reuse raises; incomplete young dirs are treated as in-progress (not quarantined under the grace window)

## Identity layers

| Layer | Key contents | Busts on |
|-------|--------------|----------|
| Inference | model/tokenizer ids+SHAs, label map, activation, max length, dtype, device class, lib versions, language policy, text digest, transcript revision | model / text / runtime identity |
| Aggregation | `inference_generation_id` + speaker/timeline digests + thresholds + caps + aggregation semantics | threshold / grouping / timeline |
| Projection / presentation | `artifact_generation_id` + schema/semantics + display fingerprint | projection schema / UI ontology |

Thresholds are **not** part of inference compatibility. Device class remains in inference identity (CPU/MPS/CUDA caches are not shared).

## Generational store

- Safe identifiers only (`^[0-9a-f]{32}$` generation IDs; path joins reject traversal/symlink escape)
- Durable atomic writes: restrictive temp perms, flush, fsync, replace, parent-dir fsync; `allow_nan=False` / reject tuple keys
- Exclusive generation directory creation; per-generation `generation_manifest.json` is authoritative
- Index history is a pointer log only; FileLock guards index RMW; corrupt indexes fail closed
- Activate `current_complete_generation` only when `run_status=complete` and `usable_output=true`
- Canonical commit failure is fatal (`EmotionFamilyPersistError`); enriched / secondary outputs are rebuildable — failure sets `enriched_projection_status` / `secondary_output_status` without deactivating
- Shared-segment projections are applied only after successful canonical activation (`_pending_projections`); terminal persist failure clears owned fields without applying pending scores
- `repair_enriched_projections` rebuilds owned fields from validated `current_complete_generation` only (never rewrites canonical rows or activation)
- Orphan GC under index lock quarantines incomplete/unindexed/stale generation dirs after a grace window; abandoned temp prefixes are removed
- Strip `_canonical_rows` from the in-memory result after successful canonical activation
- Consumers resolve `*_canonical_ref` against manifest membership + row integrity checksum + `semantics_version` + `scored_text_hash` (not only text hash)

## Fingerprints / provenance

- `compatibility_fingerprint` — inference analytical identity only
- `runtime_metadata` — visible provenance (resolved revisions, libs, device, dtype, batch size, thresholds for display)
- `display_fingerprint` — UI/grouping only; never partitions analytical compatibility
- Builtin HF profiles pin full 40-char Hub commit SHAs; floating tags (`main`, `latest`, …) are rejected on load

## Run status

`complete` | `partial` | `failed` | `skipped` | `not_applicable`

Downstream optional deps and group pooling require `run_status=complete` AND `segments_scored > 0` AND `usable_output=true`.

Empty failed generations must use `ordered_segment_ids=[]` with empty rows and agreeing counters.

## Contagion / affect_tension

Named branches only: lexical-only from `emotion`, contextual from `contextual_emotion` when the explicit consumer contract is satisfied. Never blend.

- Optional producer `selected` comes from planner/execution `selected_modules`, not artifact presence
- Missing `module_id` or missing scored-text hash on merge → fail closed
- Zero-hit lexical score dicts and abstained/no-label contextual outcomes are not contagious; labeled `"neutral"` remains eligible
- Contagion counts are JSON-safe lists of `{actor, target, emotion, count}`
- affect_tension loads scores only via validated generation integrity — never unvalidated disk rows or in-memory write buffers
- Stale projections (canonical ref generation ≠ active producer generation) are cleared even when text hash still matches

## Charts gallery

Gallery captions and ranks live in [`chart_definitions.json`](../../src/transcriptx/core/utils/chart_definitions.json) (resolved on the Charts page and in exports via artifact `viz_id`). Single-transcript surfaces:

| Module | viz_id | Scope | Notes |
|--------|--------|-------|-------|
| `emotion` | `emotion.radar.global` / `emotion.radar.speaker` | global / speaker_set | Lexical vocabulary-association counts (stable) |
| `emotion` | `emotion.radar_polar.global` / `emotion.radar_polar.speaker` | global / speaker_set | Polar variant of the same profile |
| `contextual_emotion` | `contextual_emotion.label_counts.global` / `.speaker` | global / speaker_set | Softmax label counts (includes neutral); experimental; not blended with lexical |
| `contextual_emotion` | `contextual_emotion.label_counts_excluding_neutral.global` / `.speaker` | global / speaker_set | Absolute counts with neutral omitted |
| `contextual_emotion` | `contextual_emotion.label_share_non_neutral.global` / `.speaker` | global / speaker_set | Each non-neutral label as a share of all non-neutral assignments (sums to 1 when non-empty) |
| `fine_grained_emotion` | `fine_grained_emotion.label_counts.global` / `.speaker` | global / speaker_set | Top-15 native multilabel prevalence (may include neutral); experimental |
| `fine_grained_emotion` | `fine_grained_emotion.label_counts_excluding_neutral.global` / `.speaker` | global / speaker_set | Top-15 after dropping neutral |
| `fine_grained_emotion` | `fine_grained_emotion.label_share_non_neutral.global` / `.speaker` | global / speaker_set | Shares use the **full** non-neutral total as denominator before top-15 truncation; displayed bars may sum to less than 1 |

Exclude-neutral and share charts reuse the same selected category list per scope. They are derived presentation artifacts only: **no bump** to result `schema_version`, `semantics_version`, compatibility fingerprints, or aggregation-cache keys.

Speaker charts emit only for named speakers with non-empty `label_counts` / assignment counts (non-neutral variants additionally require a positive non-neutral total). These single-transcript viz IDs are **not** on the default overview strip. Group temporal/pooled emotion charts remain lexical-session contracts (`group.emotion.*`); see [`group_charts_emotion_temporal_contract.md`](../groups/group_charts_emotion_temporal_contract.md) and [`group_charts_emotion_pooled_contract.md`](../groups/group_charts_emotion_pooled_contract.md).

## Calibration

`threshold_profile_v1` requires separate calibration and held-out fixtures with predefined promotion metrics. Provisional profiles must not be advertised as stable. Channel remains `experimental` until Phase 5 even with pinned SHAs.

## Long-text policy

`long_text_policy_v2` records truncation as `omitted_token_count_lower_bound` (lower bound, not exact omitted count). Effective max length is capped by tokenizer `model_max_length` and model positional limit.
