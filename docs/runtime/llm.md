Type: GUIDE
Authority: runtime/docker.md

# Local LLM integration (Ollama)

LLM-backed analysis modules are **disabled by default**. Enable them only when you have a local Ollama daemon (or another configured endpoint) and understand that prompts may contain sensitive transcript content.

## Configuration

Environment variables (highest precedence):

```bash
export TRANSCRIPTX_LLM_ENABLED=1
export TRANSCRIPTX_LLM_PROVIDER=ollama
export TRANSCRIPTX_LLM_MODEL=qwen3:8b
export TRANSCRIPTX_LLM_BASE_URL=http://localhost:11434
export TRANSCRIPTX_LLM_SEED=42
```

Or in `config.json`:

```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "model": "qwen3:8b",
    "base_url": "http://localhost:11434",
    "seed": 42,
    "request_timeout": 1350,
    "max_input_chars": 48000,
    "default_temperature": 0.3
  }
}
```

Configure timeout via `llm.request_timeout` / `TRANSCRIPTX_LLM_REQUEST_TIMEOUT` (default **1350** seconds / 22.5 minutes).

**Remote endpoints:** the default `base_url` is local. A non-local URL sends transcript content to that endpoint. TranscriptX does not block remote URLs but you are responsible for where your data is sent.

## Run Analysis model selection

On **Run Analysis** (Transcript, Group, and Batch), when `llm.enabled` and `provider=ollama`, you can:

- Use **one shared model** for all LLM consumers, or **select per module**
- Load / save **LLM model profiles** (ProfileManager target `llm_models`, stored under `.transcriptx/profiles/llm_models/`)
- Inspect a collapsible table of **installed Ollama models** and what transcript LLM tasks they are best for (to guide per-module picks)

Per-run selections are snapshotted onto the analysis request and do **not** rewrite `llm.model` unless you save a profile and optionally set it as the project active profile (Settings → Configuration → Active Profiles, or the save checkbox on the run form).

**Resolution precedence** for each LLM consumer (`narrative_summary`, `llm_summary`, `llm_speaker_summary`, `llm_action_items`, `chart_descriptions`, `group_llm_synthesis`):

1. Request override from Run Analysis / Batch
2. Active `llm_models` profile applied onto `llm.model_selection`
3. Global `llm.model` / default (`qwen3:8b`)

Effort-profile `model` fields are **not** part of this chain when a consumer id is set. Corrections Studio (no consumer id) may still use an effort-profile model over global `llm.model`.

On the run form, **Project default (active)** loads the already-applied project `llm.model_selection` pack. **Custom (this run)** keeps free-edited widgets for this launch only. Unavailable saved tags are cleared with an explanation (no silent substitute); launch stays gated until an installed model is chosen.

If LLM is disabled or the provider is not Ollama while selected modules (or enabled group synthesis) need LLM, the launch button stays disabled.

**Thinking models (JSON-unsafe):** tags matching `qwen3*`, `deepseek-r1*`, and `gpt-oss*` often put tokens in Ollama’s `thinking` field and leave `response` empty when TranscriptX requests `format=json`. That fails `narrative_summary`, `llm_action_items`, `chart_descriptions`, and `group_llm_synthesis`. The Run Analysis model selector **hides** those tags from shared picks whenever any JSON module is selected, and from per-module rows for JSON consumers. Launch stays gated if a saved profile still assigns a thinking tag to a JSON consumer. Prefer non-thinking tags such as `gemma3:*`, `qwen2.5:*`, `llama3.2:*`, or `mistral:*` for those modules (plain-text `llm_summary` / `llm_speaker_summary` may still work with thinking models).

If a selected model is missing at generate time, the LLM consumer fails with a clear model-missing error (no silent substitute). Corrections Studio continues to use global `llm.model` only.

## Modules

