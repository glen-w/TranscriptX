# Theme E — Performance & hardware guidance

Status: implemented (probe + estimates + recommendations + docs)  
Last updated: 2026-10-22

**Roadmap home:** [docs/ROADMAP.md](../ROADMAP.md) §E  
**User guide:** [docs/runtime/hardware.md](../runtime/hardware.md)  
**Measurement authority:** [performance_envelopes_1_0.md](performance_envelopes_1_0.md)  
**Observed telemetry:** [run_performance.md](run_performance.md)

## Goal

Help operators plan a run on *this* machine: a labelled wall-time range, a hardware-aware backend/size hint, and thicker docs. Estimates never disable **Run analysis**.

## Locked decisions

1. **One probe, many consumers** — `HardwareProbe` / `probe_hardware()` in `core/observability/hardware_probe.py` returns a snapshot used by Run Analysis, Batch, LLM picker, Transcribe Audio, and `run_performance` sidecar writes.
2. **Guidance, never a gate** — estimates are captions only. Uncertain forecasts do not set `can_launch = False`. Thinking-model JSON gating remains separate.
3. **Hybrid estimator** — published coefficients (seeded from envelopes) blended with matching local `run_performance.json` priors when fingerprint + preset + similar duration match.
4. **STT gets backends, not ETAs** — analysis wall-clock only. Transcribe Audio uses the probe to recommend whispermlx vs WhisperX CUDA vs CPU.
5. **Honesty about where the process runs** — Docker analysis often has no GPU even when the host can run CUDA STT. Probe fields describe *this process*.
6. **View → Performance stays observed truth** — that page remains post-run telemetry.

## Memory / CPU / acceleration bands

| Field | Bands / values |
|-------|----------------|
| `memory_band` | `low` &lt;8 GiB · `mid` 8–16 · `high` 16–32 · `very_high` ≥32 · `unknown` |
| `cpu_class` | `low` ≤4 cores · `mid` ≤8 · `high` &gt;8 · `unknown` |
| `acceleration` | `cuda` → `mps` → `cpu` (honours `TRANSCRIPTX_FORCE_CPU`) |
| `in_container` | `/.dockerenv` / cgroup heuristics |
| `install_profile` | `core` / `full` / absent (`get_install_profile`) |

## Estimator inputs / outputs

**Inputs:** hardware snapshot, analysis preset, selected module ids, LLM size class, workload (`transcript_duration_s` / segments / speakers), optional prior sidecars, target type (transcript / group).

**Output:** `RunTimeEstimate(low_s, high_s, confidence, drivers, caveats)` with `confidence ∈ {heuristic, calibrated, low}`.

**Display:** `format_run_time_estimate` → caption under Run Analysis / Batch footer.

## Sidecar population

At `freeze()` (transcript + group):

- `runtime_fingerprint` from `probe_hardware().to_runtime_fingerprint()`
- `workload` from canonical segments (transcript runs)
- `analysis.profile` carries `analysis_preset` when present on `run_results.json` (schema has no dedicated preset field)
- `analysis.config_hash` when the prepared workspace snapshot is available

## Acceptance checklist

- [x] Shared probe never raises into UI; cache clearable for tests
- [x] Pre-run estimate caption on Run Analysis and Batch; does not disable Start
- [x] LLM hardware caption in compact setup + Settings → Models
- [x] STT provider/device preselect + caption on Transcribe Audio
- [x] Sidecar writes fingerprint (+ workload on transcript runs)
- [x] User doc `runtime/hardware.md` + thickened models/llm/transcription
- [x] Unit tests for probe, estimator, recommendations

## Out of scope

- Live remaining-time in the progress panel
- STT wall-clock ETAs; VRAM / `nvidia-smi` from the analysis image
- Auto-changing the operator’s Ollama tag or spaCy model
- Theme N cloud LLM; Theme I loopback API

## Related code

| Area | Path |
|------|------|
| Probe | `src/transcriptx/core/observability/hardware_probe.py` |
| Estimator | `src/transcriptx/core/observability/run_estimate.py` |
| STT / analysis hints | `src/transcriptx/core/observability/backend_recommend.py` |
| Sidecar helpers | `src/transcriptx/core/observability/run_performance_context.py` |
| LLM ranking | `recommend_llm_for_hardware` in `llm_support/model_guidance.py` |
| GUI captions | `web/components/run_time_guidance.py` |
