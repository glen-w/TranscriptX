# UI Docker Thorough batch — partial / stalled (2026-08-09)

**Status:** stalled (incomplete)  
**Package:** `0.9.8.9`  
**Environment:** Docker Compose `transcriptx-web` · host Ollama  
**Preset:** Thorough (**41** requested modules, incl. BERTopic, LLM consumers, `chart_descriptions`, `narrative_summary`)  
**Live LLM:** `gemma3:4b` (effective config also listed `gemma3:12b`; runtime module log used 4b)  
**Library root:** host transcripts mount → `/mnt/transcripts`  
**Outputs root:** host outputs mount → `/mnt/outputs`

## Prelude (aborted Balanced kick)

An earlier UI batch on the same evening used the **Balanced** module set (~30 modules) and was **stopped by the owner** once that mismatch was noticed. Treat that kick as non-evidence for Thorough envelopes.

## Selection

UI Batch Analysis over the managed library (Docker mount). Early transcripts in library sort order were mostly **unnamed-speaker** (Thorough modules gated → heavy SKIP). The first **full** Thorough transcript in the batch had named speakers and ran the complete 41-module set including `chart_descriptions`.

## Timings (observed before stall)

| Phase | Wall | Status | Notes |
|---|---:|---|---|
| 10 skip-heavy library-head transcripts | **~2.1 min** sum (~9–16 s each) | `succeeded` | Typically ~4–5 modules RUN / ~20 SKIP; LLM/`bertopic` gated on unnamed speakers |
| First full Thorough transcript (`tx-full-01`) | **~18 min** (approx. start→`run_results` write) | pipeline artifacts written; **batch did not advance** | **41/41** modules run, 0 failures; **197/197** `chart_descriptions` |
| **Batch corpus (incomplete)** | **~20+ min** clock then stall | **stalled** | No further `Starting analysis pipeline` after `tx-full-01` |

### `tx-full-01` finalize symptoms

- `manifest.json` and `run_results.json` present under the run dir
- `.run_finalization.lock` still present
- `.transcriptx/run_performance.json` **not** written
- Container CPU idle; Streamlit process alive
- Suspected: Streamlit batch session hung in post-pipeline finalize / UI callback after chart-description publication

## Ops notes for 1.0 envelopes

- Docker UI Thorough on a large mixed library is **not** equivalent to the native speaker-complete stress pass (`stress_pass_20260808`): skip-heavy heads finish in seconds; named-speaker + `chart_descriptions` dominates wall.
- Long `chart_descriptions` passes (hundreds of viz) are a **UI batch resilience** risk: progress can look “done” in logs while the batch queue never advances.
- Prefer speaker-complete (or explicitly filtered) corpora for Thorough envelope claims; document UI stall as a capacity / UX failure mode until fixed.

## Artifacts

- This summary + machine-readable stubs in this directory
- Private mirror: `.local/release_evidence/20260809_ui_docker_thorough_batch/`
- Transcript and path stems intentionally **anonymised** (`tx-full-01`, aggregated skip-heavy head)