| Module | Description | Depends on |
|--------|-------------|------------|
| `narrative_summary` | Grounded executive narrative from deterministic `summary` output (temperature 0.0, JSON) | `summary` chain (highlights + upstream) |
| `llm_summary` | Abstractive transcript summary from readable transcript text (plain text, `default_temperature`) | segments only |
| `llm_speaker_summary` | Abstractive summary per **named** speaker from that speaker's utterances only (plain text, `default_temperature`) | segments + speaker labels |
| `llm_action_items` | Structured action items (owner, deadline, status, quote) from transcript text (strict JSON, `default_temperature`) | segments + speaker labels |
| `chart_descriptions` | Finalize-phase per-chart LLM narratives (temperature 0.0, JSON). Excluded from DAG execution; run by the run-finalization coordinator after all charts exist | selected + `analysis.chart_descriptions.enabled` + LLM enabled |

All LLM modules except finalize-phase `chart_descriptions` are included in the **recommended** default module list when enabled. `chart_descriptions` is selectable and recommended with other LLM modules but executes only in finalization. Uncheck **Use recommended modules** in Run Analysis (or pass an explicit `modules` list via the API) to opt out. When LLM is disabled they are **skipped** before execution (not failed) with reason `LLM disabled`. For `chart_descriptions`, a skipped generation is still **committed** (ACTIVE + epoch) with **zero client calls**.

### `analysis.chart_descriptions`

```json
{
  "analysis": {
    "chart_descriptions": {
      "enabled": true,
      "chart_set": "all"
    }
  }
}
```

- **`enabled`** (default `true`): gate with module selection and LLM enabled.
- **`chart_set`**: `all` (default) | `transcript_group` | `overview_only`.
- Layout: `.chart_descriptions/LATEST_ATTEMPT.json`, `ACTIVE.json`, `generations/<id>/` with COMMIT/index/outcome/descriptions.
- Resolvers require ACTIVE.attempt_epoch to match LATEST_ATTEMPT (suppresses stale text after crash).
- Ordering: chart-description publish → group LLM synthesis → single manifest write under one run-finalization lock.


**Privacy:** transcript text for LLM modules (`llm_summary`, `llm_speaker_summary`, `llm_action_items`, and structured input to `narrative_summary`) is sent only through the configured Ollama path (`llm.provider=ollama`). TranscriptX does not block non-local `base_url` values, but you are responsible for where your data is sent; the default is loopback (`http://localhost:11434`). Group LLM synthesis sends **member summary texts only** (not raw transcripts) over the same Ollama path.

`llm_speaker_summary` is skipped when the transcript has no eligible named speakers (for example, before Speaker ID mapping). Ignored speakers are excluded.

Selecting `narrative_summary` automatically runs the `summary` dependency chain first.

## Group LLM synthesis

After group finalize collects per-member `llm_summary` / `llm_speaker_summary` artifacts, an optional **cross-session synthesizer** writes generation-scoped rollups under `.group_llm_synthesis/` (ACTIVE/COMMIT). See [group_llm_synthesis_contract.md](../groups/group_llm_synthesis_contract.md).

```json
{
  "analysis": {
    "group_llm_synthesis": {
      "enabled": true,
      "effort": "high"
    }
  }
}
```

- **`enabled`** (default `true`): when false, finalize commits a skipped generation and flips ACTIVE so prior success is no longer shown.
- **`effort`**: same tiers as `llm_summary`. Resolves **effective** `max_input_chars` / `request_timeout` / `max_output_tokens` for synthesis calls only; it does **not** mutate process-global `llm.*` values used by other modules.
- **Ollama-only:** non-Ollama or disabled LLM → skipped generation (not a hard group failure).
- **UI:** group Overview/Insights use the central resolver; no member-summary primary fallback on group runs.

## `llm_summary` effort (not `llm.effort`)

The setting **`analysis.llm_summary.effort`** controls summary effort for the **`llm_summary` module only** (full-transcript abstractive summary). It is **not** `llm.effort` and does **not** affect `narrative_summary`, global `llm.*` provider settings, or other analysis modules.

Valid values: `low`, `medium`, `high`, `max` (default: `high`).

```json
{
  "analysis": {
    "llm_summary": {
      "effort": "medium"
    }
  }
}
```

