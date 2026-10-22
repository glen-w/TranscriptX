# IBM Granite Speech (mlx-audio, Apple Silicon)

Host-orchestrated **Granite Speech** via [`mlx-audio`](https://github.com/Blaizzy/mlx-audio) (≥ 0.5.9). Apache-2.0 weights. **Not** inside the analysis Docker image or the TranscriptX analysis venv.

- **Run in app:** Transcribe Audio → provider **Granite Speech (MLX)** (`granite_mlx`).
- **Copy command:** Transcribe Audio → **Granite Speech mlx-audio (macOS host)**.

On Linux/CUDA, keep WhisperX Docker or Parakeet. Granite mlx-audio is macOS / Apple Silicon.

## Checkpoints

| Intent | Hugging Face id | Notes |
|--------|-----------------|-------|
| Accuracy, punctuation, keyword lists (up to 2,000) | `ibm-granite/granite-speech-5.0-2b` | Default when **Diarize** is off. IBM recommends ~2 minute chunks; Run in app splits at 110s. |
| Meetings / who said what | `ibm-granite/granite-speech-4.1-2b-plus` | Default when **Diarize** is on (`task=saa`). Native speaker turns. **No HF_TOKEN / pyannote.** Plus cannot emit word timestamps in the same pass as speaker labels. |

Segment times from this provider are **chunk wall-clock** (and character-split estimates for speaker turns). For WhisperX-grade words **and** speakers, keep WhisperX Docker.

## Host install

Use a **separate** Python (not `.venv` / analysis):

```bash
python3 -m venv ~/venvs/mlx-audio
~/venvs/mlx-audio/bin/pip install -U mlx-audio jinja2
export MLX_AUDIO_PYTHON=~/venvs/mlx-audio/bin/python
```

First run downloads Hub weights. Optional: `GRANITE_SPEECH_MODEL=ibm-granite/granite-speech-5.0-2b`.

## Keyword biasing (default off)

Settings → **Keywords** stores named lists. On Transcribe Audio, enable **Keyword biasing** and pick a list (plus optional extra terms). Granite receives them as `hotwords` / `Keywords:` in the prompt. Whisper providers ignore the lists in this version. Cap: 2000 terms.

## Stub mode (dev/CI)

`TRANSCRIPTX_GRANITE_STUB=1` writes placeholder WhisperX-shaped JSON — no Hub download.

## Convert BYO mlx-audio JSON

```bash
python3 -m transcriptx.services.transcription.granite_json_to_whisperx \
  --input /path/to/granite_raw.json \
  --output /path/to/originals/meeting.json
```

## Trust / licence

IBM Granite Speech checkpoints are **Apache-2.0**. User-triggered Hub download. See [trust_privacy_model_governance_1_0.md](../../dev/trust_privacy_model_governance_1_0.md) and [NOTICE](../../../NOTICE).

## Related

- [STT stacks](../stt-stacks/README.md)
- [transcription.md](../../runtime/transcription.md)
- [mlx-audio Granite docs](https://blaizzy.github.io/mlx-audio/models/stt/granite-speech/)
- [Granite Speech 5.0 blog](https://huggingface.co/blog/ibm-granite/granite-speech-5)
