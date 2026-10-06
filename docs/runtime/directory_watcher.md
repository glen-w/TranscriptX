# Directory watcher

Optional **directory watcher** (roadmap G2) notices new files in a monitored inbox and runs **New → Import** for transcripts (and queues audio for later **Transcribe → Import**). Default **off**. Configure in **Settings → Watcher** or via `config_dir/watcher.json` / `TRANSCRIPTX_WATCHER_*` env.

## Behaviour

| Kind | Mode | Action |
|------|------|--------|
| Transcript (`.json`/`.srt`/`.vtt`/`.txt`/`.html`) | `auto_import` (default when enabled) | Stabilize → classify → `admit_and_register` |
| Transcript | `offer` / `ignore` | Record/skip only |
| Audio | `offer` (default) | Queue as `queued_transcription` (no silent STT) |
| Audio | `auto_transcribe` | Run an available host STT provider (whispermlx / WhisperX Docker) and import |
| Audio | `ignore` | Skip |

Inbox files are **never deleted or modified**. Admission always copies into app `imports/` then uses the managed import path (canonical JSON + sidecar + originals + index). The watcher does **not** scan the managed transcripts library.

## Ops notes

- Runs only while `transcriptx-web` is running (in-process supervisor). Stopping the container stops watching.
- Docker: watch a mounted inbox such as `/mnt/transcript-inbox` (`HOST_TRANSCRIPT_INBOX_DIR`). Paths must be absolute **inside** the container.
- Debounce (~2s) plus size/mtime stability checks before admit; identity is re-checked at admit time (fail closed if the file moved/grew).
- Job records and activity live under `data_dir/watcher/` (see [STORAGE.md](STORAGE.md)).
- Prefer Settings UI for enablement; env overrides are for automation.

## Host-side helper (`inbox-watch`)

The in-app watcher **can** run STT when **Settings → Watcher → Audio mode** is `auto_transcribe` and a provider is available (theme **H**). Offer mode still queues audio for **Transcribe Audio**. For host-side convert/STT without Streamlit, use [`scripts/inbox-watch.py`](../../scripts/inbox-watch.py) documented under [Host inbox watcher (`inbox-watch`)](host-stt.md#host-inbox-watcher-inbox-watch) in [host-stt.md](host-stt.md):

- `--watch-audio` — ffmpeg 16 kHz mono 64k MP3 into recordings
- `--transcribe` — host STT after convert: `whispermlx-missing` (default), `none` (convert/copy/admit only), or `command` (`--transcribe-cmd` argv template). Optional `--skip-serial` is forwarded to `whispermlx-missing` only.
- `--watch-transcripts` — copy new JSON/SRT/VTT/txt/html into a transcripts dest if the stem is missing
- `--admit` (default off) — after the above, run `python -m transcriptx.admit_originals` so new `originals/` files enter the managed library (`admit_and_register`). Enable with `--admit`, `"admit_to_library": true` in `.transcriptx/inbox-watch.json`, or `INBOX_WATCH_ADMIT=1` in repo `.env`. Needs a native TranscriptX Python (`admit_python` / `--admit-python` / `INBOX_WATCH_ADMIT_PYTHON`).
- `--auto-name` / `--auto-link` — after admit, auto-write speaker-map names and/or create `auto_identified` profile links when voice + text fusion is confident (`INBOX_WATCH_AUTO_NAME` / `INBOX_WATCH_AUTO_LINK`). `--auto-name` implies admit and defaults auto-link on. In-app Settings → Speakers knobs (`config_dir/identify.json`) apply to G2 auto-import. Operator reference: [auto-identify.md](auto-identify.md).
- Terminal UX — same Review / Processing / Run summary shape as analysis CLI feedback ([Terminal feedback](host-stt.md#terminal-feedback))

It does not import `transcriptx` in-process. Default STT (`whispermlx-missing`) is macOS/MLX. `--transcribe none` or `--transcribe command` can convert (and optionally admit) without that binary. G2 stays the in-app auto-import path. Both can run; do not point them at the same inbox unless you intend double handling of transcripts (G2 admits, host copies — and `--admit` would admit the copies).

Short voice notes are roadmap **G4** ([`scripts/voice-note-watch.py`](../../scripts/voice-note-watch.py)), not a second G2 on the library folder and not a second `inbox-watch` config. See [Voice notes](host-stt.md#voice-notes-voice-note-watch).

## Related

- Folder scan (manual): Import Transcript → Import all from folder
- Transcription: optional host-orchestrated STT plus BYO import — [transcription.md](transcription.md)
- Auto-identify after admit: [auto-identify.md](auto-identify.md)
- Product roadmap: [ROADMAP.md](../ROADMAP.md) theme G2 / H