When `llm.enabled` is true and `llm.provider` is `ollama`, `llm_summary` resolves builtin effort profiles that set `max_input_chars`, `request_timeout`, and `max_output_tokens` for that module run. Those effort limits **replace** the corresponding `llm.*` values for `llm_summary` only; they are not merged with user-tuned `llm.max_input_chars` / `llm.request_timeout` / `llm.max_output_tokens`. The model still defaults to `llm.model` unless a future profile sets an override.

**Tier intent:**
- `low` — useful preview mode
- `medium` — default completeness-oriented mode for normal long transcripts (not legacy `llm.*` defaults)
- `high` — patient mode for long meetings, workshops, lectures, and dense transcripts
- `max` — push-the-laptop mode; prefers waiting over truncating or timing out

This pass supports `provider="ollama"` only for `llm_summary`, `llm_speaker_summary`, and `llm_action_items`; other non-null providers raise configuration errors. Shared eligibility is enforced via `require_ollama_analysis` in `core/analysis/llm_support/runtime.py`, which also owns the shared effort-profile map (`resolve_llm_runtime`), the analysis Ollama client factory (`build_ollama_analysis_client`), and input-coverage provenance (`build_input_coverage`). These helpers are shared by all three transcript-direct modules; there are no summary-specific aliases.

Artifact provenance records `effort`, `effort_profile`, resolved limits, and input coverage (`input_truncated`, `input_chars_total`, `input_chars_used`, `input_coverage_ratio`). The legacy `input_chars` field remains the full prompt size including wrapper text.

## `llm_speaker_summary` effort

The setting **`analysis.llm_speaker_summary.effort`** controls per-speaker summary effort for the **`llm_speaker_summary` module only**. It uses the same builtin tiers as `llm_summary` (`low`, `medium`, `high`, `max`; default **`high`** in code).

```json
{
  "analysis": {
    "llm_speaker_summary": {
      "effort": "high"
    }
  }
}
```

Each named speaker triggers one sequential Ollama call over that speaker's utterances. Per-speaker failures (for example, an empty model response) are recorded in the index artifact; the module succeeds when at least one speaker summary is written.

**Artifacts:**

- `llm_speaker_summary/data/speakers/{base}_{Speaker}_llm_speaker_summary.json` (+ `.md`) per speaker
- `llm_speaker_summary/data/global/{base}_llm_speaker_summary_index.json` (+ `.md`) listing speakers and statuses

## `llm_action_items` effort

The setting **`analysis.llm_action_items.effort`** controls action-item extraction effort for the **`llm_action_items` module only**. It uses the same builtin tiers as `llm_summary` (`low`, `medium`, `high`, `max`; default **`high`** because extraction is completeness-oriented across long meetings).

```json
{
  "analysis": {
    "llm_action_items": {
      "effort": "high"
    }
  }
}
```

**Artifacts:**

- `llm_action_items/data/global/{base}_llm_action_items.json` (+ `.md`)

### Output contract

`schema_id`: `transcriptx.llm_action_items.v1`

| Field | Notes |
|-------|-------|
| `items[]` | Ordered list; empty list is a successful result |
| `items[].text` | Non-empty trimmed action description |
| `items[].owner` / `deadline` | Verbatim transcript wording or `null` (no entity/date normalisation in v1) |
| `items[].status` | `open` \| `done` \| `unclear` — `done` only when completion is explicit; do not infer from tense alone |
| `items[].quote` | Exact transcript substring after whitespace normalisation, or `null` |
| `items[].confidence` | Finite float in `[0, 1]` |
| `diagnostics` | `items_parsed`, `items_grounded`, `items_dropped`, `quotes_nulled` |
| `provenance` | Includes `module_version`, `prompt_version`, `cache_key`, effort/runtime, input coverage |

Malformed model JSON, unknown keys, or invalid fields fail with `llm_invalid_response` — no partially trusted items are stored. Ungrounded quotes are set to `null` (confidence reduced); items that cannot be grounded on text or quote are dropped. Deduplication prefers grounded quotes and higher confidence; ordering uses transcript occurrence of quote/text with stable model-order fallback.

