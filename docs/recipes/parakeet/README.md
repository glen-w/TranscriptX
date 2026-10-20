# NeMo Parakeet / Canary (optional reference recipe)

Theme **K** (Copy command) and Theme **H5** (Run in app via `parakeet_docker` provider) for NVIDIA NeMo ASR on a **CUDA Linux host**. Not supported inside the analysis Docker image. On macOS, prefer **whispermlx** Run-in-app.

## What this is for

1. Transcribe audio with NeMo Parakeet or Canary on a GPU host.
2. Convert output to WhisperX-shaped JSON (`nemo_json_to_whisperx`).
3. **Import Transcript** in TranscriptX.

## Copy command (Theme K)

Transcribe Audio → **Copy command** → **NeMo Parakeet Docker** or **NeMo Canary Docker**. Customize the inner `docker run` NeMo invocation per your cluster, then run:

```bash
python3 -m transcriptx.services.transcription.nemo_json_to_whisperx \
  --input /path/to/hypotheses.jsonl \
  --output /path/to/originals/meeting.json
```

## Run in app (Theme H5)

When `docker` is visible to Streamlit and `TRANSCRIPTX_TRANSCRIPTION_PROVIDER=parakeet_docker` (or select Parakeet in the UI when wired), jobs use `ParakeetDockerProvider`.

- **Stub mode (dev/CI only):** `TRANSCRIPTX_PARAKEET_STUB=1` writes a placeholder JSONL and converts — no GPU weights.
- **Production:** replace the placeholder `docker run` command in `parakeet_docker_provider.py` / your fork with a real NeMo transcribe script (documented here).

## Trust / licence

NeMo Parakeet and Canary model weights are **CC-BY-4.0**. User-triggered download on first run. See [trust_privacy_model_governance_1_0.md](../../dev/trust_privacy_model_governance_1_0.md) and [NOTICE](../../../NOTICE).

## Related

- [STT stacks](../stt-stacks/README.md)
- [transcription.md](../../runtime/transcription.md)
- Implementation plan: [.cursor/plans/2026-10-20-undiarized-asr-waves.md](../../../.cursor/plans/2026-10-20-undiarized-asr-waves.md)
