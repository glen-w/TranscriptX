# Host STT automation

Advanced host-side transcription helpers. Mainstream path (Import Transcript, Transcribe Audio command generation): [Transcription](transcription.md). Audio merge/preprocess before STT: [Audio prep](audio-prep.md).

There is no `transcriptx transcript …` terminal subcommand. Validate and import from the GUI, or from code as below.

## Finding whispermlx

```bash
which whispermlx
```

If not found, set `WHISPERMLX` in `whisperx.env` at the repo root to the full binary path.

**Host note (macOS whispermlx):** pyannote may dump a long `torchcodec is not installed correctly` warning (FFmpeg ABI / PyTorch mismatch while probing libtorchcodec). If VAD and transcription continue and segments appear, treat it as noise — whispermlx usually hands pyannote a preloaded waveform. Worth aligning torchcodec + PyTorch + FFmpeg only if a later job needs pyannote to decode a file path directly and fails.

## Environment defaults (`whisperx.env`)

Copy `docs/recipes/whisperx/whisperx.env.example` to `whisperx.env` and configure:

| Variable | Purpose |
|----------|---------|
| `WHISPERMLX` | Path to whispermlx binary |
| `WHISPERMLX_MODEL` | Default model (e.g. `large-v3`) |
| `WHISPERMLX_LANGUAGE` | Default language |
| `WHISPERMLX_DIARIZE` | Default diarization on/off |
| `WHISPERMLX_TIMEOUT_SECONDS` | Per-file timeout (0 = no limit) |
| `HF_TOKEN` | Required when diarization is on |

## whispermlx-missing bulk script

Install once from the repo root (not shipped as a package entrypoint):

```bash
mkdir -p ~/.local/bin
install -m 755 scripts/whispermlx-missing.py ~/.local/bin/whispermlx-missing
# ensure ~/.local/bin is on PATH (new shell, or: export PATH="$HOME/.local/bin:$PATH")
which whispermlx-missing
```

If `command not found`, either PATH is missing `~/.local/bin` or the install step was skipped. You can also run without installing:

```bash
python3 scripts/whispermlx-missing.py --dry-run …
```

It processes MP3s in a source folder that lack matching JSON in a transcripts output folder.

**Resume / duplicates:** stems with matching JSON are skipped by default — in `--transcripts` (typically `…/originals`), in the parent library root when that folder is named `originals` (already-imported canonical JSON), as `foo (N).json` import-archive names, or as a sidecar next to the MP3. Use `--force` / `--rerun` to replace after a valid new JSON is produced. `--fuzzy-json-match` also treats `foo-….json` / `foo_….json` / `foo.….json` as already done. Writes still go only to `originals/` (see [STORAGE.md](STORAGE.md)).

**Skip likely serial parts:** `--skip-serial` (also JSON `skip_serial` / `WHISPERMLX_SKIP_SERIAL`) does **not** transcribe MP3s that [Tools → Auto-merge](audio-prep.md) would group as split parts or voice-note runs (`meeting_part2`, timestamp `_1`/`_2`, WhatsApp bursts, …). Merge those files first, then transcribe the `*_merged.mp3`. Standalone files still run. `--force` does not override this; use `--no-skip-serial`. When TranscriptX is importable (repo checkout / installed package), detection uses the same Auto-merge profiles; otherwise a filename + common voice-note fallback. Opt-in (off by default).

**Dry-run:** `--dry-run` previews work without requiring HF_TOKEN or a working whispermlx binary.

**Partial failures:** failed items leave temps under `transcripts/.whispermlx-missing/tmp/`; no partial JSON is written to the transcripts root. `--clean-failed` removes those temps.

**Spaces:** pass paths via quoted CLI args (the Transcribe Audio generator does this) or via the JSON config file.

**Local config (gitignored):** copy [`config/whispermlx-missing.example.json`](../../config/whispermlx-missing.example.json) to `.transcriptx/whispermlx-missing.json` and set your paths. For standalone use outside the repo, pass `--config /path/to/config.json` or set `WHISPERMLX_MISSING_CONFIG`.

**Config merge order:** portable repo defaults ← `TRANSCRIPTX_*` / `WHISPERMLX*` env ← local JSON ← CLI flags.

**When the script will process**

- `source` and `transcripts` are each set via **CLI**, **local JSON**, or **`TRANSCRIPTX_*` env** (not portable defaults alone).
- A fresh clone with no local JSON and no env overrides will **not** auto-run batch transcription.

**When it only saves or prints config**

