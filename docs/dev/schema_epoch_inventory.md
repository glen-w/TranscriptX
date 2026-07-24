Type: PRODUCT
Authority: self

# Schema epoch inventory (1.0)

**Status:** **implemented in 0.9.3** — public schema targets are integer **`1`** only (no dotted `.x` forms); data-root marker + remediation UX shipped  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §8  
**Package baseline:** 0.9.3 (epoch implementation)  
**Approved:** 2026-07-24 (owner clean-slate + integer-1 standardisation); **cut:** 2026-07-24 as `v0.9.3`

## Locked convention

1. Classify every version-like value before changing it.
2. **Public persisted schema versions are integers only** — use **`1`**, never `"1.0"`, `"2.0"`, or other dotted `.x` forms.
3. Canonical transcript / speaker-map / state envelopes that today use `"1.0"` or `"2.0"` **→ integer `1`** in the epoch.
4. Public persisted string schema IDs → **`transcriptx.<domain>.v1`** (`.v1` suffix is an ID token, not a dotted schema number).
5. Refuse or isolate pre-epoch artifacts; **no** long-lived compatibility adapters for wiped pre-public data.
6. Write **`schema_epoch` / public-schema epoch marker** at managed data-root; detect early; explain clearly in GUI and supported remediation surfaces (**not** a new public analysis CLI).
7. **Never** renumber, reuse, or reset public schema IDs after 1.0.
8. **Policy / prompt / algorithm-semantics / cache identity** strings are not public `schema_version` numbers — do not cosmetic-reset them unless the inventory row says so. Prefer leaving them unchanged across the epoch.

## Retain / wipe decisions (approved)

| Asset | Decision |
|-------|----------|
| Compatible managed transcripts (content) | **Retain** (or reimport); schema stamp → integer `1` |
| Source recordings | **Retain** — never touch for epoch neatness |
| Speaker-map sidecars | **Owner clean-slate:** backed up then removed from live trees for testing; restore from backup when needed. Live schema stamp → integer `1` (today often `"1.0"`) |
| Speaker profiles / voice | **Owner clean-slate:** backed up then removed from live `data/speaker_profiles` for testing |
| Other incompatible derived state (run outputs, manifests/`run_results`, caches, indexes, groups, corrections, cleanup journals, local config overrides as needed) | **Refuse / remove** via supported reset path only |
| Automatic deletion without user action | **Forbidden** (owner-driven wipe for testing is explicit and separate) |

### Backup location (2026-07-24)

`/Users/89298/Documents/transcriptx backup/epoch_clean_slate_2026-07-24/`

- `library_transcripts_speaker_maps/` — from `/Users/89298/Documents/transcripts/metadata/speaker_maps` (168 files)
- `working_tree_speaker_maps/` — from repo `data/transcripts/**/*.speaker_map.json`
- `working_tree_speaker_profiles/` — from repo `data/speaker_profiles`

### `speaker_id_to_db_id`

Treat as **legacy / unused** for current product (no DB-backed speaker features in 0.9.x). Sidecars may still contain an empty `{}` object. Do not invent new DB linkage in the epoch; safe to keep the field as an empty object for wire compatibility or drop in a later cleanup once readers tolerate absence.

## Inventory rows

Paths abbreviated under `src/transcriptx/`.

### Public persisted → integer `1` / rename string IDs

