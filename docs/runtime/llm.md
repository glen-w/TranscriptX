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

## Modules

| Module | Description | Depends on |
|--------|-------------|------------|
| `narrative_summary` | Grounded executive narrative from deterministic `summary` output (temperature 0.0, JSON) | `summary` chain (highlights + upstream) |
| `llm_summary` | Abstractive transcript summary from readable transcript text (plain text, `default_temperature`) | segments only |
| `llm_speaker_summary` | Abstractive summary per **named** speaker from that speaker's utterances only (plain text, `default_temperature`) | segments + speaker labels |
| `llm_action_items` | Structured action items (owner, deadline, status, quote) from transcript text (strict JSON, `default_temperature`) | segments + speaker labels |

All four LLM modules are included in the **recommended** default module list when enabled. Uncheck **Use recommended modules** in Run Analysis (or pass an explicit `modules` list via the API) to opt out of any of them. When LLM is disabled they are **skipped** before execution (not failed) with reason `LLM disabled`.

**Privacy:** transcript text for LLM modules (`llm_summary`, `llm_speaker_summary`, `llm_action_items`, and structured input to `narrative_summary`) is sent only through the configured Ollama path (`llm.provider=ollama`). TranscriptX does not block non-local `base_url` values, but you are responsible for where your data is sent; the default is loopback (`http://localhost:11434`).

`llm_speaker_summary` is skipped when the transcript has no eligible named speakers (for example, before Speaker ID mapping). Ignored speakers are excluded.

Selecting `narrative_summary` automatically runs the `summary` dependency chain first.

## `llm_summary` effort (not `llm.effort`)

The setting **`analysis.llm_summary.effort`** controls summary effort for the **`llm_summary` module only** (full-transcript abstractive summary). It is **not** `llm.effort` and does **not** affect `narrative_summary`, global `llm.*` provider settings, or other analysis modules.

Valid values: `low`, `medium`, `high`, `max` (default: `medium`).

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

This pass supports `provider="ollama"` only for `llm_summary`, `llm_speaker_summary`, and `llm_action_items`; other non-null providers raise configuration errors. Shared eligibility is enforced via `require_ollama_analysis` (with `require_llm_summary_ollama` kept as a compatibility alias).

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

`max_input_chars` must be at least the runtime-derived prompt wrapper overhead (instruction text, delimiters, and safety copy). Config load rejects lower values.

## Provenance

Successful LLM artifacts include mandatory provenance fields:

- `llm_request_sha256` — SHA-256 of canonical JSON `{user, system?}` sent to `client.generate()`
- `model`, `provider`, `seed`, `temperature`, `max_output_tokens`, `generation_options` (including effective `num_predict`)
- `transcriptx_version` when importable
- For `llm_action_items`: also `module_version`, `prompt_version`, and `cache_key` (distinct cache identity namespace)

Optional metadata such as `model_digest` is included only when already cached (e.g. from a prior `is_available()` tags fetch); no extra `/api/tags` call is made solely for provenance.

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
