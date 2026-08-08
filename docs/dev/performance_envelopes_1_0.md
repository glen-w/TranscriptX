Type: PRODUCT
Authority: self

# Performance and resource envelopes (1.0)

**Status:** measurement recipe + baseline notes (**0.9.7**); large-library UI soak **pass** 2026-08-07 (200+ transcripts); Medium Balanced batch **pass** 2026-08-07 (~9.3 min / 6 transcripts on Docker Compose); thorough full-preset LLM timings on speaker-complete corpus **pass** 2026-08-07 (`qwen2.5:7b`)
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §12  
**Related:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [run_performance.md](run_performance.md), [runtime/docker-efficiency-baseline.md](../runtime/docker-efficiency-baseline.md)

Documented expectations and regression indicators — not necessarily strict universal guarantees. Capacity failures that corrupt data or hang without recovery are release blockers / must-fix; non-critical misses may ship as known limitations.

## Representative corpus sizes

| Class | Working definition | Notes |
|-------|-------------------|-------|
| Small | 1 short meeting (~2–8 minutes, low segment count) | First useful result / smoke |
| Medium | ~5–10 transcripts; default (Balanced) preset | Typical personal corpus |
| Large-for-1.0 | ~50 transcripts in library + one multi-member group (3–5 members) | Upper documented expectation for 1.0 |

Raw measurement notes may live under ignored `.local/` scratch; curated numbers only below.

## Measurement recipe

From repo root on the machine under test (record package version, OS, Docker vs native, CPU/RAM class):

```bash
# 1) Package / image identity
python -c "import transcriptx; print(transcriptx.__version__)"
docker images --digests transcriptx:latest   # if Docker profile

# 2) Startup (GUI cold)
# Time until Home is interactive after `make run` / `./transcriptx.sh`
# Record wall seconds.

# 3) Import (Small / Medium)
# Managed import of N WhisperX/whispermlx JSON transcripts; record wall + disk delta under data root.

# 4) Default-preset runtime
# Run Balanced (or product default) on Small and Medium; read
#   <run>/.transcriptx/run_performance.json
# and module duration_ms in run_results.json (see run_performance.md).

# 5) Time to first useful result
# Clock from empty library → import Small → first Overview/Insights paint.

# 6) Memory / disk
# Peak RSS during Medium default preset; data-root disk before/after.

# 7) Model download sizes (optional extras)
# Document Hub / spaCy / Ollama pulls from runtime/models.md; do not re-download in CI.

# 8) Docker image size
docker images transcriptx:latest
docker history transcriptx:latest
# Compare docs/runtime/docker-efficiency-baseline.md (~3.7GB class historically).

# 9) Group scaling
# One group of 3–5 Medium-class members; record group wall from group run_performance sidecar.

# 10) Insufficient capacity
# Note behaviour when disk full / OOM / missing model: must fail closed with recovery path (no corrupt commit).
```

Optional helper (maintainer):

```bash
make perf-envelopes
# or: python3 scripts/release/perf_envelope_recipe.py
```

Keep notes in `.local/perf_envelopes_<date>.md` (gitignored). Curated numbers only below.

## Metrics checklist

| Metric | Status | Expectation / note |
|--------|--------|--------------------|
| Startup time | measured-or-tagged | Target: interactive Home under ~30s cold on supported Docker/native (known limitation if host-bound) |
| Import time | measured-or-tagged | Small: seconds–low tens; Medium scales ~linear with file count |
| Time to first useful result | measured-or-tagged | Small path should complete without undocumented steps |
| Default-preset runtime | measured | Medium Balanced **pass** 2026-08-07 — 6 transcripts, batch wall ~9.3 min, all succeeded (see [manual_acceptance_1_0.md](manual_acceptance_1_0.md) §3.12). Thorough full-preset + local LLM (`qwen2.5:7b`) on speaker-complete corpus: see § Thorough full-preset LLM timings below. |
| Memory and disk use | measured-or-tagged | Record peak RSS + data-root delta; OOM without recovery = blocker |
| Model download sizes | documented | See [runtime/models.md](../runtime/models.md); first-run download is expected when enabled |
| Docker image size | documented baseline | Historical ~3.7GB class — [docker-efficiency-baseline.md](../runtime/docker-efficiency-baseline.md); re-measure on release hardware |
| Group-analysis scaling | measured-or-tagged | Group wall ≠ sum of members; includes aggregation |
| UI responsiveness with large library | measured | **pass** 2026-08-07 — Home/library responsive with **200+** transcripts (exceeds Large-for-1.0 ~50); see [manual_acceptance_1_0.md](manual_acceptance_1_0.md) §3.12 |
| Behaviour when disk/RAM/model insufficient | must document | Fail closed; no corrupt run commit; actionable GUI/docs errors |

