# Hardware & run-time guidance

Plan analysis on *your* machine. TranscriptX detects a coarse hardware band for this process, shows a **guidance-only** wall-time range on Run Analysis / Batch, and suggests LLM size and STT backends that fit. Estimates never block **Run analysis**.

For maintainer measurement recipes and lab timings, see [performance envelopes](../dev/performance_envelopes_1_0.md). For post-run observed timings, use **View → Performance**.

## What we detect

| Signal | Meaning |
|--------|---------|
| Memory band | `low` (&lt;8 GiB) · `mid` (8–16) · `high` (16–32) · `very_high` (≥32) |
| CPU class | Coarse core-count band |
| Acceleration | What **this process** can use: `cuda`, `mps`, or `cpu` (respects `TRANSCRIPTX_FORCE_CPU`) |
| Container | Whether the analysis process looks like Docker/cgroup |
| Install profile | `core` or `full` marker from install |

**Honesty:** Docker analysis often has **no GPU** even when the host can run CUDA WhisperX. Acceleration describes the analysis process, not host STT VRAM. We do not call `nvidia-smi` from the analysis image.

## Run-time estimates

On **Run Analysis** and **Batch**, after you pick a preset and modules, a caption shows a range such as:

> Estimated wall time: about 8–15 min (heuristic). Guidance, not a promise.

| Confidence | Meaning |
|------------|---------|
| heuristic | Coefficient table (preset × audio length × modules × LLM size × hardware band) |
| calibrated | Blended with similar past runs on this machine (`run_performance.json`) |
| low | Duration/workload unknown — wider range |

Caveats that often add minutes: first-run model downloads, Ollama holding another large model, Thorough + `chart_descriptions`, group = members + aggregation.

## LLM size vs RAM

| Memory band | Prefer | Avoid on this band |
|-------------|--------|--------------------|
| low | small (~3–4B), e.g. `gemma3:4b` | 27B-class tags |
| mid | mid (~7–14B), e.g. `qwen2.5:7b`, `mistral-nemo` | Large tags unless you accept swap risk |
| high / very_high | mid or large when you want quality | Loading several multi-GB models at once (contention) |

Settings → Models and the Run Analysis LLM expander show a one-line hardware hint for installed tags. Your selection is never rewritten automatically. Detail: [llm.md](llm.md).

## Analysis models

Defaults (`en_core_web_md` + MiniLM) are CPU-friendly. On **low/mid** RAM bands, stay there unless you have headroom. Higher-accuracy env presets (`lg` / `mpnet` / transformer sentiment) need more memory — see [models.md](models.md).

Thorough with install profile **core** may skip heavy extras (BERTopic, voice).

## STT backends

Transcription engines stay **out of the analysis image**. Transcribe Audio captions a recommendation and preselects provider/device when you have not chosen yet:

| Situation | Recommendation |
|-----------|----------------|
| macOS + whispermlx available | **whispermlx** (MLX) |
| CUDA visible to this process | WhisperX Docker **cuda** (host must pass `--gpus`) |
| Analysis container without CUDA | WhisperX Docker **cpu**; host STT may still use a GPU via a separate recipe |
| Apple Silicon without whispermlx | WhisperX Docker usually CPU-only — prefer installing whispermlx |

No STT wall-clock ETA in v1. Stacks: [transcription.md](transcription.md), [stt-stacks](../recipes/stt-stacks/README.md).

## Related

- [Installation](installation.md) — Docker vs native, `TRANSCRIPTX_FORCE_CPU`
- [Models](models.md) — spaCy / embeddings presets
- [LLM (Ollama)](llm.md) — module consumers and complementary pulls
- [Known limitations](../known_limitations.md) — MPS and capacity notes