- `--show-config` — print effective settings; never runs whispermlx.
- `--save-config` without meaningful paths — writes `.transcriptx/whispermlx-missing.json` and exits.
- Normal run with portable defaults only — prints guidance; does not process.

**Transcripts path semantics**

| Source | Meaning |
|--------|---------|
| `TRANSCRIPTX_TRANSCRIPTS_DIR` env | Transcripts **base** directory; script appends `/originals` for batch output |
| `transcripts` in JSON or `--transcripts` CLI | Exact **output** directory — must be `…/transcripts/originals` (scripts refuse the library root that contains `metadata/` / `imports/`) |
| `TRANSCRIPTX_RECORDINGS_DIR` env | Maps directly to `source` (recordings folder) |

Host helpers write raw engine JSON under `originals/` only. Library admission requires **Import Transcript**, Settings → Watcher, or optional `inbox-watch --admit` (`admit_and_register`), which writes canonical `schema_version` / `source` markers plus an import sidecar.

**`whisperx.env`** is used only for the whispermlx **subprocess** environment (`HF_TOKEN`, etc.), not for resolving config paths. Repo `.env` is loaded early (without overriding existing shell env) for `TRANSCRIPTX_*` path overrides — same pattern as Docker/native TranscriptX.

## Host inbox watcher (`inbox-watch`)

Optional **host-side** companion (not the in-app Settings → Watcher). Watches a drop folder for new **audio** and/or **transcripts**. Streamlit never runs it. Admission into the library is **off by default**; pass `--admit` (or `"admit_to_library": true`) to run `python -m transcriptx.admit_originals` after convert/copy/`whispermlx-missing`.

Install once from the repo root:

```bash
mkdir -p ~/.local/bin
install -m 755 scripts/inbox-watch.py ~/.local/bin/inbox-watch
which inbox-watch
```

Or run without installing: `python3 scripts/inbox-watch.py --once --dry-run …`.

| Mode | What it does | Skip when |
|------|----------------|-----------|
| `--watch-audio` (default on) | Convert new inbox audio to 16 kHz mono 64k MP3 in the recordings folder, then run `whispermlx-missing` | Recordings already has that stem (any audio extension). With `--skip-serial`, `whispermlx-missing` also skips Auto-merge serial groups |
| `--watch-transcripts` (default on) | Copy new JSON/SRT/VTT/txt/html into the transcripts dest | Dest already has that stem (any transcript extension) |
| `--admit` (default off) | After audio/transcript handling, admit eligible files in the transcripts dest (typically `originals/`) into the library | Already-imported stems; `foo (1).json` archive names. Requires a Python that can `import transcriptx` (`--admit-python` or `.transcriptx/bin/python`) |
| `--no-watch-audio` / `--no-watch-transcripts` | Disable that mode | At least one mode must stay on |

```bash
# Preview (no ffmpeg, no copy, no whispermlx)
inbox-watch --once --dry-run \
  --inbox /path/to/drop \
  --recordings /path/to/recordings \
  --transcripts /path/to/transcripts/originals

# One scan (cron / launchd)
inbox-watch --once --inbox … --recordings … --transcripts …

# Poll until Ctrl-C. If the USB inbox path is missing, --watch keeps running
# (empty scans) and still runs whispermlx-missing + --admit on the first cycle.
inbox-watch --watch --interval 5

# Same, and admit new originals/ JSON into the library
inbox-watch --watch --admit
```

ffmpeg (audio mode): `-nostdin -y -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k -f mp3`. Writes a temp `.mp3.partial` file then renames into recordings so `whispermlx-missing` never sees a half-written MP3. `-f mp3` is required so ffmpeg 8+ can mux even when the temp name does not end in `.mp3`.

### Terminal feedback

Host output mirrors the analysis CLI **Review before run** / **Run summary** shape (plain text; the script does not import `transcriptx` or Rich):

1. **Review before cycle** — inbox / recordings / transcripts paths, modes, and candidate file list
2. **Processing** — `[i/n] audio|transcript: filename`, then indented convert/copy/skip lines; long encodes print elapsed time and stream ffmpeg `time=` / `speed=` on **stderr**
3. **Transcription (whispermlx-missing)** — when audio mode ran (child process output follows)
4. **Library admit** — when `--admit` ran (`python -m transcriptx.admit_originals` output follows)
5. **Run summary** — `Status` (`completed` / `partial` / `failed` / `dry-run`), counts, and limited bullet lists for converted / skipped / failed

Example (abbreviated):