Identity for future caching is a distinct namespace (`provenance.cache_key`); it is not shared with `llm_summary` artifacts.

### UI and export

- **Insights** layout (`default`, `executive`): block `llm_action_items_block` renders Markdown or a structured table.
- **Overview** module metrics: summary extractor surfaces item counts by status.
- **Zip export**: JSON/MD are included in module/data exports; `index.html` lists an **Action Items** summary section (see `resolve_export_text_summaries` in `export_index.py`).

## Truncation

`llm_summary` and other transcript-direct Ollama modules (including `llm_action_items`) cap the full user prompt (instructions, delimiters, and transcript block) to an input budget using the existing head/tail truncation algorithm. On the Ollama effort path, the budget comes from the selected effort profile's `max_input_chars`. When the formatted transcript exceeds the budget, TranscriptX uses a deterministic **head/tail** strategy:

- Reserve space for an omission marker in the middle.
- Allocate roughly **60%** of the remaining budget to early segments and **40%** to late segments (whole segments only).
- Long transcripts may omit middle material; provenance records `truncated`, segment counts, and `truncation_strategy`.

## Error codes

Failed LLM modules return `execution_status=failed` with a stable `error_code` in `module_result` and `run_results.json` (`module_outcomes`):

| Code | Meaning |
|------|---------|
| `llm_unavailable` | Daemon unreachable after retries |
| `llm_model_missing` | Configured model not installed |
| `llm_timeout` | Request timed out after retries |
| `llm_invalid_response` | Malformed JSON, wrong shape, empty response, or invalid narrative JSON |
| `llm_generation_error` | Non-retryable HTTP/client generation failure (e.g. HTTP 400/401/403, exhausted 5xx retries) |
| `llm_configuration_error` | Invalid LLM configuration |
| `llm_dependency_missing` | Required upstream module output missing, failed, skipped, or blocked |
| `llm_empty_input` | No usable transcript or summary signal |

`llm_invalid_response` is reserved for successful HTTP responses with unusable body content. HTTP 4xx/5xx generation failures map to `llm_generation_error` unless the response body explicitly indicates a missing model (`llm_model_missing`). A bare HTTP 404 with an empty body maps to `llm_generation_error`, not `llm_model_missing`.

`llm_dependency_missing` may include structured `error_context` on the module error envelope, for example `{"dependency": "summary", "state": "missing|skipped|blocked|failed"}`. UI and canonical outcome rows surface `error_code` alongside human-readable messages.

Prompt-budget validation happens at two levels:

- **Config load (global):** `llm.max_input_chars` must be at least the fixed prompt-envelope minimum (delimiters and safety copy only, no feature instruction; `core/llm/prompting.py::prompt_envelope_min_chars`). Config load rejects lower values.
- **Runtime (per feature):** because effort-profile limits replace the global `llm.max_input_chars`, each transcript-direct module (`llm_summary`, `llm_speaker_summary`, `llm_action_items`) validates its resolved effort budget against its exact instruction plus delimiters (`core/llm/prompting.py::require_prompt_budget`) before constructing a client or making a network call. `narrative_summary` is excluded: it uses a findings-rewrite prompt, not the bounded transcript envelope.

## Provenance

Successful LLM artifacts include mandatory provenance fields:

- `llm_request_sha256` — SHA-256 of canonical JSON `{user, system?}` sent to `client.generate()`
- `model`, `provider`, `seed`, `temperature`, `max_output_tokens`, `generation_options` (including effective `num_predict`)
- `transcriptx_version` when importable
- For `llm_action_items`: also `module_version`, `prompt_version`, and `cache_key` (distinct cache identity namespace)

Optional metadata such as `model_digest` is included only when already cached (e.g. from a prior `is_available()` tags fetch); no extra `/api/tags` call is made solely for provenance.

## Artifact writes

