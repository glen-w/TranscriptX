Type: PRODUCT
Authority: self

# Performance and resource envelopes (1.0)

**Status:** measurement recipe + baseline notes (**0.9.7**); large-library UI soak **pass** 2026-08-07 (200+ transcripts); Medium Balanced batch **pass** 2026-08-07 (~9.3 min / 6 transcripts on Docker Compose)
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
| Default-preset runtime | measured | Medium Balanced **pass** 2026-08-07 — 6 transcripts, batch wall ~9.3 min, all succeeded (see [manual_acceptance_1_0.md](manual_acceptance_1_0.md) §3.12) |
| Memory and disk use | measured-or-tagged | Record peak RSS + data-root delta; OOM without recovery = blocker |
| Model download sizes | documented | See [runtime/models.md](../runtime/models.md); first-run download is expected when enabled |
| Docker image size | documented baseline | Historical ~3.7GB class — [docker-efficiency-baseline.md](../runtime/docker-efficiency-baseline.md); re-measure on release hardware |
| Group-analysis scaling | measured-or-tagged | Group wall ≠ sum of members; includes aggregation |
| UI responsiveness with large library | measured | **pass** 2026-08-07 — Home/library responsive with **200+** transcripts (exceeds Large-for-1.0 ~50); see [manual_acceptance_1_0.md](manual_acceptance_1_0.md) §3.12 |
| Behaviour when disk/RAM/model insufficient | must document | Fail closed; no corrupt run commit; actionable GUI/docs errors |

## Recording

Record measured values per environment (Docker vs native) in release-evidence notes when claiming envelopes. Soft-cut for 0.9.7 allows recipe + tagged gaps; RC prefers filled Small/Medium rows on release hardware.