```text
---
Review before cycle
---
  Mode:        once
  Inbox:       /Volumes/USB-DISK/RECORD
  Candidates:  1 (1 audio, 0 transcript)
  Will consider:
    • audio: R20260814-175320.WAV
---
---
Processing
---
[1/1] audio: R20260814-175320.WAV
  Converting: R20260814-175320.WAV -> R20260814-175320.mp3 (… GiB)
  ffmpeg progress on stderr (time=/speed=)…
  Converted: R20260814-175320.WAV -> R20260814-175320.mp3 (… MiB) in 123.4s
---
---
Run summary
---
  Status:   completed
  Converted: 1
  …
---
```

Long WAV→MP3 converts can take minutes with little stdout while ffmpeg prints progress on stderr — that is expected. Ctrl-C stops the cycle (`Stopped.`); a half-written `.mp3.partial` is discarded on the next failed/interrupted convert.

Inbox sources are **kept by default**. After a successful convert (audio) or copy (transcript):

| Option | Effect |
|--------|--------|
| `--backup-wav` | Copy the **audio** inbox original into the WAV backup folder (`--wav-backup`, or `TRANSCRIPTX_WAV_BACKUP_DIR`) |
| `--delete-originals` | Delete the inbox source (after backup, if backup was requested and succeeded) |
| `--move-processed DIR` | Relocate the inbox source instead of deleting (mutually exclusive with `--delete-originals`) |
| `--force` | Overwrite an existing destination stem |

`--backup-wav` and `--delete-originals` are independent (use either or both). Deleting with no backup prints a warning. A failed WAV backup skips delete for that file.

**Local config (gitignored):** copy [`config/inbox-watch.example.json`](../../config/inbox-watch.example.json) to `.transcriptx/inbox-watch.json`. Repo `.env` is loaded with `setdefault` (existing shell env wins). Merge order: portable repo defaults ← `.env` / `TRANSCRIPTX_*` / `INBOX_WATCH_*` ← local JSON ← CLI.

| Key | JSON | Env |
|-----|------|-----|
| Drop folder | `inbox` | `INBOX_WATCH_INBOX` |
| Recordings | `recordings` | `TRANSCRIPTX_RECORDINGS_DIR` |
| Transcripts dest | `transcripts` (use `…/originals`) | `TRANSCRIPTX_TRANSCRIPTS_DIR` is the **library base**; the script appends `/originals` |
| WAV archive | `wav_backup` | `TRANSCRIPTX_WAV_BACKUP_DIR` |
| Convert audio | `watch_audio` | `INBOX_WATCH_AUDIO` |
| Copy transcripts | `watch_transcripts` | `INBOX_WATCH_TRANSCRIPTS` |
| Admit to library (default **off**) | `admit_to_library` | `INBOX_WATCH_ADMIT` |
| Admit interpreter | `admit_python` | `INBOX_WATCH_ADMIT_PYTHON` |
| Config path | — | `INBOX_WATCH_CONFIG` / `--config` |
| Also | `backup_wavs`, `delete_originals`, `skip_serial` | `INBOX_WATCH_BACKUP_WAV`, `INBOX_WATCH_DELETE_ORIGINALS`, `INBOX_WATCH_SKIP_SERIAL` |

Library admit needs a **native** TranscriptX install (the JSON/`--admit-python` interpreter must `import transcriptx`). It does not enter the Docker analysis container. Set `TRANSCRIPTX_TRANSCRIPTS_DIR` and `TRANSCRIPTX_OUTPUT_DIR` to the same host folders Docker mounts so the GUI index stays in sync.

Enable admit in local JSON (and/or `.env` `INBOX_WATCH_ADMIT=1`):

```json
"admit_to_library": true,
"admit_python": "/path/to/python3"
```

**macOS login agent (optional):** [`scripts/macos/inbox-watch-agent.sh`](../../scripts/macos/inbox-watch-agent.sh) plus [`scripts/macos/com.transcriptx.inbox-watch.plist`](../../scripts/macos/com.transcriptx.inbox-watch.plist) can run `--watch` at login. Admit is controlled by local JSON / `.env`, not by the plist. If the USB inbox is unplugged, `--watch` keeps polling empty cycles; the first cycle still catch-up transcribes missing MP3s and admits `originals/`. Logs: `.transcriptx/inbox-watch.launchd.log`.

Do **not** point this inbox at the same folder as the in-app G2 watcher unless you intend both to handle new transcripts (G2 admits; inbox-watch copies). See [directory_watcher.md](directory_watcher.md).

## Import a whole folder (details)

On **Import Transcript**, section **Import all from folder** scans an **absolute** local directory (Docker: mount the host folder — typically `HOST_TRANSCRIPT_INBOX_DIR` → `/mnt/transcript-inbox`; do not scan `/mnt/transcripts` or its subdirs) and imports only eligible files:

- Supported extensions: `.json`, `.srt`, `.vtt`, `.txt`, `.html`, `.htm` (case-insensitive).
- **Eligible** statuses: new, incomplete (repairable), needs registration. Already-imported stems, stem conflicts, size/symlink/special-file failures, and unrepairable incompletes are blocked (preview uses human labels).
- Skips stems that are already in the library (canonical JSON + import sidecar). Incomplete JSON without a safe `originals/` provenance is **not** treated as a new import.
- Duplicate stems in the folder (including case variants) are all marked conflict — none are imported.
- Source files in the scanned folder are **never** deleted or modified; the app copies into `transcripts/imports/` then admits them.
- Defaults: **100 MiB** per file (`TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES`) and **500** candidates (`TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES`). Exceeding the candidate limit fails the scan closed (Import eligible stays disabled).
- Preview is invalidated if the path, transcripts root, limits, or admission policy change. Use **Rescan**; a successful folder import auto-rescans so statuses refresh.
- Preview includes a read-only **audio** column: same-stem companions under approved recordings roots (`found: stem.mp3` / `none`). No automatic copy — upload via section 3 or place matching audio for playback linking.

Programmatic admission with registration under one lock: `transcriptx.io.admit_and_register.admit_and_register`.

## Python API

Canonical validation is required for library admission and analysis — see [STORAGE.md](STORAGE.md).

**Validate** a document already loaded as a dict (raises `ValueError` if invalid):

```python
import json
from pathlib import Path

from transcriptx.io.transcript_schema import validate_transcript_document

path = Path("path/to/transcript.json")
data = json.loads(path.read_text(encoding="utf-8"))
validate_transcript_document(data)
```

**Import** raw or legacy transcript files (e.g. WhisperX JSON, SRT, VTT) into the library:

```python
from pathlib import Path

from transcriptx.core.utils.paths import PATHS
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

result = run_managed_import_workflow(
    PATHS.transcripts_originals_dir / "whisperx_output.json",
    overwrite=False,
)
print(result.json_path)
print(result.sidecar_path)
print(result.archived_original_path)
```

The import workflow detects the format, normalizes speakers (missing or empty → `SPEAKER_UNKNOWN` where applicable), writes canonical `schema_version/source/metadata`, writes a sidecar, and archives the original source. Web flow does not overwrite existing canonical JSON by default; programmatic callers may opt into overwrite as a new import attempt.

Downstream analysis APIs (for example `AnalysisRequest` + `run_analysis`) assume `transcript_path` is a library transcript produced by this workflow or an equivalent loader. Then analyse from the web interface or via `AnalysisRequest` + `run_analysis` (see [generated/cli.md](../generated/cli.md)).

Other engines (AssemblyAI, Deepgram, Google, manual edits): each segment needs `start`, `end`, `speaker`, and `text`. Use **validate** (above) and the import workflow so metadata, sidecar, and archive exist.

## Multi-language variants

Import alternate-language versions of an existing transcript using a flat filename suffix in the same directory:

- Base (default): `meeting.json`
- French variant: `meeting_fr.json`
- English explicit variant: `meeting_en.json` (optional; `meeting.json` remains the conventional default English path)

**Workflow:**

1. Import and identify speakers on the base transcript first (Speaker ID page, or segment-derived names on import).
2. Import the language variant via the same path (web **Import Transcript** or `run_managed_import_workflow`).
3. On import, speaker-map inheritance runs automatically when the base has a speaker-map sidecar and the variant does not yet.

**Requirements:** variant segments should use the same diarized speaker IDs as the base (`SPEAKER_00`, `SPEAKER_01`, …). See [STORAGE.md](STORAGE.md) for variant rules.

**What is copied:** display names, ignored speakers, and `speaker_id_to_db_id`. Each variant gets its own sidecar under `metadata/speaker_maps/` (see [STORAGE.md](STORAGE.md)).

**When inheritance is skipped:** the filename is not `{base}_{lang}`, the base transcript is missing, the base has no speaker-map sidecar, or the variant already has its own speaker-map sidecar (re-import safe).

**Fallback:** if inheritance does not apply, segment `original_cue.original_speaker` names are used as on a normal import.

## Related

- [Transcription](transcription.md) — bring a file / generate a host command
- [Audio prep](audio-prep.md) — merge split recordings before STT
- [Directory watcher](directory_watcher.md) — in-app G2 watcher
- [WhisperX recipe](../recipes/whisperx/README.md) · [Whisper-WebUI recipe](../recipes/whisper-webui/README.md)