## Thorough full-preset LLM timings (2026-08-07)

**Scope:** every managed transcript whose speaker map is **complete** (every diarized ID named or ignored). After a local `schema_version` `"1.0"` → `1` patch so the files load under the integer-1 epoch, that set is:

| Transcript | Segments | Speakers | Duration | Status |
|------------|---------:|---------:|---------:|--------|
| `260615_Ana_phd_presentation_QA.json` | 297 | 10 | ~28 min | complete |
| `260615_Ana_phd_supervision_meeting.json` | 450 | 3 | ~36 min | complete |

(`_deep_test_large_norm` remains **partial** — 1 unidentified speaker — and was excluded. Mini / fixture transcripts are `none` / incomplete.)

**Environment:** native host Python `0.9.8.7`, Apple Silicon / host Ollama, shared model **`qwen2.5:7b`** (~7.6B, Q4_K_M; project-recommended ~6–8B class). Mode=`full`, modules=`None` (default full set including LLM consumers + `chart_descriptions` finalize).

### Results

| Transcript | Wall | DAG | `chart_descriptions` finalize | Final status | Notes |
|------------|-----:|----:|-------------------------------:|--------------|-------|
| Presentation QA (initial) | **71.4 min** (4283 s) | 53.3 min | 18.1 min | **partial** | 4 LLM modules timed out at 600 s each while Ollama still held `qwen3-vl:8b` (~44 GB). Soft-fail continued the pipeline. |
| Presentation QA (LLM retry) | **32 s** | n/a | n/a | **succeeded** | Retried only `llm_action_items` / `llm_speaker_summary` / `llm_summary` / `narrative_summary` with free Ollama — all green (3–6 s each). |
| Supervision meeting | **10.1 min** (606 s) | 3.9 min | 6.1 min | **succeeded** | 42 modules, 0 errors. Clean run with `qwen2.5:7b` resident. |
| **Corpus effective sum** | **~42.0 min** | — | — | composite | QA effective (~31.9 min = initial − 2400 s timeout dead time + retry) + supervision 10.1 min |

### LLM consumer timings (clean Ollama / `qwen2.5:7b`)

| Module | Presentation QA (retry) | Supervision |
|--------|------------------------:|------------:|
| `llm_action_items` | 6.0 s | 7.0 s |
| `llm_speaker_summary` | 5.7 s | 6.5 s |
| `llm_summary` | 3.2 s | 2.9 s |
| `narrative_summary` | 5.7 s | 3.0 s |
| `topic_shift` | (545 s under contention in initial QA) | 13.6 s |
| `chart_descriptions` | ~18 min (197-class chart set; initial QA) | ~6.1 min |

### Regression / ops notes

- **Ollama contention is a first-class risk:** a resident multi-GB vision model can push LLM modules into the 600 s soft-timeout path and inflate wall clock by ~40 minutes even though non-LLM work is fine. Documented expectation: keep the intended chat model loaded (or unload others) before thorough LLM runs; treat multi-model contention hangs as capacity / ops, not analysis correctness failures when the circuit-breaker soft-fails.
- **`chart_descriptions` dominate thorough walls** once LLM chat modules are healthy (often longer than the entire DAG on chart-heavy transcripts).
- Machine-readable copies: `artifacts/roadmap_1_0_llm_analysis/corpus_timings.json`, `qa_timings.json`, plus run logs / `thorough_named_speaker_corpus.md`. Private mirror: `.local/release_evidence/20260807_thorough_qwen25_7b/`. Run dirs: `…/260615_Ana_phd_presentation_QA/20260807_171909_15949872` (+ retry `…/20260807_232957_38197390`), `…/260615_Ana_phd_supervision_meeting/20260807_233852_38732557`.

## Recording

Record measured values per environment (Docker vs native) in release-evidence notes when claiming envelopes. Soft-cut for 0.9.7 allows recipe + tagged gaps; RC prefers filled Small/Medium rows on release hardware.
