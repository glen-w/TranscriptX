# Maintainability waves (2026-11-02)

PR-sized, behaviour-preserving refactors from the 2026-11-02 `/refactor` assessment.
No Streamlit rewrite, no dual-config package merge, no `processing_state` epic,
no `SpeakerProfileService` journal rewrite.

**Branch:** `refactor/maintainability-waves`
**Baseline:** `main` @ 1.0.2 (`873468b3`)

## Non-goals (must not land)

- Merging `core.utils.config` with `core.config`
- Replacing Streamlit, adding SQLite, unifying “profile” types
- Changing aggregation output shapes, registry `agg_id`s, or DAG behaviour
- Changing Speaker ID / Speakers / Insights user-visible behaviour
- Changing Settings knob defaults or registry leaf counts (wave 3 is file-split only)

## Wave 1 — Aggregation registry extraction

**Goal:** `registry.py` is a catalog (`AggregationEntry` + `build_registry`). Inline `_aggregate_*` bodies move to `aggregation/aggregators.py`.

**Landed when:**

- `src/transcriptx/core/analysis/aggregation/aggregators.py` holds the moved functions
- `registry.py` re-exports `_aggregate_*` so existing test imports keep working
- Module aggregators (`names`, `keyphrases`, `politeness`, `epistemic_markers`) import helpers from `aggregation.common` instead of `registry`
- Docs (`docs/groups/group_analysis_module_outputs.md`) point at the new module for wordclouds charts
- Aggregation registry tests still pass; no `agg_id` / dep / output_type changes

**Probe scope:** `scoped`. Seeds: group-capable modules implied by aggregation (`stats`, `sentiment`) plus `for_group=True` group probe. Omit `chart_descriptions`.

## Wave 2 — Insights blocks split

**Goal:** Split `web/blocks/implementations/insights.py` along `web_blocks.md` surfaces (contract, highlights, LLM, markers, keyphrases). Re-export public `render_*` names so `builtin.py` and renderer tests do not churn.

**Probe scope:** `skipped` (GUI-only).

## Wave 3 — Config facade file split

**Goal:** Split `core/utils/config/analysis.py` 1:1 with Pydantic model modules. Hydrate behaviour unchanged. No package merge, no golden churn unless imports require it.

**Probe scope:** `skipped` (config facade layout only). Run config ownership tests in light-test.

## Wave 4 — Speakers directory UI split

**Goal:** Move `page_modules/speakers.py` render helpers under `web/ui/speakers/`. Leave `SpeakerProfileService` intact.

**Probe scope:** `skipped` (GUI-only).

## Wave 5 — Speaker ID page extract

**Goal:** Extract session-key namespace + voice callbacks from `page_modules/speaker_id.py` into helpers already used by CCv2. No protocol/service behaviour change.

**Probe scope:** `skipped` (Speaker ID UI; protocol unchanged).

## Wave 6 — Opportunistic coupling

**Goal (only if still cheap after waves 1–5):**

- Break `cache_helpers` ↔ `file_service` import cycle
- Share STT `speaker_label` between granite/nemotron converters
- Peel preflight/save envelope from `EmotionAnalysis.analyze` without changing artifact shape

**Probe scope:** `scoped` only if emotion analyze is split (`emotion`); otherwise `skipped`.

## Close-out

- Developer docs: `docs/dev/COMPLEXITY_GATES.md` or a short architecture note pointing at the new module homes
- `/tests` coverage expansion around extracted helpers
- Incremental version `1.0.3` + tag (user-requested; not the pre-release command)
- `/pre-release` local confidence report