LLM modules write JSON/Markdown pairs through `core/analysis/llm_support/artifacts.py` under an **atomic pair promotion with rollback, then registration** contract:

1. Both files are fully staged (and prior canonical files backed up) in a per-write `.staging/` subdirectory before any promotion.
2. JSON is promoted first, then Markdown. If the Markdown promotion fails, the JSON promotion is undone exactly once — restored from backup, or removed when there was no prior file. Prior canonical files are never deleted optimistically.
3. If the rollback itself fails, the original promotion error is propagated (the rollback failure is logged and attached as exception context).
4. The staging directory is cleaned up in `finally`.
5. Artifact registration (`record_file`) begins only after both promotions succeed, and there is **no filesystem rollback after registration begins**. Registration is not transactional: if the first (JSON) registration fails, both files remain promoted and nothing is registered; if the second (Markdown) registration fails, both files remain promoted and the JSON registration remains. Undoing a registration would require an `OutputService` unregister API, which does not exist.

Speaker artifact filenames sanitise display names by replacing spaces and slashes with underscores (`llm_support/filenames.py`). Distinct names can collide to the same filename (e.g. `A B`, `A_B`, and `A/B` all map to `A_B`); this is documented, tested behaviour — collision-safe identity is tracked as separate work because changing it would change artifact paths.

## Manual smoke test

Prerequisites:

1. Ollama running locally (`ollama serve`)
2. Model installed: `ollama pull qwen3:8b`

```bash
export TRANSCRIPTX_LLM_ENABLED=1
export TRANSCRIPTX_LLM_PROVIDER=ollama
export TRANSCRIPTX_LLM_MODEL=qwen3:8b

python -c "
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path=Path('tests/fixtures/mini_transcript.json'),
    modules=['summary', 'narrative_summary', 'llm_summary', 'llm_speaker_summary', 'llm_action_items'],
))
print('success:', result.success)
print('errors:', result.errors)
"
```

Expected artifacts per module under the run output directory:

- `narrative_summary/data/global/*_narrative_summary.json` (+ `.md`)
- `llm_summary/data/global/*_llm_summary.json` (+ `.md`)
- `llm_speaker_summary/data/speakers/*_llm_speaker_summary.json` (+ `.md`) per named speaker
- `llm_speaker_summary/data/global/*_llm_speaker_summary_index.json` (+ `.md`)
- `llm_action_items/data/global/*_llm_action_items.json` (+ `.md`)

**Partial failure:** if a selected LLM module fails, the overall run is partially failed. Deterministic modules (e.g. `summary`) and their artifacts remain available. Failed LLM modules produce no canonical LLM artifacts.

**Graceful failure when Ollama is stopped:** modules report `failed` with `error_code=llm_unavailable` after up to 3 connection retries (~2s backoff cap).

## Optional live integration tests

Client smoke + LLM analysis modules (`llm_summary`, `llm_speaker_summary`,
`llm_action_items`):

```bash
export TRANSCRIPTX_LLM_LIVE_TEST=1
# optional: export TRANSCRIPTX_LLM_MODEL=qwen3:8b
# optional: export TRANSCRIPTX_LLM_SMOKE_MODEL=llama3.2:3b
# optional: export TRANSCRIPTX_LLM_ACTION_ITEMS_MODEL=llama3.2:3b
# optional (host-side): export TRANSCRIPTX_LLM_LIVE_BASE_URL=http://127.0.0.1:11434
pytest tests/core/llm/test_ollama_live.py tests/core/analysis/test_llm_modules_live.py -m "integration and requires_api"
```

Requires a running Ollama daemon and the configured model installed locally.
These tests are excluded from the default fast suite (`integration` /
`requires_api` / `slow`). Module live tests use `analysis.*.effort=low` to keep
runtime bounded.

On the Mac host, prefer `TRANSCRIPTX_LLM_LIVE_BASE_URL=http://127.0.0.1:11434`.
A project `.env` value of `http://host.docker.internal:11434` is for the Docker
GUI container and is ignored by these host-side live tests unless you set the
live-specific override.
