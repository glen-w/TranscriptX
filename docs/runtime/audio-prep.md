# Audio prep (before transcription)

Host-side recording cleanup **before** you transcribe elsewhere. TranscriptX does not transcribe in the app — after merge/preprocess, use [Transcribe Audio](transcription.md#if-you-still-need-to-transcribe-audio) then **Import Transcript**.

Interactive GUI: **System → Tools** (tabs **Preprocessing**, **Auto-merge**, **Manual merge**). Requires host `ffmpeg` and `pydub`. Supported inputs include WAV, MP3, OGG, **Opus** (WhatsApp Desktop voice notes), M4A, FLAC, AAC, and WMA.

Theme **G1** still covers optional transcript-part stitching vs remove — see [ROADMAP.md](../ROADMAP.md).

## Merge source profiles

**Merge** tab expander controls how split recordings and voice-note bursts are suggested and auto-merged. Settings live in `{config_dir}/audio_merge_profiles.json` (not project `config.json`). Edits in the expander apply to detection immediately; **Save** persists them.

Builtin defaults keep a 20-minute consecutive gap for messaging/recorder families; serial filename parts always merge. Per-profile **day** and **minutes** sliders let you tighten or loosen grouping (examples: WhatsApp same day within 2 hours; Zoom full day; Telegram same day within 6 hours).

Detected groups start **unchecked**; **Select all** / **Select none** toggle them. **Auto-merge selected groups** runs one merge per checked suggestion using the shared Merge options (backup / overwrite / preprocess / delete-originals). **Hide** drops a false match for this session; **Don't suggest again** stores the group in `{config_dir}/audio_merge_dismissed.json` so it stays off the list later (Restore from the expander if you change your mind).

Host batch transcription can skip remaining groups with `whispermlx-missing --skip-serial` (and `inbox-watch --skip-serial`) so parts are not transcribed before you merge; dismissed groups are not skipped. See [Host STT automation](host-stt.md#whispermlx-missing-bulk-script).

## CLI helpers

**Assess / preprocess** (`scripts/audio_preprocess.py`):

```bash
uv run python scripts/audio_preprocess.py assess recording.wav
uv run python scripts/audio_preprocess.py run recording.wav --mode auto
uv run python scripts/audio_preprocess.py run recording.wav \
  --mode selected --step denoise --step normalize -o ./out --format mp3
```

**Merge split parts** (`scripts/audio_merge.py`):

Concatenates files into one MP3. Does **not** preprocess unless you pass `--preprocess` (or enable the Merge-form checkbox). Run **Preprocessing** separately when you want DSP without assuming it.

```bash
uv run python scripts/audio_merge.py part_1.wav part_2.wav -o merged.mp3
uv run python scripts/audio_merge.py --list paths.txt --no-backup --overwrite
uv run python scripts/audio_merge.py part_1.wav part_2.wav --preprocess -o merged.mp3
```

Requires `ffmpeg` (and typically `pydub` via the project install). Transcribe the resulting files externally, then use **Import Transcript**.

## Related

- [Transcription](transcription.md) — import the result
- [Host STT automation](host-stt.md) — whispermlx-missing `--skip-serial`, inbox-watch
- Merge vs Profiles taxonomy: [settings.md](settings.md)
