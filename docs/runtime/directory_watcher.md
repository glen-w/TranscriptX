Type: GUIDE
Authority: runtime/STORAGE.md

# Directory watcher

Optional **directory watcher** (roadmap G2) notices new files in a monitored inbox and runs **New → Import** for transcripts (and queues audio for later **Transcribe → Import**). Default **off**. Configure in **Settings → Watcher** or via `config_dir/watcher.json` / `TRANSCRIPTX_WATCHER_*` env.

## Behaviour

| Kind | Mode | Action |
|------|------|--------|
| Transcript (`.json`/`.srt`/`.vtt`/`.txt`/`.html`) | `auto_import` (default when enabled) | Stabilize → classify → `admit_and_register` |
| Transcript | `offer` / `ignore` | Record/skip only |
| Audio | `offer` (default) | Queue as `queued_transcription` (no silent STT) |
| Audio | `auto_transcribe` | Rejected until host STT (theme H) is available |
| Audio | `ignore` | Skip |

Inbox files are **never deleted or modified**. Admission always copies into app `imports/` then uses the managed import path (canonical JSON + sidecar + originals + index). The watcher does **not** scan the managed transcripts library.

## Ops notes

- Runs only while `transcriptx-web` is running (in-process supervisor). Stopping the container stops watching.
- Docker: watch a mounted inbox such as `/mnt/transcript-inbox` (`HOST_TRANSCRIPT_INBOX_DIR`). Paths must be absolute **inside** the container.
- Debounce (~2s) plus size/mtime stability checks before admit; identity is re-checked at admit time (fail closed if the file moved/grew).
- Job records and activity live under `data_dir/watcher/` (see [STORAGE.md](STORAGE.md)).
- Prefer Settings UI for enablement; env overrides are for automation.

## Host-side helper (`inbox-watch`)

The in-app watcher does **not** convert audio or run STT. For that, use the host script [`scripts/inbox-watch.py`](../../scripts/inbox-watch.py) documented under [Host inbox watcher (`inbox-watch`)](transcription.md#host-inbox-watcher-inbox-watch) in [transcription.md](transcription.md):

- `--watch-audio` — ffmpeg 16 kHz mono 64k MP3 into recordings, then `whispermlx-missing`
- `--watch-transcripts` — copy new JSON/SRT/VTT/txt/html into a transcripts dest if the stem is missing
- Terminal UX — same Review / Processing / Run summary shape as analysis CLI feedback ([Terminal feedback](transcription.md#terminal-feedback))

It runs on the Mac host (outside `transcriptx-web`), does not import `transcriptx`, and does not admit into the managed library. G2 stays the GUI auto-import path. Both can run; do not point them at the same inbox unless you intend double handling of transcripts (G2 admits, host copies).

## Related

- Folder scan (manual): Import Transcript → Import all from folder
- Transcription remains external for 1.0: [transcription.md](transcription.md)
- Product roadmap: [ROADMAP.md](../ROADMAP.md) theme G2 / H
