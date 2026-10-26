# Mac system-audio capture (G5)

Host companion that records **computer audio** (what Zoom/Meet/browser play) via
[BlackHole](https://existential.audio/blackhole/) and a Multi-Output Device, then
on Stop runs existing **host whispermlx** and writes WhisperX-shaped JSON under
`transcripts/originals/`. Optional `--admit` promotes that JSON into the managed
library.

This is roadmap **G5**. It is **not** live captions (theme **H6**), **not** a
meeting bot, and **not** inside the Linux analysis Compose image.

Script: [`scripts/system-audio-capture.py`](../../scripts/system-audio-capture.py).
Example config: [`config/system-audio-capture.example.json`](../../config/system-audio-capture.example.json).

## Who this is for

Native **macOS** host with whispermlx and ffmpeg. Docker Desktop / Compose
cannot see BlackHole. The Transcribe Audio panel shows Start/Stop only on a
native Mac process; Compose shows a caption and this page.

## One-time Audio MIDI Setup

1. Install **BlackHole 2ch**.
2. Open **Audio MIDI Setup** → create a **Multi-Output Device** that includes
   Built-in Output (or your headphones) **and** BlackHole.
3. Set that Multi-Output Device as the Mac’s system output so you still hear
   audio while the capture process records BlackHole.

**TCC:** ffmpeg needs **Microphone** / Input Monitoring. Screen Recording is
**not** required for BlackHole. ScreenCaptureKit is a later alternative, not
this MVP.

Empty / near-silent WAVs usually mean system output is not the Multi-Output
Device (nothing is routed into BlackHole). The script warns; it does not delete
the file.

## Commands

```bash
python3 scripts/system-audio-capture.py probe
python3 scripts/system-audio-capture.py start --name "supervision"
python3 scripts/system-audio-capture.py status
python3 scripts/system-audio-capture.py stop
python3 scripts/system-audio-capture.py stop --admit
python3 scripts/system-audio-capture.py record --name "webinar"
python3 scripts/system-audio-capture.py finalize <session_id>
```

| Command | Role |
|---------|------|
| `probe` | List AVFoundation audio devices and match BlackHole |
| `start` | Background ffmpeg; writes `data_dir/capture/sessions/<id>.json` |
| `status` / `list` | Active or latest session (`status --json` for GUI) |
| `stop` | SIGINT ffmpeg → 16 kHz mono 64k MP3 → whispermlx JSON → optional `--admit` |
| `record` | Foreground; Ctrl-C (or duration cap) then the same Stop path |
| `finalize` | Crash recovery of a leftover WAV when the ffmpeg PID is already dead |

`--diarize` is off by default (T0 undiarized; Overview already has the honesty
banner). `--admit` is off by default (same as `inbox-watch`). `--mix-mic` is
optional for headphone meetings.

`--no-transcribe` on Stop leaves the WAV (and session `recorded`) without STT.

## Layout

| Path | Meaning |
|------|---------|
| `recordings_dir/capture/` | Session WAV / MP3 (never the G2 inbox, G4 note inbox, or USB `RECORD` root) |
| `data_dir/capture/sessions/` | File-backed session JSON (app-owned) |
| `transcripts/originals/` | Raw whispermlx JSON before admit |

Config merge: portable `TRANSCRIPTX_*` defaults ← `SYSTEM_AUDIO_CAPTURE_*` env ←
`.transcriptx/system-audio-capture.json` ← CLI. The env prefix cannot turn
`INBOX_WATCH_ADMIT` on.

Refuse rather than truncate: `max_duration_seconds` (default 7200) auto-stops
the session; `min_free_bytes` (default 500 MiB) refuses `start`.

## Privacy / agents

Do **not** attach this script to the login agent that runs `inbox-watch --watch`.
Do **not** install a KeepAlive LaunchAgent — always-on system-audio recording is
a footgun. Sessions are operator-started.

Optional wrapper: [`scripts/macos/system-audio-capture-agent.sh`](../../scripts/macos/system-audio-capture-agent.sh)
(execs the Python script; no plist KeepAlive).

## Related

- Host STT: [host-stt.md](host-stt.md)
- Transcription: [transcription.md](transcription.md)
- In-app watcher (different folder): [directory_watcher.md](directory_watcher.md)
- Voice notes (plain text, no admit): [host-stt.md](host-stt.md#voice-notes-voice-note-watch)
- Roadmap: [ROADMAP.md](../ROADMAP.md) theme G5 / H6
