# Nemotron 3.5 Transcribe (optional reference recipe)

Theme **K** (Copy command) and Theme **H5** (Run in app via `nemotron_vllm`) for [NVIDIA Nemotron 3.5 Transcribe](https://huggingface.co/blog/nvidia/nemotron-transcribe-granary) on a **CUDA host**. Not supported inside the analysis Docker image. On macOS, prefer **whispermlx** or Granite Speech.

This is a promptable SALM (`nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B`), not Parakeet JSONL ASR. Official inference is a **local** OpenAI-compatible server (vLLM / NeMo Speech / NIM). TranscriptX owns the client + WhisperX-shaped converter; it does **not** daemonize the GPU server and does **not** call cloud NIM unless you set an explicit remote URL.

**Granary v2** is training data. It is not part of this recipe.

## What this is for

1. Serve Nemotron once on a CUDA machine (`127.0.0.1:8000`).
2. Transcribe with `nemotron_vllm_client` (speaker-tagged prompt + `ctc_timestamps` when diarize is on).
3. Convert to WhisperX-shaped JSON (`nemotron_json_to_whisperx`).
4. **Import Transcript** in TranscriptX.

## Hardware

| Checkpoint | Typical GPU |
|------------|-------------|
| BF16 `NVIDIA-Nemotron-3.5-Transcribe-30B-A4B` | 1× H100 80 GB |
| FP8 / NVFP4 Hub variants | Blackwell (RTX 5090, RTX PRO 6000, Spark) |

This is **not** a Mac Run-in-app engine. Paste Copy command on the CUDA host (or WSL2).

## Copy command (Theme K)

Transcribe Audio → **Copy command** → **Nemotron 3.5 Transcribe (local vLLM, CUDA)**.

The snippet comments a one-time `vllm serve` (operator-owned), then runs:

```bash
python3 -m transcriptx.services.transcription.nemotron_vllm_client \
  --audio /path/to/meeting.wav \
  --output-raw /path/to/originals/meeting.wav.nemotron.json \
  --base-url http://127.0.0.1:8000/v1 \
  --model nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B

python3 -m transcriptx.services.transcription.nemotron_json_to_whisperx \
  --input /path/to/originals/meeting.wav.nemotron.json \
  --output /path/to/originals/meeting.wav.json
```

Serve flags follow the [Hugging Face model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B) (`VLLM_PLUGINS=nemo_speechlm`, CTC timestamp middleware, `--host 127.0.0.1`). Bind loopback. Do not publish the port.

v1 prompts: speaker-attributed transcription when **Diarize** is on; written-form transcript-only when off. Keyword lists become `Context terms:` in the prompt. Translation / audio Q&A stay BYO prompts.

## Run in app (Theme H5)

When Streamlit can reach `http://127.0.0.1:8000/v1` on a non-macOS host (or `TRANSCRIPTX_NEMOTRON_BASE_URL`), jobs use `NemotronVllmProvider`.

- **Stub mode (dev/CI only):** `TRANSCRIPTX_NEMOTRON_STUB=1` writes a placeholder dump and converts — no GPU weights.
- **Production:** start vLLM yourself, then **Run in app**. TranscriptX does not `docker run` the 34B checkpoint per file.

Default endpoint is loopback. `TRANSCRIPTX_NEMOTRON_ALLOW_REMOTE=1` is required for any non-loopback URL (explicit opt-in, not silent cloud).

## Trust / licence

Nemotron 3.5 Transcribe weights are **OpenMDW-1.1**. User-triggered download on first serve. See [trust_privacy_model_governance_1_0.md](../../dev/trust_privacy_model_governance_1_0.md) and [NOTICE](../../../NOTICE).

## Related

- [STT stacks](../stt-stacks/README.md)
- [transcription.md](../../runtime/transcription.md)
- [Parakeet / Canary](../parakeet/README.md) — smaller NeMo ASR, different converter
