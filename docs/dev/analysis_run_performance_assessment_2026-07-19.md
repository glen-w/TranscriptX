Type: PRODUCT
Authority: self

# Assessing analysis-run performance (low custom code)

> How to evaluate **runtime**, **health/completeness**, and (with a thin scorer) **quality** of analysis runs using existing artifacts and helpers — without standing up a new eval platform.
>
> Related: [`COMPLEXITY_GATES.md`](COMPLEXITY_GATES.md) (import cold/warm), [`analysis_module_backlog_2026-07-17.md`](analysis_module_backlog_2026-07-17.md) items 12 & 18 (performance budgets, evaluation fixtures), [`../run_outcome_contract.md`](../run_outcome_contract.md), [`../contracts/output-contract-v1.md`](../contracts/output-contract-v1.md).

---

## 1. What an analysis run is

One isolated DAG pipeline execution over a canonical transcript (or a group of them).

**Flow:** managed/canonical transcript JSON → module selection (`quick`/`full` + profile) → dependency-aware DAG → modules write artifacts → `run_results.json` + `manifest.json` + reproducibility manifest.

| Layer | Key symbols / paths |
|--------|---------------------|
| Mental model | `docs/dev/developer_quickstart.md` |
| Request/result | `AnalysisRequest`, `GroupAnalysisRequest`, `BatchAnalysisRequest` in `src/transcriptx/app/models/requests.py`; `AnalysisResult` / `RunSummary` in `…/results.py` |
| Workflow | `run_analysis`, `run_group_analysis` in `src/transcriptx/app/workflows/analysis.py` |
| Controller | `AnalysisController` in `src/transcriptx/app/controllers/analysis_controller.py` |
| Pipeline | `run_analysis_pipeline` in `src/transcriptx/core/pipeline/pipeline.py` |
| Outcomes | `CanonicalModuleOutcome`, `RUN_RESULTS_SCHEMA_VERSION` in `module_outcomes.py` |
| Web UI | `src/transcriptx/web/page_modules/run_analysis.py`; browse via Transcript Overview / Insights / Artifacts |
| Run discovery | `RunController` in `src/transcriptx/app/controllers/run_controller.py` |

**Public surfaces** (`docs/public_surfaces.md`): Streamlit GUI + Python API. There is no supported `transcriptx analyze` CLI — `transcriptx` only launches the web app.

**On-disk layout** (`docs/contracts/output-contract-v1.md`):

```
outputs/<slug>/<run_id>/
  run_results.json          # execution truth (+ per-module duration_ms)
  manifest.json             # artifact registry
  report.json|md|txt        # optional projections
  .transcriptx/manifest.json              # reproducibility (run_manifest)
  .transcriptx/run_config_effective.json
  <module>/data|charts/...
```

Group runs live under `outputs/groups/` (see `docs/runtime/STORAGE.md`).

---

## 2. What already exists

### 2.1 Latency / runtime (analysis-relevant)

- Per-module **`duration_ms`** on outcomes in `run_results.json` (`module_outcomes.py`; measured in DAG execution).
- Wall-clock **`AnalysisResult.duration_seconds`** from the workflow.
- Progress events carry `duration_ms` (`app/progress.py`).

### 2.2 Contract / health / completeness (not ML accuracy)

- **Run health UI:** `ArtifactService.check_run_health`, `run_health_presentation.py`, Overview block `run_health`.
- **Typed loaders:** `load_run_results`, `load_artifact_manifest`, `load_run_manifest` in `manifest_loader.py`.
- **Reproducibility check:** `verify_run_manifest()` in `src/transcriptx/core/utils/run_manifest.py`.
- **Golden / contract tests:**
  - `tests/integration/core/test_pipeline_golden_runs_integration.py`
  - `tests/contracts/` (+ `tests/contracts/normalization.py` for stable manifest snapshots)
  - `tests/smoke/test_analysis_pipeline_smoke.py`
  - `tests/regression/test_pipeline_determinism.py`
- **Expected-output fixture (schema-level):** `tests/fixtures/expected_outputs/tiny_diarized_expected.json`
- **Docs for a missing assess script:** `scripts/README_test_analysis_assess.md`  
  **Gap:** `scripts/test_analysis_assess.py` is documented but absent. The fixture also assumes a sidecar DB (`PipelineRun` / `ModuleRun`) that was removed historically.

### 2.3 UI / import performance (not analysis quality)

- `src/transcriptx/core/observability/perf.py` (`RunMetrics`, JSONL) via `src/transcriptx/web/perf.py`
- `scripts/capture_streamlit_perf_scenarios.py`, `scripts/streamlit_perf_report.py`
- `scripts/bench_pipeline_cold_warm.py` + `docs/dev/COMPLEXITY_GATES.md` (import cold/warm only)

### 2.4 Heuristic “quality” inside modules (not ground-truth eval)

