# NeMo Parakeet / Canary (optional reference recipe)

Theme **K** (Copy command) and Theme **H5** (Run in app via `parakeet_docker`) for NVIDIA NeMo ASR on a **CUDA Linux host**. Not supported inside the analysis Docker image. On macOS, prefer **whispermlx** Run-in-app. **Canary is Copy command only** — there is no `canary_docker` provider.

## What this is for

1. Transcribe audio with NeMo Parakeet (or Canary via Copy command) on a GPU host.
2. Convert JSONL (`start` / `end` / `text`) to WhisperX-shaped JSON (`nemo_json_to_whisperx`).
3. **Import Transcript** in TranscriptX.

Parakeet TDT is **undiarized**. Import may mint `SPEAKER_00` (T0/T1). Do not expect pyannote speaker labels from this recipe.

## Pinned image and model

- Image: `nvcr.io/nvidia/nemo:24.07.1`
- Parakeet: `nvidia/parakeet-tdt-0.6b-v3`
- Canary (copy only): `nvidia/canary-1b`

Weights are **CC-BY-4.0**. First run downloads them into the container unless you mount a Hugging Face cache (`TRANSCRIPTX_PARAKEET_HF_CACHE` or `-v "$HOME/.cache/huggingface:/root/.cache/huggingface"`).

## Copy command (Theme K)

Transcribe Audio → **Copy command** → **NeMo Parakeet Docker** or **NeMo Canary Docker**. The snippet writes `_parakeet_transcribe.py`, runs `docker run --gpus all`, then:

```bash
python3 -m transcriptx.services.transcription.nemo_json_to_whisperx \
  --input /path/to/meeting.jsonl \
  --output /path/to/originals/meeting.json
```

## Run in app (Theme H5, Parakeet only)

When `docker` is visible to Streamlit and the provider is `parakeet_docker` (Settings / Transcribe Audio → Run in app):

- **Stub mode (dev/CI only):** `TRANSCRIPTX_PARAKEET_STUB=1` writes a placeholder JSONL and converts — no GPU weights.
- **Production:** `ParakeetDockerProvider` runs the pinned `docker run` + inner Python (`ASRModel.from_pretrained` + `transcribe(..., timestamps=True)`), then `nemo_json_to_whisperx`. Streamlit in `transcriptx-web` needs a docker CLI; Compose analysis image does not ship one.

`TRANSCRIPTX_TRANSCRIPTION_PROVIDER=parakeet_docker` — see [parakeet.env.example](parakeet.env.example).

## Trust / licence

NeMo Parakeet and Canary model weights are **CC-BY-4.0**. User-triggered download on first run. See [trust_privacy_model_governance_1_0.md](../../dev/trust_privacy_model_governance_1_0.md) and [NOTICE](../../../NOTICE).

## Related

- [STT stacks](../stt-stacks/README.md)
- [transcription.md](../../runtime/transcription.md)
- Implementation plan: [.cursor/plans/2026-10-20-undiarized-asr-waves.md](../../../.cursor/plans/2026-10-20-undiarized-asr-waves.md)
