Type: CONTRACT
Authority: self

# Group LLM synthesis contract

Cross-session synthesis of per-member `llm_summary` / `llm_speaker_summary` texts during group finalize. **Not** a new analysis module ID.

Related: [group_analysis_module_outputs.md](group_analysis_module_outputs.md), [runtime/llm.md](../runtime/llm.md), [web_blocks.md](../dev/web_blocks.md).

## Purpose / non-goals

- **Does:** After collect aggregation persists authoritative files, synthesise one global and per-canonical-speaker rollups via Ollama; publish under a generation directory; flip `ACTIVE.json`.
- **Does not:** Re-read raw transcripts; invent new module IDs; mutate collect blobs; store `cancelled` in ACTIVE/COMMIT; rely on hidden-dir scans for the Artifacts browser.

## Authoritative inputs

| File | Path |
|------|------|
| Global collect | `{run}/llm_summary/llm_summary.json` |
| Speaker rows | `{run}/llm_speaker_summary/speaker_rows.json` |

Missing when required → `MISSING_COLLECT_ARTIFACT`. Schema/key mismatch → `COLLECT_SCHEMA_MISMATCH`.

## Digests

Always record:

- `global_collect_sha256` — SHA-256 of collect file bytes (empty-file sentinel if absent)
- `speaker_rows_sha256` — same for speaker rows
- `combined_input_digest` — SHA-256 of `global + "\\n" + speaker`

Resolver compares these to **live** collect files, not only ACTIVE≡COMMIT.

## On-disk layout

```text
{run}/.group_llm_synthesis/
  .lock
  ACTIVE.json
  generations/{generation_id}/
    COMMIT.json
    outcome.json
    llm_summary/group_llm_summary.{json,md}
    llm_speaker_summary/group_llm_speaker_summary_index.{json,md}
    llm_speaker_summary/group_llm_speaker_summaries/{token}_group_llm_speaker_summary.{json,md}
    meta/
```

## Lock

- **File:** `{run}/.group_llm_synthesis/.lock`
- **Order:** acquire synthesis lock before writing/reading authoritative collect files, generation publish, synthesis manifest merge, or GC under `.group_llm_synthesis/`. No other locks in v1 while holding this one.
- **Timeout:** `SYNTHESIS_LOCK_TIMEOUT` — skip synthesis, leave ACTIVE unchanged; live digest checks hide stale ACTIVE if collect changed.

## Commit / cancel

1. Stage under `generations/{id}/`
2. Durable COMMIT (`write_json_atomic`: fsync → replace → parent fsync)
3. Durable ACTIVE flip
4. Explicit manifest entries; **then** GC older committed gens (only if manifest OK)
5. Uncommitted dirs may be GC’d earlier

**`cancelled` / lock timeout / pre-COMMIT exceptions:** attempt status in run_results only; **never** ACTIVE/COMMIT `overall_status`; ACTIVE unchanged.

Intentional skip/fail (disabled, non-Ollama, validation) **does** COMMIT + flip ACTIVE.

## overall_status (ACTIVE/COMMIT only)

See `compute_overall_status` / plan matrix: `success` | `partial` | `failed` | `skipped`. Global success with all speakers skipped → `success`. Global failure with speaker successes → `partial`.

## Config

`analysis.group_llm_synthesis.enabled` (default `true`), `effort` (`low|medium|high|max`, default `high`). Effort resolves **effective** per-call limits without mutating global `llm.*`. Ollama-only via `require_ollama_analysis`.

## Prompts

JSON user payload with `records[].summary` (untrusted data). Prompt versions `GROUP_LLM_*_PROMPT_VERSION = "1"`. Middle-session drop for budget. Max 32 speakers; serial calls; 0 retries.

## Resolver

`transcriptx.core.analysis.group_llm_synthesis.resolve`: ACTIVE → COMMIT → live collect digests → path containment → per-file COMMIT digests. Cache COMMIT metadata per request. Consumers: summary precedence, speaker block, availability, export.

**Group UI:** no member `_llm_summary` primary fallback.

## Manifest

Explicit artifact entries with `module` / `kind` under `.group_llm_synthesis/generations/{active}/…`. Directory scan skips `.group_llm_synthesis/` noise.

## Error codes

See `transcriptx.core.analysis.group_llm_synthesis.errors` (`MISSING_COLLECT_ARTIFACT`, `COLLECT_SCHEMA_MISMATCH`, `SYNTHESIS_LOCK_TIMEOUT`, `LLM_UNAVAILABLE`, `PROMPT_BUDGET`, …). UI/export show sanitised messages only.

## Merge checklist

- [x] Contract covers lock order, digests, durable writes, cancel vs ACTIVE, GC/manifest, resolver, schemas
- [x] `docs/runtime/llm.md` Group LLM synthesis section
- [x] `docs/groups/group_analysis_module_outputs.md` links synthesis
- [x] `docs/dev/web_blocks.md` group resolver behaviour
- [x] `docs/dev/output_conventions.md` generation layout
- [x] `.env.example` / CHANGELOG / README capability line
- [x] Schema IDs and error codes match `schemas.py` / `errors.py`
- [x] No normative rule only in the plan file
