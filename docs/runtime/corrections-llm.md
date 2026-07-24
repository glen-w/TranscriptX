Type: GUIDE
Authority: docs/runtime/llm.md

# Corrections Studio LLM discovery

Optional Ollama-assisted correction **candidate discovery** for Corrections Studio.

## Enablement

Requires **both**:

1. Global `llm.enabled: true` with `llm.provider: ollama`
2. `analysis.corrections.llm.enabled: true` (default **false**)

When disabled, Corrections Studio is fully deterministic: zero model calls and no LLM UI artefacts beyond an empty diagnostics `outcome=skipped`.

### Environment / Docker

```bash
export TRANSCRIPTX_LLM_ENABLED=1
export TRANSCRIPTX_LLM_PROVIDER=ollama
export TRANSCRIPTX_LLM_MODEL=qwen3:8b
export TRANSCRIPTX_LLM_BASE_URL=http://host.docker.internal:11434  # Docker → host Ollama
export TRANSCRIPTX_CORRECTIONS_LLM_ENABLED=1
```

Local `docker compose up` (with `docker-compose.override.yml`) defaults these on when unset. Production-like runs that use only `docker-compose.yml` leave Corrections Studio LLM off unless you set the vars.

Ollama must be running on the host with the configured model pulled.

### Config file

```yaml
llm:
  enabled: true
  provider: ollama
  model: qwen3:8b
  base_url: http://127.0.0.1:11434

analysis:
  corrections:
    llm:
      enabled: true
      effort: low
      request_timeout_seconds: 120
      total_wall_clock_seconds: 180
      chunk_max_segments: 40
      max_candidates_per_transcript: 80
      continue_on_failure: true
```

## When generation runs

LLM discovery does **not** run on page open alone. It runs during **candidate generation**:

1. **Start / Resume Session** — generates if the session has no candidates yet (spinner: “Generating candidates…”).
2. **Regenerate Candidates** — force-regenerates (needed after enabling LLM on a session that already has deterministic-only candidates).

## Behaviour

- LLM runs **only during candidate generation**, before compile/export.
- Suggestions are grounded locally (segment + exact source text → span). Hallucinations are rejected.
- Occurrences are expanded by exact local search; apply-all migration never silently covers newly expanded hits.
- Human review remains mandatory. Model output never mutates transcript text directly.
- On Ollama failure/timeout/budget exhaustion, deterministic candidates are retained (`continue_on_failure` default true).
- Concurrent session changes during a long generation **abort the commit** (optimistic concurrency); prior generation remains authoritative.

## Privacy

- Disabled by default (except local compose override defaults above).
- Non-local Ollama hosts trigger a UI warning (generation is still allowed). `localhost` / `127.0.0.1` / `host.docker.internal` count as local.
- Logs record chunk indices and error codes only — not transcript bodies, prompts, or raw model responses.

## Provenance

Export provenance includes `llm_influenced_candidate_ids` for accepted/learned candidates whose `sources` contain `llm_discovery` (including merges with memory/deterministic hits).