| path | current | class | action | tests / fixtures | notes |
|------|---------|-------|--------|------------------|-------|
| `core/pipeline/module_outcomes.py` `RUN_RESULTS_SCHEMA_VERSION` | `2` | public_persisted | **→ 1** | run outcome / contract tests | Highest impact |
| `web/services/run_cleanup/models.py` `CLEANUP_RESULT_SCHEMA_VERSION` | `2` | public_persisted | **→ 1** | cleanup tests | |
| `web/layouts/specs.py` `CURRENT_LAYOUT_SCHEMA_VERSION` | `2` | public_persisted | **→ 1** | layout store tests | Drop dual-accept after wipe |
| `core/config/persistence.py` `CONFIG_SCHEMA_VERSION` | `1` | public_persisted | keep `1` | config tests | |
| `speaker_profiles/versioning.py` `SCHEMA_VERSION` | `1` | public_persisted | keep `1` | speaker profile tests | |
| `speaker_profiles/voice/versioning.py` `VOICE_SCHEMA_VERSION` | `1` | public_persisted | keep `1` | voice tests | |
| `services/corrections_studio/normalize.py` `STUDIO_SCHEMA_VERSION` | `2` | public_persisted | **→ 1** | corrections tests | |
| `core/utils/state_schema.py` `STATE_SCHEMA_VERSION` | `"2.0"` | public_persisted | **→ `1`** (integer; no dotted form) | state tests | |
| `io/import_metadata/schema.py` `SIDECAR_SCHEMA_VERSION` | `1` | public_persisted | keep | import tests | |
| `io/import_admission.py` `SCAN_HANDLE_SCHEMA_VERSION` | `1` | public_persisted | keep | admission tests | |
| `web/action_menus/prefs.py` `INTERFACE_SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `observability/run_performance/schema.py` `RUN_PERFORMANCE_SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/pipeline/manifest_builder.py` `SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/pipeline/contracts.py` `SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/analysis/bertopic/schema.py` `SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/analysis/transcript_quality/analyze.py` `SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/analysis/interactions/graph_export.py` `SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/analysis/group_llm_synthesis/schemas.py` `COLLECT_SCHEMA_VERSION` | `1` | public_persisted | keep | | |
| `core/analysis/llm_support/action_items_contract.py` `LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION` | `2` | public_persisted | **→ 1** | group LLM tests | |
| `core/analysis/llm_custom_qa/versioning.py` `COMMIT_MARKER_SCHEMA_VERSION_V1` / `_V2` | `"1"` / `"2"` | public_persisted | **Rename** to a single `COMMIT_MARKER_SCHEMA_VERSION = 1` (integer); delete `_V1`/`_V2` symbol names | custom QA tests | Dual live markers + `V2` in the name are confusing once everything is epoch-1; collapse writers/readers to one constant |
| Speaker-map wire `speaker_map_schema_version` | `"1.0"` | public_persisted | **→ `1`** | mapping service / fixtures | Written by `SpeakerMappingService` |
| `core/analysis/emotion/lexical_pipeline.py` `SCHEMA_VERSION` | `transcriptx.emotion_result.v1` | public_persisted | **→ `transcriptx.emotion_result.v1`** | emotion fixtures | |
| `core/analysis/contextual_emotion/__init__.py` `SCHEMA_VERSION` | `contextual_transcriptx.emotion_result.v1` | public_persisted | **→ `transcriptx.contextual_emotion_result.v1`** | | |
| `core/analysis/fine_grained_emotion/__init__.py` `SCHEMA_VERSION` | `fine_grained_transcriptx.emotion_result.v1` | public_persisted | **→ `transcriptx.fine_grained_emotion_result.v1`** | | |
| `core/analysis/topic_shift/semantics.py` `SCHEMA_VERSION` | `transcriptx.topic_shift_result.v1` | public_persisted | **→ `transcriptx.topic_shift_result.v1`** | | |
| `core/analysis/topic_shift/enrichment.py` `ENRICHMENT_SCHEMA` | `transcriptx.topic_shift_enrichment.v1` | public_persisted | **→ `transcriptx.topic_shift_enrichment.v1`** | | |
| `core/analysis/topic_shift/store.py` `INDEX_SCHEMA` | `transcriptx.topic_shift_artifact_index.v1` | public_persisted | **→ `transcriptx.topic_shift_artifact_index.v1`** | | |
| `core/analysis/emotion_family/generational_store.py` index/manifest | `emotion_family_*_v1` | public_persisted | **→ `transcriptx.emotion_family_*.v1`** | | |

### Canonical transcript → integer `1`

| path | current | class | action | notes |
|------|---------|-------|--------|-------|
| `domain/canonical_transcript.py` `CANONICAL_SCHEMA_VERSION` | `"1.0"` | canonical_transcript | **→ `1`** | No dotted forms |
| `io/transcript_schema.py` `SCHEMA_VERSION` | `"1.0"` | canonical_transcript | **→ `1`** | Fixtures/goldens must follow |

### Contract string IDs

| path | current | action |
|------|---------|--------|
| `llm_support/action_items_contract.py` `LLM_ACTION_ITEMS_SCHEMA_ID` | `transcriptx.llm_action_items.v2` | **→ `.v1`**; remove v1 coerce after wipe |
| `llm_custom_qa/versioning.py` `V2_SCHEMA_ID` | `transcriptx.llm_custom_qa.v2` | **→ `.v1`** as sole live ID |
| Already-`transcriptx.*.v1` IDs | `…v1` | keep |
| `llm_feedback/models.py` `EVENT_SCHEMA_ID` | `transcriptx.llm_feedback_event.v1` | **→ `transcriptx.llm_feedback_event.v1`** |
| `speaker_profiles/versioning.py` `*_SCHEMA_ID` | `speaker_profile*.v1` | **→ `transcriptx.speaker_profile*.v1`** |
| `speaker_profiles/voice/versioning.py` voice schema ids | `voice_*.v1` | **→ `transcriptx.voice_*.v1`** |

### Journal / policy / cache / semantics / prompt / package

| path | current | class | action |
|------|---------|-------|--------|
| `web/services/run_cleanup/models.py` `JOURNAL_SCHEMA_VERSION` | `3` | journal | **→ `1`** (integer epoch; no dotted form) |
| `core/utils/rename/journal.py` `JOURNAL_SCHEMA_VERSION` | `1` | journal | keep |
| `web/services/run_cleanup/models.py` `CLEANUP_POLICY_VERSION` | `7` | policy | **keep** (behaviour generation, not schema envelope) |
| Other policy IDs | various | policy | **keep** |
| emotion_family / clip / voice excerpt cache versions | v3 / 2 / 1 | cache | **keep** unless wipe invalidates caches deliberately |
| algorithm / semantics / prompt versions | various | non-schema | **keep** method fingerprints; see **Public module ids** below for `_vN` in registry names |
| `pyproject.toml` / `__version__` | `0.9.2` | package | bump via normal release when epoch implementation ships |

### Public analysis module ids (not schema envelopes)

Registry scan: **`semantic_similarity` is the only public module id / package that embeds a `_vN` suffix.** Older siblings still exist as unversioned legacy ids (not named `_v1`).

| Module id | Package | Status today | Epoch / 1.0 action |
|-----------|---------|--------------|--------------------|
| `semantic_similarity` | `core/analysis/semantic_similarity/` | Default / current product path; `SCHEMA_VERSION = "semantic_similarity.1.1"` is method identity | **Rename** → `semantic_similarity` after legacy retirement (registry, package dir, config `analysis.semantic_similarity*`, UI presets, profile ids `*_v2`, artifact basenames, docs). Retarget method string so it does not imply a second live module (e.g. keep a semantics fingerprint without requiring `_v2` in the **module id**). |
| `semantic_similarity` | `core/analysis/semantic_similarity/` | `legacy: True` | **Retire / remove** from public registry (no reason to keep a parallel legacy module for 1.0) |
| `semantic_similarity_advanced` | same legacy package | `legacy: True` | **Retire / remove** |
| `llm_custom_qa` | `…/llm_custom_qa/` (`analyze_v2.py` internal) | Public id already unversioned | **Keep module id**; collapse dual commit-marker / schema-id writer symbols (see row above) |

**Why not “keep `_v2` as method identity” forever:** same naming smell as `COMMIT_MARKER_SCHEMA_VERSION_V2` — the product default should not look like a temporary upgrade path. Group aggregation already uses unversioned agg id `semantic_similarity` while preferring `semantic_similarity` payloads — rename aligns those.

**Breakage surface if renamed without retiring legacy:** config/presets collision on id `semantic_similarity`; must delete or archive legacy modules first. Owner clean-slate / pre-public wipe means **no long-lived module-id alias map** is required.

**Near misses (not public module ids):** artifact schema strings (`transcriptx.emotion_result.v1`), profile keys (`fast_v2`), voice output path `voice/v1/` — handled under schema-id / layout rules, not module rename.

## Compatibility helpers to archive/remove after reset

| Location | Role |
|----------|------|
| `pipeline/module_outcomes` run_results support gate | Update to epoch-1 only |
| `web/layouts/store.py` layout schema dual-accept | Drop pre-epoch after wipe |
| `web/services/run_cleanup/journal.py` schema decode dispatch | Epoch-1 journal only after reset |
| `llm_support/action_items_contract.py` v1 coerce | Remove after wipe |
| `llm_custom_qa` dual V1/V2 readers | Collapse to epoch-1 |
| `core/utils/state_schema.migrate_state_entry` | Replace with refuse/remediate for pre-epoch |
| Readers accepting `"1.0"` / `"2.0"` dotted schema stamps | Accept integer `1` only after migration |
| Emotion/corrections legacy payload builders | Remove or quarantine post-wipe |
| Legacy semantic modules + `semantic_similarity` id | Retire legacy; rename v2 → unversioned `semantic_similarity` (see Public module ids) |
| `llm_custom_qa` `COMMIT_MARKER_SCHEMA_VERSION_V1`/`_V2` | Single `COMMIT_MARKER_SCHEMA_VERSION = 1` |

## Transition UX design

Keep within **existing public surfaces** — no new public analysis CLI.

### Proposed behaviour

1. **Data-root marker:** write `schema_epoch` (or equivalent) at managed data root when creating/opening an epoch-1 store.
2. **GUI preflight:** on app start / library open, detect missing or pre-epoch marker; block principal work with clear copy naming the incompatible root.
3. **Remediation choices (no auto-delete):**
   - Create fresh data directory (recommended default path)
   - Optional inventory/export of compatible transcripts before reset
   - Supported reset of incompatible **derived** state only (with reset report)
   - Backup guidance link to docs (owner backup path documented above)
4. **Typed Python workflow / internal maintainer utility:** same detection + remediation for automation; not advertised as analysis CLI.
5. **Tests:** recordings never touched; compatible transcripts retained by default; epoch-1 store opens in later 0.9.x / 1.0 candidates.

### Checklist

- [x] GUI preflight detects incompatible roots before work begins
- [x] Typed Python workflow and/or internal maintainer utility
- [x] Optional inventory/export before reset path
- [x] Explicit “create fresh data directory” path
- [x] No automatic deletion of user data
- [x] Precise identification of which root is incompatible
- [x] Backup guidance in GUI/docs
- [x] Reset report when supported reset path is used
- [x] Tests proving unrelated source recordings are never touched
- [x] Retain decision for managed transcripts recorded (retain / reimport OK)
- [x] Validation that a 0.9 epoch-1 store opens unchanged later (epoch-1 marker + stamps frozen in **0.9.3**; reconfirm on later 0.9.x / 1.0 candidates)

## Doc / script locations referencing old versions

| location | what it encodes | update in epoch PR? |
|----------|-----------------|---------------------|
| `docs/contracts/output-contract-v1.md` | run_results schema_version 2; speaker_map `"1.0"` | yes → integer `1` |
| `docs/run_outcome_contract.md` | run truth / schema refs | yes |
| `docs/contracts/speaker_profiles_*.md` | schema_ids | yes if renamed |
| `docs/contracts/llm_feedback_v1.md` | event schema id | yes if renamed |
| Fixtures under `tests/fixtures/` encoding schema_version 2 / `"1.0"` / `*_v2` | wire values | yes — regenerate |
| Goldens / characterization dumps | | yes |
| This inventory | actions | mark done after epoch |

## Sign-off

- [x] Inventory rows drafted for known version-like constants
- [x] Retain/wipe decisions accepted (incl. owner clean-slate backup of maps/profiles)
- [x] Transition UX design proposed
- [x] **Integer-only public schemas → `1`** (no dotted `.x` forms) standardised
- [x] **Human sign-off — ready for epoch implementation** (2026-07-24)
