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

## Related

- Folder scan (manual): Import Transcript → Import all from folder
- Transcription remains external for 1.0: [transcription.md](transcription.md)
- Product roadmap: [ROADMAP.md](../ROADMAP.md) theme G2 / H
