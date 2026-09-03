> **Archived / superseded.** Historical mapping only. Current user recipe: [docs/recipes/whisperx/README.md](../../recipes/whisperx/README.md). Env knobs live in `whisperx.env.example`. Do not treat this table as live product configuration.

# WhisperX TranscriptionConfig migration

When in-app transcription was removed, former TranscriptX `TranscriptionConfig` fields moved to WhisperX env vars and CLI flags. The table is kept so no old knob is silently lost. New setups should use `whisperx.env.example` and the recipe README — not this page.

If you add a new WhisperX knob, update `whisperx.env.example` first; only extend this table when documenting a former TranscriptX field.

| Old TranscriptX field     | Old env var                      | New mechanism                | Default                     | Notes                                                                 |
|---------------------------|----------------------------------|-------------------------------|-----------------------------|-----------------------------------------------------------------------|
| `model_name`              | `TRANSCRIPTX_MODEL_NAME`        | `WHISPERX_MODEL` env var      | `large-v2`                  | Set in `whisperx.env`                                                 |
| `language`                | `TRANSCRIPTX_LANGUAGE`          | `WHISPERX_LANGUAGE` env var   | `en`                        | Set in `whisperx.env`                                                 |
| `compute_type`            | `TRANSCRIPTX_COMPUTE_TYPE`      | `WHISPERX_COMPUTE_TYPE` env   | `float16`                   | `float16` for GPU, `int8` for CPU                                     |
| `diarize`                 | (config only)                    | `WHISPERX_DIARIZE` env var    | `true`                      | Requires `HF_TOKEN`                                                    |
| `huggingface_token`       | `HF_TOKEN`                       | `HF_TOKEN` env var | (none)                      | Required for diarization + gated models                               |
| `batch_size`              | (config only)                    | WhisperX CLI: `--batch_size 16` | `16`                     | Not env-configurable; pass via docker exec command                    |
| `min_speakers`            | (config only)                    | WhisperX CLI: `--min_speakers 1` | `1`                      | Not env-configurable; pass via docker exec command                   |
| `max_speakers`            | (config only)                    | WhisperX CLI: `--max_speakers 20` | `20` (or omit)           | Not env-configurable; pass via docker exec command                    |
| `model_download_policy`   | (config only)                    | No 1:1 equivalent             | `require_token`             | Gated models require `HF_TOKEN`; set or omit `HF_TOKEN`.              |
| (device — not in config)  | (not in config)                  | `WHISPERX_DEVICE` env var     | `cpu`                       | `cuda` for GPU                                                        |