- Phrase quality: `phrase_quality/scoring.py` (+ corpus smoke in `tests/analysis/test_key_themes_corpus_acceptance.py`)
- Semantic filtering: `semantic_similarity/quality_scoring.py`
- QA response quality: `qa_analysis/analysis.py`
- Audio noise assessment: `core/audio/preprocessing.py` / Audio Prep page (pre-transcription)

### 2.5 External eval / experiment trackers

**None.** No Trackio, W&B, MLflow, inspect-ai, or lighteval. Hugging Face appears for models / WhisperX diarization, not analysis benchmarking.

Backlog explicitly calls out missing **representative evaluation fixtures** and **performance budgets** (`analysis_module_backlog_2026-07-17.md` §7 items 12, 18).

---

## 3. Practical options (prefer existing tooling)

### A. Latency + success rate from an existing run (≈0 new infrastructure)

1. Run via Python API or GUI.
2. Load truth with `load_run_results(run_dir / "run_results.json")`.
3. Aggregate `module_outcomes[].duration_ms` and statuses (`succeeded` / `failed` / `blocked` / …).

```python
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from transcriptx.core.pipeline.manifest_loader import load_run_results

result = run_analysis(AnalysisRequest(
    transcript_path=Path("tests/fixtures/mini_transcript.json"),
    modules=["stats", "sentiment"],
    mode="quick",
))
rr = load_run_results(result.run_dir / "run_results.json")
# result.duration_seconds + rr["module_outcomes"][*].duration_ms / status
```

**Plugs into:** spreadsheet, notebook, or a thin pytest in CI.

### B. Schema / artifact regression (minimal custom code)

Reuse golden-test patterns:

- Assert artifact families with `assert_module_has_artifact_family` / `normalize_golden_manifest` from `tests/contracts/normalization.py`.
- Validate with `RunResultsSummary.validate_run_results` (or equivalent run-results validators).
- Optional: revive the spirit of `tiny_diarized_expected.json` **without** DB checks (roles + required JSON keys + PNG validity only).

**Do not** rely on `scripts/test_analysis_assess.py` until it is restored.

### C. Idempotency / determinism

- Run twice (same modules/config), compare normalized manifests and stable fields in module data JSON.
- Or extend/enable `tests/regression/test_pipeline_determinism.py`.

### D. Reproducibility gate

- After a run: `load_run_manifest` + `verify_run_manifest` before claiming a baseline is still valid.

### E. UI load only

- `TRANSCRIPTX_STREAMLIT_PERF=1` + capture/report scripts — measures Streamlit reruns, not analysis module accuracy.

### F. Ground-truth accuracy (ASR WER, label F1, etc.)

**Not available.** Needs a custom scorer against held-out labels. Best hook points:

| Compare | Against | Using |
|---------|---------|--------|
| Module JSON under `<run>/<module>/data/` | Hand-labeled expected JSON | Thin scorer + fixture pattern like `expected_outputs/` |
| Run outcomes / timings | Prior run’s `run_results.json` | Diff `duration_ms` + status |
| Artifact set | Prior `manifest.json` | Normalized snapshot helpers |

There is no built-in “compare run A vs ground truth” CLI.

---

## 4. Gaps

| Need | Status |
|------|--------|
| Analysis accuracy vs ground truth | Missing |
| Unified assess CLI | Documented (`README_test_analysis_assess.md`) but **script gone**; fixture half-obsolete (DB) |
| Experiment tracking (Trackio/W&B/MLflow) | Missing |
| Formal eval harness (inspect-ai/lighteval) | Missing |
| Analysis latency budgets in CI | Backlog only; only import bench + Streamlit perf exist |
| ASR WER | Out of scope by design (transcription is separate; analysis-first) |

---

## 5. Recommended default path

1. **Runtime / reliability:** aggregate `duration_ms` + outcomes from `run_results.json`.
2. **Regression:** extend golden/contract tests for artifact families (not byte-identical files).
3. **Semantic quality:** only then add a small scorer against hand-labeled expected JSON under each module’s `data/` — the stable hook is the run directory layout, not a new tracker.

---

## 6. Source index

| Topic | Path |
|-------|------|
| Outcome contract | `docs/run_outcome_contract.md` |
| Output layout | `docs/contracts/output-contract-v1.md` |
| Storage / groups | `docs/runtime/STORAGE.md` |
| Import perf gates | `docs/dev/COMPLEXITY_GATES.md` |
| Assess script docs (script missing) | `scripts/README_test_analysis_assess.md` |
| Expected fixture example | `tests/fixtures/expected_outputs/tiny_diarized_expected.json` |
| Manifest normalization helpers | `tests/contracts/normalization.py` |
| Golden integration tests | `tests/integration/core/test_pipeline_golden_runs_integration.py` |
| Run health | `src/transcriptx/web/services/artifact_service.py` (`check_run_health`) |
| Loaders | `src/transcriptx/core/pipeline/manifest_loader.py` |
